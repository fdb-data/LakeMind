from __future__ import annotations
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    engines = request.app.state.engines
    return engines.all_health()


@router.get("/nodes")
async def nodes(request: Request):
    return {
        "nodes": [
            {"name": "server-api", "status": "active", "port": 10823},
            {"name": "postgres", "status": "active"},
            {"name": "seaweedfs", "status": "active"},
            {"name": "valkey", "status": "active"},
        ]
    }


@router.get("/metrics")
async def metrics(request: Request):
    engines = request.app.state.engines
    health = engines.all_health()
    return {
        "engines": health,
        "healthy_count": sum(1 for v in health.values() if v),
        "total_count": len(health),
    }
