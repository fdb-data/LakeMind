from __future__ import annotations
import hashlib
import json
import secrets as pysecrets
import ulid
from datetime import datetime, timezone
from ..db import execute, execute_one
from .context import SecurityContext


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _ulid(prefix: str) -> str:
    return f"{prefix}_{str(ulid.new())}"


def issue_token(principal_id: str, tenant_id: str, scopes: list[str],
                expires_at: datetime | None = None) -> dict:
    token_plain = pysecrets.token_urlsafe(32)
    token_hash = _hash_token(token_plain)
    token_id = _ulid("tok")
    jti = _ulid("jti")
    p_row = execute_one("SELECT security_version FROM principals WHERE principal_id = %s", (principal_id,))
    security_version = p_row["security_version"] if p_row else 0
    execute(
        "INSERT INTO v2_tokens (token_id, principal_id, tenant_id, token_hash, scopes, expires_at, security_version, jti) "
        "VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)",
        (token_id, principal_id, tenant_id, token_hash, json.dumps(scopes), expires_at, security_version, jti),
    )
    return {
        "token_id": token_id,
        "token": token_plain,
        "principal_id": principal_id,
        "tenant_id": tenant_id,
        "scopes": scopes,
        "security_version": security_version,
        "jti": jti,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


def revoke_token(token_id: str) -> dict:
    rows = execute(
        "UPDATE v2_tokens SET revoked_at = %s WHERE token_id = %s AND revoked_at IS NULL "
        "RETURNING token_id, principal_id",
        (datetime.now(timezone.utc), token_id),
    )
    if not rows:
        return {"token_id": token_id, "revoked": False}
    return {"token_id": token_id, "revoked": True}


def list_tokens(tenant_id: str | None = None, principal_id: str | None = None) -> list[dict]:
    query = "SELECT token_id, principal_id, tenant_id, scopes, expires_at, revoked_at, created_at FROM v2_tokens WHERE 1=1"
    params: list = []
    if tenant_id:
        query += " AND tenant_id = %s"
        params.append(tenant_id)
    if principal_id:
        query += " AND principal_id = %s"
        params.append(principal_id)
    query += " ORDER BY created_at DESC"
    return execute(query, tuple(params) if params else None)


def parse_token(token_str: str, request_id: str, correlation_id: str | None = None) -> SecurityContext:
    token_hash = _hash_token(token_str)
    row = execute_one(
        "SELECT t.token_id, t.principal_id, t.tenant_id, t.scopes, t.expires_at, t.revoked_at, "
        "t.security_version AS token_security_version, t.jti, "
        "p.principal_type, p.name, p.status, p.security_version AS principal_security_version "
        "FROM v2_tokens t JOIN principals p ON t.principal_id = p.principal_id "
        "WHERE t.token_hash = %s",
        (token_hash,),
    )
    if row is None:
        raise ValueError("AUTHENTICATION_FAILED")
    if row["revoked_at"] is not None:
        raise ValueError("TOKEN_REVOKED")
    if row["expires_at"] is not None and row["expires_at"] < datetime.now(timezone.utc):
        raise ValueError("TOKEN_EXPIRED")
    if row["status"] != "active":
        raise ValueError("PRINCIPAL_DISABLED")
    if row["token_security_version"] != row["principal_security_version"]:
        raise ValueError("SECURITY_VERSION_MISMATCH")

    role_rows = execute(
        "SELECT r.name FROM role_bindings rb JOIN roles r ON rb.role_id = r.role_id "
        "WHERE rb.principal_id = %s",
        (row["principal_id"],),
    )
    roles = [r["name"] for r in role_rows]
    scopes = row["scopes"] if isinstance(row["scopes"], list) else list(row["scopes"])

    return SecurityContext(
        principal_id=row["principal_id"],
        principal_type=row["principal_type"],
        tenant_id=row["tenant_id"],
        roles=roles,
        scopes=scopes,
        token_id=row["token_id"],
        request_id=request_id,
        correlation_id=correlation_id,
        security_version=row["principal_security_version"],
    )


def create_principal(principal_type: str, name: str, tenant_id: str,
                     metadata: dict | None = None) -> dict:
    principal_id = _ulid("prn")
    execute(
        "INSERT INTO principals (principal_id, principal_type, name, tenant_id, metadata) "
        "VALUES (%s, %s, %s, %s, %s)",
        (principal_id, principal_type, name, tenant_id, json.dumps(metadata or {})),
    )
    return {"principal_id": principal_id, "principal_type": principal_type, "name": name, "tenant_id": tenant_id}


def assign_role(principal_id: str, role_name: str, tenant_id: str) -> dict:
    role_row = execute_one("SELECT role_id FROM roles WHERE name = %s", (role_name,))
    if role_row is None:
        raise ValueError(f"Role {role_name} not found")
    binding_id = _ulid("rb")
    execute(
        "INSERT INTO role_bindings (binding_id, principal_id, role_id, tenant_id) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (principal_id, role_id, tenant_id) DO NOTHING",
        (binding_id, principal_id, role_row["role_id"], tenant_id),
    )
    return {"binding_id": binding_id, "principal_id": principal_id, "role": role_name, "tenant_id": tenant_id}


def authorize(ctx: SecurityContext, action: str, resource_tenant_id: str | None = None) -> bool:
    if not ctx.has_scope(action):
        return False
    if resource_tenant_id is not None and not ctx.can_access_tenant(resource_tenant_id):
        return False
    return True


def check_tenant(ctx: SecurityContext, tenant_id: str) -> None:
    if not ctx.can_access_tenant(tenant_id):
        raise PermissionError("TENANT_SCOPE_VIOLATION")
