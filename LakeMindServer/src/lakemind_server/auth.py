from __future__ import annotations
from fastapi import Request, HTTPException
from .config import ServerConfig


async def verify_api_key(request: Request, cfg: ServerConfig):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth[7:]
    if token != cfg.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def get_tenant_context(request: Request) -> dict[str, str]:
    return {
        "tenant_id": request.headers.get("X-Tenant-Id", "default"),
        "agent_id": request.headers.get("X-Agent-Id", "unknown"),
        "scopes": request.headers.get("X-Scopes", "").split(","),
    }
