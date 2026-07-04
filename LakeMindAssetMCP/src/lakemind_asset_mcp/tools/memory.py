"""Memory 资产工具：remember / recall / forget。"""
from __future__ import annotations

from typing import Any

from ..context import get_tenant
from ..server_client import ServerClient
from ._helpers import audited, require_scope

SCOPE = "asset"


def register(mcp, server: ServerClient, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def remember(
        content: str,
        context: dict | None = None,
        ttl: int | None = None,
        kind: str = "general",
    ) -> dict[str, Any]:
        """记住一件事。ttl（秒）仅作用于短期记忆。kind 标记记忆类别。"""
        require_scope(SCOPE)
        get_tenant()
        ctx_str = str(context) if context else None
        resp = await server.memory_remember(content, ctx_str, ttl, kind)
        return resp

    @mcp.tool()
    @audited(redact_keys)
    async def recall(query: str, limit: int = 5, kind: str | None = None) -> dict[str, Any]:
        """语义/关键词召回长期记忆。kind 不为 None 时按类别过滤。"""
        require_scope(SCOPE)
        get_tenant()
        resp = await server.memory_recall(query, limit, kind)
        results = resp.get("results", [])
        memories = [
            {
                "memory_id": r.get("memory_id"),
                "kind": r.get("kind"),
                "content": r.get("content"),
                "_distance": r.get("_distance"),
            }
            for r in results
        ]
        return {"query": query, "memories": memories, "count": len(memories)}

    @mcp.tool()
    @audited(redact_keys)
    async def forget(query: str | None = None) -> dict[str, Any]:
        """遗忘匹配的记忆。query 为 None 时清空当前 Agent 的短期记忆。"""
        require_scope(SCOPE)
        get_tenant()
        resp = await server.memory_forget(query)
        return resp
