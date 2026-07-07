"""Data face transparent passthrough tools."""
from __future__ import annotations
from typing import Any

from ..context import get_tenant
from ..server_client import ServerClient
from ._helpers import audited, require_scope

SCOPE = "data"


def _iceberg_ns(tenant_id: str, domain: str) -> str:
    return f"{tenant_id}_{domain}"


def _vec_db(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


def register(mcp, server: ServerClient, redact_keys: list[str]) -> None:
    # ── Iceberg 表 ──

    @mcp.tool()
    @audited(redact_keys)
    async def query_table(table: str, columns: str | None = None, filter: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Scan Iceberg table. columns: comma-separated, filter: SQL expression."""
        require_scope(SCOPE)
        ctx = get_tenant()
        ns = _iceberg_ns(ctx.tenant_id, "data")
        resp = await server.table_scan(ns, table, columns=columns, filter=filter, limit=limit)
        return {"table": table, "rows": resp.get("rows", []), "count": resp.get("count", 0)}

    @mcp.tool()
    @audited(redact_keys)
    async def write_table(table: str, rows: list[dict], mode: str = "append") -> dict[str, Any]:
        """Write to Iceberg table. mode: append|overwrite."""
        require_scope(SCOPE)
        ctx = get_tenant()
        if not rows:
            return {"table": table, "written": 0}
        ns = _iceberg_ns(ctx.tenant_id, "data")
        if mode == "overwrite":
            resp = await server.table_overwrite(ns, table, rows)
        else:
            resp = await server.table_append(ns, table, rows)
        return {"table": table, "written": resp.get("rows_written", 0), "mode": mode}

    @mcp.tool()
    @audited(redact_keys)
    async def sql_query(sql: str) -> dict[str, Any]:
        """Execute ad-hoc SQL via DuckDB."""
        require_scope(SCOPE)
        resp = await server.sql_execute(sql)
        return {"sql": sql, "rows": resp.get("results", []), "count": resp.get("count", 0)}

    @mcp.tool()
    @audited(redact_keys)
    async def list_tables(namespace: str | None = None) -> dict[str, Any]:
        """List Iceberg tables."""
        require_scope(SCOPE)
        ctx = get_tenant()
        domain = namespace or "data"
        ns = _iceberg_ns(ctx.tenant_id, domain)
        resp = await server.table_list(ns)
        return {"namespace": domain, "tables": resp.get("tables", [])}

    @mcp.tool()
    @audited(redact_keys)
    async def describe_table(table: str) -> dict[str, Any]:
        """Describe Iceberg table schema."""
        require_scope(SCOPE)
        ctx = get_tenant()
        ns = _iceberg_ns(ctx.tenant_id, "data")
        return await server.table_describe(ns, table)

    @mcp.tool()
    @audited(redact_keys)
    async def create_table(name: str, schema: dict[str, str], partition: str | None = None) -> dict[str, Any]:
        """Create Iceberg table. schema: {column: type}. partition: optional partition column."""
        require_scope(SCOPE)
        ctx = get_tenant()
        ns = _iceberg_ns(ctx.tenant_id, "data")
        await server.table_create(ns, name, schema)
        return {"table": name, "columns": list(schema.keys()), "partition": partition}

    @mcp.tool()
    @audited(redact_keys)
    async def drop_table(table: str) -> dict[str, Any]:
        """Drop Iceberg table."""
        require_scope(SCOPE)
        ctx = get_tenant()
        ns = _iceberg_ns(ctx.tenant_id, "data")
        await server.table_drop(ns, table)
        return {"status": "ok", "dropped": table}

    # ── 向量 ──

    @mcp.tool()
    @audited(redact_keys)
    async def vector_search(table: str, query: str, top_k: int = 5, filter: str | None = None) -> dict[str, Any]:
        """Vector search via LanceDB."""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        embed_resp = await server.embed([query])
        qvec = embed_resp["vectors"][0]
        resp = await server.vector_search(db, table, qvec, top_k, filter)
        hits = resp.get("results", [])
        return {"table": table, "hits": hits, "count": len(hits)}

    # ── S3 对象 ──

    @mcp.tool()
    @audited(redact_keys)
    async def s3_get(uri: str) -> dict[str, Any]:
        """Read S3 object. Returns content and size."""
        require_scope(SCOPE)
        parts = uri.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
        data = await server.object_get(bucket, key)
        content = data.decode("utf-8") if isinstance(data, bytes) else str(data)
        return {"uri": uri, "content": content, "size": len(data) if data else 0}

    @mcp.tool()
    @audited(redact_keys)
    async def s3_put(uri: str, body: str) -> dict[str, Any]:
        """Write S3 object."""
        require_scope(SCOPE)
        parts = uri.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
        await server.object_put(bucket, key, body.encode())
        return {"uri": uri, "written": len(body)}

    @mcp.tool()
    @audited(redact_keys)
    async def s3_list(uri: str, limit: int = 100) -> dict[str, Any]:
        """List S3 objects under prefix."""
        require_scope(SCOPE)
        parts = uri.replace("s3://", "").split("/", 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        resp = await server.object_list(bucket, prefix, limit)
        return {"uri": uri, "keys": resp.get("keys", []), "count": resp.get("count", 0)}

    @mcp.tool()
    @audited(redact_keys)
    async def s3_delete(uri: str) -> dict[str, Any]:
        """Delete S3 object."""
        require_scope(SCOPE)
        parts = uri.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
        await server.object_delete(bucket, key)
        return {"status": "ok", "deleted": uri}

    # ── KV ──

    @mcp.tool()
    @audited(redact_keys)
    async def kv_get(key: str) -> dict[str, Any]:
        """Read Dragonfly KV."""
        require_scope(SCOPE)
        ctx = get_tenant()
        full_key = f"{ctx.tenant_id}:{key}"
        try:
            resp = await server.kv_get(full_key)
            return {"key": key, "value": resp.get("value")}
        except Exception:
            return {"key": key, "value": None}

    @mcp.tool()
    @audited(redact_keys)
    async def kv_set(key: str, value: str, ttl: int | None = None) -> dict[str, Any]:
        """Write Dragonfly KV."""
        require_scope(SCOPE)
        ctx = get_tenant()
        full_key = f"{ctx.tenant_id}:{key}"
        await server.kv_set(full_key, value, ttl)
        return {"key": key, "set": True}

    @mcp.tool()
    @audited(redact_keys)
    async def kv_delete(key: str) -> dict[str, Any]:
        """Delete Dragonfly KV."""
        require_scope(SCOPE)
        ctx = get_tenant()
        full_key = f"{ctx.tenant_id}:{key}"
        await server.kv_delete(full_key)
        return {"status": "ok", "deleted": key}

    @mcp.tool()
    @audited(redact_keys)
    async def kv_scan(pattern: str = "*", limit: int = 100) -> dict[str, Any]:
        """Scan Dragonfly KV keys."""
        require_scope(SCOPE)
        ctx = get_tenant()
        full_pattern = f"{ctx.tenant_id}:{pattern}"
        resp = await server.kv_scan(full_pattern, limit)
        return {"pattern": pattern, "keys": resp.get("keys", []), "count": resp.get("count", 0)}

    # ── Graph ──

    @mcp.tool()
    @audited(redact_keys)
    async def graph_query(concept: str | None = None, relation: str | None = None) -> dict[str, Any]:
        """Query graph nodes and edges. concept filters by label, relation filters edges by rel_type."""
        require_scope(SCOPE)
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        nodes_resp = await server.graph_query_nodes(graph, ctx.tenant_id, label=concept)
        nodes = nodes_resp.get("nodes", [])
        edges = []
        for n in nodes:
            edges_resp = await server.graph_query_edges(graph, n["node_id"], ctx.tenant_id)
            node_edges = edges_resp.get("edges", [])
            if relation:
                node_edges = [e for e in node_edges if e.get("rel_type") == relation]
            edges.extend(node_edges)
        return {"nodes": nodes, "edges": edges}

    @mcp.tool()
    @audited(redact_keys)
    async def graph_update(concept: str, relation: str, target: str) -> dict[str, Any]:
        """Add graph triple."""
        require_scope(SCOPE)
        import uuid
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        await server.graph_add_node(graph, concept, "Concept", {"name": concept}, ctx.tenant_id)
        await server.graph_add_node(graph, target, "Concept", {"name": target}, ctx.tenant_id)
        edge_id = f"e_{uuid.uuid4().hex[:8]}"
        await server.graph_add_edge(graph, edge_id, concept, target, relation, {}, ctx.tenant_id)
        return {"concept": concept, "relation": relation, "target": target}

    # ── Ray Jobs (Skill-based) ──

    @mcp.tool()
    @audited(redact_keys + ["env_overrides"])
    async def ray_submit_job(
        skill_uri: str,
        job_name: str,
        params: dict = {},
        task_id: str = "",
        env_overrides: dict = {},
        resources: dict = {},
    ) -> dict[str, Any]:
        """Submit a Skill-based Ray job. Server fetches code, reads ray.yaml, injects secrets."""
        require_scope(SCOPE)
        return await server.job_submit_skill(
            skill_uri=skill_uri,
            job_name=job_name,
            params=params,
            task_id=task_id,
            env_overrides=env_overrides,
            resources=resources,
        )

    @mcp.tool()
    @audited(redact_keys)
    async def ray_job_status(job_id: str) -> dict[str, Any]:
        """Query Ray job status."""
        require_scope(SCOPE)
        return await server.job_get(job_id)

    @mcp.tool()
    @audited(redact_keys)
    async def ray_job_result(job_id: str) -> dict[str, Any]:
        """Get Ray job result."""
        require_scope(SCOPE)
        return await server.job_result(job_id)

    @mcp.tool()
    @audited(redact_keys)
    async def ray_job_cancel(job_id: str) -> dict[str, Any]:
        """Cancel a Ray job."""
        require_scope(SCOPE)
        return await server.job_cancel(job_id)

    @mcp.tool()
    @audited(redact_keys)
    async def ray_job_list(status: str = "") -> dict[str, Any]:
        """List Ray jobs for current tenant."""
        require_scope(SCOPE)
        return await server.job_list(status)

    @mcp.tool()
    @audited(redact_keys)
    async def list_skill_jobs(skill_uri: str) -> dict[str, Any]:
        """List available job_names in a Skill package's jobs/ directory."""
        require_scope(SCOPE)
        return await server.skill_job_list(skill_uri)
