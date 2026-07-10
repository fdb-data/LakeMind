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
    embedding_service = request.app.state.embedding_service
    gateway = request.app.state.gateway

    if body.model == embedding_service.model_name or body.model == "jina-embeddings-v2-base-zh":
        try:
            vectors = embedding_service.embed(body.input)
            data = [{"embedding": v, "index": i} for i, v in enumerate(vectors)]
            return {
                "object": "list",
                "model": embedding_service.model_name,
                "data": data,
                "usage": {"prompt_tokens": sum(len(t.split()) for t in body.input), "total_tokens": sum(len(t.split()) for t in body.input)},
            }
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
    else:
        try:
            return gateway.embed(body.input, model=body.model)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
