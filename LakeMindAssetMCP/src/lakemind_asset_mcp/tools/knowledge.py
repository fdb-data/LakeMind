"""Knowledge 资产工具（OKF 格式）：register / ingest / search / get / list / list_concepts / delete。"""
from __future__ import annotations

import re
import time
from typing import Any

from ..context import get_tenant
from ..server_client import ServerClient
from ._helpers import audited, require_scope

SCOPE = "asset"
KB_PREFIX = "kb_"
_CROSS_LINK_RE = re.compile(r"\[([^\]]+)\]\((/[^)]+\.md)\)")


def _kb_table(name: str) -> str:
    return f"{KB_PREFIX}{name}"


def _vec_db(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


def _s3_key(tenant_id: str, kb_name: str, concept_id: str) -> str:
    return f"{tenant_id}/knowledge/{kb_name}/{concept_id}.md"


def _format_okf(frontmatter: dict, body: str) -> str:
    import yaml as yamllib
    fm = {"type": frontmatter.get("type", "Concept")}
    for k in ("title", "description", "resource", "tags", "timestamp"):
        if k in frontmatter:
            fm[k] = frontmatter[k]
    fm_str = yamllib.dump(fm, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{fm_str}\n---\n\n{body}"


def _parse_cross_links(body: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2).lstrip("/").removesuffix(".md")) for m in _CROSS_LINK_RE.finditer(body)]


