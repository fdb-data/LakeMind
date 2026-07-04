"""Dragonfly 客户端（短期记忆 TTL KV，Redis 兼容，按租户分 DB）。"""
from __future__ import annotations

import json
from typing import Any

from ..config import DragonflyCfg
from ..context import TenantContext

__all__ = ["DragonflyClient"]


class DragonflyClient:
    def __init__(self, cfg: DragonflyCfg) -> None:
        self._cfg = cfg
        self._client = None

    def _ensure(self):
        if self._client is None:
            import redis

            self._client = redis.Redis(
                host=self._cfg.host,
                port=self._cfg.port,
                password=self._cfg.password or None,
                socket_timeout=5,
                decode_responses=True,
            )
        return self._client

    def _db(self, ctx: TenantContext):
        c = self._ensure()
        return c  # 通过 select 切换 DB；连接非线程安全，MVP 单线程足够

    def remember(self, ctx: TenantContext, key: str, value: dict, ttl: int | None = None) -> None:
        c = self._ensure()
        c.execute_command("SELECT", ctx.dragonfly_db())
        c.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)

    def get(self, ctx: TenantContext, key: str) -> dict | None:
        c = self._ensure()
        c.execute_command("SELECT", ctx.dragonfly_db())
        v = c.get(key)
        return json.loads(v) if v else None

    def forget(self, ctx: TenantContext, key: str) -> bool:
        c = self._ensure()
        c.execute_command("SELECT", ctx.dragonfly_db())
        return bool(c.delete(key))

    def scan(self, ctx: TenantContext, pattern: str) -> list[str]:
        c = self._ensure()
        c.execute_command("SELECT", ctx.dragonfly_db())
        return list(c.scan_iter(match=pattern))

    def close(self) -> None:
        self._client = None
