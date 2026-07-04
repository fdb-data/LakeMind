"""Ontology asset resources: lake://ontology."""
from __future__ import annotations

from ..context import get_tenant
from ..engines import Engines


def register(mcp, engines: Engines) -> None:
    @mcp.resource("lake://ontology")
    def list_ontology() -> list[dict]:
        """List available ontology graphs for current tenant."""
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        nodes = engines.graph.query_nodes(graph, ctx.tenant_id)
        return [{"graph": graph, "node_count": len(nodes), "nodes": nodes[:20]}]
