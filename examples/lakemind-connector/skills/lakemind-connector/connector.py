"""
LakeMind 连接器 — 通过 MCP (AssetMCP + AdminMCP) + ModelServing + Server REST 存取认知资产。

架构:
    AssetMCP (:8401)  → 知识/记忆/技能/本体 (23 tools, MCP protocol)
    AdminMCP (:8403)  → 租户/Token/健康 (17 tools, MCP protocol)
    ModelServing (:10824) → Embedding / LLM (REST API)
    Server (:10823)   → 向量存储 (REST API, 绕过 AssetMCP embedding 端点未 mount 的问题)
"""

from __future__ import annotations

import json
import logging
import os
import time

import httpx
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

logger = logging.getLogger(__name__)


class LakeMindConnector:
    """LakeMind 统一连接器，封装 MCP + REST 全部接口。"""

    def __init__(
        self,
        asset_mcp_url: str | None = None,
        admin_mcp_url: str | None = None,
        server_url: str | None = None,
        server_key: str | None = None,
        model_serving_url: str | None = None,
        model_serving_key: str | None = None,
        tenant_token: str | None = None,
        admin_token: str | None = None,
        tenant_id: str = "opencode",
    ):
        self.asset_mcp_url = asset_mcp_url or os.environ.get("ASSET_MCP_URL", "http://localhost:8401/mcp")
        self.admin_mcp_url = admin_mcp_url or os.environ.get("ADMIN_MCP_URL", "http://localhost:8403/mcp")
        self.server_url = (server_url or os.environ.get("SERVER_API_URL", "http://localhost:10823")).rstrip("/")
        self.server_key = server_key or os.environ.get("SERVER_API_KEY", "lakemind-internal-api-key")
        self.ms_url = (model_serving_url or os.environ.get("MODEL_SERVING_URL", "http://localhost:10824")).rstrip("/")
        self.ms_key = model_serving_key or os.environ.get("MODELSERVING_API_KEY", "lakemind-modelserving-key")
        self.tenant_token = tenant_token or os.environ.get("OPENCODE_TOKEN", "tk_9d377e74c0c14969")
        self.admin_token = admin_token or os.environ.get("ADMIN_TOKEN", "test-steward-token")
        self.tenant_id = tenant_id or os.environ.get("TENANT_ID", "opencode")

        self._http = httpx.AsyncClient(timeout=120)
        self._embedding_model = "jina-embeddings-v2-base-zh"
        self._llm_model = "deepseek-v4-flash"

    async def close(self):
        await self._http.aclose()

    @property
    def _db(self) -> str:
        return f"tenant_{self.tenant_id}"

    def _table(self, kb_name: str) -> str:
        return f"kb_{kb_name}"

    @property
    def _server_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.server_key}"}

    @property
    def _ms_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.ms_key}"}

    # ── MCP 调用 ──────────────────────────────────────────────

    async def _call_asset_mcp(self, tool: str, arguments: dict) -> dict:
        async with streamablehttp_client(
            self.asset_mcp_url, headers={"Authorization": f"Bearer {self.tenant_token}"}
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments=arguments)
                if result.isError:
                    raise RuntimeError(f"AssetMCP {tool}: {result.content}")
                return json.loads(result.content[0].text)

    async def _call_admin_mcp(self, tool: str, arguments: dict) -> dict:
        async with streamablehttp_client(
            self.admin_mcp_url, headers={"Authorization": f"Bearer {self.admin_token}"}
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments=arguments)
                if result.isError:
                    raise RuntimeError(f"AdminMCP {tool}: {result.content}")
                return json.loads(result.content[0].text)

    async def list_mcp_tools(self) -> dict:
        result = {}
        for name, url, token in [
            ("AssetMCP", self.asset_mcp_url, self.tenant_token),
            ("AdminMCP", self.admin_mcp_url, self.admin_token),
        ]:
            async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    result[name] = [t.name for t in tools.tools]
        return result

    # ── Embedding & LLM (ModelServing) ────────────────────────

    async def embed(self, text: str) -> list[float]:
        r = await self._http.post(
            f"{self.ms_url}/v1/embeddings",
            headers=self._ms_headers,
            json={"model": self._embedding_model, "input": [text]},
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]

    async def llm_chat(self, system_prompt: str, user_content: str) -> str:
        r = await self._http.post(
            f"{self.ms_url}/v1/chat/completions",
            headers=self._ms_headers,
            json={
                "model": self._llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # ── 知识 (向量存储, Server REST) ──────────────────────────

    async def store_knowledge(self, kb_name: str, concepts: list[dict]) -> int:
        table = self._table(kb_name)
        data = []
        for c in concepts:
            fm = c.get("frontmatter", {})
            title = fm.get("title", c.get("title", ""))
            body = c.get("body", "")
            text = f"{title}\n{body}"
            vec = await self.embed(text)
            data.append({
                "concept_id": f"{kb_name}_{int(time.time() * 1000)}_{len(data)}",
                "type": fm.get("type", c.get("type", "knowledge")),
                "title": title,
                "description": body[:500],
                "tags": fm.get("tags", c.get("tags", [])),
                "s3_uri": "",
                "vector": vec,
                "created_at": time.time(),
            })

        r = await self._http.post(
            f"{self.server_url}/api/v1/storage/vectors/{self._db}",
            headers=self._server_headers,
            json={"name": table, "data": data, "mode": "append"},
        )
        if r.status_code == 500:
            r = await self._http.post(
                f"{self.server_url}/api/v1/storage/vectors/{self._db}",
                headers=self._server_headers,
                json={"name": table, "data": data, "mode": "overwrite"},
            )
        r.raise_for_status()
        logger.info("[OK] store_knowledge: %d concepts -> %s", len(data), table)
        return len(data)

    async def search_knowledge(self, query: str, kb_name: str, top_k: int = 5) -> list[dict]:
        table = self._table(kb_name)
        vec = await self.embed(query)
        r = await self._http.post(
            f"{self.server_url}/api/v1/storage/vectors/{self._db}/{table}/search",
            headers=self._server_headers,
            json={"query_vec": vec, "top_k": top_k},
        )
        if r.status_code in (404, 500):
            return []
        r.raise_for_status()
        return r.json().get("results", [])

    async def describe_knowledge(self, kb_name: str) -> dict:
        table = self._table(kb_name)
        r = await self._http.get(
            f"{self.server_url}/api/v1/storage/vectors/{self._db}/{table}",
            headers=self._server_headers,
        )
        r.raise_for_status()
        return r.json()

    async def scan_knowledge(self, kb_name: str, limit: int = 100) -> list[dict]:
        table = self._table(kb_name)
        r = await self._http.get(
            f"{self.server_url}/api/v1/storage/vectors/{self._db}/{table}/scan",
            headers=self._server_headers,
            params={"limit": limit},
        )
        r.raise_for_status()
        return r.json().get("results", [])

    async def list_knowledge_bases(self) -> list[str]:
        r = await self._http.get(
            f"{self.server_url}/api/v1/storage/vectors/{self._db}",
            headers=self._server_headers,
        )
        r.raise_for_status()
        return [t for t in r.json().get("tables", []) if t.startswith("kb_")]

    # ── 记忆 (AssetMCP) ───────────────────────────────────────

    async def add_memory(self, messages: list[dict], metadata: dict | None = None) -> dict:
        args = {"messages": messages, "infer": False}
        if metadata:
            args["metadata"] = metadata
        return await self._call_asset_mcp("add_memory", args)

    async def search_memory(self, query: str, top_k: int = 5) -> dict:
        return await self._call_asset_mcp("search_memory", {"query": query, "top_k": top_k})

    async def list_memory(self, page: int = 1, page_size: int = 20) -> dict:
        return await self._call_asset_mcp("list_memory", {"page": page, "page_size": page_size})

    async def get_memory(self, memory_id: str) -> dict:
        return await self._call_asset_mcp("get_memory", {"memory_id": memory_id})

    async def delete_memory(self, memory_id: str) -> dict:
        return await self._call_asset_mcp("delete_memory", {"memory_id": memory_id})

    async def clear_memory(self) -> dict:
        return await self._call_asset_mcp("clear_memory", {})

    # ── 租户管理 (AdminMCP) ───────────────────────────────────

    async def create_tenant(self, tenant_id: str, name: str, description: str = "") -> dict:
        return await self._call_admin_mcp("create_tenant", {
            "tenant_id": tenant_id, "name": name, "description": description,
        })

    async def issue_token(self, tenant_id: str, agent_id: str, scopes: list[str]) -> dict:
        return await self._call_admin_mcp("issue_token", {
            "tenant_id": tenant_id, "agent_id": agent_id, "scopes": scopes,
        })

    async def list_tenants(self) -> dict:
        return await self._call_admin_mcp("list_tenants", {})

    async def platform_health(self) -> dict:
        return await self._call_admin_mcp("get_platform_health", {})

    # ── S3 (Server REST) ──────────────────────────────────────

    async def s3_put(self, bucket: str, key: str, data: bytes) -> dict:
        r = await self._http.put(
            f"{self.server_url}/api/v1/storage/objects/{bucket}/{key}",
            content=data, headers=self._server_headers,
        )
        r.raise_for_status()
        return r.json()

    async def s3_get(self, bucket: str, key: str) -> bytes:
        r = await self._http.get(
            f"{self.server_url}/api/v1/storage/objects/{bucket}/{key}",
            headers=self._server_headers,
        )
        r.raise_for_status()
        return r.content

    async def s3_list(self, bucket: str, prefix: str = "") -> dict:
        r = await self._http.get(
            f"{self.server_url}/api/v1/storage/objects/{bucket}",
            headers=self._server_headers, params={"prefix": prefix},
        )
        r.raise_for_status()
        return r.json()
