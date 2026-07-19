from __future__ import annotations
from datetime import datetime, timezone
import ulid
from ..db import execute, execute_one
from ..security.token_parser import issue_token, revoke_token, list_tokens, create_principal, assign_role, authorize, check_tenant
from ..security.context import SecurityContext
from ..security.actions import actions_for_roles


class AuthorizationService:

    @staticmethod
    def issue_token(principal_id: str, tenant_id: str, scopes: list[str],
                    expires_at: datetime | None = None) -> dict:
        result = issue_token(principal_id, tenant_id, scopes, expires_at)
        AuditService.record(
            event_type="auth.token_issued",
            principal_id=principal_id,
            tenant_id=tenant_id,
            resource_id=result["token_id"],
            action="issue_token",
            result="success",
        )
        return result

    @staticmethod
    def revoke_token(token_id: str, ctx: SecurityContext) -> dict:
        result = revoke_token(token_id)
        AuditService.record(
            event_type="auth.token_revoked",
            principal_id=ctx.principal_id,
            tenant_id=ctx.tenant_id,
            resource_id=token_id,
            action="revoke_token",
            result="success",
        )
        return result

    @staticmethod
    def list_tokens(ctx: SecurityContext, tenant_id: str | None = None) -> list[dict]:
        if not ctx.is_platform_admin:
            tenant_id = ctx.tenant_id
        return list_tokens(tenant_id)

    @staticmethod
    def authorize(ctx: SecurityContext, action: str, resource_tenant_id: str | None = None) -> bool:
        return authorize(ctx, action, resource_tenant_id)

    @staticmethod
    def check_tenant(ctx: SecurityContext, tenant_id: str) -> None:
        check_tenant(ctx, tenant_id)

    @staticmethod
    def create_principal(principal_type: str, name: str, tenant_id: str,
                         role: str = "agent", metadata: dict | None = None) -> dict:
        result = create_principal(principal_type, name, tenant_id, metadata)
        assign_role(result["principal_id"], role, tenant_id)
        return result

    @staticmethod
    def login(username: str, password_hash: str) -> dict:
        row = execute_one(
            "SELECT p.principal_id, p.tenant_id, p.status, p.password_hash "
            "FROM principals p WHERE p.username = %s",
            (username,),
        )
        if row is None:
            raise ValueError("AUTHENTICATION_FAILED")
        if row["status"] != "active":
            raise ValueError("PRINCIPAL_DISABLED")
        if row["password_hash"] != password_hash:
            raise ValueError("AUTHENTICATION_FAILED")

        role_rows = execute(
            "SELECT r.name FROM role_bindings rb JOIN roles r ON rb.role_id = r.role_id "
            "WHERE rb.principal_id = %s",
            (row["principal_id"],),
        )
        roles = [r["name"] for r in role_rows]
        primary_role = roles[0] if roles else "readonly"

        result = issue_token(row["principal_id"], row["tenant_id"], actions_for_roles(roles))
        AuditService.record(
            event_type="auth.login",
            principal_id=row["principal_id"],
            tenant_id=row["tenant_id"],
            resource_id=result["token_id"],
            action="login",
            result="success",
        )
        return {
            "token": result["token"],
            "token_id": result["token_id"],
            "role": primary_role,
            "roles": roles,
            "tenant_id": row["tenant_id"],
            "principal_id": row["principal_id"],
            "security_version": result.get("security_version", 0),
        }


from .audit_service import AuditService
