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
    @mcp.tool()
    @audited(redact_keys)
    async def data_query(table: str, columns: str | None = None, filter: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Scan Iceberg table. columns: comma-separated, filter: SQL expression."""
        require_scope(SCOPE)
        ctx = get_tenant()
        ns = _iceberg_ns(ctx.tenant_id, "data")
        resp = await server.table_scan(ns, table, columns=columns, filter=filter, limit=limit)
        return {"table": table, "rows": resp.get("rows", []), "count": resp.get("count", 0)}

    @mcp.tool()
    @audited(redact_keys)
    async def data_write(table: str, rows: list[dict], mode: str = "append") -> dict[str, Any]:
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
    async def data_sql(sql: str) -> dict[str, Any]:
        """Execute ad-hoc SQL via DuckDB."""
        require_scope(SCOPE)
        resp = await server.sql_execute(sql)
        return {"sql": sql, "rows": resp.get("results", []), "count": resp.get("count", 0)}

    @mcp.tool()
    @audited(redact_keys)
    async def data_list_tables(namespace: str | None = None) -> dict[str, Any]:
        """List Iceberg tables."""
        require_scope(SCOPE)
        ctx = get_tenant()
        domain = namespace or "data"
        ns = _iceberg_ns(ctx.tenant_id, domain)
        resp = await server.table_list(ns)
        return {"namespace": domain, "tables": resp.get("tables", [])}

    @mcp.tool()
    @audited(redact_keys)
    async def data_describe(table: str) -> dict[str, Any]:
        """Describe Iceberg table schema."""
        require_scope(SCOPE)
        ctx = get_tenant()
        ns = _iceberg_ns(ctx.tenant_id, "data")
        return await server.table_describe(ns, table)

    @mcp.tool()
    @audited(redact_keys)
    async def data_create_table(name: str, schema: dict[str, str], partition: str | None = None) -> dict[str, Any]:
        """Create Iceberg table. schema: {column: type}."""
        require_scope(SCOPE)
        ctx = get_tenant()
        ns = _iceberg_ns(ctx.tenant_id, "data")
        await server.table_create(ns, name, schema)
        return {"table": name, "columns": list(schema.keys())}

    @mcp.tool()
    @audited(redact_keys)
    async def lance_query(table: str, query: str, top_k: int = 5, filter: str | None = None) -> dict[str, Any]:
        """Vector search via LanceDB."""
        require_scope(SCOPE)
        ctx = get_tenant()
        db = _vec_db(ctx.tenant_id)
        embed_resp = await server.embed([query])
        qvec = embed_resp["vectors"][0]
        resp = await server.vector_search(db, table, qvec, top_k, filter)
        hits = resp.get("results", [])
        return {"table": table, "hits": hits, "count": len(hits)}

    @mcp.tool()
    @audited(redact_keys)
    async def s3_get(uri: str) -> dict[str, Any]:
        """Read S3 object."""
        require_scope(SCOPE)
        parts = uri.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
        data = await server.object_get(bucket, key)
        return {"uri": uri, "size": len(data) if data else 0}

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
    async def graph_query(concept: str, relation: str | None = None) -> dict[str, Any]:
        """Query graph nodes and edges."""
        require_scope(SCOPE)
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        nodes_resp = await server.graph_query_nodes(graph, ctx.tenant_id)
        nodes = nodes_resp.get("nodes", [])
        edges = []
        for n in nodes:
            edges_resp = await server.graph_query_edges(graph, n["node_id"], ctx.tenant_id)
            edges.extend(edges_resp.get("edges", []))
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
