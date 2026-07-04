"""Embedding 提供者。fastembed (ONNX) 缺省，外部 OpenAI 兼容可选。"""
from __future__ import annotations

from typing import Protocol

import httpx

from ..config import EmbeddingCfg

__all__ = ["EmbeddingProvider", "FastEmbedProvider", "OpenAICompatibleProvider", "build_embedding"]


class EmbeddingProvider(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedProvider:
    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", dim: int = 384) -> None:
        self._model_name = model
        self._model = None
        self.dim = dim

    def _ensure_model(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self._model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_model()
        return [list(v) for v in self._model.embed(texts)]


class OpenAICompatibleProvider:
    def __init__(self, cfg: EmbeddingCfg, timeout: float = 30.0) -> None:
        self._cfg = cfg
        self._client = httpx.Client(timeout=timeout)

    @property
    def dim(self) -> int:
        return self._cfg.dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.post(
            f"{self._cfg.base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {self._cfg.api_key}"},
            json={"input": texts, "model": self._cfg.model, "dimensions": self._cfg.dim},
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    def close(self) -> None:
        self._client.close()


def build_embedding(cfg: EmbeddingCfg) -> EmbeddingProvider:
    if cfg.provider == "external":
        return OpenAICompatibleProvider(cfg)
    return FastEmbedProvider(model=cfg.model, dim=cfg.dim)
