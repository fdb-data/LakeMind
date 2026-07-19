from __future__ import annotations

import asyncio
import os
import logging
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException

from ..auth import check_auth

logger = logging.getLogger(__name__)
router = APIRouter()
_asr_concurrency = int(os.environ.get("ASR_CONCURRENCY", "1"))
_asr_semaphore = asyncio.Semaphore(_asr_concurrency)
_asr_max_upload_mb = int(os.environ.get("ASR_MAX_UPLOAD_MB", "100"))
_allowed_extensions = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}


@router.post("/v1/audio/transcriptions")
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("default-asr"),
    language: str = Form("auto"),
):
    check_auth(request)
    asr_mgr = getattr(request.app.state, "asr_mgr", None)
    registry = request.app.state.registry
    if asr_mgr is None:
        raise HTTPException(status_code=503, detail="ASR service not configured")

    target_model = model
    resolved = registry.resolve_profile(model)
    if resolved:
        target_model = resolved["model_name"]

    if target_model not in asr_mgr.list_registered():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unsupported_asr_model",
                "requested": target_model,
                "available": asr_mgr.list_registered(),
            },
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    if len(audio_bytes) > _asr_max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large, max {_asr_max_upload_mb}MB")

    filename = file.filename or "audio.wav"
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in _allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}")

    async with _asr_semaphore:
        try:
            text = await asyncio.to_thread(
                asr_mgr.transcribe_bytes,
                audio_bytes,
                target_model,
                filename=filename,
                language=language,
            )
            return {"text": text, "model": target_model}
        except Exception as e:
            logger.error("ASR failed: %s", e)
            raise HTTPException(status_code=502, detail=f"ASR transcription failed: {e}")
