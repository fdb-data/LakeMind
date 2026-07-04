"""请求级上下文：Identity 与 TenantContext。

Identity 由安全层在中间件中解析并写入 ``current_identity`` ContextVar，
工具/资源 handler 通过 :func:`get_identity` / :func:`get_tenant` 读取。
"""
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
    """租户隔离上下文，由引擎适配层据此拼路径/库名。"""

    tenant_id: str
    agent_id: str

    # ── 各层隔离键 ──────────────────────────────────────────
    def s3_prefix(self) -> str:
        """S3 对象键前缀。"""
        return f"{self.tenant_id}/"

    def iceberg_namespace(self, domain: str) -> str:
        """Iceberg namespace（按数据域）。"""
        return f"{self.tenant_id}_{domain}"

    def lancedb_name(self) -> str:
        """LanceDB 数据库名。"""
        return f"tenant_{self.tenant_id}"

    def dragonfly_db(self) -> int:
        """Dragonfly DB 编号（0-15）。"""
        return abs(hash(self.tenant_id)) % 16


current_identity: contextvars.ContextVar[Identity] = contextvars.ContextVar(
    "current_identity"
)


def get_identity() -> Identity:
    """在 handler 内取当前请求 Identity；未设置则抛错。"""
    return current_identity.get()


def get_tenant() -> TenantContext:
    ident = get_identity()
    return TenantContext(tenant_id=ident.tenant_id, agent_id=ident.agent_id)
