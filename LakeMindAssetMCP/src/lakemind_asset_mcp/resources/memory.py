"""Memory 资产资源：lake://memory。"""
from __future__ import annotations

from ..context import get_tenant
from ..engines import Engines

MEM_TABLE = "memory_vectors"


def register(mcp, engines: Engines) -> None:
    @mcp.resource("lake://memory")
    def memory_overview() -> dict:
        """当前 Agent 记忆概况。"""
        ctx = get_tenant()
        long_count = engines.lancedb.count_rows(ctx, MEM_TABLE) if engines.lancedb.table_exists(ctx, MEM_TABLE) else 0
        short_keys = engines.dragonfly.scan(ctx, f"mem:{ctx.agent_id}:*")
        return {
            "agent_id": ctx.agent_id,
            "tenant_id": ctx.tenant_id,
            "long_term_count": long_count,
            "short_term_keys": short_keys,
        }
