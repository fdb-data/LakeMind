from __future__ import annotations
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from fastapi import Request, HTTPException
from .config import SECRET_KEY, SERVER_URL, SERVER_KEY, TENANT_ID
import httpx


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_session_cookie(token: str) -> str:
    sig = hmac.new(SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()
    return f"{token}.{sig}"


def parse_session_cookie(cookie_val: str) -> str | None:
    if not cookie_val or "." not in cookie_val:
        return None
    token, sig = cookie_val.rsplit(".", 1)
    expected = hmac.new(SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return token


class AuthContext:
    def __init__(self, principal_id: str, tenant_id: str, token: str, roles: list[str], capabilities: list[str]):
        self.principal_id = principal_id
        self.tenant_id = tenant_id
        self.token = token
        self.roles = roles
        self.capabilities = capabilities

    @property
    def is_admin(self) -> bool:
        return "platform_admin" in self.roles or "tenant_admin" in self.roles


async def verify_token(token: str) -> AuthContext:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SERVER_URL}/api/v1/security/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="INVALID_TOKEN")
        data = resp.json()
        return AuthContext(
            principal_id=data["principal_id"],
            tenant_id=data["tenant_id"],
            token=token,
            roles=data.get("roles", []),
            capabilities=data.get("capabilities", []),
        )


async def get_auth_context(request: Request) -> AuthContext:
    cookie_val = request.cookies.get("session")
    if not cookie_val:
        raise HTTPException(status_code=401, detail="NOT_AUTHENTICATED")
    token = parse_session_cookie(cookie_val)
    if not token:
        raise HTTPException(status_code=401, detail="INVALID_SESSION")
    return await verify_token(token)


async def login_to_server(username: str, password: str) -> dict:
    password_hash = hash_password(password)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{SERVER_URL}/api/v1/security/auth/login",
            json={"username": username, "password_hash": password_hash},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="LOGIN_FAILED")
        return resp.json()


async def register_principal(username: str, password: str, display_name: str) -> dict:
    password_hash = hash_password(password)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{SERVER_URL}/api/v1/security/principals",
            headers={"Authorization": f"Bearer {SERVER_KEY}", "X-Tenant-Id": TENANT_ID},
            json={
                "username": username,
                "password_hash": password_hash,
                "display_name": display_name,
                "tenant_id": TENANT_ID,
                "role_name": "meeting_user",
            },
        )
        if resp.status_code == 409:
            raise HTTPException(status_code=409, detail="USERNAME_EXISTS")
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"REGISTER_FAILED: {resp.text}")
        return resp.json()
