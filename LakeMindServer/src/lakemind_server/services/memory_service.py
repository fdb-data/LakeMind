from __future__ import annotations
import hashlib
from datetime import datetime, timezone
import ulid
from ..db import execute, execute_one
from ..security.context import SecurityContext
from .asset_service import AssetService
from .audit_service import AuditService


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


class MemoryService:

    @staticmethod
    def add(ctx: SecurityContext, messages: list[dict], metadata: dict | None = None,
            memory_type: str = "agent_private", subject: str | None = None,
            scope: str = "default", source: str = "chat") -> dict:
        content = " ".join(m.get("content", "") for m in messages)
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        existing = execute_one(
            "SELECT a.asset_id FROM assets a JOIN memory_meta m ON a.asset_id = m.asset_id "
            "WHERE a.tenant_id = %s AND a.checksum = %s AND a.deleted_at IS NULL",
            (ctx.tenant_id, content_hash),
        )
        if existing:
            return {"asset_id": existing["asset_id"], "message": "Duplicate memory, skipped"}

        asset = AssetService.create_asset(
            ctx, asset_type="memory", name=subject or f"memory_{content_hash[:8]}",
            source_type=source, metadata=metadata or {},
        )
        asset_id = asset["asset_id"]

        execute(
            "UPDATE assets SET checksum = %s WHERE asset_id = %s",
            (content_hash, asset_id),
        )

        execute(
            "INSERT INTO memory_meta (asset_id, memory_type, subject, scope, source, content, "
            "importance, retention, access_scope, embedding_status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 0.5, 'permanent', 'private', 'PENDING')",
            (asset_id, memory_type, subject, scope, source, content),
        )

        AssetService.create_binding(
            asset_id=asset_id,
            binding_type="ORIGINAL_OBJECT",
            provider="postgres",
            physical_uri=f"{ctx.tenant_id}/{asset_id}/memory",
            is_required=True,
        )
        AssetService.create_binding(
            asset_id=asset_id,
            binding_type="VECTOR_INDEX",
            provider="lancedb",
            physical_uri=f"{ctx.tenant_id}/{asset_id}/vector",
            is_required=True,
        )

        AssetService.update_asset_status(asset_id, "CREATING")

        return {"asset_id": asset_id, "status": "CREATING"}

    @staticmethod
    def search(ctx: SecurityContext, query: str, filters: dict | None = None,
               top_k: int = 10) -> list[dict]:
        return execute(
            "SELECT a.asset_id, m.subject, m.content, m.importance, a.status "
            "FROM assets a JOIN memory_meta m ON a.asset_id = m.asset_id "
            "WHERE a.tenant_id = %s AND a.asset_type = 'memory' "
            "AND a.status IN ('READY', 'DEGRADED') AND a.deleted_at IS NULL "
            "ORDER BY m.importance DESC LIMIT %s",
            (ctx.tenant_id, top_k),
        )

    @staticmethod
    def get(ctx: SecurityContext, memory_id: str) -> dict | None:
        row = execute_one(
            "SELECT a.*, m.* FROM assets a JOIN memory_meta m ON a.asset_id = m.asset_id "
            "WHERE a.asset_id = %s AND a.tenant_id = %s",
            (memory_id, ctx.tenant_id),
        )
        return row

    @staticmethod
    def list(ctx: SecurityContext, filters: dict | None = None,
             page: int = 1, page_size: int = 50) -> dict:
        items = execute(
            "SELECT a.asset_id, a.name, a.status, m.memory_type, m.subject, m.importance, a.created_at "
            "FROM assets a JOIN memory_meta m ON a.asset_id = m.asset_id "
            "WHERE a.tenant_id = %s AND a.deleted_at IS NULL "
            "ORDER BY a.created_at DESC",
            (ctx.tenant_id,),
        )
        total = len(items)
        offset = (page - 1) * page_size
        return {"items": items[offset:offset + page_size], "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def update(ctx: SecurityContext, memory_id: str, content: str) -> dict:
        execute(
            "UPDATE memory_meta SET content = %s, revision = revision + 1 WHERE asset_id = %s",
            (content, memory_id),
        )
        execute(
            "UPDATE assets SET updated_at = %s WHERE asset_id = %s",
            (datetime.now(timezone.utc), memory_id),
        )
        return {"asset_id": memory_id, "updated": True}

    @staticmethod
    def delete(ctx: SecurityContext, memory_id: str) -> dict:
        return AssetService.delete_asset(ctx, memory_id)

    @staticmethod
    def clear(ctx: SecurityContext, filters: dict | None = None) -> int:
        rows = execute(
            "SELECT a.asset_id FROM assets a JOIN memory_meta m ON a.asset_id = m.asset_id "
            "WHERE a.tenant_id = %s AND a.deleted_at IS NULL",
            (ctx.tenant_id,),
        )
        count = 0
        for row in rows:
            try:
                AssetService.delete_asset(ctx, row["asset_id"])
                count += 1
            except Exception:
                pass
        return count

    @staticmethod
    def history(ctx: SecurityContext, memory_id: str) -> list[dict]:
        return execute(
            "SELECT audit_id, event_type, details, created_at FROM audit_log "
            "WHERE resource_id = %s ORDER BY created_at DESC",
            (memory_id,),
        )
