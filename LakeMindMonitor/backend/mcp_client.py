"""MCP 只读客户端封装。

复用单个 streamable HTTP 会话读取 MCP 资源。仅暴露 read_resource / call_tool，
BFF 只调只读资源 + lake://system/health，不调写工具。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .config import Config

_log = logging.getLogger("lakemind.monitor")
__all__ = ["McpReadClient"]


class McpReadClient:
    def __init__(self, config: Config) -> None:
        self._url = config.mcp.url
        self._token = config.mcp.read_token
        self._cm = None
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        self._cm = streamablehttp_client(
            self._url, headers={"Authorization": f"Bearer {self._token}"}
        )
        read, write, _ = await self._cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

    async def close(self) -> None:
        try:
            if self._session is not None:
                await self._session.__aexit__(None, None, None)
            if self._cm is not None:
                await self._cm.__aexit__(None, None, None)
        except Exception:
            pass
        self._session = None
        self._cm = None

    async def read_resource(self, uri: str) -> Any:
        if self._session is None:
            raise RuntimeError("MCP client not connected")
        res = await self._session.read_resource(uri)
        text = res.contents[0].text if res.contents else ""
        try:
            return json.loads(text)
        except Exception:
            return text

    async def call_tool(self, name: str, arguments: dict | None = None) -> Any:
        if self._session is None:
            raise RuntimeError("MCP client not connected")
        res = await self._session.call_tool(name, arguments or {})
        text = res.content[0].text if res.content else ""
        try:
            return json.loads(text)
        except Exception:
            return text

    @property
    def connected(self) -> bool:
        return self._session is not None
