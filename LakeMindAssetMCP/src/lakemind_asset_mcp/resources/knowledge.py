"""Knowledge 资产资源：lake://knowledge、lake://knowledge/{id}。"""
from __future__ import annotations

from ..context import get_tenant
from ..engines import Engines

KB_PREFIX = "kb_"


def knowledge_tables(engines: Engines, ctx) -> list[str]:
    return [t for t in engines.lancedb.list_tables(ctx) if t.startswith(KB_PREFIX)]


def register(mcp, engines: Engines) -> None:
    @mcp.resource("lake://knowledge")
    def list_knowledge() -> list[dict]:
        """知识库列表。"""
        ctx = get_tenant()
        out = []
        for t in knowledge_tables(engines, ctx):
            try:
                out.append(engines.lancedb.describe(ctx, t))
            except Exception:
                out.append({"name": t})
        return out

    @mcp.resource("lake://knowledge/{id}")
    def describe_knowledge(id: str) -> dict:
        """知识库描述、文档数、索引状态。"""
        ctx = get_tenant()
        return engines.lancedb.describe(ctx, f"{KB_PREFIX}{id}")
