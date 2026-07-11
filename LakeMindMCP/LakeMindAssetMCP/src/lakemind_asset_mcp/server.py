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

    # ── Resources ──

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

    @mcp.resource("lake://knowledge")
    async def list_knowledge() -> list[dict]:
        """知识库列表（OKF bundle 概览）。"""
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
        except Exception:
            return []

    @mcp.resource("lake://knowledge/{id}")
    async def describe_knowledge(id: str) -> dict:
        """知识库详情（概念列表 + 元信息）。"""
        from .context import get_tenant
        ctx = get_tenant()
        db = f"tenant_{ctx.tenant_id}"
        table = f"kb_{id}" if not id.startswith("kb_") else id
        info = await server.vector_describe(db, table)
        try:
            concepts = await server.vector_scan(db, table, limit=200)
        except Exception:
            concepts = []
        for c in concepts:
            c.pop("vector", None)
        return {
            "name": info.get("name", table),
            "concept_count": info.get("concept_count", info.get("row_count", 0)),
            "schema": info.get("schema", []),
            "concepts": concepts,
        }

    @mcp.resource("lake://knowledge/{kb_name}/{concept_id}")
    async def get_knowledge_resource(kb_name: str, concept_id: str) -> dict:
        """单个 OKF 概念文档（frontmatter + body）。"""
        from .context import get_tenant
        ctx = get_tenant()
        bucket = "lakemind-filesets"
        s3_key = f"{ctx.tenant_id}/knowledge/{kb_name}/{concept_id}.md"
        data = await server.object_get(bucket, s3_key)
        content = data.decode("utf-8") if isinstance(data, bytes) else str(data)
        return {"kb_name": kb_name, "concept_id": concept_id, "content": content}

    @mcp.resource("lake://skills")
    async def list_skills() -> dict:
        """Skill 列表。"""
        from .context import get_tenant
        try:
            ctx = get_tenant()
            ns = f"{ctx.tenant_id}_skills"
            resp = await server.table_scan(ns, "skill_meta", limit=100)
            return {"skills": resp.get("rows", []), "count": resp.get("count", 0)}
        except Exception:
            return {"skills": [], "count": 0}

    @mcp.resource("lake://skills/{name}")
    async def describe_skill(name: str) -> dict:
        """Skill 详情（元信息 + s3_uri）。"""
        from .context import get_tenant
        ctx = get_tenant()
        bucket = "lakemind-filesets"
        s3_key = f"{ctx.tenant_id}/skills/{name}.py"
        data = await server.object_get(bucket, s3_key)
        code = data.decode("utf-8") if isinstance(data, bytes) else str(data)
        return {"name": name, "code": code, "s3_uri": f"s3://{bucket}/{s3_key}"}

    @mcp.resource("lake://memory")
    async def memory_status() -> dict:
        """记忆概览（总数、按 kind 统计）。"""
        from .context import get_tenant
        try:
            ctx = get_tenant()
            resp = await server.memory_list(page=1, page_size=1)
            return {"total": resp.get("count", 0)}
        except Exception:
            return {"total": 0}

    @mcp.resource("lake://memory/{memory_id}")
    async def get_memory_resource(memory_id: str) -> dict:
        """单条记忆详情（含 metadata、history）。"""
        from .context import get_tenant
        get_tenant()
        return await server.memory_get(memory_id)

    @mcp.resource("lake://ontology")
    async def list_ontology() -> dict:
        """本体图概览（节点数 + 边数 + 顶层概念）。"""
        from .context import get_tenant
        try:
            ctx = get_tenant()
            graph = f"ontology_{ctx.tenant_id}"
            resp = await server.graph_query_nodes(graph, ctx.tenant_id)
            return {"nodes": resp.get("nodes", []), "count": resp.get("count", 0)}
        except Exception as e:
            return {"nodes": [], "count": 0, "error": str(e)}

    @mcp.resource("lake://ontology/{concept}")
    async def describe_ontology(concept: str) -> dict:
        """概念详情（属性 + 关联关系）。"""
        from .context import get_tenant
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        nodes_resp = await server.graph_query_nodes(graph, ctx.tenant_id, label=concept)
        nodes = nodes_resp.get("nodes", [])
        edges = []
        for n in nodes:
            edges_resp = await server.graph_query_edges(graph, n["node_id"], ctx.tenant_id)
            edges.extend(edges_resp.get("edges", []))
        return {"concept": concept, "nodes": nodes, "edges": edges}

    # ── Tools ──
    rk = config.audit.redact_keys

    from .tools import knowledge as kb_tools
    from .tools import memory as mem_tools
    from .tools import ontology as ont_tools
    from .tools import skill as skill_tools

    kb_tools.register(mcp, server, rk)
    skill_tools.register(mcp, server, rk)
    mem_tools.register(mcp, server, rk)
    ont_tools.register(mcp, server, rk)

    # ── Prompts ──

    @mcp.prompt()
    def search_knowledge_guide(query: str, kb_name: str) -> str:
        """引导 Agent 高效检索知识库。"""
        return (
            f"你要在知识库 \"{kb_name}\" 中检索：\"{query}\"\n\n"
            "步骤：\n"
            "1. 调用 search_knowledge(query=\"" + query + "\", kb_name=\"" + kb_name + "\", top_k=5)\n"
            "2. 检查返回的 hits，关注 _distance 字段（越小越相关）\n"
            "3. 如果结果不相关，尝试用 filter 参数缩窄范围\n"
            "4. 如果仍不相关，考虑用更具体的 query 重新检索\n\n"
            "注意：query 的语义质量直接影响检索结果，尽量用自然语言完整描述你的问题。"
        )

    @mcp.prompt()
    def okf_concept_guide(type: str, title: str) -> str:
        """引导编写 OKF 概念文档。"""
        return (
            f"你要写入一个 OKF 概念文档，类型：\"{type}\"，标题：\"{title}\"\n\n"
            "OKF 概念 = YAML frontmatter + markdown body\n\n"
            "frontmatter 必填字段：\n"
            f"  type: {type}\n"
            f"  title: {title}\n"
            "  description: ...      # 一句话摘要\n"
            "  resource: ...         # 资产 URI（可选）\n"
            "  tags: [tag1, tag2]    # 跨切面分类\n\n"
            "body 约定节：\n"
            "  # Schema    — 结构化描述\n"
            "  # Examples  — 用法示例\n"
            "  # Citations — 外部引用\n\n"
            "cross-link：用 markdown 链接 [概念名](/path/to/concept.md) 表达概念间关系\n\n"
            "调用 ingest_knowledge(kb_name, concepts=[{\n"
            "  \"frontmatter\": {\"type\": ..., \"title\": ..., \"description\": ..., \"tags\": [...]},\n"
            "  \"body\": \"markdown content with [cross-links](/path)\"\n"
            "}])"
        )

    @mcp.prompt()
    def register_skill_guide(name: str, description: str, code: str) -> str:
        """引导 Skill 注册。"""
        return (
            f"你要注册一个 Skill：\"{name}\"\n\n"
            "最佳实践：\n"
            "1. description 要语义化（直接影响检索质量），用一句话描述 Skill 的功能\n"
            "2. code 要自包含，不依赖外部状态\n"
            "3. version 从 1.0.0 开始，语义化版本号\n\n"
            f"调用 register_skill(name=\"{name}\", description=\"{description}\", code=..., version=\"1.0.0\")"
        )

    @mcp.prompt()
    def add_memory_guide(messages: str) -> str:
        """引导记忆添加。"""
        return (
            f"你要添加记忆，消息内容：\"{messages}\"\n\n"
            "mem0 风格记忆添加：\n\n"
            "1. infer=True（默认）：平台用 LLM 从 messages 中抽取结构化事实，自动去重\n"
            "   - 适合：对话记录、用户偏好、事件描述\n"
            "   - messages 格式：[{\"role\": \"user\", \"content\": \"...\"}]\n\n"
            "2. infer=False：直接裸存储，不经过 LLM 抽取\n"
            "   - 适合：已结构化的数据、不需要去重的原始记录\n\n"
            "metadata：自定义 key-value，可用于后续过滤\n"
            "expiration_date：YYYY-MM-DD 格式，过期后默认隐藏\n\n"
            "调用 add_memory(messages=..., metadata=..., infer=True)"
        )

    @mcp.prompt()
    def search_memory_guide(query: str) -> str:
        """引导记忆检索。"""
        return (
            f"你要检索记忆：\"{query}\"\n\n"
            "步骤：\n"
            f"1. 调用 search_memory(query=\"{query}\", top_k=10, threshold=0.1)\n"
            "2. 检查返回的 results，关注 score 字段（越高越相关）\n"
            "3. 可用 filters 按 metadata 过滤（如 filters={{\"source\": \"chat\"}}）\n"
            "4. 可用 run_id 限定会话范围\n\n"
            "注意：threshold 越高越严格（0-1），默认 0.1。"
        )

    @mcp.prompt()
    def query_ontology_guide(concept: str) -> str:
        """引导本体查询。"""
        return (
            f"你要查询本体概念：\"{concept}\"\n\n"
            "步骤：\n"
            f"1. 调用 query_ontology(concept=\"{concept}\")\n"
            "2. 查看返回的 nodes 和 edges\n"
            "3. 可用 relation 参数过滤特定关系类型\n"
            "4. 如果概念不存在，查看 lake://ontology 获取所有概念\n"
            "5. 用 update_ontology 添加新的三元组"
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
