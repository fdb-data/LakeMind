from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    gateway = getattr(request.app.state, "gateway", None)
    embedding_service = getattr(request.app.state, "embedding_service", None)
    asr_service = getattr(request.app.state, "asr_service", None)
    registry = getattr(request.app.state, "registry", None)

    result = {
        "status": "ok",
        "services": {
            "gateway": gateway.health() if gateway else False,
            "embedding": embedding_service.health() if embedding_service else False,
            "asr": asr_service.health() if asr_service else False,
            "registry": registry.health() if registry else False,
        },
    }
    all_healthy = all(result["services"].values())
    result["status"] = "ok" if all_healthy else "degraded"
    return result
