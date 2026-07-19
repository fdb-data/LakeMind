from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from ..auth import check_auth

router = APIRouter()


class EmbeddingRequest(BaseModel):
    model: str = "jina-embeddings-v2-base-zh"
    input: list[str]


@router.post("/v1/embeddings")
async def create_embeddings(body: EmbeddingRequest, request: Request):
    check_auth(request)
    registry = request.app.state.registry
    embedding_mgr = getattr(request.app.state, "embedding_mgr", None)
    gateway = request.app.state.gateway

    target_model = body.model
    resolved = registry.resolve_profile(body.model)
    if resolved:
        target_model = resolved["model_name"]

    if embedding_mgr and target_model in embedding_mgr.list_registered():
        try:
            vectors, dim = embedding_mgr.embed(body.input, target_model)
            data = [{"embedding": v, "index": i} for i, v in enumerate(vectors)]
            return {
                "object": "list",
                "model": target_model,
                "data": data,
                "usage": {"prompt_tokens": sum(len(t.split()) for t in body.input),
                          "total_tokens": sum(len(t.split()) for t in body.input)},
            }
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
    else:
        try:
            return gateway.embed(body.input, model=target_model)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
