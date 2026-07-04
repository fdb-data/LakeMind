"""Knowledge 资产工具：search_knowledge / ingest_knowledge / register_knowledge。"""
from __future__ import annotations

from typing import Any

from ..context import get_tenant
from ..server_client import ServerClient
from ._helpers import audited, require_scope

SCOPE = "asset"
KB_PREFIX = "kb_"


def _kb_table(fileset: str) -> str:
    return f"{KB_PREFIX}{fileset}"


def _vec_db(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


def register(mcp, server: ServerClient, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def search_knowledge(
        fileset: str, query: str, top_k: int = 5, filter: str | None = None
    ) -> dict[str, Any]:
        """在知识库中做向量/全文检索。fileset 为知识库名。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        table = _kb_table(fileset)
        embed_resp = await server.embed([query])
        qvec = embed_resp["vectors"][0]
        search_resp = await server.vector_search(db, table, qvec, top_k, filter)
        hits = search_resp.get("results", [])
        return {"fileset": fileset, "query": query, "hits": hits, "count": len(hits)}

    @mcp.tool()
    @audited(redact_keys)
    async def ingest_knowledge(
        fileset: str, documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """向知识库写入文档。每个文档含 content 及可选 title / doc_uri。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        if not documents:
            return {"fileset": fileset, "ingested": 0}
        db = _vec_db(ctx.tenant_id)
        table = _kb_table(fileset)
        contents = [d.get("content", "") for d in documents]
        embed_resp = await server.embed(contents)
        vecs = embed_resp["vectors"]
        data = [
            {
                "doc_uri": d.get("doc_uri", ""),
                "title": d.get("title", ""),
                "content": d.get("content", ""),
                "vector": vecs[i],
            }
            for i, d in enumerate(documents)
        ]
        try:
            await server.vector_add(db, table, data)
        except Exception:
            await server.vector_create(db, table, data, mode="overwrite")
        return {"fileset": fileset, "ingested": len(documents)}

    @mcp.tool()
    @audited(redact_keys)
    async def register_knowledge(
        name: str, description: str | None = None
    ) -> dict[str, Any]:
        """注册知识库：在当前租户下创建空 Lance 向量表。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        table = _kb_table(name)
        embed_resp = await server.embed(["init"])
        dim = embed_resp["dim"]
        await server.vector_create(db, table, [], mode="overwrite")
        return {"knowledge": name, "table": table, "description": description, "dim": dim}
