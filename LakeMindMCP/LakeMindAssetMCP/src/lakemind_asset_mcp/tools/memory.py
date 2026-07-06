"""Memory 资产工具（mem0 风格）：add / search / get / list / update / delete / clear / history。"""
from __future__ import annotations

from typing import Any

from ..context import get_tenant
from ..server_client import ServerClient
from ._helpers import audited, require_scope

SCOPE = "asset"


def register(mcp, server: ServerClient, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def add_memory(
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
        infer: bool = True,
        expiration_date: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """添加记忆。infer=True 时 LLM 抽取事实+去重；infer=False 时裸存储。tenant_id/agent_id 自动注入。"""
        require_scope(SCOPE)
        get_tenant()
        return await server.memory_add(messages, metadata, infer, expiration_date, run_id)

    @mcp.tool()
    @audited(redact_keys)
    async def search_memory(
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
        threshold: float = 0.1,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """混合检索记忆（语义+关键词）。filters 支持 metadata 过滤。"""
        require_scope(SCOPE)
        get_tenant()
        resp = await server.memory_search(query, filters, top_k, threshold, run_id)
        return {"query": query, "results": resp.get("results", []), "count": resp.get("count", 0)}

    @mcp.tool()
    @audited(redact_keys)
    async def get_memory(memory_id: str) -> dict[str, Any]:
        """按 ID 获取单条记忆。"""
        require_scope(SCOPE)
        get_tenant()
        return await server.memory_get(memory_id)

    @mcp.tool()
    @audited(redact_keys)
    async def list_memory(
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 50,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """分页列出记忆。"""
        require_scope(SCOPE)
        get_tenant()
        return await server.memory_list(filters, page, page_size, run_id)

    @mcp.tool()
    @audited(redact_keys)
    async def update_memory(memory_id: str, content: str) -> dict[str, Any]:
        """按 ID 更新记忆内容。"""
        require_scope(SCOPE)
        get_tenant()
        return await server.memory_update(memory_id, content)

    @mcp.tool()
    @audited(redact_keys)
    async def delete_memory(memory_id: str) -> dict[str, Any]:
        """按 ID 删除单条记忆。"""
        require_scope(SCOPE)
        get_tenant()
        return await server.memory_delete(memory_id)

    @mcp.tool()
    @audited(redact_keys)
    async def clear_memory(
        filters: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """批量清除记忆。filters 为 None 时清空当前 Agent 全部记忆。"""
        require_scope(SCOPE)
        get_tenant()
        return await server.memory_clear(filters, run_id)

    @mcp.tool()
    @audited(redact_keys)
    async def memory_history(memory_id: str) -> dict[str, Any]:
        """查看记忆变更历史（ADD/UPDATE/DELETE 记录）。"""
        require_scope(SCOPE)
        get_tenant()
        return await server.memory_history(memory_id)
