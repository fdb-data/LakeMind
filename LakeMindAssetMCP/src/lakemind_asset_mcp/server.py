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
from .server_client import ServerClient
from .security.audit import configure_logging
from .security.auth import AuthMiddleware

_log = logging.getLogger("lakemind_asset_mcp")
__all__ = ["build_mcp", "build_app", "create_server"]


def build_mcp(config: Config, server: ServerClient) -> FastMCP:
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

    @mcp.resource("lake://system/health")
    async def system_health_resource() -> dict[str, Any]:
        """System component health (read-only)."""
        try:
            return await server.health()
        except Exception as e:
            return {"error": str(e)}

    rk = config.audit.redact_keys

    from .tools import knowledge as kb_tools
    from .tools import memory as mem_tools
    from .tools import ontology as ont_tools
    from .tools import skill as skill_tools

    kb_tools.register(mcp, server, rk)
    skill_tools.register(mcp, server, rk)
    mem_tools.register(mcp, server, rk)
    ont_tools.register(mcp, server, rk)

    @mcp.resource("lake://knowledge")
    async def list_knowledge() -> list[dict]:
        """知识库列表。"""
        from .context import get_tenant
        try:
            ctx = get_tenant()
            db = f"tenant_{ctx.tenant_id}"
            resp = await server.vector_list(db)
            tables = [t for t in resp.get("tables", []) if t.startswith("kb_")]
            out = []
            for t in tables:
                try:
                    out.append(await server.vector_describe(db, t))
                except Exception:
                    out.append({"name": t})
            return out
        except Exception as e:
            return [{"error": str(e)}]

    @mcp.resource("lake://knowledge/{id}")
    async def describe_knowledge(id: str) -> dict:
        """知识库描述。"""
        from .context import get_tenant
        ctx = get_tenant()
        db = f"tenant_{ctx.tenant_id}"
        return await server.vector_describe(db, f"kb_{id}")

    @mcp.resource("lake://skills")
    async def list_skills() -> dict:
        """Skill 列表。"""
        from .context import get_tenant
        try:
            ctx = get_tenant()
            ns = f"{ctx.tenant_id}_skills"
            resp = await server.table_scan(ns, "skill_meta", limit=100)
            return {"skills": resp.get("rows", []), "count": resp.get("count", 0)}
        except Exception as e:
            return {"skills": [], "count": 0, "error": str(e)}

    @mcp.resource("lake://memory")
    async def memory_status() -> dict:
        """记忆状态。"""
        from .context import get_tenant
        try:
            ctx = get_tenant()
            db = f"tenant_{ctx.tenant_id}"
            resp = await server.vector_list(db)
            has_mem = "memory_vectors" in resp.get("tables", [])
            return {"has_long_term": has_mem}
        except Exception as e:
            return {"error": str(e)}

    @mcp.resource("lake://ontology")
    async def list_ontology() -> dict:
        """本体图节点。"""
        from .context import get_tenant
        try:
            ctx = get_tenant()
            graph = f"ontology_{ctx.tenant_id}"
            resp = await server.graph_query_nodes(graph, ctx.tenant_id)
            return {"nodes": resp.get("nodes", []), "count": resp.get("count", 0)}
        except Exception as e:
            return {"nodes": [], "count": 0, "error": str(e)}

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
