from __future__ import annotations

import logging
import os
import tempfile

logger = logging.getLogger(__name__)


class ASRService:
    def __init__(self, model_name: str = "iic/SenseVoiceSmall",
                 language: str = "auto",
                 cache_dir: str = "/data/funasr_cache"):
        self._model = None
        self._model_name = model_name
        self._language = language
        self._cache_dir = cache_dir

    def _ensure_model(self):
        if self._model is None:
            from funasr import AutoModel
            self._model = AutoModel(
                model=self._model_name,
                vad_model="fsmn-vad",
                punc_model="ct-punc",
                disable_update=True,
                hub="ms",
            )
            logger.info("FunASR model loaded: %s", self._model_name)

    def transcribe(self, audio_path: str) -> str:
        self._ensure_model()
        result = self._model.generate(
            input=audio_path,
            language=self._language,
        )
        if result and isinstance(result, list):
            return result[0].get("text", "")
        return ""

    def transcribe_bytes(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, filename)
        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)
        try:
            return self.transcribe(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
                os.rmdir(tmp_dir)
            except Exception:
                pass

    @property
    def model_name(self) -> str:
        return self._model_name

    def health(self) -> bool:
        try:
            import funasr
            return True
        except Exception:
            return False
