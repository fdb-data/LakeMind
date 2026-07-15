from __future__ import annotations

import enum
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

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


class ASRService:
    def __init__(
        self,
        model_path: str = "/models/asr/faster-whisper-small",
        model_alias: str = "whisper-small",
        language: str = "auto",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        num_workers: int = 1,
        beam_size: int = 5,
        vad_filter: bool = True,
        vad_min_silence_duration_ms: int = 500,
        condition_on_previous_text: bool = False,
        word_timestamps: bool = False,
        required: bool = False,
    ):
        self._model = None
        self._model_path = model_path
        self._model_alias = model_alias
        self._language = _normalize_language(language)
        self._device = device
        self._compute_type = compute_type
        self._cpu_threads = cpu_threads
        self._num_workers = num_workers
        self._beam_size = beam_size
        self._vad_filter = vad_filter
        self._vad_min_silence_duration_ms = vad_min_silence_duration_ms
        self._condition_on_previous_text = condition_on_previous_text
        self._word_timestamps = word_timestamps
        self._required = required

        self._status = ASRStatus.MISSING
        self._last_error: str | None = None
        self._loaded_at: datetime | None = None

        if not Path(model_path).exists():
            self._status = ASRStatus.MISSING
            logger.warning("ASR model path not found: %s", model_path)
        else:
            missing = [f for f in REQUIRED_FILES if not (Path(model_path) / f).is_file()]
            if missing:
                self._status = ASRStatus.MISSING
                logger.warning("ASR model files missing at %s: %s", model_path, missing)
            else:
                self._status = ASRStatus.LOADING if False else ASRStatus.MISSING
                logger.info("ASR model files present at %s, not yet loaded", model_path)

    def load(self) -> None:
        if self._status == ASRStatus.READY:
            return
        if self._status == ASRStatus.FAILED and self._model is not None:
            return

        self._status = ASRStatus.LOADING
        self._last_error = None

        try:
            model_path = Path(self._model_path)
            if not model_path.exists():
                raise RuntimeError(
                    f"ASR model not found at {model_path}. "
                    "Run asr-model-init or pre-download models. "
                    "Runtime download is disabled (design principle 5)."
                )

            missing = [f for f in REQUIRED_FILES if not (model_path / f).is_file()]
            if missing:
                raise RuntimeError(f"ASR model files missing at {model_path}: {missing}")

            from faster_whisper import WhisperModel

            logger.info(
                "Loading faster-whisper: path=%s, device=%s, compute_type=%s, cpu_threads=%d, num_workers=%d",
                model_path, self._device, self._compute_type, self._cpu_threads, self._num_workers,
            )
            self._model = WhisperModel(
                str(model_path),
                device=self._device,
                compute_type=self._compute_type,
                cpu_threads=self._cpu_threads,
                num_workers=self._num_workers,
            )
            self._status = ASRStatus.READY
            self._loaded_at = datetime.now(timezone.utc)
            logger.info("Whisper model loaded: %s", model_path)

        except Exception as exc:
            self._status = ASRStatus.FAILED
            self._last_error = str(exc)
            self._model = None
            logger.exception("ASR model load failed")
            if self._required:
                raise

    def transcribe(self, audio_path: str, language: str | None = None) -> str:
        if self._model is None:
            self.load()
        if self._model is None:
            raise RuntimeError(f"ASR model not loaded: {self._last_error}")

        lang = _normalize_language(language) if language else self._language

        segments, _info = self._model.transcribe(
            audio_path,
            language=lang,
            beam_size=self._beam_size,
            vad_filter=self._vad_filter,
            vad_parameters={"min_silence_duration_ms": self._vad_min_silence_duration_ms},
            condition_on_previous_text=self._condition_on_previous_text,
            word_timestamps=self._word_timestamps,
        )

        segment_list = list(segments)
        text = "".join(seg.text for seg in segment_list).strip()
        return text

    def transcribe_bytes(self, audio_bytes: bytes, filename: str = "audio.wav", language: str | None = None) -> str:
        tmp_dir = tempfile.mkdtemp(prefix="lakemind-asr-")
        tmp_path = os.path.join(tmp_dir, filename)
        try:
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)
            return self.transcribe(tmp_path, language=language)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @property
    def model_name(self) -> str:
        return self._model_alias

    @property
    def model_path(self) -> str:
        return self._model_path

    @property
    def status(self) -> ASRStatus:
        return self._status

    @property
    def public_error(self) -> str | None:
        return self._last_error

    def health(self) -> bool:
        return self._status in (ASRStatus.READY, ASRStatus.LOADING, ASRStatus.MISSING)

    def ready(self) -> bool:
        return self._status == ASRStatus.READY
