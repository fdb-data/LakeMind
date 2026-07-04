"""Ontology asset tools: query_ontology / update_ontology."""
from __future__ import annotations

import uuid
from typing import Any

from ..context import get_tenant
from ..engines import Engines
from ._helpers import audited, require_scope

SCOPE = "asset"


def register(mcp, engines: Engines, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def query_ontology(concept: str, relation: str | None = None) -> dict[str, Any]:
        """Query ontology: find concept and its relations."""
        require_scope(SCOPE)
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        nodes = engines.graph.query_nodes(graph, ctx.tenant_id, label=concept)
        if not nodes:
            nodes = engines.graph.query_nodes(graph, ctx.tenant_id)
        result = {"concept": concept, "nodes": nodes, "edges": []}
        for n in nodes:
            edges = engines.graph.query_edges(graph, n["node_id"], ctx.tenant_id)
            if relation:
                edges = [e for e in edges if e["rel_type"] == relation]
            result["edges"].extend(edges)
        return result

    @mcp.tool()
    @audited(redact_keys)
    async def update_ontology(
        concept: str,
        relation: str,
        target: str,
        concept_label: str = "Concept",
        target_label: str = "Concept",
    ) -> dict[str, Any]:
        """Add or update ontology triple: concept -[relation]-> target."""
        require_scope(SCOPE)
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        engines.graph.add_node(graph, concept, concept_label, {"name": concept}, ctx.tenant_id)
        engines.graph.add_node(graph, target, target_label, {"name": target}, ctx.tenant_id)
        edge_id = f"e_{uuid.uuid4().hex[:8]}"
        engines.graph.add_edge(graph, edge_id, concept, target, relation, {}, ctx.tenant_id)
        return {"concept": concept, "relation": relation, "target": target, "edge_id": edge_id}
