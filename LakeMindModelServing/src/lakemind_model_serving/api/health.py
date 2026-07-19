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
    embedding_mgr = getattr(request.app.state, "embedding_mgr", None)
    registry = getattr(request.app.state, "registry", None)

    components = {
        "gateway": gateway.health() if gateway else False,
        "embedding": embedding_mgr.health() if embedding_mgr else False,
        "registry": registry.health() if registry else False,
    }

    all_ready = all(components.values())
    return {
        "ready": all_ready,
        "components": components,
    }


@router.get("/health/components/asr")
async def health_asr(request: Request):
    asr_mgr = getattr(request.app.state, "asr_mgr", None)
    if asr_mgr is None:
        return {"status": "disabled", "ready": False}

    registered = asr_mgr.list_registered()
    if not registered:
        return {"status": "disabled", "ready": False, "models": []}

    models_info = []
    any_ready = False
    for mid in registered:
        status = asr_mgr.get_status(mid)
        info = {"model": mid, "status": status.value, "ready": status.value == "ready"}
        if status.value != "ready":
            err = asr_mgr.get_error(mid)
            if err:
                info["error"] = err
        else:
            any_ready = True
        models_info.append(info)

    result = {"ready": any_ready, "models": models_info}
    if not any_ready:
        return JSONResponse(status_code=503, content=result)
    return result
