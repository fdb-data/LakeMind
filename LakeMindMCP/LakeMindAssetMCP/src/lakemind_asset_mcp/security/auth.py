"""Bearer Token 认证中间件。

仅对 MCP 端点路径（默认 ``/mcp``）强制认证；其余路径（如 ``/health``）放行。
认证成功后把 :class:`~lakemind_asset_mcp.context.Identity` 写入 ContextVar，
供下游 handler 读取。
"""
from __future__ import annotations

from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..config import Config
from ..context import Identity, current_identity

__all__ = ["AuthMiddleware"]


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config: Config, mcp_path: str = "/mcp") -> None:
        super().__init__(app)
        self._token_map = config.token_map()
        self._mcp_path = mcp_path

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # 非 MCP 端点放行（健康检查等）
        if not request.url.path.startswith(self._mcp_path):
            return await call_next(request)

        token = _extract_bearer(request)
        if token is None:
            return _unauthorized("missing or malformed Authorization header")

        ident_raw = self._token_map.get(token)
        if ident_raw is None:
            return _unauthorized("invalid token")

        identity = Identity.from_token(ident_raw)
        # 写入 ContextVar，下游 handler / 引擎适配层据此做租户隔离
        current_identity.set(identity)
        return await call_next(request)


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse({"error": "unauthorized", "detail": detail}, status_code=401)
