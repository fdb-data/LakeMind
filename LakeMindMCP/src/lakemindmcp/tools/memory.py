"""Memory 资产工具：remember / recall / forget。

短期记忆走 Dragonfly（TTL KV），长期记忆走 Lance 向量 + Iceberg 元信息小表
（``lance_uri`` 关联），Agent 无感知。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pyarrow as pa

from ..context import get_tenant
from ..engines import Engines
from ..engines.schema_convert import arrow_to_iceberg_schema
from ._helpers import audited, require_scope

SCOPE = "data"
DOMAIN = "memory"
MEM_TABLE = "memory_vectors"      # Lance 向量表名
META_TABLE = "memory_meta"        # Iceberg 元信息小表


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_lance(engines: Engines, ctx, dim: int) -> None:
    if not engines.lancedb.table_exists(ctx, MEM_TABLE):
        empty = pa.table(
            {
                "memory_id": pa.array([], pa.string()),
                "content": pa.array([], pa.string()),
                "vector": pa.array([], pa.list_(pa.float32(), dim)),
            }
        )
        engines.lancedb.create_table(ctx, MEM_TABLE, empty, mode="overwrite")


def _ensure_meta(engines: Engines, ctx) -> None:
    if not engines.iceberg.table_exists(ctx, DOMAIN, META_TABLE):
        schema = pa.schema(
            [
                pa.field("memory_id", pa.string()),
                pa.field("agent_id", pa.string()),
                pa.field("session_id", pa.string()),
                pa.field("lance_uri", pa.string()),
                pa.field("content", pa.string()),
                pa.field("created_at", pa.string()),
            ]
        )
        engines.iceberg.create_table_from_arrow(ctx, DOMAIN, META_TABLE, schema)


def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def remember(
        content: str, context: dict | None = None, ttl: int | None = None
    ) -> dict[str, Any]:
        """记住一件事。ttl（秒）仅作用于短期记忆。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        dim = engines.embedding.dim
        mem_id = f"mem-{uuid.uuid4().hex[:12]}"

        # 短期记忆 → Dragonfly
        short_key = f"mem:{ctx.agent_id}:{mem_id}"
        engines.dragonfly.remember(
            ctx, short_key, {"content": content, "context": context or {}}, ttl
        )

        # 长期记忆 → Lance 向量 + Iceberg 元信息小表
        _ensure_lance(engines, ctx, dim)
        _ensure_meta(engines, ctx)
        vec = engines.embedding.embed([content])[0]
        lance_row = pa.table(
            {
                "memory_id": [mem_id],
                "content": [content],
                "vector": pa.array([vec], type=pa.list_(pa.float32(), dim)),
            }
        )
        engines.lancedb.add(ctx, MEM_TABLE, lance_row)
        lance_uri = f"lance://{engines.lancedb._cfg.uri}/{ctx.lancedb_name()}/{MEM_TABLE}/{mem_id}"
        session_id = (context or {}).get("session_id", "")
        meta_row = pa.table(
            {
                "memory_id": [mem_id],
                "agent_id": [ctx.agent_id],
                "session_id": [session_id],
                "lance_uri": [lance_uri],
                "content": [content],
                "created_at": [_now()],
            }
        )
        engines.iceberg.append(ctx, DOMAIN, META_TABLE, meta_row)
        return {"memory_id": mem_id, "short_term_key": short_key, "lance_uri": lance_uri}

    @mcp.tool()
    @audited(redact_keys)
    async def recall(query: str, limit: int = 5) -> dict[str, Any]:
        """语义/关键词召回长期记忆。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        if not engines.lancedb.table_exists(ctx, MEM_TABLE):
            return {"query": query, "memories": [], "count": 0}
        qvec = engines.embedding.embed([query])[0]
        hits = engines.lancedb.search(ctx, MEM_TABLE, qvec, limit)
        memories = [
            {"memory_id": h.get("memory_id"), "content": h.get("content"), "_distance": h.get("_distance")}
            for h in hits
        ]
        return {"query": query, "memories": memories, "count": len(memories)}

    @mcp.tool()
    @audited(redact_keys)
    async def forget(query: str | None = None) -> dict[str, Any]:
        """遗忘匹配的记忆。query 为 None 时清空当前 Agent 的短期记忆。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        deleted = 0
        if query is None:
            keys = engines.dragonfly.scan(ctx, f"mem:{ctx.agent_id}:*")
            for k in keys:
                engines.dragonfly.forget(ctx, k)
                deleted += 1
            return {"deleted": deleted, "scope": "short_term"}
        # 语义匹配后删除（长期记忆）
        if engines.lancedb.table_exists(ctx, MEM_TABLE):
            qvec = engines.embedding.embed([query])[0]
            hits = engines.lancedb.search(ctx, MEM_TABLE, qvec, 10)
            for h in hits:
                mid = h.get("memory_id")
                if mid:
                    try:
                        engines.lancedb._tenant_db(ctx).open_table(MEM_TABLE).delete(f"memory_id = '{mid}'")
                    except Exception:
                        pass
                    deleted += 1
        return {"deleted": deleted, "scope": "long_term"}
