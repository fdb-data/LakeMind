from __future__ import annotations


class FastEmbedPlugin:
    def __init__(self, model: str = "jinaai/jina-embeddings-v2-base-zh", dim: int = 768, **kwargs):
        self._model_name = model
        self._dim = dim
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self._model_name,
                                        cache_dir="/tmp/fastembed_cache")

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_model()
        return [[float(x) for x in v] for v in self._model.embed(texts)]

    def health(self) -> bool:
        try:
            import fastembed
            return True
        except Exception:
            return False
