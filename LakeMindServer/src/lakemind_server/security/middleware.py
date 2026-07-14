from __future__ import annotations
import os
import uuid
from fastapi import Request, HTTPException
from .context import SecurityContext
from .token_parser import parse_token


PUBLIC_PATHS = {"/api/v1/health", "/api/v1/system/health", "/api/v1/security/auth/login", "/docs", "/openapi.json", "/redoc"}


async def security_middleware(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or not path.startswith("/api/v1/"):
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"error": {"code": "AUTHENTICATION_FAILED", "message": "Missing or invalid Authorization header", "request_id": str(uuid.uuid4())}})

    token = auth[7:]
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    correlation_id = request.headers.get("X-Correlation-Id")

    try:
        ctx = parse_token(token, request_id, correlation_id)
    except ValueError as exc:
        from fastapi.responses import JSONResponse
        code = str(exc) if str(exc) != "AUTHENTICATION_FAILED" else "AUTHENTICATION_FAILED"
        status = 401 if code in ("AUTHENTICATION_FAILED", "TOKEN_REVOKED", "TOKEN_EXPIRED", "PRINCIPAL_DISABLED") else 401
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": code, "request_id": request_id}})

    request.state.security_context = ctx
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    if correlation_id:
        response.headers["X-Correlation-Id"] = correlation_id
    return response


def get_security_context(request: Request) -> SecurityContext:
    ctx = getattr(request.state, "security_context", None)
    if ctx is None:
        raise HTTPException(status_code=401, detail="No security context")
    return ctx


from fastapi import Depends

def require_action(action: str):
    async def dependency(request: Request) -> SecurityContext:
        ctx = get_security_context(request)
        if not ctx.has_scope(action):
            raise HTTPException(status_code=403, detail={"error": {"code": "PERMISSION_DENIED", "message": f"Missing scope: {action}", "request_id": ctx.request_id}})
        return ctx
    return dependency
