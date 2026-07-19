from __future__ import annotations

import enum
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ASRStatus(str, enum.Enum):
    DISABLED = "disabled"
    MISSING = "missing"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


REQUIRED_FILES = (
    "model.bin",
    "config.json",
    "tokenizer.json",
    "vocabulary.txt",
)


def _normalize_language(language: str | None) -> str | None:
    if language is None:
        return None
    value = language.strip().lower()
    if value in {"", "auto", "detect"}:
        return None
    return value


class ASRManager:
    """Manage multiple local faster-whisper models with lazy loading."""

    def __init__(self):
        self._models: dict[str, Any] = {}
        self._configs: dict[str, dict] = {}
        self._statuses: dict[str, ASRStatus] = {}
        self._errors: dict[str, str | None] = {}
        self._lock = threading.Lock()

    def register(self, model_id: str, model_path: str, config: dict | None = None):
        with self._lock:
            cfg = {"model_path": model_path, **(config or {})}
            self._configs[model_id] = cfg
            if Path(model_path).exists():
                missing = [f for f in REQUIRED_FILES if not (Path(model_path) / f).is_file()]
                if missing:
                    self._statuses[model_id] = ASRStatus.MISSING
                    self._errors[model_id] = f"Missing files: {missing}"
                else:
                    self._statuses[model_id] = ASRStatus.MISSING
                    self._errors[model_id] = None
            else:
                self._statuses[model_id] = ASRStatus.MISSING
                self._errors[model_id] = f"Path not found: {model_path}"

    def unregister(self, model_id: str):
        with self._lock:
            self._models.pop(model_id, None)
            self._configs.pop(model_id, None)
            self._statuses.pop(model_id, None)
            self._errors.pop(model_id, None)
            logger.info("ASR model unloaded: %s", model_id)

    def _load_model(self, model_id: str):
        with self._lock:
            if model_id in self._models:
                return
            cfg = self._configs.get(model_id)
            if not cfg:
                raise RuntimeError(f"ASR model not registered: {model_id}")

            self._statuses[model_id] = ASRStatus.LOADING
            self._errors[model_id] = None

            try:
                model_path = Path(cfg["model_path"])
                if not model_path.exists():
                    raise RuntimeError(f"ASR model not found at {model_path}")

                missing = [f for f in REQUIRED_FILES if not (model_path / f).is_file()]
                if missing:
                    raise RuntimeError(f"ASR model files missing: {missing}")

                from faster_whisper import WhisperModel

                self._models[model_id] = WhisperModel(
                    str(model_path),
                    device=cfg.get("device", "cpu"),
                    compute_type=cfg.get("compute_type", "int8"),
                    cpu_threads=cfg.get("cpu_threads", 4),
                    num_workers=cfg.get("num_workers", 1),
                )
                self._statuses[model_id] = ASRStatus.READY
                logger.info("ASR model loaded: %s -> %s", model_id, model_path)
            except Exception as exc:
                self._statuses[model_id] = ASRStatus.FAILED
                self._errors[model_id] = str(exc)
                self._models.pop(model_id, None)
                raise

    def transcribe_bytes(self, audio_bytes: bytes, model_id: str,
                         filename: str = "audio.wav", language: str | None = None) -> str:
        if model_id not in self._models:
            self._load_model(model_id)
        model = self._models[model_id]
        cfg = self._configs.get(model_id, {})

        tmp_dir = tempfile.mkdtemp(prefix="lakemind-asr-")
        tmp_path = os.path.join(tmp_dir, filename)
        try:
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)

            lang = _normalize_language(language) or _normalize_language(cfg.get("language", "auto"))
            segments, _info = model.transcribe(
                tmp_path,
                language=lang,
                beam_size=cfg.get("beam_size", 5),
                vad_filter=cfg.get("vad_filter", True),
                vad_parameters={"min_silence_duration_ms": cfg.get("vad_min_silence_duration_ms", 500)},
                condition_on_previous_text=cfg.get("condition_on_previous_text", False),
                word_timestamps=cfg.get("word_timestamps", False),
            )
            text = "".join(seg.text for seg in segments).strip()
            return text
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def list_loaded(self) -> list[str]:
        return list(self._models.keys())

    def list_registered(self) -> list[str]:
        return list(self._configs.keys())

    def get_status(self, model_id: str) -> ASRStatus:
        return self._statuses.get(model_id, ASRStatus.MISSING)

    def get_error(self, model_id: str) -> str | None:
        return self._errors.get(model_id)

    def health(self) -> bool:
        return True
