from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str = "jinaai/jina-embeddings-v2-base-zh",
                 dim: int = 768, cache_dir: str = "/data/fastembed_cache"):
        self._model = None
        self._model_name = model_name
        self._dim = dim
        self._cache_dir = cache_dir

    def _ensure_model(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(
                model_name=self._model_name,
                cache_dir=self._cache_dir,
            )
            logger.info("fastembed model loaded: %s", self._model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_model()
        return [[float(x) for x in v] for v in self._model.embed(texts)]

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model_name

    def health(self) -> bool:
        try:
            import fastembed
            return True
        except Exception:
            return False
