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
    model: str = Form("whisper-small"),
    language: str = Form("auto"),
):
    check_auth(request)
    asr_service = getattr(request.app.state, "asr_service", None)
    if asr_service is None:
        raise HTTPException(status_code=503, detail="ASR service not configured")

    if not asr_service.ready():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "asr_not_ready",
                "status": asr_service.status.value,
                "error": asr_service.public_error,
            },
        )

    if model not in {asr_service.model_name, "whisper-small"}:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unsupported_asr_model",
                "requested": model,
                "available": [asr_service.model_name],
            },
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    if len(audio_bytes) > _asr_max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large, max {_asr_max_upload_mb}MB",
        )

    filename = file.filename or "audio.wav"
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in _allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: {ext}",
        )

    async with _asr_semaphore:
        try:
            text = await asyncio.to_thread(
                asr_service.transcribe_bytes,
                audio_bytes,
                filename=filename,
                language=language,
            )
            return {"text": text, "model": asr_service.model_name}
        except Exception as e:
            logger.error("ASR failed: %s", e)
            raise HTTPException(status_code=502, detail="ASR transcription failed")
