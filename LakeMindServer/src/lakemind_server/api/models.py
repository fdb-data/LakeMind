from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from ..security.middleware import get_security_context
from ..security.actions import Action
from ..services.model_management_service import ModelManagementService

router = APIRouter()


def _check_perm(ctx, action: str) -> None:
    if not ctx.has_scope(action):
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")


@router.post("/definitions")
async def create_model(request: Request):
    ctx = get_security_context(request)
    _check_perm(ctx, Action.MODEL_CONFIGURE.value)
    body = await request.json()
    return ModelManagementService.create_model(**body)


@router.get("/definitions")
async def list_models(request: Request):
    ctx = get_security_context(request)
    params = request.query_params
    return ModelManagementService.list_models(params.get("type"))


@router.post("/deployments")
async def create_deployment(request: Request):
    ctx = get_security_context(request)
    _check_perm(ctx, Action.MODEL_CONFIGURE.value)
    body = await request.json()
    return ModelManagementService.create_deployment(**body)


@router.get("/deployments")
async def list_deployments(request: Request):
    ctx = get_security_context(request)
    params = request.query_params
    return ModelManagementService.list_deployments(params.get("model_id"))


@router.post("/deployments/{deployment_id}/enable")
async def enable_deployment(deployment_id: str, request: Request):
    ctx = get_security_context(request)
    _check_perm(ctx, Action.MODEL_CONFIGURE.value)
    return ModelManagementService.enable_deployment(ctx, deployment_id)


@router.post("/deployments/{deployment_id}/disable")
async def disable_deployment(deployment_id: str, request: Request):
    ctx = get_security_context(request)
    _check_perm(ctx, Action.MODEL_CONFIGURE.value)
    return ModelManagementService.disable_deployment(ctx, deployment_id)


@router.post("/profiles")
async def create_profile(request: Request):
    ctx = get_security_context(request)
    _check_perm(ctx, Action.MODEL_CONFIGURE.value)
    body = await request.json()
    return ModelManagementService.create_profile(**body)


@router.get("/profiles")
async def list_profiles(request: Request):
    ctx = get_security_context(request)
    return ModelManagementService.list_profiles()


@router.get("/routes")
async def list_routes(request: Request):
    ctx = get_security_context(request)
    params = request.query_params
    return ModelManagementService.list_routes(params.get("profile_name"))


@router.post("/profiles/resolve")
async def resolve_profile(request: Request):
    ctx = get_security_context(request)
    body = await request.json()
    return ModelManagementService.resolve_profile(body["profile_name"], ctx.tenant_id)
