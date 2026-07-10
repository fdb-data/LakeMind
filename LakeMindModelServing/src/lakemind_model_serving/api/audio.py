from __future__ import annotations

import httpx
import logging
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException

from ..auth import check_auth

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/audio/transcriptions")
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("sensevoice-small"),
    language: str = Form("auto"),
):
    check_auth(request)
    asr_service = getattr(request.app.state, "asr_service", None)
    if asr_service is None:
        raise HTTPException(status_code=503, detail="ASR service not configured")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        text = asr_service.transcribe_bytes(audio_bytes, filename=file.filename or "audio.wav")
        return {"text": text, "model": asr_service.model_name}
    except Exception as e:
        logger.error("ASR failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
