from __future__ import annotations
from fastapi import APIRouter, Request
from pydantic import BaseModel
from ..auth import get_tenant_context

router = APIRouter()


def _eng(request: Request):
    return request.app.state.engines.memory


class RememberBody(BaseModel):
    content: str
    context: str | None = None
    ttl: int | None = None
    kind: str = "general"


class RecallBody(BaseModel):
    query: str
    limit: int = 5
    kind: str | None = None


class ForgetBody(BaseModel):
    query: str | None = None


@router.post("/remember")
async def remember(body: RememberBody, request: Request):
    ctx = get_tenant_context(request)
    return _eng(request).remember(ctx["agent_id"], ctx["tenant_id"],
                                  body.content, body.context, body.ttl, body.kind)


@router.post("/recall")
async def recall(body: RecallBody, request: Request):
    ctx = get_tenant_context(request)
    results = _eng(request).recall(ctx["agent_id"], ctx["tenant_id"],
                                   body.query, body.limit, body.kind)
    return {"results": results, "count": len(results)}


@router.post("/forget")
async def forget(body: ForgetBody, request: Request):
    ctx = get_tenant_context(request)
    return _eng(request).forget(ctx["agent_id"], ctx["tenant_id"], body.query)
