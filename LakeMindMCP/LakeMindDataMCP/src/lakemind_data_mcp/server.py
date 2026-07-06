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

    # ── Resources ──

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

    @mcp.resource("lake://tables")
    async def list_tables_resource() -> dict[str, Any]:
        """Iceberg 表列表（按 namespace 分组）。"""
        from .context import get_tenant
        try:
            ctx = get_tenant()
            ns = f"{ctx.tenant_id}_data"
            resp = await server.table_list(ns)
            return {"namespace": ns, "tables": resp.get("tables", [])}
        except Exception as e:
            return {"error": str(e)}

    @mcp.resource("lake://tables/{namespace}/{table}")
    async def describe_table_resource(namespace: str, table: str) -> dict[str, Any]:
        """表 schema + 行数。"""
        from .context import get_tenant
        ctx = get_tenant()
        ns = f"{ctx.tenant_id}_{namespace}"
        return await server.table_describe(ns, table)

    @mcp.resource("lake://vectors")
    async def list_vectors_resource() -> dict[str, Any]:
        """向量表列表。"""
        from .context import get_tenant
        try:
            ctx = get_tenant()
            db = f"tenant_{ctx.tenant_id}"
            resp = await server.vector_list(db)
            return {"db": db, "tables": resp.get("tables", [])}
        except Exception as e:
            return {"error": str(e)}

    @mcp.resource("lake://vectors/{table}")
    async def describe_vector_resource(table: str) -> dict[str, Any]:
        """向量表 schema + 维度。"""
        from .context import get_tenant
        ctx = get_tenant()
        db = f"tenant_{ctx.tenant_id}"
        return await server.vector_describe(db, table)

    # ── Tools ──
    rk = config.audit.redact_keys
    from .tools import data as data_tools
    data_tools.register(mcp, server, rk)

    # ── Prompts ──

    @mcp.prompt()
    def sql_query_guide(intent: str) -> str:
        """引导写跨表 SQL。"""
        return (
            f"你要执行数据分析，意图：\"{intent}\"\n\n"
            "步骤：\n"
            "1. 调用 list_tables() 查看可用的表\n"
            "2. 对相关表调用 describe_table(table=...) 了解 schema\n"
            "3. 构造 SQL（仅 SELECT，禁止 DDL/DML）\n"
            "4. 调用 sql_query(sql=...) 执行\n"
            "5. 检查返回 rows 和 count\n\n"
            "注意：SQL 在 DuckDB 中执行，支持跨表 JOIN，但大表查询注意加 LIMIT。"
        )

    @mcp.prompt()
    def data_exploration_guide(table: str) -> str:
        """引导数据探索。"""
        return (
            f"你要探索表：\"{table}\"\n\n"
            "步骤：\n"
            f"1. 调用 describe_table(table=\"{table}\") 了解 schema\n"
            f"2. 调用 query_table(table=\"{table}\", limit=10) 采样\n"
            "3. 分析数据分布、空值、异常值\n"
            "4. 如需跨表分析，用 sql_query 构造 JOIN\n\n"
            "注意：先看 schema 再写查询，避免列名错误。"
        )

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
