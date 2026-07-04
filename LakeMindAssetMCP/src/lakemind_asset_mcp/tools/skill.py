"""Skill 资产工具：search_skill / register_skill / execute_skill。"""
from __future__ import annotations

import uuid
from typing import Any

import pyarrow as pa

from ..context import get_tenant
from ..engines import Engines
from ._helpers import audited, require_scope

SCOPE = "asset"
SKILL_VEC_TABLE = "skill_vectors"
SKILL_META_DOMAIN = "skills"
SKILL_META_TABLE = "skill_meta"


def _ensure_skill_meta(engines: Engines, ctx) -> None:
    if not engines.iceberg.table_exists(ctx, SKILL_META_DOMAIN, SKILL_META_TABLE):
        schema = pa.schema(
            [
                pa.field("skill_id", pa.string()),
                pa.field("name", pa.string()),
                pa.field("description", pa.string()),
                pa.field("version", pa.string()),
                pa.field("owner", pa.string()),
                pa.field("s3_uri", pa.string()),
            ]
        )
        engines.iceberg.create_table_from_arrow(ctx, SKILL_META_DOMAIN, SKILL_META_TABLE, schema)


def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def search_skill(query: str, top_k: int = 5) -> dict[str, Any]:
        """语义搜索匹配的 Skill。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        if not engines.lancedb.table_exists(ctx, SKILL_VEC_TABLE):
            return {"query": query, "skills": [], "count": 0}
        qvec = engines.embedding.embed([query])[0]
        hits = engines.lancedb.search(ctx, SKILL_VEC_TABLE, qvec, top_k)
        skills = [
            {
                "skill_id": h.get("skill_id"),
                "name": h.get("name"),
                "description": h.get("description"),
                "_distance": h.get("_distance"),
            }
            for h in hits
        ]
        return {"query": query, "skills": skills, "count": len(skills)}

    @mcp.tool()
    @audited(redact_keys)
    async def register_skill(
        name: str, description: str | None = None, code: str = "", version: str = "1.0.0"
    ) -> dict[str, Any]:
        """注册 Skill：上传代码到 S3、写 Iceberg 元信息、建 Lance 向量索引。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        bucket = "lakemind-filesets"
        s3_key = f"{ctx.tenant_id}/skills/{name}.py"
        engines.s3.put(bucket, s3_key, code)
        s3_uri = f"s3://{bucket}/{s3_key}"

        _ensure_skill_meta(engines, ctx)
        skill_id = f"skill-{uuid.uuid4().hex[:8]}"
        meta_row = pa.table(
            {
                "skill_id": [skill_id],
                "name": [name],
                "description": [description or ""],
                "version": [version],
                "owner": [ctx.agent_id],
                "s3_uri": [s3_uri],
            }
        )
        engines.iceberg.append(ctx, SKILL_META_DOMAIN, SKILL_META_TABLE, meta_row)

        dim = engines.embedding.dim
        vec = engines.embedding.embed([description or name])[0]
        vec_row = pa.table(
            {
                "skill_id": [skill_id],
                "name": [name],
                "description": [description or ""],
                "vector": pa.array([vec], type=pa.list_(pa.float32(), dim)),
            }
        )
        if engines.lancedb.table_exists(ctx, SKILL_VEC_TABLE):
            engines.lancedb.add(ctx, SKILL_VEC_TABLE, vec_row)
        else:
            engines.lancedb.create_table(ctx, SKILL_VEC_TABLE, vec_row, mode="create")
        return {"skill_id": skill_id, "name": name, "s3_uri": s3_uri}

    @mcp.tool()
    @audited(redact_keys)
    async def execute_skill(name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """执行 Skill（MVP 占位）。"""
        require_scope(SCOPE)
        return {"name": name, "inputs": inputs, "status": "execution not implemented in MVP"}
