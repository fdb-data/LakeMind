from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModelGateway:
    def __init__(self, providers: list | None = None, gateway_config: dict | None = None):
        self._providers = providers or []
        self._gateway_config = gateway_config or {}
        self._router = None
        self._model_names: dict[str, dict] = {}
        self._init_router()

    def _init_router(self):
        from litellm import Router

        model_list = []
        for p_cfg in self._providers:
            p_name = p_cfg.get("name", "unknown")
            p_type = p_cfg.get("type", "openai")
            api_key = p_cfg.get("api_key", "")
            base_url = p_cfg.get("base_url", "")

            for m in p_cfg.get("models", []):
                litellm_model = m.get("litellm_model", f"{p_type}/{m['id']}")
                entry = {
                    "model_name": m["id"],
                    "litellm_params": {
                        "model": litellm_model,
                        "api_key": api_key,
                    },
                }
                if base_url:
                    entry["litellm_params"]["api_base"] = base_url
                model_list.append(entry)
                self._model_names[m["id"]] = {
                    "id": m["id"],
                    "type": "llm",
                    "provider": p_name,
                    "litellm_model": litellm_model,
                    "tags": m.get("tags", []),
                    "context": m.get("context", 0),
                }

        fallbacks = []
        fb_chat = self._gateway_config.get("fallback", {}).get("chat", [])
        primary = self._gateway_config.get("default_chat_model", "")
        if fb_chat and primary and primary != "auto":
            fb_list = [m for m in fb_chat if m != primary]
            if fb_list:
                fallbacks.append({primary: fb_list})

        self._router = Router(
            model_list=model_list,
            fallbacks=fallbacks,
            num_retries=3,
            timeout=120,
        )
        logger.info("litellm Router initialized with %d models", len(model_list))

    def chat(self, messages: list[dict], model: str = "",
             temperature: float = 0.7, max_tokens: int = 0,
             stream: bool = False, **kwargs) -> dict:
        target = self._resolve_model(model, "chat")
        resp = self._router.completion(
            model=target,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens if max_tokens > 0 else None,
            stream=stream,
            **kwargs,
        )
        if stream:
            return resp
        result = {
            "id": resp.get("id", ""),
            "object": "chat.completion",
            "model": target,
            "choices": resp.get("choices", []),
            "usage": resp.get("usage", {}),
        }
        return result

    def embed(self, texts: list[str], model: str = "") -> dict:
        target = self._resolve_model(model, "embed")
        resp = self._router.embedding(model=target, input=texts)
        data = []
        for i, item in enumerate(resp.get("data", [])):
            data.append({"embedding": item.get("embedding", []), "index": i})
        return {
            "object": "list",
            "model": target,
            "data": data,
            "usage": resp.get("usage", {}),
        }

    def list_models(self) -> list[dict]:
        return list(self._model_names.values())

    def register_model(self, model_config: dict) -> bool:
        model_name = model_config["model_id"]
        litellm_model = model_config.get("litellm_model", f"{model_config.get('provider', 'openai')}/{model_name}")
        entry = {
            "model_name": model_name,
            "litellm_params": {
                "model": litellm_model,
                "api_key": model_config.get("api_key", ""),
            },
        }
        if model_config.get("base_url"):
            entry["litellm_params"]["api_base"] = model_config["base_url"]
        try:
            try:
                self._router.add_deployment(entry)
            except Exception:
                self._router.model_list.append(entry)
                self._router.set_model_list(model_list=self._router.model_list)
            self._model_names[model_name] = {
                "id": model_name,
                "type": model_config.get("type", "llm"),
                "provider": model_config.get("provider", "external"),
                "litellm_model": litellm_model,
                "tags": model_config.get("tags", []),
                "context": model_config.get("context_window", 0),
            }
            logger.info("Registered model: %s", model_name)
            return True
        except Exception as e:
            logger.error("Failed to register model %s: %s", model_name, e)
            return False

    def deregister_model(self, model_id: str) -> bool:
        if model_id not in self._model_names:
            return False
        try:
            self._router.delete_deployment(model_id)
            del self._model_names[model_id]
            logger.info("Deregistered model: %s", model_id)
            return True
        except Exception as e:
            logger.error("Failed to deregister model %s: %s", model_id, e)
            try:
                self._model_names.pop(model_id, None)
                return True
            except Exception:
                return False

    def _resolve_model(self, model: str, task: str) -> str:
        if model and model != "auto":
            return model
        default = self._gateway_config.get(f"default_{task}_model", "auto")
        if default and default != "auto":
            return default
        for name, info in self._model_names.items():
            if task in info.get("tags", []):
                return name
        if self._model_names:
            return next(iter(self._model_names))
        raise RuntimeError(f"No {task} model available")

    def health(self) -> bool:
        return len(self._model_names) > 0
