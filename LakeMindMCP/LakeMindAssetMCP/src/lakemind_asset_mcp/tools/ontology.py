"""Ontology asset tools: query_ontology / update_ontology."""
from __future__ import annotations

import uuid
from typing import Any

from ..context import get_tenant
from ..server_client import ServerClient
from ._helpers import audited, require_scope

SCOPE = "asset"


def register(mcp, server: ServerClient, redact_keys: list[str]) -> None:
    @mcp.tool()
    @audited(redact_keys)
    async def query_ontology(concept: str, relation: str | None = None) -> dict[str, Any]:
        """Query ontology: find concept and its relations."""
        require_scope(SCOPE)
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        nodes_resp = await server.graph_query_nodes(graph, ctx.tenant_id, label=concept)
        nodes = nodes_resp.get("nodes", [])
        if not nodes:
            nodes_resp = await server.graph_query_nodes(graph, ctx.tenant_id)
            nodes = nodes_resp.get("nodes", [])
        result = {"concept": concept, "nodes": nodes, "edges": []}
        for n in nodes:
            edges_resp = await server.graph_query_edges(graph, n["node_id"], ctx.tenant_id)
            edges = edges_resp.get("edges", [])
            if relation:
                edges = [e for e in edges if e.get("rel_type") == relation]
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
        await server.graph_add_node(graph, concept, concept_label, {"name": concept}, ctx.tenant_id)
        await server.graph_add_node(graph, target, target_label, {"name": target}, ctx.tenant_id)
        edge_id = f"e_{uuid.uuid4().hex[:8]}"
        await server.graph_add_edge(graph, edge_id, concept, target, relation, {}, ctx.tenant_id)
        return {"concept": concept, "relation": relation, "target": target, "edge_id": edge_id}

    @mcp.tool()
    @audited(redact_keys)
    async def delete_ontology(concept: str) -> dict[str, Any]:
        """删除概念节点及其关联边。"""
        require_scope(SCOPE)
        ctx = get_tenant()
        graph = f"ontology_{ctx.tenant_id}"
        await server.graph_delete_node(graph, concept, ctx.tenant_id)
        return {"status": "ok", "deleted": concept}
