"""Gravitino REST 客户端（8090：资源发现 + admin 注册）。P1 实现。"""
from __future__ import annotations

import httpx

from ..config import GravitinoCfg

__all__ = ["GravitinoClient"]


class GravitinoClient:
    def __init__(self, cfg: GravitinoCfg, timeout: float = 15.0) -> None:
        self._cfg = cfg
        self._client = httpx.Client(timeout=timeout, base_url=cfg.uri)

    def close(self) -> None:
        self._client.close()
