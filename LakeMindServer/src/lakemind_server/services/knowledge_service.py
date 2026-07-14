from __future__ import annotations
from datetime import datetime, timezone
import ulid
from ..db import execute, execute_one
from ..security.context import SecurityContext
from .asset_service import AssetService
from .audit_service import AuditService
from .operation_service import OperationService
from ..outbox.worker import enqueue


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


class KnowledgeService:

    @staticmethod
    def ingest(ctx: SecurityContext, name: str, content: bytes,
               source_type: str = "upload", parser: str | None = None,
               kb_name: str | None = None) -> dict:
        asset = AssetService.create_asset(
            ctx, asset_type="knowledge", name=name,
            source_type=source_type, metadata={"parser": parser, "kb_name": kb_name or name},
        )
        asset_id = asset["asset_id"]

        AssetService.update_asset_status(asset_id, "CREATING")

        execute(
            "INSERT INTO knowledge_meta (asset_id, kb_name, parser_version, chunk_config, index_status) "
            "VALUES (%s, %s, %s, %s, 'PENDING')",
            (asset_id, kb_name or name, parser or "v1", {"chunk_size": 512, "overlap": 50}),
        )

        for btype in ["ORIGINAL_OBJECT", "PARSED_CONTENT", "CHUNK_DATA", "VECTOR_INDEX"]:
            AssetService.create_binding(
                asset_id=asset_id,
                binding_type=btype,
                provider="seaweedfs" if btype != "VECTOR_INDEX" else "lancedb",
                physical_uri=f"{ctx.tenant_id}/{asset_id}/{btype.lower()}",
                is_required=True,
            )

        enqueue(
            event_type="asset.created",
            aggregate_id=asset_id,
            aggregate_type="asset",
            payload={
                "asset_id": asset_id,
                "tenant_id": ctx.tenant_id,
                "content_size": len(content) if content else 0,
            },
            correlation_id=ctx.request_id,
        )

        return {"asset_id": asset_id, "status": "CREATING", "message": "Knowledge ingestion started"}

    @staticmethod
    def search(ctx: SecurityContext, query: str, kb_name: str | None = None,
               filters: dict | None = None, top_k: int = 10) -> list[dict]:
        return execute(
            "SELECT a.asset_id, a.name, a.status, a.metadata FROM assets a "
            "JOIN knowledge_meta k ON a.asset_id = k.asset_id "
            "WHERE a.tenant_id = %s AND a.asset_type = 'knowledge' "
            "AND a.status IN ('READY', 'DEGRADED') AND a.deleted_at IS NULL "
            "AND (%s = '' OR k.kb_name = %s) "
            "ORDER BY a.updated_at DESC LIMIT %s",
            (ctx.tenant_id, kb_name or "", kb_name or "", top_k),
        )

    @staticmethod
    def get_concept(ctx: SecurityContext, kb_name: str, concept_id: str) -> dict | None:
        return execute_one(
            "SELECT a.* FROM assets a JOIN knowledge_meta k ON a.asset_id = k.asset_id "
            "WHERE a.tenant_id = %s AND k.kb_name = %s AND a.asset_id = %s",
            (ctx.tenant_id, kb_name, concept_id),
        )

    @staticmethod
    def list_concepts(ctx: SecurityContext, kb_name: str = "", page: int = 1, page_size: int = 50) -> dict:
        if kb_name:
            items = execute(
                "SELECT a.* FROM assets a JOIN knowledge_meta k ON a.asset_id = k.asset_id "
                "WHERE a.tenant_id = %s AND k.kb_name = %s AND a.deleted_at IS NULL "
                "ORDER BY a.created_at DESC",
                (ctx.tenant_id, kb_name),
            )
        else:
            items = execute(
                "SELECT a.* FROM assets a JOIN knowledge_meta k ON a.asset_id = k.asset_id "
                "WHERE a.tenant_id = %s AND a.deleted_at IS NULL "
                "ORDER BY a.created_at DESC",
                (ctx.tenant_id,),
            )
        total = len(items)
        offset = (page - 1) * page_size
        return {"items": items[offset:offset + page_size], "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def reindex(ctx: SecurityContext, kb_name: str) -> dict:
        op = OperationService.create(
            op_type="asset_reindex",
            target_resource=f"lake://knowledge/{kb_name}",
            initiator_id=ctx.principal_id,
            initiator_channel="rest",
            reason=f"Reindex knowledge base {kb_name}",
            risk_level="LOW",
        )
        enqueue(
            event_type="asset.reindex_requested",
            aggregate_id=kb_name,
            aggregate_type="knowledge",
            payload={"kb_name": kb_name, "tenant_id": ctx.tenant_id},
            correlation_id=ctx.request_id,
        )
        return {"operation_id": op["operation_id"], "status": "PENDING"}
