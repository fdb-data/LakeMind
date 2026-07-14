from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from ..security.middleware import require_action, get_security_context
from ..services.authorization_service import AuthorizationService

router = APIRouter()


@router.post("/auth/login")
async def login_endpoint(request: Request):
    body = await request.json()
    try:
        result = AuthorizationService.login(
            username=body["username"],
            password_hash=body["password_hash"],
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"error": {"code": str(exc), "message": str(exc)}})


@router.post("/tokens")
async def issue_token_endpoint(request: Request):
    ctx = get_security_context(request)
    body = await request.json()
    result = AuthorizationService.issue_token(
        principal_id=body["principal_id"],
        tenant_id=body.get("tenant_id", ctx.tenant_id),
        scopes=body.get("scopes", []),
        expires_at=datetime.fromisoformat(body["expires_at"]) if body.get("expires_at") else None,
    )
    return result


@router.delete("/tokens/{token_id}")
async def revoke_token_endpoint(token_id: str, request: Request):
    ctx = get_security_context(request)
    return AuthorizationService.revoke_token(token_id, ctx)


@router.get("/tokens")
async def list_tokens_endpoint(request: Request):
    ctx = get_security_context(request)
    return AuthorizationService.list_tokens(ctx)


@router.get("/roles")
async def list_roles_endpoint():
    from ..db import execute
    return execute("SELECT role_id, name, permissions, is_builtin FROM roles ORDER BY name")


@router.get("/principals")
async def list_principals_endpoint(request: Request):
    ctx = get_security_context(request)
    from ..db import execute
    return {"items": execute(
        "SELECT principal_id, principal_type, tenant_id, status FROM principals "
        "WHERE tenant_id = %s ORDER BY principal_id",
        (ctx.tenant_id,),
    )}
