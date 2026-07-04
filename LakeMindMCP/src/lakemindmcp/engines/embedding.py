"""Embedding 提供者。

缺省 ``LocalEmbeddingProvider``：纯 numpy/stdlib 的确定性向量，无需外部服务、
无 torch，开箱即用（补足本地能力）。生产可切 ``openai_compatible`` 走外部服务。
"""
from __future__ import annotations

import hashlib
import struct
from typing import Protocol

import httpx

from ..config import EmbeddingCfg

__all__ = ["EmbeddingProvider", "LocalEmbeddingProvider", "OpenAICompatibleProvider", "build_embedding"]


class EmbeddingProvider(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbeddingProvider:
    """本地确定性 embedding（缺省）。

    基于 SHA256 的归一化伪向量，无语义但稳定、零依赖、零外部服务，
    让 MCP 在无 embedding 服务时亦具备向量化与检索能力。
    生产建议切 openai_compatible 获得真实语义。
    """

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(self.dim):
            b = h[(i * 4) % len(h) : (i * 4) % len(h) + 4]
            if len(b) < 4:
                b = b + h[: 4 - len(b)]
            vec.append(struct.unpack("f", b)[0])
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec] if norm > 0 else vec


class OpenAICompatibleProvider:
    """走 OpenAI 兼容协议的 embedding 客户端。

    可指向 OpenAI 官方或任意自托管服务（vLLM / TEI / Infinity 等）。
    """

    def __init__(self, cfg: EmbeddingCfg, timeout: float = 30.0) -> None:
        self._cfg = cfg
        self._client = httpx.Client(timeout=timeout)
        self._fallback = cfg.fallback_base_url or None

    @property
    def dim(self) -> int:
        return self._cfg.dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._call(self._cfg.base_url, texts) or (
            self._call(self._fallback, texts) if self._fallback else []
        )

    def _call(self, base_url: str | None, texts: list[str]) -> list[list[float]]:
        if not base_url:
            return []
        resp = self._client.post(
            f"{base_url.rstrip('/')}/embeddings",
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
    if cfg.provider == "openai_compatible":
        return OpenAICompatibleProvider(cfg)
    return LocalEmbeddingProvider(dim=cfg.dim)
