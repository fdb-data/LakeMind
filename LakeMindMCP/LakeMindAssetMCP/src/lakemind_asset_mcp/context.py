"""请求级上下文：Identity 与 TenantContext。"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass

from .config import TokenIdentity

__all__ = ["Identity", "TenantContext", "current_identity", "get_identity", "get_tenant"]


@dataclass(frozen=True)
class Identity:
    agent_id: str
    tenant_id: str
    scopes: tuple[str, ...]

    @classmethod
    def from_token(cls, t: TokenIdentity) -> "Identity":
        return cls(t.agent_id, t.tenant_id, tuple(t.scopes))

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    agent_id: str

    def s3_prefix(self) -> str:
        return f"{self.tenant_id}/"

    def iceberg_namespace(self, domain: str) -> str:
        return f"{self.tenant_id}_{domain}"


current_identity: contextvars.ContextVar[Identity] = contextvars.ContextVar("current_identity")


def get_identity() -> Identity:
    return current_identity.get()


def get_tenant() -> TenantContext:
    ident = get_identity()
    return TenantContext(tenant_id=ident.tenant_id, agent_id=ident.agent_id)
