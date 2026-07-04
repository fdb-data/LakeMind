"""租户隔离辅助（路径/库名拼接）。"""
from __future__ import annotations

from ..context import TenantContext, get_tenant

__all__ = ["get_tenant", "TenantContext"]
