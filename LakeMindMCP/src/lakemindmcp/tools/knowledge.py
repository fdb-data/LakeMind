"""Knowledge 资产工具：search_knowledge。"""
from __future__ import annotations

from typing import Any

from ..context import get_tenant
from ..engines import Engines
from ..resources.knowledge import KB_PREFIX
from ._helpers import audited, require_scope

SCOPE = "data"


def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def search_knowledge(
        fileset: str, query: str, top_k: int = 5, filter: str | None = None
    ) -> dict[str, Any]:
        """在知识库中做向量/全文检索。fileset 为知识库名。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        qvec = engines.embedding.embed([query])[0]
        hits = engines.lancedb.search(ctx, f"{KB_PREFIX}{fileset}", qvec, top_k, filter)
        return {"fileset": fileset, "query": query, "hits": hits, "count": len(hits)}
