from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ScopeType(str, Enum):
    PLATFORM = "PLATFORM"
    TENANT = "TENANT"


@dataclass(frozen=True)
class Scope:
    scope_type: ScopeType
    scope_id: str | None = None

    def __str__(self) -> str:
        if self.scope_type == ScopeType.PLATFORM:
            return "PLATFORM"
        return f"TENANT:{self.scope_id}"

    def matches(self, ctx: "SecurityContext") -> bool:
        if self.scope_type == ScopeType.PLATFORM:
            return ctx.is_platform_admin
        return ctx.can_access_tenant(self.scope_id)

    @property
    def db_type(self) -> str:
        return self.scope_type.value

    @property
    def db_id(self) -> str | None:
        return self.scope_id


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
    security_version: int = 0

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

    def accessible_scope_filter(self) -> dict:
        if self.is_platform_admin:
            return {}
        return {"scope_type": "TENANT", "scope_id": self.tenant_id}

    @property
    def capabilities(self) -> list[str]:
        from .actions import capabilities_for_role, ALL_CAPABILITIES
        if self.is_platform_admin:
            return ALL_CAPABILITIES
        caps: set[str] = set()
        for role in self.roles:
            caps.update(capabilities_for_role(role))
        for scope in self.scopes:
            from .actions import Action, ACTION_TO_CAPABILITY
            try:
                action = Action(scope)
                cap = ACTION_TO_CAPABILITY.get(action)
                if cap:
                    caps.add(cap.value)
            except ValueError:
                pass
        return sorted(caps)
