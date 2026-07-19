from __future__ import annotations
from datetime import datetime, timezone
import ulid
from ..db import execute, execute_one
from ..security.context import SecurityContext
from ..security.tenant_isolation import resolve_s3_key, resolve_s3_bucket
from .audit_service import AuditService
from .asset_state_machine import can_transition, transition, check_ready, check_degraded
from .operation_service import OperationService
from ..outbox.worker import enqueue


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


class AssetService:

    @staticmethod
    def create_asset(ctx: SecurityContext, asset_type: str, name: str,
                     source_type: str = "upload", source_uri: str | None = None,
                     metadata: dict | None = None, visibility: str = "private",
                     version: str = "1.0.0") -> dict:
        asset_id = _ulid("ast")
        execute(
            "INSERT INTO assets (asset_id, tenant_id, asset_type, name, version, status, owner_id, created_by, "
            "visibility, source_type, source_uri, metadata) "
            "VALUES (%s, %s, %s, %s, %s, 'DRAFT', %s, %s, %s, %s, %s, %s)",
            (asset_id, ctx.tenant_id, asset_type, name, version, ctx.principal_id, ctx.principal_id,
             visibility, source_type, source_uri, metadata or {}),
        )
        AuditService.record(
            event_type="asset.create",
            principal_id=ctx.principal_id,
            tenant_id=ctx.tenant_id,
            resource_id=asset_id,
            action="create_asset",
            result="success",
            details={"asset_type": asset_type, "name": name},
        )
        return {"asset_id": asset_id, "asset_type": asset_type, "name": name, "status": "DRAFT"}

    @staticmethod
    def get_asset(ctx: SecurityContext, asset_id: str) -> dict | None:
        row = execute_one("SELECT * FROM assets WHERE asset_id = %s", (asset_id,))
        if row is None:
            return None
        if not ctx.can_access_tenant(row["tenant_id"]):
            raise PermissionError("TENANT_SCOPE_VIOLATION")
        return row

    @staticmethod
    def list_assets(ctx: SecurityContext, asset_type: str | None = None,
                    status: str | None = None, page: int = 1, page_size: int = 50) -> dict:
        if ctx.is_platform_admin:
            query = "SELECT * FROM assets WHERE 1=1"
            params: list = []
        else:
            query = "SELECT * FROM assets WHERE tenant_id = %s"
            params = [ctx.tenant_id]
        if asset_type:
            query += " AND asset_type = %s"; params.append(asset_type)
        if status:
            query += " AND status = %s"; params.append(status)
        query += " AND deleted_at IS NULL ORDER BY created_at DESC"
        items = execute(query, tuple(params))
        total = len(items)
        offset = (page - 1) * page_size
        return {"items": items[offset:offset + page_size], "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def update_asset(ctx: SecurityContext, asset_id: str, metadata: dict) -> dict:
        row = AssetService.get_asset(ctx, asset_id)
        if row is None:
            raise ValueError("RESOURCE_NOT_FOUND")
        execute(
            "UPDATE assets SET metadata = %s, updated_at = %s WHERE asset_id = %s",
            (metadata, datetime.now(timezone.utc), asset_id),
        )
        AuditService.record(
            event_type="asset.update",
            principal_id=ctx.principal_id,
            tenant_id=ctx.tenant_id,
            resource_id=asset_id,
            action="update_asset",
            result="success",
        )
        return {"asset_id": asset_id, "updated": True}

    @staticmethod
    def delete_asset(ctx: SecurityContext, asset_id: str) -> dict:
        row = AssetService.get_asset(ctx, asset_id)
        if row is None:
            raise ValueError("RESOURCE_NOT_FOUND")
        execute(
            "UPDATE assets SET status = 'DELETING', updated_at = %s WHERE asset_id = %s",
            (datetime.now(timezone.utc), asset_id),
        )
        op = OperationService.create(
            op_type="asset_delete",
            target_resource=f"lake://assets/{asset_id}",
            initiator_id=ctx.principal_id,
            initiator_channel="rest",
            reason=f"Delete asset {asset_id}",
            risk_level="HIGH",
        )
        enqueue(
            event_type="asset.delete_requested",
            aggregate_id=asset_id,
            aggregate_type="asset",
            payload={"asset_id": asset_id, "tenant_id": ctx.tenant_id},
            correlation_id=ctx.request_id,
        )
        AuditService.record(
            event_type="asset.delete",
            principal_id=ctx.principal_id,
            tenant_id=ctx.tenant_id,
            resource_id=asset_id,
            action="delete_asset",
            result="success",
        )
        return {"asset_id": asset_id, "status": "DELETING", "operation_id": op["operation_id"]}

    @staticmethod
    def get_bindings(asset_id: str) -> list[dict]:
        return execute("SELECT * FROM asset_bindings WHERE asset_id = %s ORDER BY binding_type", (asset_id,))

    @staticmethod
    def get_lineage(asset_id: str) -> dict:
        upstream = execute("SELECT * FROM asset_lineage WHERE asset_id = %s", (asset_id,))
        downstream = execute("SELECT * FROM asset_lineage WHERE source_type = 'asset' AND source_id = %s", (asset_id,))
        return {"asset_id": asset_id, "upstream": upstream, "downstream": downstream}

    @staticmethod
    def reindex(ctx: SecurityContext, asset_id: str) -> dict:
        op = OperationService.create(
            op_type="asset_reindex",
            target_resource=f"lake://assets/{asset_id}",
            initiator_id=ctx.principal_id,
            initiator_channel="rest",
            reason=f"Reindex asset {asset_id}",
            risk_level="LOW",
        )
        enqueue(
            event_type="asset.reindex_requested",
            aggregate_id=asset_id,
            aggregate_type="asset",
            payload={"asset_id": asset_id, "tenant_id": ctx.tenant_id},
            correlation_id=ctx.request_id,
        )
        return {"asset_id": asset_id, "operation_id": op["operation_id"]}

    @staticmethod
    def create_binding(asset_id: str, binding_type: str, provider: str,
                       physical_uri: str, is_required: bool = True,
                       checksum: str | None = None) -> dict:
        binding_id = _ulid("bnd")
        execute(
            "INSERT INTO asset_bindings (binding_id, asset_id, binding_type, provider, physical_uri, "
            "is_required, checksum, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING')",
            (binding_id, asset_id, binding_type, provider, physical_uri, is_required, checksum),
        )
        return {"binding_id": binding_id, "asset_id": asset_id, "binding_type": binding_type, "status": "PENDING"}

    @staticmethod
    def update_binding_status(binding_id: str, status: str, last_error: str | None = None) -> None:
        execute(
            "UPDATE asset_bindings SET status = %s, last_error = %s, updated_at = %s WHERE binding_id = %s",
            (status, last_error, datetime.now(timezone.utc), binding_id),
        )

    @staticmethod
    def update_asset_status(asset_id: str, new_status: str) -> None:
        row = execute_one("SELECT status FROM assets WHERE asset_id = %s", (asset_id,))
        if row is None:
            raise ValueError("RESOURCE_NOT_FOUND")
        if not can_transition(row["status"], new_status):
            raise ValueError(f"Invalid transition: {row['status']} -> {new_status}")
        execute(
            "UPDATE assets SET status = %s, updated_at = %s WHERE asset_id = %s",
            (new_status, datetime.now(timezone.utc), asset_id),
        )
        AuditService.record(
            event_type="asset.state_change",
            resource_id=asset_id,
            action="state_change",
            result="success",
            details={"from": row["status"], "to": new_status},
        )

    @staticmethod
    def record_lineage(asset_id: str, source_type: str, source_id: str,
                       relation: str, source_version: str | None = None,
                       details: dict | None = None) -> dict:
        lineage_id = _ulid("lin")
        execute(
            "INSERT INTO asset_lineage (lineage_id, asset_id, source_type, source_id, source_version, relation, details) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (lineage_id, asset_id, source_type, source_id, source_version, relation, details or {}),
        )
        return {"lineage_id": lineage_id}
