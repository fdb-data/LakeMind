import asyncio
import json
import os
import logging

import httpx

logger = logging.getLogger(__name__)


class LakeMindClient:
    def __init__(
        self,
        server_url: str | None = None,
        server_key: str | None = None,
        model_serving_url: str | None = None,
        model_serving_key: str | None = None,
        asset_mcp_url: str | None = None,
        asset_token: str | None = None,
        tenant_id: str = "retail",
    ):
        self.server_url = (server_url or os.environ.get("SERVER_API_URL", "http://localhost:10823")).rstrip("/")
        self.server_key = server_key or os.environ.get("SERVER_API_KEY", "lakemind-internal-api-key")
        self.ms_url = (model_serving_url or os.environ.get("MODEL_SERVING_URL", "http://localhost:10824")).rstrip("/")
        self.ms_key = model_serving_key or os.environ.get("MODELSERVING_API_KEY", "lakemind-modelserving-key")
        self.asset_mcp_url = asset_mcp_url or os.environ.get("ASSET_MCP_URL", "http://localhost:8401/mcp")
        self.asset_token = asset_token or os.environ.get("ASSET_TOKEN", "test-business-token")
        self.tenant_id = tenant_id or os.environ.get("TENANT_ID", "retail")
        self._http = httpx.AsyncClient(timeout=120)

    async def close(self):
        await self._http.aclose()

    # ── S3 (REST API, binary-safe) ──────────────────────────────

    async def s3_put(self, uri: str, data: bytes) -> dict:
        from urllib.parse import urlparse
        p = urlparse(uri)
        url = f"{self.server_url}/api/v1/storage/objects/{p.netloc}/{p.path.lstrip('/')}"
        resp = await self._http.put(url, content=data, headers={"Authorization": f"Bearer {self.server_key}"})
        resp.raise_for_status()
        return resp.json()

    async def s3_get(self, uri: str) -> bytes:
        from urllib.parse import urlparse
        p = urlparse(uri)
        url = f"{self.server_url}/api/v1/storage/objects/{p.netloc}/{p.path.lstrip('/')}"
        resp = await self._http.get(url, headers={"Authorization": f"Bearer {self.server_key}"})
        resp.raise_for_status()
        return resp.content

    async def s3_exists(self, uri: str) -> bool:
        from urllib.parse import urlparse
        p = urlparse(uri)
        url = f"{self.server_url}/api/v1/storage/objects/{p.netloc}/{p.path.lstrip('/')}"
        resp = await self._http.head(url, headers={"Authorization": f"Bearer {self.server_key}"})
        return resp.status_code == 200

    # ── ModelServing: ASR ───────────────────────────────────────

    @staticmethod
    def _convert_to_wav(audio: bytes) -> bytes:
        import tempfile, subprocess, os
        if audio[:4] == b'RIFF':
            return audio
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as inf:
            inf.write(audio)
            in_path = inf.name
        out_path = in_path + ".wav"
        try:
            ffmpeg_bin = os.environ.get("FFMPEG_PATH", "ffmpeg")
            result = subprocess.run(
                [ffmpeg_bin, "-y", "-i", in_path, "-f", "wav", "-ar", "16000", "-ac", "1", out_path],
                capture_output=True, timeout=30,
            )
            if result.returncode != 0 or not os.path.exists(out_path):
                logger.warning("ffmpeg conversion failed: %s", result.stderr[:200])
                return audio
            with open(out_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.warning("ffmpeg exception: %s", e)
            return audio
        finally:
            for p in (in_path, out_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    async def asr(self, audio: bytes, filename: str = "audio.wav") -> dict:
        wav_audio = self._convert_to_wav(audio)
        resp = await self._http.post(
            f"{self.ms_url}/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {self.ms_key}"},
            files={"file": ("audio.wav", wav_audio, "audio/wav")},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    # ── ModelServing: LLM ───────────────────────────────────────

    async def llm_chat(self, system_prompt: str, user_content: str, model: str = "deepseek-v4-flash") -> str:
        resp = await self._http.post(
            f"{self.ms_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.ms_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    # ── Knowledge (AssetMCP) ────────────────────────────────────

    async def _call_mcp(self, tool: str, arguments: dict) -> dict:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession

        async with streamablehttp_client(
            self.asset_mcp_url,
            headers={"Authorization": f"Bearer {self.asset_token}"},
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments=arguments)
                if result.isError:
                    raise RuntimeError(f"MCP tool {tool} error: {result.content}")
                return json.loads(result.content[0].text)

    async def search_knowledge(self, query: str, kb_name: str | None = None, top_k: int = 5) -> dict:
        resp = await self._http.post(
            f"{self.ms_url}/v1/embeddings",
            headers={"Authorization": f"Bearer {self.ms_key}"},
            json={"model": "jina-embeddings-v2-base-zh", "input": [query]},
            timeout=30,
        )
        resp.raise_for_status()
        query_vec = resp.json()["data"][0]["embedding"]

        db = f"tenant_{self.tenant_id}"
        table = f"kb_{kb_name}" if kb_name else ""
        url = f"{self.server_url}/api/v1/storage/vectors/{db}/{table}/search"
        resp = await self._http.post(
            url,
            headers={"Authorization": f"Bearer {self.server_key}"},
            json={"query_vec": query_vec, "top_k": top_k},
            timeout=30,
        )
        if resp.status_code in (404, 500):
            return {"query": query, "hits": [], "count": 0}
        resp.raise_for_status()
        data = resp.json()
        return {"query": query, "hits": data.get("results", []), "count": data.get("count", 0)}

    async def register_knowledge(self, name: str, description: str | None = None) -> dict:
        args = {"name": name}
        if description:
            args["description"] = description
        return await self._call_mcp("register_knowledge", args)

    async def ingest_knowledge(self, kb_name: str, concepts: list[dict]) -> dict:
        db = f"tenant_{self.tenant_id}"
        table = f"kb_{kb_name}"
        data = []
        for concept in concepts:
            fm = concept.get("frontmatter", {})
            title = fm.get("title", concept.get("title", ""))
            body = concept.get("body", "")
            text = f"{title}\n{body}"
            
            resp = await self._http.post(
                f"{self.ms_url}/v1/embeddings",
                headers={"Authorization": f"Bearer {self.ms_key}"},
                json={"model": "jina-embeddings-v2-base-zh", "input": [text]},
                timeout=30,
            )
            resp.raise_for_status()
            vec = resp.json()["data"][0]["embedding"]
            
            import time as _time
            data.append({
                "concept_id": fm.get("resource", f"{kb_name}_{int(_time.time()*1000)}"),
                "type": fm.get("type", "Concept"),
                "title": title,
                "description": body[:500],
                "tags": fm.get("tags", []),
                "s3_uri": "",
                "vector": vec,
                "created_at": _time.time(),
            })
        
        resp = await self._http.post(
            f"{self.server_url}/api/v1/storage/vectors/{db}",
            headers={"Authorization": f"Bearer {self.server_key}"},
            json={"name": table, "data": data, "mode": "append"},
            timeout=30,
        )
        if resp.status_code == 500:
            resp = await self._http.post(
                f"{self.server_url}/api/v1/storage/vectors/{db}",
                headers={"Authorization": f"Bearer {self.server_key}"},
                json={"name": table, "data": data, "mode": "overwrite"},
                timeout=30,
            )
        resp.raise_for_status()
        return {"kb_name": kb_name, "ingested": len(data)}

    async def list_knowledge(self) -> dict:
        return await self._call_mcp("list_knowledge", {})

    async def add_memory(self, messages: list[dict], metadata: dict | None = None) -> dict:
        args = {"messages": messages, "infer": False}
        if metadata:
            args["metadata"] = metadata
        return await self._call_mcp("add_memory", args)
