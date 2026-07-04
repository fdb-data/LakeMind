"""LakeMindAdminMCP server."""
from __future__ import annotations
import logging
from typing import Any
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from .config import Config
from .security.audit import configure_logging
from .security.auth import AuthMiddleware

_log = logging.getLogger("lakemind_admin_mcp")

def build_mcp(config: Config) -> FastMCP:
    mcp = FastMCP("LakeMindAdminMCP", host=config.server.host, port=config.server.port,
                  streamable_http_path=config.server.mcp_path, stateless_http=config.server.stateless, json_response=True)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "lakemind-admin-mcp"})

    from .tools import admin as admin_tools
    rk = config.audit.redact_keys
    admin_tools.register(mcp, config, rk)
    return mcp

def build_app(config: Config) -> Starlette:
    mcp = build_mcp(config)
    mcp_app = mcp.streamable_http_app()
    mcp_app.user_middleware.insert(0, Middleware(AuthMiddleware, config=config, mcp_path=config.server.mcp_path))
    mcp_app.middleware_stack = None
    return mcp_app

def create_server(config: Config) -> Starlette:
    configure_logging(config.audit.level)
    return build_app(config)
