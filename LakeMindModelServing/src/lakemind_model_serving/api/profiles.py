from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from ..auth import check_auth

router = APIRouter()


class CreateProfileRequest(BaseModel):
    name: str
    model_type: str
    model_id: str
    fallback_model_id: str | None = None
    tenant_id: str | None = None
    description: str | None = None


@router.get("/v1/profiles")
async def list_profiles(request: Request):
    check_auth(request)
    registry = request.app.state.registry
    return {"data": registry.list_profiles()}


@router.post("/v1/profiles")
async def create_profile(body: CreateProfileRequest, request: Request):
    check_auth(request)
    registry = request.app.state.registry
    try:
        return registry.create_profile(**body.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/v1/profiles/{profile_id}")
async def update_profile(profile_id: str, request: Request):
    check_auth(request)
    registry = request.app.state.registry
    body = await request.json()
    try:
        return registry.update_profile(profile_id, **body)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/v1/profiles/{profile_id}")
async def delete_profile(profile_id: str, request: Request):
    check_auth(request)
    registry = request.app.state.registry
    try:
        return registry.delete_profile(profile_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/v1/profiles/{name}/resolve")
async def resolve_profile(name: str, request: Request):
    check_auth(request)
    registry = request.app.state.registry
    result = registry.resolve_profile(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found or model disabled")
    return result
