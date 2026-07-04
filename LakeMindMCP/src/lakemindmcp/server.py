"""LakeMindMCP 服务组装。

组装顺序：FastMCP → 注册 resources/tools → streamable_http_app（Starlette）
→ 注入 AuthMiddleware → uvicorn 启动。
"""
from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import Config
from .engines import Engines, build_engines
from .security.audit import configure_logging
from .security.auth import AuthMiddleware

_log = logging.getLogger("lakemindmcp")
__all__ = ["build_mcp", "build_app", "create_server"]


def build_mcp(config: Config, engines: Engines | None = None) -> FastMCP:
    """构造 FastMCP 实例并注册资源/工具。"""
    mcp = FastMCP(
        "LakeMindMCP",
        host=config.server.host,
        port=config.server.port,
        streamable_http_path=config.server.mcp_path,
        stateless_http=config.server.stateless,
        json_response=True,
    )

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "lakemind-mcp"})

    _register_capabilities(mcp)

    if engines is not None:
        from .health import system_health
        from .resources import data as data_res
        from .resources import experience as exp_res
        from .resources import knowledge as kb_res
        from .resources import memory as mem_res
        from .resources import skill as skill_res
        from .resources import system as sys_res
        from .tools import admin as admin_tools
        from .tools import data as data_tools
        from .tools import experience as exp_tools
        from .tools import knowledge as kb_tools
        from .tools import memory as mem_tools
        from .tools import skill as skill_tools

        @mcp.resource("lake://system/health")
        def system_health_resource() -> dict[str, Any]:
            """系统组件健康（只读，任何已认证用户可读）。"""
            return system_health(engines)

        rk = config.audit.redact_keys
        data_res.register(mcp, engines)
        kb_res.register(mcp, engines)
        mem_res.register(mcp, engines)
        skill_res.register(mcp, engines)
        exp_res.register(mcp, engines)
        sys_res.register(mcp)

        data_tools.register(mcp, engines, rk)
        kb_tools.register(mcp, engines, rk)
        mem_tools.register(mcp, engines, rk)
        skill_tools.register(mcp, engines, rk)
        exp_tools.register(mcp, engines, rk)
        admin_tools.register(mcp, engines, rk)
    return mcp


def _register_capabilities(mcp: FastMCP) -> None:
    """``lake://capabilities`` 系统资源。"""
    from .assets.registry import AssetType, registry

    for at in _builtin_types():
        registry.register(at)

    @mcp.resource("lake://capabilities")
    def capabilities() -> dict[str, Any]:
        """资产类型 → 支持操作列表的映射图，Agent 首次连接必读。"""
        return {
            t.type: {
                "description": t.description,
                "resource_root": t.resource_root,
                "capabilities": t.capabilities,
                "enabled": t.type != "ontology",
            }
            for t in registry.types.values()
        }

    @mcp.resource("lake://workspace")
    def workspace() -> dict[str, Any]:
        """当前租户上下文。"""
        from .context import get_identity

        try:
            ident = get_identity()
            return {
                "agent_id": ident.agent_id,
                "tenant_id": ident.tenant_id,
                "scopes": list(ident.scopes),
            }
        except LookupError:
            return {"error": "no identity"}


def _builtin_types() -> list:
    from .assets.registry import AssetType

    return [
        AssetType("data", "结构化数据", {}, "lake://data", ["query", "insert", "merge"]),
        AssetType("knowledge", "知识/多模态 RAG", {}, "lake://knowledge", ["search"]),
        AssetType("memory", "记忆", {}, "lake://memory", ["remember", "recall", "forget"]),
        AssetType("skill", "技能", {}, "lake://skills", ["search", "execute"]),
        AssetType("experience", "经验", {}, "lake://experience", ["record"]),
        AssetType("ontology", "本体（预留）", {}, "lake://ontology", [], lifecycle=None),
    ]


def build_app(config: Config, engines: Engines | None = None) -> Starlette:
    """构造 ASGI app：在 MCP Starlette 上注入 Auth 中间件（保留其 lifespan）。"""
    if engines is None:
        try:
            engines = build_engines(config)
        except Exception as e:  # 引擎不可用，降级为仅系统资源
            _log.warning("engines unavailable, starting without data assets: %s", e)
            engines = None

    mcp = build_mcp(config, engines)
    mcp_app = mcp.streamable_http_app()

    mcp_app.user_middleware.insert(
        0, Middleware(AuthMiddleware, config=config, mcp_path=config.server.mcp_path)
    )
    mcp_app.middleware_stack = None
    return mcp_app


def create_server(config: Config) -> Starlette:
    configure_logging(config.audit.level)
    return build_app(config)
