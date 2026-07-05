from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(self, name: str, base_url: str = "http://localhost:11434",
                 api_key: str = "", models: list = None, priority: int = 99, **kwargs):
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._models = models or []
        self._priority = priority
        self._client = None

    def _ensure(self):
        if self._client is None:
            import httpx
            self._client = httpx.Client(base_url=self._base_url, timeout=60.0)

    def chat(self, messages: list[dict], model: str,
             temperature: float = 0.7, max_tokens: int = 0, **kwargs) -> dict:
        self._ensure()
        body = {"model": model, "messages": messages, "stream": False,
                "options": {"temperature": temperature}}
        if max_tokens > 0:
            body["options"]["num_predict"] = max_tokens

        r = self._client.post("/api/chat", json=body)
        r.raise_for_status()
        data = r.json()
        msg = data.get("message", {})
        return {
            "id": f"ollama_{data.get('created_at', '')}",
            "model": data.get("model", model),
            "choices": [{"message": msg}],
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            },
        }

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        self._ensure()
        results = []
        for text in texts:
            r = self._client.post("/api/embeddings", json={"model": model, "prompt": text})
            r.raise_for_status()
            results.append(r.json().get("embedding", []))
        return results

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
        return bool(self._base_url)
