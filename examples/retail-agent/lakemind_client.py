"""LakeMind MCP 客户端 — 业务 Agent 通过此客户端访问 3 个 MCP。"""
from __future__ import annotations

import os
import json
from typing import Any

import httpx

ASSET_MCP_URL = os.environ.get("ASSET_MCP_URL", "http://localhost:8401/mcp")
ASSET_TOKEN = os.environ.get("ASSET_TOKEN", "test-business-token")

_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


class LakeMindClient:
    def __init__(self, url: str | None = None, token: str | None = None):
        self._url = url or ASSET_MCP_URL
        self._token = token or ASSET_TOKEN
        self._client = httpx.Client(timeout=30.0)

    def _call(self, tool: str, arguments: dict | None = None) -> dict:
        resp = self._client.post(
            self._url,
            headers={**_HEADERS, "Authorization": f"Bearer {self._token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": tool, "arguments": arguments or {}}},
        )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")
        return data

    def _read(self, uri: str) -> Any:
        resp = self._client.post(
            self._url,
            headers={**_HEADERS, "Authorization": f"Bearer {self._token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                  "params": {"uri": uri}},
        )
        data = resp.json()
        text = data.get("result", {}).get("contents", [{}])[0].get("text", "{}")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    def _extract(self, result: dict) -> Any:
        text = result.get("result", {}).get("content", [{}])[0].get("text", "{}")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    # ── Knowledge ──

    def ingest_knowledge(self, kb_name: str, concepts: list[dict]) -> dict:
        return self._extract(self._call("ingest_knowledge", {"kb_name": kb_name, "concepts": concepts}))

    def search_knowledge(self, kb_name: str, query: str, top_k: int = 5) -> list:
        r = self._extract(self._call("search_knowledge", {"kb_name": kb_name, "query": query, "top_k": top_k}))
        if isinstance(r, dict):
            return r.get("hits", [])
        return r if isinstance(r, list) else []

    # ── Memory ──

    def add_memory(self, messages: list[dict], metadata: dict | None = None) -> dict:
        return self._extract(self._call("add_memory", {"messages": messages, "metadata": metadata or {}}))

    def search_memory(self, query: str, top_k: int = 5, threshold: float = 0.0) -> list:
        r = self._extract(self._call("search_memory", {"query": query, "top_k": top_k, "threshold": threshold}))
        if isinstance(r, dict):
            return r.get("results", [])
        return r if isinstance(r, list) else []

    # ── Skill ──

    def register_skill(self, name: str, description: str, code: str, version: str = "1.0.0") -> dict:
        return self._extract(self._call("register_skill", {
            "name": name, "description": description, "code": code, "version": version}))

    def search_skill(self, query: str, top_k: int = 3) -> list:
        r = self._extract(self._call("search_skill", {"query": query, "top_k": top_k}))
        if isinstance(r, dict):
            return r.get("skills", r.get("hits", []))
        return r if isinstance(r, list) else []

    # ── Resources ──

    def list_knowledge(self) -> dict:
        return self._read("lake://knowledge")

    def memory_overview(self) -> dict:
        return self._read("lake://memory")

    def close(self):
        self._client.close()
