"""Skill 资产工具：search_skill / register_skill / execute_skill。"""
from __future__ import annotations

import uuid
from typing import Any

from ..context import get_tenant
from ..server_client import ServerClient
from ._helpers import audited, require_scope

SCOPE = "asset"
SKILL_VEC_TABLE = "skill_vectors"
SKILL_META_DOMAIN = "skills"
SKILL_META_TABLE = "skill_meta"


def _vec_db(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


def _iceberg_ns(tenant_id: str, domain: str) -> str:
    return f"{tenant_id}_{domain}"


def register(mcp, server: ServerClient, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def search_skill(query: str, top_k: int = 5) -> dict[str, Any]:
        """语义搜索匹配的 Skill。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        embed_resp = await server.embed([query])
        qvec = embed_resp["vectors"][0]
        try:
            search_resp = await server.vector_search(db, SKILL_VEC_TABLE, qvec, top_k)
            hits = search_resp.get("results", [])
        except Exception:
            hits = []
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
        await server.object_put(bucket, s3_key, code.encode())
        s3_uri = f"s3://{bucket}/{s3_key}"

        skill_id = f"skill-{uuid.uuid4().hex[:8]}"
        ns = _iceberg_ns(ctx.tenant_id, SKILL_META_DOMAIN)
        meta_row = {
            "skill_id": skill_id,
            "name": name,
            "description": description or "",
            "version": version,
            "owner": ctx.agent_id,
            "s3_uri": s3_uri,
        }
        try:
            await server.table_append(ns, SKILL_META_TABLE, [meta_row])
        except Exception:
            await server.table_create(ns, SKILL_META_TABLE, {
                "skill_id": "string", "name": "string", "description": "string",
                "version": "string", "owner": "string", "s3_uri": "string",
            })
            await server.table_append(ns, SKILL_META_TABLE, [meta_row])

        embed_resp = await server.embed([description or name])
        vec = embed_resp["vectors"][0]
        db = _vec_db(ctx.tenant_id)
        vec_row = {
            "skill_id": skill_id,
            "name": name,
            "description": description or "",
            "vector": vec,
        }
        try:
            await server.vector_add(db, SKILL_VEC_TABLE, [vec_row])
        except Exception:
            await server.vector_create(db, SKILL_VEC_TABLE, [vec_row], mode="overwrite")
        return {"skill_id": skill_id, "name": name, "s3_uri": s3_uri}

    @mcp.tool()
    @audited(redact_keys)
    async def execute_skill(name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """执行 Skill（MVP 占位）。"""
        require_scope(SCOPE)
        return {"name": name, "inputs": inputs, "status": "execution not implemented in MVP"}
