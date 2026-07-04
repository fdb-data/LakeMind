"""健康检查。"""
from __future__ import annotations

from typing import Any

from .engines import Engines


def system_health(engines: Engines) -> dict[str, Any]:
    health: dict[str, Any] = {}
    try:
        engines.s3._client.list_buckets()
        health["s3"] = "ok"
    except Exception:
        health["s3"] = "error"
    try:
        engines.dragonfly._r.ping()
        health["dragonfly"] = "ok"
    except Exception:
        health["dragonfly"] = "error"
    try:
        engines.graph.health()
        health["postgres"] = "ok"
    except Exception:
        health["postgres"] = "error"
    try:
        v = engines.embedding.embed(["test"])
        health["embedding"] = "ok" if v else "error"
    except Exception:
        health["embedding"] = "error"
    return health
