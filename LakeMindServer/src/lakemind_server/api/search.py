from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from ..security.middleware import get_security_context
from ..services.search_service import SearchService

router = APIRouter()


@router.get("")
async def search(request: Request):
    ctx = get_security_context(request)
    params = request.query_params
    q = params.get("q", "").strip()
    if not q:
        return {"items": [], "total": 0, "page": 1, "page_size": 20, "groups": {}}
    object_types = params.get("type", "").split(",") if params.get("type") else None
    object_types = [t.strip() for t in object_types if t.strip()] if object_types else None
    page = int(params.get("page", "1"))
    page_size = int(params.get("page_size", "20"))
    scope_filter = ctx.accessible_scope_filter()
    return SearchService.search(
        q=q,
        object_types=object_types,
        scope_type=scope_filter.get("scope_type"),
        scope_id=scope_filter.get("scope_id"),
        platform_admin=ctx.is_platform_admin,
        page=page, page_size=page_size,
    )
