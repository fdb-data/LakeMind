from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from ..auth import get_tenant_context

router = APIRouter()


def _eng(request: Request):
    return request.app.state.engines.memory


class AddBody(BaseModel):
    messages: list[dict]
    metadata: dict | None = None
    infer: bool = True
    expiration_date: str | None = None
    run_id: str | None = None


class SearchBody(BaseModel):
    query: str
    filters: dict | None = None
    top_k: int = 10
    threshold: float = 0.1
    run_id: str | None = None


class UpdateBody(BaseModel):
    content: str


class ListBody(BaseModel):
    filters: dict | None = None
    page: int = 1
    page_size: int = 50
    run_id: str | None = None


class ClearBody(BaseModel):
    filters: dict | None = None
    run_id: str | None = None


@router.post("/add")
async def add_memory(body: AddBody, request: Request):
    ctx = get_tenant_context(request)
    return _eng(request).add(ctx["agent_id"], ctx["tenant_id"], body.messages,
                             body.metadata, body.infer, body.expiration_date, body.run_id)


@router.post("/search")
async def search_memory(body: SearchBody, request: Request):
    ctx = get_tenant_context(request)
    results = _eng(request).search(ctx["agent_id"], ctx["tenant_id"], body.query,
                                   body.filters, body.top_k, body.threshold, body.run_id)
    return {"results": results, "count": len(results)}


@router.get("/{memory_id}")
async def get_memory(memory_id: str, request: Request):
    ctx = get_tenant_context(request)
    result = _eng(request).get(ctx["agent_id"], ctx["tenant_id"], memory_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return result


@router.post("/list")
async def list_memory(body: ListBody, request: Request):
    ctx = get_tenant_context(request)
    return _eng(request).list_all(ctx["agent_id"], ctx["tenant_id"], body.filters,
                                  body.page, body.page_size, body.run_id)


@router.put("/{memory_id}")
async def update_memory(memory_id: str, body: UpdateBody, request: Request):
    ctx = get_tenant_context(request)
    return _eng(request).update(ctx["agent_id"], ctx["tenant_id"], memory_id, body.content)


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, request: Request):
    ctx = get_tenant_context(request)
    return _eng(request).delete(ctx["agent_id"], ctx["tenant_id"], memory_id)


@router.post("/clear")
async def clear_memory(body: ClearBody, request: Request):
    ctx = get_tenant_context(request)
    return _eng(request).clear(ctx["agent_id"], ctx["tenant_id"], body.filters, body.run_id)


@router.get("/{memory_id}/history")
async def memory_history(memory_id: str, request: Request):
    ctx = get_tenant_context(request)
    results = _eng(request).history(ctx["agent_id"], ctx["tenant_id"], memory_id)
    return {"results": results, "count": len(results)}
