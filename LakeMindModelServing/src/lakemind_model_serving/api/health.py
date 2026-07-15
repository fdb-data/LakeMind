from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
@router.get("/health/live")
async def health_live(request: Request):
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(request: Request):
    gateway = getattr(request.app.state, "gateway", None)
    embedding_service = getattr(request.app.state, "embedding_service", None)

    components = {
        "gateway": gateway.health() if gateway else False,
        "embedding": embedding_service.health() if embedding_service else False,
    }

    all_ready = all(components.values())
    return {
        "ready": all_ready,
        "components": components,
    }


@router.get("/health/components/asr")
async def health_asr(request: Request):
    asr_service = getattr(request.app.state, "asr_service", None)
    if asr_service is None:
        return {"status": "disabled", "ready": False}

    result = {
        "status": asr_service.status.value,
        "ready": asr_service.ready(),
        "model": asr_service.model_name,
    }
    if asr_service.public_error:
        result["error"] = asr_service.public_error

    if asr_service.ready():
        return result
    else:
        return JSONResponse(status_code=503, content=result)
