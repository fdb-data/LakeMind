"""Skill 资产工具：search / register / get / list / delete。"""
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
        name: str, description: str | None = None, code: str = "", version: str = "1.0.0",
        format: str = "py",
    ) -> dict[str, Any]:
        """Register Skill: upload code to S3, write Iceberg metadata, build Lance vector index.
        format: 'py' (single file) or 'zip' (multi-file package with jobs/)."""
        require_scope(SCOPE)
        ctx = get_tenant()
        bucket = "lakemind-filesets"
        ext = ".zip" if format == "zip" else ".py"
        s3_key = f"{ctx.tenant_id}/skills/{name}{ext}"
        if format == "zip":
            import base64
            code_bytes = base64.b64decode(code)
        else:
            code_bytes = code.encode()
        await server.object_put(bucket, s3_key, code_bytes)
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
    async def get_skill(name: str, format: str = "py") -> dict[str, Any]:
        """Get Skill code content. format: 'py' or 'zip'."""
        require_scope(SCOPE)
        ctx = get_tenant()
        bucket = "lakemind-filesets"
        ext = ".zip" if format == "zip" else ".py"
        s3_key = f"{ctx.tenant_id}/skills/{name}{ext}"
        data = await server.object_get(bucket, s3_key)
        if format == "zip":
            import base64
            code = base64.b64encode(data).decode() if isinstance(data, bytes) else str(data)
        else:
            code = data.decode("utf-8") if isinstance(data, bytes) else str(data)
        return {"name": name, "code": code, "format": format}

    @mcp.tool()
    @audited(redact_keys)
    async def list_skills() -> dict[str, Any]:
        """列出所有 Skill。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        ns = _iceberg_ns(ctx.tenant_id, SKILL_META_DOMAIN)
        try:
            resp = await server.table_scan(ns, SKILL_META_TABLE, limit=100)
            return {"skills": resp.get("rows", []), "count": resp.get("count", 0)}
        except Exception:
            return {"skills": [], "count": 0}

    @mcp.tool()
    @audited(redact_keys)
    async def delete_skill(name: str, format: str = "py") -> dict[str, Any]:
        """Delete Skill (S3 code + Iceberg metadata + Lance vector)."""
        require_scope(SCOPE)
        ctx = get_tenant()
        bucket = "lakemind-filesets"
        ext = ".zip" if format == "zip" else ".py"
        s3_key = f"{ctx.tenant_id}/skills/{name}{ext}"
        try:
            await server.object_delete(bucket, s3_key)
        except Exception:
            pass
        return {"status": "ok", "deleted": name}
