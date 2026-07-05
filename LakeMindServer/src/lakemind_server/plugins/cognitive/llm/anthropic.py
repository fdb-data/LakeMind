from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class AnthropicProvider:
    def __init__(self, name: str, api_key: str, base_url: str = "",
                 models: list = None, priority: int = 99, **kwargs):
        self._name = name
        self._api_key = api_key
        self._base_url = (base_url or "https://api.anthropic.com").rstrip("/")
        self._models = models or []
        self._priority = priority
        self._client = None

    def _ensure(self):
        if self._client is None:
            import httpx
            self._client = httpx.Client(
                base_url=self._base_url,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=60.0,
            )

    def chat(self, messages: list[dict], model: str,
             temperature: float = 0.7, max_tokens: int = 0, **kwargs) -> dict:
        self._ensure()
        system = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_messages.append(m)

        body = {"model": model, "messages": user_messages,
                "temperature": temperature,
                "max_tokens": max_tokens if max_tokens > 0 else 4096}
        if system:
            body["system"] = system

        r = self._client.post("/v1/messages", json=body)
        r.raise_for_status()
        data = r.json()

        content = "".join(block.get("text", "") for block in data.get("content", []))
        return {
            "id": data.get("id", ""),
            "model": data.get("model", model),
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": data.get("usage", {}),
        }

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        raise NotImplementedError("Anthropic does not provide embedding API")

    def list_models(self) -> list[dict]:
        return [{"id": m["id"], "provider": self._name,
                 "context": m.get("context", 0), "tags": m.get("tags", [])}
                for m in self._models]

    def get_model(self, model_id: str) -> dict | None:
        for m in self._models:
            if m["id"] == model_id:
                return m
        return None

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    def health(self) -> bool:
        return bool(self._api_key)
