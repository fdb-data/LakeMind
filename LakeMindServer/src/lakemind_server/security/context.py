from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class SecurityContext:
    principal_id: str
    principal_type: str
    tenant_id: str
    roles: list[str]
    scopes: list[str]
    token_id: str
    request_id: str
    correlation_id: str | None = None

    @property
    def is_platform_admin(self) -> bool:
        return "platform_admin" in self.roles

    @property
    def is_tenant_admin(self) -> bool:
        return "tenant_admin" in self.roles or self.is_platform_admin

    def has_scope(self, action: str) -> bool:
        if self.is_platform_admin:
            return True
        return action in self.scopes

    def can_access_tenant(self, tenant_id: str) -> bool:
        if self.is_platform_admin:
            return True
        return self.tenant_id == tenant_id
