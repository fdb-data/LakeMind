"""LakeMindAssetMCP 服务组装。"""
from __future__ import annotations

import logging
from pathlib import Path
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

_log = logging.getLogger("lakemind_asset_mcp")
__all__ = ["build_mcp", "build_app", "create_server"]


def build_mcp(config: Config, engines: Engines | None = None) -> FastMCP:
    mcp = FastMCP(
        "LakeMindAssetMCP",
        host=config.server.host,
        port=config.server.port,
        streamable_http_path=config.server.mcp_path,
        stateless_http=config.server.stateless,
        json_response=True,
    )

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "lakemind-asset-mcp"})

    from .assets.registry import registry

    native_dir = Path(__file__).parent / "assets" / "native"
    registry.load_native(native_dir)

    @mcp.resource("lake://capabilities")
    def capabilities() -> dict[str, Any]:
        """Asset type → capabilities mapping."""
        return registry.capability_graph()

    @mcp.resource("lake://workspace")
    def workspace() -> dict[str, Any]:
        """Current tenant context."""
        from .context import get_identity
        try:
            ident = get_identity()
            return {"agent_id": ident.agent_id, "tenant_id": ident.tenant_id, "scopes": list(ident.scopes)}
        except LookupError:
            return {"error": "no identity"}

    if engines is not None:
        from .health import system_health
        from .resources import knowledge as kb_res
        from .resources import memory as mem_res
        from .resources import ontology as ont_res
        from .resources import skill as skill_res
        from .tools import knowledge as kb_tools
        from .tools import memory as mem_tools
        from .tools import ontology as ont_tools
        from .tools import skill as skill_tools

        @mcp.resource("lake://system/health")
        def system_health_resource() -> dict[str, Any]:
            """System component health (read-only)."""
            return system_health(engines)

        rk = config.audit.redact_keys
        kb_res.register(mcp, engines)
        skill_res.register(mcp, engines)
        mem_res.register(mcp, engines)
        ont_res.register(mcp, engines)

        kb_tools.register(mcp, engines, rk)
        skill_tools.register(mcp, engines, rk)
        mem_tools.register(mcp, engines, rk)
        ont_tools.register(mcp, engines, rk)

    return mcp


def build_app(config: Config, engines: Engines | None = None) -> Starlette:
    if engines is None:
        try:
            engines = build_engines(config)
        except Exception as e:
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
