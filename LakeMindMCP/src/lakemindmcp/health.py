"""系统健康检查（共享逻辑，供 admin 工具与只读资源复用）。"""
from __future__ import annotations

from typing import Any

from .engines import Engines

__all__ = ["system_health"]


def system_health(engines: Engines) -> dict[str, Any]:
    health: dict[str, Any] = {}
    try:
        engines.s3.ensure_bucket("lakemind-iceberg")
        health["s3"] = "ok"
    except Exception as e:
        health["s3"] = f"fail: {e}"
    try:
        engines.dragonfly._ensure().ping()
        health["dragonfly"] = "ok"
    except Exception as e:
        health["dragonfly"] = f"fail: {e}"
    try:
        resp = engines.gravitino._client.get("/api/version")
        health["gravitino"] = "ok" if resp.status_code == 200 else f"status {resp.status_code}"
    except Exception as e:
        health["gravitino"] = f"fail: {e}"
    try:
        v = engines.embedding.embed(["ping"])
        health["embedding"] = "ok" if v else "empty"
    except Exception as e:
        health["embedding"] = f"fail: {e}"
    return health
