from __future__ import annotations
from fastapi import APIRouter, Request, UploadFile, File
from ..security.middleware import get_security_context, require_action
from ..services.asset_service import AssetService
from ..security.actions import Action

router = APIRouter()


@router.post("")
async def create_asset(request: Request):
    ctx = get_security_context(request)
    if not ctx.has_scope(Action.ASSET_CREATE.value):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")
    body = await request.json()
    return AssetService.create_asset(ctx, **body)


@router.get("")
async def list_assets(request: Request):
    ctx = get_security_context(request)
    params = request.query_params
    return AssetService.list_assets(
        ctx,
        asset_type=params.get("type"),
        status=params.get("status"),
        page=int(params.get("page", "1")),
    )


@router.get("/{asset_id}")
async def get_asset(asset_id: str, request: Request):
    ctx = get_security_context(request)
    return AssetService.get_asset(ctx, asset_id)


@router.patch("/{asset_id}")
async def update_asset(asset_id: str, request: Request):
    ctx = get_security_context(request)
    body = await request.json()
    return AssetService.update_asset(ctx, asset_id, body.get("metadata", {}))


@router.delete("/{asset_id}")
async def delete_asset(asset_id: str, request: Request):
    ctx = get_security_context(request)
    return AssetService.delete_asset(ctx, asset_id)


@router.get("/{asset_id}/bindings")
async def get_bindings(asset_id: str):
    return AssetService.get_bindings(asset_id)


@router.get("/{asset_id}/lineage")
async def get_lineage(asset_id: str):
    return AssetService.get_lineage(asset_id)


@router.post("/{asset_id}/reindex")
async def reindex_asset(asset_id: str, request: Request):
    ctx = get_security_context(request)
    return AssetService.reindex(ctx, asset_id)
