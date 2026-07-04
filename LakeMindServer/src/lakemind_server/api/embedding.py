from __future__ import annotations
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


def _eng(request: Request):
    return request.app.state.engines.embedding


class EmbedBody(BaseModel):
    texts: list[str]


@router.post("/embed")
async def embed(body: EmbedBody, request: Request):
    vectors = _eng(request).embed(body.texts)
    return {"vectors": vectors, "dim": _eng(request).dim, "count": len(vectors)}
