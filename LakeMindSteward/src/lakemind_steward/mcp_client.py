"""MCP client for all 3 MCPs."""
from __future__ import annotations
import httpx
from .config import McpCfg

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}

class McpClient:
    def __init__(self, cfg: McpCfg) -> None:
        self._cfg = cfg
        self._client = httpx.AsyncClient(timeout=60.0)

    async def call(self, face: str, tool: str, arguments: dict | None = None) -> dict:
        ep = getattr(self._cfg, face)
        resp = await self._client.post(
            ep.url,
            headers={**HEADERS, "Authorization": f"Bearer {ep.token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": tool, "arguments": arguments or {}}},
        )
        return resp.json()

    async def read(self, face: str, uri: str) -> dict:
        ep = getattr(self._cfg, face)
        resp = await self._client.post(
            ep.url,
            headers={**HEADERS, "Authorization": f"Bearer {ep.token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                  "params": {"uri": uri}},
        )
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()
