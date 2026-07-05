from __future__ import annotations
import logging
from typing import Any

from .openai_compat import OpenAICompatProvider
from .anthropic import AnthropicProvider
from .ollama import OllamaProvider

logger = logging.getLogger(__name__)

_PROVIDER_TYPES = {
    "openai_compat": OpenAICompatProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
}


class GatewayLLM:
    def __init__(self, providers: list = None, routing: list = None,
                 fallback: dict = None, default_chat_model: str = "auto",
                 default_embed_model: str = "auto", **kwargs):
        self._providers: dict[str, Any] = {}
        self._model_registry: dict[str, tuple[str, dict]] = {}
        self._routing = routing or []
        self._fallback = fallback or {}
        self._default_chat = default_chat_model
        self._default_embed = default_embed_model

        for p_cfg in (providers or []):
            p_type = p_cfg.get("type", "openai_compat")
            cls = _PROVIDER_TYPES.get(p_type)
            if cls is None:
                logger.warning("Unknown provider type: %s", p_type)
                continue
            try:
                inst = cls(**p_cfg)
                self._providers[inst.name] = inst
                for m in p_cfg.get("models", []):
                    self._model_registry[m["id"]] = (inst.name, m)
                logger.info("Loaded provider: %s (%s), models: %d",
                            inst.name, p_type, len(p_cfg.get("models", [])))
            except Exception as e:
                logger.warning("Failed to init provider %s: %s", p_cfg.get("name"), e)

    def _resolve_chat_model(self, model: str) -> str:
        if model and model != "auto":
            return model
        if self._default_chat and self._default_chat != "auto":
            return self._default_chat
        sorted_providers = sorted(self._providers.values(), key=lambda p: p.priority)
        for p in sorted_providers:
            for m in p.list_models():
                if "chat" in m.get("tags", []):
                    return m["id"]
        raise RuntimeError("No chat model available")

    def _resolve_embed_model(self, model: str) -> str:
        if model and model != "auto":
            return model
        if self._default_embed and self._default_embed != "auto":
            return self._default_embed
        for p in sorted(self._providers.values(), key=lambda p: p.priority):
            for m in p.list_models():
                if "embed" in m.get("tags", []):
                    return m["id"]
        raise RuntimeError("No embed model available")

    def _fallback_chain(self, model: str, task: str) -> list[str]:
        chain = [model]
        fb_list = self._fallback.get(task, [])
        for m in fb_list:
            if m not in chain:
                chain.append(m)
        return chain

    def _get_provider(self, model_id: str):
        entry = self._model_registry.get(model_id)
        if entry is None:
            for p in self._providers.values():
                if p.get_model(model_id):
                    return p
            return None
        return self._providers.get(entry[0])

    def chat(self, messages: list[dict], model: str = "",
             temperature: float = 0.7, max_tokens: int = 0, **kwargs) -> dict:
        target = self._resolve_chat_model(model)
        chain = self._fallback_chain(target, "chat")
        last_error = None
        for m in chain:
            provider = self._get_provider(m)
            if provider is None:
                continue
            try:
                result = provider.chat(messages, m, temperature, max_tokens, **kwargs)
                return result
            except Exception as e:
                logger.warning("Chat via %s/%s failed: %s", provider.name, m, e)
                last_error = e
        raise RuntimeError(f"All providers failed: {last_error}")

    def embed(self, texts: list[str], model: str = "") -> list[list[float]]:
        target = self._resolve_embed_model(model)
        chain = self._fallback_chain(target, "embed")
        last_error = None
        for m in chain:
            provider = self._get_provider(m)
            if provider is None:
                continue
            try:
                return provider.embed(texts, m)
            except Exception as e:
                logger.warning("Embed via %s/%s failed: %s", provider.name, m, e)
                last_error = e
        raise RuntimeError(f"All embed providers failed: {last_error}")

    def list_models(self) -> list[dict]:
        models = []
        for p in self._providers.values():
            models.extend(p.list_models())
        return models

    def health(self) -> bool:
        return any(p.health() for p in self._providers.values())
