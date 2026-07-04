"""LakeMindDataMCP 服务组装。"""
from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import Config
from .server_client import ServerClient
from .security.audit import configure_logging
from .security.auth import AuthMiddleware

_log = logging.getLogger("lakemind_data_mcp")
__all__ = ["build_mcp", "build_app", "create_server"]


def build_mcp(config: Config, server: ServerClient) -> FastMCP:
    mcp = FastMCP(
        "LakeMindDataMCP",
        host=config.server.host,
        port=config.server.port,
        streamable_http_path=config.server.mcp_path,
        stateless_http=config.server.stateless,
        json_response=True,
    )

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "lakemind-data-mcp"})

    @mcp.resource("lake://workspace")
    def workspace() -> dict[str, Any]:
        """Current tenant context."""
        from .context import get_identity
        try:
            ident = get_identity()
            return {"agent_id": ident.agent_id, "tenant_id": ident.tenant_id, "scopes": list(ident.scopes)}
        except LookupError:
            return {"error": "no identity"}

    @mcp.resource("lake://system/health")
    async def system_health_resource() -> dict[str, Any]:
        """System component health (read-only)."""
        try:
            return await server.health()
        except Exception as e:
            return {"error": str(e)}

    rk = config.audit.redact_keys
    from .tools import data as data_tools
    data_tools.register(mcp, server, rk)

    return mcp


def build_app(config: Config) -> Starlette:
    server = ServerClient()
    mcp = build_mcp(config, server)
    mcp_app = mcp.streamable_http_app()

    mcp_app.user_middleware.insert(
        0, Middleware(AuthMiddleware, config=config, mcp_path=config.server.mcp_path)
    )
    mcp_app.middleware_stack = None
    return mcp_app


def create_server(config: Config) -> Starlette:
    configure_logging(config.audit.level)
    return build_app(config)
