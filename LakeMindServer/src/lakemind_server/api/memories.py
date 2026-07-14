from __future__ import annotations
from fastapi import APIRouter, Request
from ..security.middleware import get_security_context
from ..security.actions import Action
from ..services.memory_service import MemoryService

router = APIRouter()


@router.post("/add")
async def add_memory(request: Request):
    ctx = get_security_context(request)
    if not ctx.has_scope(Action.ASSET_CREATE.value):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")
    body = await request.json()
    return MemoryService.add(ctx, **body)


@router.post("/search")
async def search_memory(request: Request):
    ctx = get_security_context(request)
    body = await request.json()
    return MemoryService.search(ctx, **body)


@router.get("/{memory_id}")
async def get_memory(memory_id: str, request: Request):
    ctx = get_security_context(request)
    return MemoryService.get(ctx, memory_id)


@router.get("")
async def list_memories(request: Request):
    ctx = get_security_context(request)
    params = request.query_params
    return MemoryService.list(
        ctx,
        page=int(params.get("page", "1")),
        page_size=int(params.get("page_size", "50")),
    )


@router.patch("/{memory_id}")
async def update_memory(memory_id: str, request: Request):
    ctx = get_security_context(request)
    body = await request.json()
    return MemoryService.update(ctx, memory_id, **body)


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, request: Request):
    ctx = get_security_context(request)
    return MemoryService.delete(ctx, memory_id)


@router.delete("")
async def clear_memories(request: Request):
    ctx = get_security_context(request)
    return MemoryService.clear(ctx)


@router.get("/{memory_id}/history")
async def memory_history(memory_id: str, request: Request):
    ctx = get_security_context(request)
    return MemoryService.history(ctx, memory_id)
