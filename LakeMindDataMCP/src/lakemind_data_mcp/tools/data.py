"""Data face transparent passthrough tools."""
from __future__ import annotations
from typing import Any
import pyarrow as pa
from ..context import get_tenant
from ..engines import Engines
from ._helpers import audited, require_scope

SCOPE = "data"

def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def data_query(table: str, columns: str | None = None, filter: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Scan Iceberg table. columns: comma-separated, filter: SQL expression."""
        require_scope(SCOPE)
        ctx = get_tenant()
        domain = "data"
        result = engines.iceberg.scan(ctx, domain, table)
        if columns:
            cols = [c.strip() for c in columns.split(",")]
            result = result.select(cols)
        data = result.slice(0, limit).to_pylist()
        return {"table": table, "rows": data, "count": len(data)}

    @mcp.tool()
    @audited(redact_keys)
    async def data_write(table: str, rows: list[dict], mode: str = "append") -> dict[str, Any]:
        """Write to Iceberg table. mode: append|overwrite."""
        require_scope(SCOPE)
        ctx = get_tenant()
        if not rows:
            return {"table": table, "written": 0}
        data = pa.table(rows)
        if mode == "overwrite":
            n = engines.iceberg.overwrite(ctx, "data", table, data)
        else:
            n = engines.iceberg.append(ctx, "data", table, data)
        return {"table": table, "written": n, "mode": mode}

    @mcp.tool()
    @audited(redact_keys)
    async def data_sql(sql: str) -> dict[str, Any]:
        """Execute ad-hoc SQL via DuckDB."""
        require_scope(SCOPE)
        result = engines.duckdb(sql)
        return {"sql": sql, "rows": result.to_pylist(), "count": result.num_rows}

    @mcp.tool()
    @audited(redact_keys)
    async def data_list_tables(namespace: str | None = None) -> dict[str, Any]:
        """List Iceberg tables."""
        require_scope(SCOPE)
        ctx = get_tenant()
        domain = namespace or "data"
        tables = engines.iceberg.list_tables(ctx, domain)
        return {"namespace": domain, "tables": tables}

    @mcp.tool()
    @audited(redact_keys)
    async def data_describe(table: str) -> dict[str, Any]:
        """Describe Iceberg table schema."""
        require_scope(SCOPE)
        ctx = get_tenant()
        return engines.iceberg.describe(ctx, "data", table)

    @mcp.tool()
    @audited(redact_keys)
    async def data_create_table(name: str, schema: dict[str, str], partition: str | None = None) -> dict[str, Any]:
        """Create Iceberg table. schema: {column: type}."""
        require_scope(SCOPE)
        ctx = get_tenant()
        type_map = {"string": pa.string(), "int64": pa.int64(), "int32": pa.int32(), "float64": pa.float64(), "float32": pa.float32(), "bool": pa.bool_(), "timestamp": pa.timestamp("us")}
        fields = [pa.field(col, type_map.get(t, pa.string())) for col, t in schema.items()]
        engines.iceberg.create_table_from_arrow(ctx, "data", name, pa.schema(fields))
        return {"table": name, "columns": list(schema.keys())}

    @mcp.tool()
    @audited(redact_keys)
    async def lance_query(table: str, query: str, top_k: int = 5, filter: str | None = None) -> dict[str, Any]:
        """Vector search via LanceDB."""
        require_scope(SCOPE)
        ctx = get_tenant()
        qvec = engines.embedding.embed([query])[0]
        hits = engines.lancedb.search(ctx, table, qvec, top_k, filter)
        return {"table": table, "hits": hits, "count": len(hits)}

    @mcp.tool()
    @audited(redact_keys)
    async def s3_get(uri: str) -> dict[str, Any]:
        """Read S3 object."""
        require_scope(SCOPE)
        parts = uri.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
        data = engines.s3.get(bucket, key)
        return {"uri": uri, "size": len(data) if data else 0}

    @mcp.tool()
    @audited(redact_keys)
    async def s3_put(uri: str, body: str) -> dict[str, Any]:
        """Write S3 object."""
        require_scope(SCOPE)
        parts = uri.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
        engines.s3.put(bucket, key, body)
        return {"uri": uri, "written": len(body)}

    @mcp.tool()
    @audited(redact_keys)
    async def kv_get(key: str) -> dict[str, Any]:
        """Read Dragonfly KV."""
        require_scope(SCOPE)
        ctx = get_tenant()
        val = engines.dragonfly.recall(ctx, f"{ctx.tenant_id}:{key}")
        return {"key": key, "value": val}

    @mcp.tool()
    @audited(redact_keys)
    async def kv_set(key: str, value: str, ttl: int | None = None) -> dict[str, Any]:
        """Write Dragonfly KV."""
        require_scope(SCOPE)
        ctx = get_tenant()
        engines.dragonfly.remember(ctx, f"{ctx.tenant_id}:{key}", value, ttl)
        return {"key": key, "set": True}

    @mcp.tool()
    @audited(redact_keys)
    async def graph_query(concept: str, relation: str | None = None) -> dict[str, Any]:
        """Query graph nodes and edges."""
        require_scope(SCOPE)
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        nodes = engines.graph.query_nodes(graph, ctx.tenant_id)
        edges = []
        for n in nodes:
            edges.extend(engines.graph.query_edges(graph, n["node_id"], ctx.tenant_id))
        return {"nodes": nodes, "edges": edges}

    @mcp.tool()
    @audited(redact_keys)
    async def graph_update(concept: str, relation: str, target: str) -> dict[str, Any]:
        """Add graph triple."""
        require_scope(SCOPE)
        import uuid
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        engines.graph.add_node(graph, concept, "Concept", {"name": concept}, ctx.tenant_id)
        engines.graph.add_node(graph, target, "Concept", {"name": target}, ctx.tenant_id)
        edge_id = f"e_{uuid.uuid4().hex[:8]}"
        engines.graph.add_edge(graph, edge_id, concept, target, relation, {}, ctx.tenant_id)
        return {"concept": concept, "relation": relation, "target": target}
