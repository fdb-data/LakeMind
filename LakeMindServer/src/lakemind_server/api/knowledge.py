from __future__ import annotations
from fastapi import APIRouter, Request, UploadFile, File, Form
from ..security.middleware import get_security_context
from ..security.actions import Action
from ..services.knowledge_service import KnowledgeService

router = APIRouter()


@router.post("/ingest")
async def ingest_knowledge(request: Request):
    ctx = get_security_context(request)
    if not ctx.has_scope(Action.ASSET_CREATE.value):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")
    body = await request.json()
    return KnowledgeService.ingest(ctx, **body)


@router.post("/search")
async def search_knowledge(request: Request):
    ctx = get_security_context(request)
    body = await request.json()
    return KnowledgeService.search(ctx, **body)


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: str, request: Request):
    ctx = get_security_context(request)
    return KnowledgeService.get_concept(ctx, concept_id)


@router.get("/concepts")
async def list_concepts(request: Request):
    ctx = get_security_context(request)
    params = request.query_params
    return KnowledgeService.list_concepts(
        ctx,
        page=int(params.get("page", "1")),
        page_size=int(params.get("page_size", "50")),
    )


@router.post("/reindex/{asset_id}")
async def reindex_knowledge(asset_id: str, request: Request):
    ctx = get_security_context(request)
    return KnowledgeService.reindex(ctx, asset_id)
