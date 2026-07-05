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
from .server_client import ServerClient
from .security.audit import configure_logging
from .security.auth import AuthMiddleware

_log = logging.getLogger("lakemind_admin_mcp")


def build_mcp(config: Config, server: ServerClient) -> FastMCP:
    mcp = FastMCP("LakeMindAdminMCP", host=config.server.host, port=config.server.port,
                  streamable_http_path=config.server.mcp_path, stateless_http=config.server.stateless, json_response=True)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "lakemind-admin-mcp"})

    # ── Resources ──

    @mcp.resource("lake://admin/health")
    async def admin_health() -> dict[str, Any]:
        """平台健康（引擎+容器）。"""
        try:
            return await server.health()
        except Exception as e:
            return {"error": str(e)}

    @mcp.resource("lake://admin/tenants")
    async def admin_tenants() -> dict[str, Any]:
        """租户列表。"""
        try:
            return await server.tenant_list()
        except Exception as e:
            return {"error": str(e)}

    @mcp.resource("lake://admin/users")
    async def admin_users() -> dict[str, Any]:
        """用户列表（按租户分组）。"""
        try:
            return await server.user_list()
        except Exception as e:
            return {"error": str(e)}

    @mcp.resource("lake://admin/tokens")
    async def admin_tokens() -> dict[str, Any]:
        """Token 列表（脱敏）。"""
        try:
            return await server.token_list()
        except Exception as e:
            return {"error": str(e)}

    @mcp.resource("lake://admin/asset-types")
    async def admin_asset_types() -> dict[str, Any]:
        """资产类型定义列表。"""
        try:
            return await server.asset_type_list()
        except Exception as e:
            return {"error": str(e)}

    @mcp.resource("lake://admin/nodes")
    async def admin_nodes() -> dict[str, Any]:
        """节点状态（容器+引擎）。"""
        try:
            return await server.nodes()
        except Exception as e:
            return {"error": str(e)}

    # ── Tools ──
    from .tools import admin as admin_tools
    rk = config.audit.redact_keys
    admin_tools.register(mcp, server, rk)

    # ── Prompts ──

    @mcp.prompt()
    def inspect_platform_guide(focus_area: str) -> str:
        """引导 Steward 巡检。"""
        return (
            f"你要巡检平台，关注领域：\"{focus_area}\"\n\n"
            "步骤：\n"
            "1. 调用 get_platform_health() 查看整体健康\n"
            "2. 调用 get_node_status() 查看各节点状态\n"
            "3. 调用 get_metrics() 查看关键指标\n"
            "4. 对异常项，结合 focus_area 深入排查：\n"
            "   - \"storage\": 检查 S3 容量、表数量\n"
            "   - \"compute\": 检查引擎响应时间\n"
            "   - \"security\": 检查 Token 状态、异常访问\n"
            "5. 汇总巡检结果，给出处置建议\n\n"
            "注意：巡检是只读操作，不应对平台产生副作用。"
        )

    @mcp.prompt()
    def manage_user_guide(action: str) -> str:
        """引导用户管理操作。"""
        return (
            f"你要执行用户管理操作：\"{action}\"\n\n"
            "可用操作：\n"
            "- create_user(username, tenant_id, role) — 创建用户\n"
            "- update_user(user_id, username, role, status) — 更新用户\n"
            "- delete_user(user_id) — 删除用户（软删除）\n"
            "- list_users(tenant_id) — 列出用户\n\n"
            "注意：delete_user 是软删除，用户记录保留但标记为 inactive。"
        )

    return mcp


def build_app(config: Config) -> Starlette:
    server = ServerClient()
    mcp = build_mcp(config, server)
    mcp_app = mcp.streamable_http_app()
    mcp_app.user_middleware.insert(0, Middleware(AuthMiddleware, config=config, mcp_path=config.server.mcp_path))
    mcp_app.middleware_stack = None
    return mcp_app


def create_server(config: Config) -> Starlette:
    configure_logging(config.audit.level)
    return build_app(config)
