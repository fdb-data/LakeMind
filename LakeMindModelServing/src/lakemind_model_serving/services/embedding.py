from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Manage multiple local fastembed models with lazy loading."""

    def __init__(self, cache_dir: str = "/data/fastembed_cache"):
        self._cache_dir = cache_dir
        self._models: dict[str, Any] = {}
        self._dims: dict[str, int] = {}
        self._paths: dict[str, str | None] = {}
        self._lock = threading.Lock()

    def register(self, name: str, dim: int = 0, model_path: str | None = None):
        with self._lock:
            self._dims[name] = dim
            self._paths[name] = model_path

    def unregister(self, name: str):
        with self._lock:
            self._models.pop(name, None)
            self._dims.pop(name, None)
            self._paths.pop(name, None)
            logger.info("Embedding model unloaded: %s", name)

    def embed(self, texts: list[str], model_name: str) -> tuple[list[list[float]], int]:
        if not texts:
            return [], self._dims.get(model_name, 0)
        if model_name not in self._models:
            with self._lock:
                if model_name not in self._models:
                    from fastembed import TextEmbedding
                    cache_dir = self._paths.get(model_name) or self._cache_dir
                    self._models[model_name] = TextEmbedding(
                        model_name=model_name,
                        cache_dir=cache_dir,
                    )
                    logger.info("fastembed model loaded: %s", model_name)
        model = self._models[model_name]
        vectors = [[float(x) for x in v] for v in model.embed(texts)]
        dim = self._dims.get(model_name) or (len(vectors[0]) if vectors else 0)
        return vectors, dim

    def list_loaded(self) -> list[str]:
        return list(self._models.keys())

    def list_registered(self) -> list[str]:
        return list(self._dims.keys())

    def get_dim(self, name: str) -> int:
        return self._dims.get(name, 0)

    def health(self) -> bool:
        try:
            import fastembed
            return True
        except Exception:
            return False
