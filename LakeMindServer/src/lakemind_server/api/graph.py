from __future__ import annotations
import asyncio
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import uuid

router = APIRouter()


def _eng(request: Request):
    return request.app.state.engines.graph


class AddNodeBody(BaseModel):
    node_id: str | None = None
    label: str
    properties: dict = {}
    tenant_id: str = "default"


class AddEdgeBody(BaseModel):
    edge_id: str | None = None
    src: str
    dst: str
    rel: str
    properties: dict = {}
    tenant_id: str = "default"


@router.post("/{graph}/nodes")
async def add_node(graph: str, body: AddNodeBody, request: Request):
    nid = body.node_id or f"n_{uuid.uuid4().hex[:8]}"
    await asyncio.to_thread(_eng(request).add_node, graph, nid, body.label, body.properties, body.tenant_id)
    return {"status": "ok", "node_id": nid}


@router.post("/{graph}/edges")
async def add_edge(graph: str, body: AddEdgeBody, request: Request):
    eid = body.edge_id or f"e_{uuid.uuid4().hex[:8]}"
    await asyncio.to_thread(_eng(request).add_edge, graph, eid, body.src, body.dst, body.rel, body.properties, body.tenant_id)
    return {"status": "ok", "edge_id": eid}


@router.get("/{graph}/nodes")
async def query_nodes(graph: str, request: Request, tenant_id: str = "default", label: str | None = None):
    nodes = await asyncio.to_thread(_eng(request).query_nodes, graph, tenant_id, label)
    return {"nodes": nodes, "count": len(nodes)}


@router.get("/{graph}/edges")
async def query_edges(graph: str, request: Request, src: str, tenant_id: str = "default"):
    edges = await asyncio.to_thread(_eng(request).query_edges, graph, src, tenant_id)
    return {"edges": edges, "count": len(edges)}


@router.delete("/{graph}/nodes/{node_id}")
async def delete_node(graph: str, node_id: str, request: Request, tenant_id: str = "default"):
    await asyncio.to_thread(_eng(request).delete_node, graph, node_id, tenant_id)
    return {"status": "ok"}