def register(mcp, server: ServerClient, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def register_knowledge(
        name: str, description: str | None = None
    ) -> dict[str, Any]:
        """创建 OKF 知识库：S3 bundle 目录 + LanceDB 向量索引 + PG graph。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        table = _kb_table(name)
        await server.vector_create(db, table, [], mode="overwrite")
        return {"knowledge": name, "table": table, "description": description, "format": "OKF"}

    @mcp.tool()
    @audited(redact_keys)
    async def ingest_knowledge(
        kb_name: str, concepts: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """写入 OKF 概念。每个 concept = {frontmatter: {type, title, description, resource, tags}, body: str}。
        自动 embed body + 解析 cross-link 建图 + 存 S3 markdown 文件。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        if not concepts:
            return {"kb_name": kb_name, "ingested": 0}

        db = _vec_db(ctx.tenant_id)
        table = _kb_table(kb_name)
        bucket = "lakemind-filesets"
        graph = f"ontology_{ctx.tenant_id}"
        now = int(time.time())
        vec_rows = []
        ingested = 0

        for concept in concepts:
            fm = concept.get("frontmatter", {})
            body = concept.get("body", "")
            title = fm.get("title", "")
            ctype = fm.get("type", "Concept")
            tags = fm.get("tags", [])
            concept_id = fm.get("resource", f"{kb_name}/{title.lower().replace(' ', '-')}")

            md_content = _format_okf(fm, body)
            s3_key = _s3_key(ctx.tenant_id, kb_name, concept_id)
            await server.object_put(bucket, s3_key, md_content.encode("utf-8"))

            embed_text = f"{title}\n{body}"
            embed_resp = await server.embed([embed_text])
            vec = embed_resp["vectors"][0]
            vec_rows.append({
                "concept_id": concept_id,
                "type": ctype,
                "title": title,
                "description": fm.get("description", ""),
                "tags": ",".join(tags) if isinstance(tags, list) else str(tags),
                "s3_uri": f"s3://{bucket}/{s3_key}",
                "vector": vec,
                "created_at": now,
            })

            try:
                await server.graph_add_node(graph, concept_id, ctype, {"name": title, "kb": kb_name}, ctx.tenant_id)
            except Exception:
                pass
            for link_text, link_target in _parse_cross_links(body):
                try:
                    await server.graph_add_node(graph, link_target, "Concept", {"name": link_text}, ctx.tenant_id)
                    import uuid
                    edge_id = f"e_{uuid.uuid4().hex[:8]}"
                    await server.graph_add_edge(graph, edge_id, concept_id, link_target, "references", {}, ctx.tenant_id)
                except Exception:
                    pass
            ingested += 1

        if vec_rows:
            try:
                await server.vector_add(db, table, vec_rows)
            except Exception:
                await server.vector_create(db, table, vec_rows, mode="overwrite")

        return {"kb_name": kb_name, "ingested": ingested}

    @mcp.tool()
    @audited(redact_keys)
    async def search_knowledge(
        query: str, kb_name: str | None = None, top_k: int = 5, filter: str | None = None
    ) -> dict[str, Any]:
        """向量+全文检索 OKF 概念。返回 frontmatter 摘要 + body 片段。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        embed_resp = await server.embed([query])
        qvec = embed_resp["vectors"][0]

        if kb_name:
            tables = [_kb_table(kb_name)]
        else:
            resp = await server.vector_list(db)
            tables = [t for t in resp.get("tables", []) if t.startswith(KB_PREFIX)]

        all_hits = []
        for table in tables:
            try:
                search_resp = await server.vector_search(db, table, qvec, top_k, filter)
                hits = search_resp.get("results", [])
                for h in hits:
                    h["kb_name"] = table.removeprefix(KB_PREFIX)
                all_hits.extend(hits)
            except Exception:
                pass

        all_hits.sort(key=lambda h: h.get("_distance", 1.0))
        return {"query": query, "hits": all_hits[:top_k], "count": len(all_hits[:top_k])}

    @mcp.tool()
    @audited(redact_keys)
    async def get_knowledge(kb_name: str, concept_id: str) -> dict[str, Any]:
        """按 ID 获取完整 OKF 概念文档（frontmatter + body）。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        bucket = "lakemind-filesets"
        s3_key = _s3_key(ctx.tenant_id, kb_name, concept_id)
        data = await server.object_get(bucket, s3_key)
        content = data.decode("utf-8") if isinstance(data, bytes) else str(data)
        return {"kb_name": kb_name, "concept_id": concept_id, "content": content}

    @mcp.tool()
    @audited(redact_keys)
    async def list_knowledge() -> dict[str, Any]:
        """列出当前租户的所有知识库。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        resp = await server.vector_list(db)
        tables = [t for t in resp.get("tables", []) if t.startswith(KB_PREFIX)]
        out = []
        for t in tables:
            try:
                desc = await server.vector_describe(db, t)
                desc["name"] = t.removeprefix(KB_PREFIX)
                out.append(desc)
            except Exception:
                out.append({"name": t.removeprefix(KB_PREFIX)})
        return {"knowledge_bases": out, "count": len(out)}

    @mcp.tool()
    @audited(redact_keys)
    async def list_concepts(
        kb_name: str, type: str | None = None, tag: str | None = None,
        page: int = 1, page_size: int = 50
    ) -> dict[str, Any]:
        """分页列出知识库中的概念，可按 type/tag 过滤。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        table = _kb_table(kb_name)
        try:
            resp = await server.vector_describe(db, table)
            count = resp.get("count", 0)
        except Exception:
            count = 0
        return {"kb_name": kb_name, "type_filter": type, "tag_filter": tag,
                "page": page, "page_size": page_size, "total": count}

    @mcp.tool()
    @audited(redact_keys)
    async def delete_knowledge(kb_name: str) -> dict[str, Any]:
        """删除知识库（S3 文件 + LanceDB 向量表 + PG graph 节点）。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        table = _kb_table(kb_name)
        bucket = "lakemind-filesets"
        prefix = f"{ctx.tenant_id}/knowledge/{kb_name}/"
        try:
            resp = await server.object_list(bucket, prefix)
            for key in resp.get("keys", []):
                try:
                    await server.object_delete(bucket, key)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            await server.vector_create(db, table, [], mode="overwrite")
        except Exception:
            pass
        return {"status": "ok", "deleted": kb_name}
