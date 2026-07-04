"""Knowledge 资产工具：search_knowledge / ingest_knowledge / register_knowledge。"""
from __future__ import annotations

from typing import Any

import pyarrow as pa

from ..context import get_tenant
from ..engines import Engines
from ..resources.knowledge import KB_PREFIX
from ._helpers import audited, require_scope

SCOPE = "asset"


def _kb_table(fileset: str) -> str:
    return f"{KB_PREFIX}{fileset}"


def _empty_kb_table(dim: int) -> pa.Table:
    return pa.table(
        {
            "doc_uri": pa.array([], pa.string()),
            "title": pa.array([], pa.string()),
            "content": pa.array([], pa.string()),
            "vector": pa.array([], pa.list_(pa.float32(), dim)),
        }
    )


def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def search_knowledge(
        fileset: str, query: str, top_k: int = 5, filter: str | None = None
    ) -> dict[str, Any]:
        """在知识库中做向量/全文检索。fileset 为知识库名。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        table = _kb_table(fileset)
        if not engines.lancedb.table_exists(ctx, table):
            return {"fileset": fileset, "query": query, "hits": [], "count": 0}
        qvec = engines.embedding.embed([query])[0]
        hits = engines.lancedb.search(ctx, table, qvec, top_k, filter)
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
        dim = engines.embedding.dim
        table = _kb_table(fileset)
        contents = [d.get("content", "") for d in documents]
        vecs = engines.embedding.embed(contents)
        if not engines.lancedb.table_exists(ctx, table):
            engines.lancedb.create_table(ctx, table, _empty_kb_table(dim), mode="overwrite")
        row = pa.table(
            {
                "doc_uri": [d.get("doc_uri", "") for d in documents],
                "title": [d.get("title", "") for d in documents],
                "content": contents,
                "vector": pa.array(vecs, type=pa.list_(pa.float32(), dim)),
            }
        )
        engines.lancedb.add(ctx, table, row)
        return {"fileset": fileset, "ingested": len(documents)}

    @mcp.tool()
    @audited(redact_keys)
    async def register_knowledge(
        name: str, description: str | None = None
    ) -> dict[str, Any]:
        """注册知识库：在当前租户下创建空 Lance 向量表。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        dim = engines.embedding.dim
        table = _kb_table(name)
        engines.lancedb.create_table(ctx, table, _empty_kb_table(dim), mode="overwrite")
        return {"knowledge": name, "table": table, "description": description, "dim": dim}
