"""系统级资源：lake://capabilities、lake://workspace。"""
from __future__ import annotations

from ..assets.registry import registry
from ..context import get_identity


def register(mcp) -> None:
    @mcp.resource("lake://capabilities")
    def capabilities() -> dict:
        """资产能力图：各资产类型的资源根与能力清单。"""
        return registry.capability_graph()

    @mcp.resource("lake://workspace")
    def workspace() -> dict:
        """当前请求身份信息。"""
        ident = get_identity()
        return {
            "agent_id": ident.agent_id,
            "tenant_id": ident.tenant_id,
            "scopes": list(ident.scopes),
        }
