from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class OpenAICompatProvider:
    def __init__(self, name: str, base_url: str, api_key: str,
                 models: list = None, priority: int = 99, **kwargs):
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._models = models or []
        self._priority = priority
        self._client = None

    def _ensure(self):
        if self._client is None:
            import httpx
            self._client = httpx.Client(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=60.0,
            )

    def chat(self, messages: list[dict], model: str,
             temperature: float = 0.7, max_tokens: int = 0, **kwargs) -> dict:
        self._ensure()
        body = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens > 0:
            body["max_tokens"] = max_tokens
        r = self._client.post("/chat/completions", json=body)
        r.raise_for_status()
        data = r.json()
        return {
            "id": data.get("id", ""),
            "model": data.get("model", model),
            "choices": data.get("choices", []),
            "usage": data.get("usage", {}),
        }

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        self._ensure()
        r = self._client.post("/embeddings", json={"model": model, "input": texts})
        r.raise_for_status()
        data = r.json()
        return [item["embedding"] for item in data.get("data", [])]

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
        return bool(self._api_key) and bool(self._base_url)
