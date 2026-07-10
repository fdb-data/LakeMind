from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from ..auth import check_auth

router = APIRouter()


class RegisterModelRequest(BaseModel):
    model_id: str
    type: str = "llm"
    provider: str = "openai"
    litellm_model: str = ""
    api_key: str = ""
    base_url: str = ""
    tags: list[str] = []
    context_window: int = 0
    dim: int = 0
    priority: int = 99


@router.get("/v1/models")
async def list_models(request: Request):
    check_auth(request)
    gateway = request.app.state.gateway
    embedding_service = request.app.state.embedding_service
    asr_service = getattr(request.app.state, "asr_service", None)

    models = gateway.list_models()

    if embedding_service:
        models.append({
            "id": embedding_service.model_name,
            "type": "embedding",
            "provider": "fastembed",
            "tags": ["embed"],
            "dim": embedding_service.dim,
        })
        models.append({
            "id": "jina-embeddings-v2-base-zh",
            "type": "embedding",
            "provider": "fastembed",
            "tags": ["embed"],
            "dim": embedding_service.dim,
        })

    if asr_service:
        models.append({
            "id": asr_service.model_name,
            "type": "asr",
            "provider": "funasr",
            "tags": ["asr"],
        })
        models.append({
            "id": "sensevoice-small",
            "type": "asr",
            "provider": "funasr",
            "tags": ["asr"],
        })

    seen = set()
    unique = []
    for m in models:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)

    return {"object": "list", "data": unique}


@router.get("/v1/models/types")
async def list_model_types(request: Request):
    check_auth(request)
    return {"types": ["llm", "embedding", "asr"]}


@router.get("/v1/models/{model_id}")
async def get_model(model_id: str, request: Request):
    check_auth(request)
    registry = request.app.state.registry
    info = registry.get(model_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return info


@router.post("/v1/models/register")
async def register_model(body: RegisterModelRequest, request: Request):
    check_auth(request)
    gateway = request.app.state.gateway
    registry = request.app.state.registry

    model_config = body.model_dump()
    litellm_model = model_config.get("litellm_model") or f"{body.provider}/{body.model_id}"

    ok = registry.register(
        model_id=body.model_id,
        model_type=body.type,
        provider=body.provider,
        litellm_model=litellm_model,
        api_key=body.api_key,
        base_url=body.base_url,
        tags=body.tags,
        context_window=body.context_window,
        dim=body.dim,
        priority=body.priority,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to persist model registration")

    if body.type == "llm":
        ok = gateway.register_model({
            "model_id": body.model_id,
            "type": body.type,
            "provider": body.provider,
            "litellm_model": litellm_model,
            "api_key": body.api_key,
            "base_url": body.base_url,
            "tags": body.tags,
            "context_window": body.context_window,
        })
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to load model into gateway")

    return {"status": "ok", "model_id": body.model_id}


@router.delete("/v1/models/{model_id}")
async def deregister_model(model_id: str, request: Request):
    check_auth(request)
    gateway = request.app.state.gateway
    registry = request.app.state.registry

    ok = registry.deregister(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found in registry")

    gateway.deregister_model(model_id)
    return {"status": "ok", "deleted": model_id}
