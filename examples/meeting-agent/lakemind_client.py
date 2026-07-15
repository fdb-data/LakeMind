import json
import os
import logging

import httpx

logger = logging.getLogger(__name__)


class LakeMindClient:
    """
    LakeMind REST API client for the meeting-agent example.

    API version status:
      - Storage endpoints (/api/v1/storage/*): data plane, version-agnostic — KEEP
      - Job endpoints (/api/v1/compute/jobs/*): v0.1.0 — v0.2.0 JobService requires
        published skills in assets table, not S3 packages. Bridge writes job_runs records.
      - Tenant creation (/api/v1/metadata/tenants): v0.1.0 — v0.2.0 security API has
        no POST /principals endpoint yet.
      - Embedding: ModelServing /v1/embeddings direct — v0.2.0 pattern.
      - Memory: via AssetMCP (MCP abstraction hides endpoint version).
    """
    def __init__(
        self,
        server_url: str | None = None,
        server_key: str | None = None,
        model_serving_url: str | None = None,
        model_serving_key: str | None = None,
        asset_mcp_url: str | None = None,
        asset_token: str | None = None,
        tenant_id: str | None = None,
    ):
        self.server_url = (server_url or os.environ.get("SERVER_API_URL", "http://localhost:10823")).rstrip("/")
        self.server_key = server_key or os.environ.get("SERVER_API_KEY", "lakemind-internal-api-key")
        self.ms_url = (model_serving_url or os.environ.get("MODEL_SERVING_URL", "http://localhost:10824")).rstrip("/")
        self.ms_key = model_serving_key or os.environ.get("MODELSERVING_API_KEY", "lakemind-modelserving-key")
        self.asset_mcp_url = asset_mcp_url or os.environ.get("ASSET_MCP_URL", "http://localhost:8401/mcp")
        self.asset_token = asset_token or os.environ.get("ASSET_TOKEN", "test-business-token")
        self.tenant_id = tenant_id or os.environ.get("TENANT_ID", "examples-meeting-agent")
        self.skill_uri = os.environ.get("SKILL_URI", "lake://skills/meeting-processing")
        self._http = httpx.AsyncClient(timeout=120)

    async def close(self):
        await self._http.aclose()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.server_key}",
            "X-Tenant-Id": self.tenant_id,
        }

    # ── S3 ──────────────────────────────────────────────────────

    async def s3_put(self, uri: str, data: bytes) -> dict:
        from urllib.parse import urlparse
        p = urlparse(uri)
        url = f"{self.server_url}/api/v1/storage/objects/{p.netloc}/{p.path.lstrip('/')}"
        resp = await self._http.put(url, content=data, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def s3_get(self, uri: str) -> bytes:
        from urllib.parse import urlparse
        p = urlparse(uri)
        url = f"{self.server_url}/api/v1/storage/objects/{p.netloc}/{p.path.lstrip('/')}"
        resp = await self._http.get(url, headers=self._headers)
        resp.raise_for_status()
        return resp.content

    async def s3_exists(self, uri: str) -> bool:
        from urllib.parse import urlparse
        p = urlparse(uri)
        url = f"{self.server_url}/api/v1/storage/objects/{p.netloc}/{p.path.lstrip('/')}"
        resp = await self._http.head(url, headers=self._headers)
        return resp.status_code == 200

    # ── Ray Jobs (Server REST API) ──────────────────────────────

    async def submit_job(self, job_name: str, params: dict, task_id: str = "") -> dict:
        resp = await self._http.post(
            f"{self.server_url}/api/v1/compute/jobs/submit",
            headers=self._headers,
            json={
                "skill_uri": self.skill_uri,
                "job_name": job_name,
                "params": params,
                "task_id": task_id,
                "env_overrides": {},
                "resources": {},
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_job_status(self, job_id: str) -> dict:
        resp = await self._http.get(
            f"{self.server_url}/api/v1/compute/jobs/{job_id}",
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    async def list_jobs(self, status: str = "") -> dict:
        params = {}
        if status:
            params["status"] = status
        resp = await self._http.get(
            f"{self.server_url}/api/v1/compute/jobs",
            headers=self._headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    async def poll_job(self, job_id: str, interval: float = 1.5, timeout: float = 120) -> dict:
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout
        max_retries = 3
        while True:
            retry = 0
            while retry < max_retries:
                try:
                    status = await self.get_job_status(job_id)
                    break
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    retry += 1
                    if retry >= max_retries:
                        raise
                    logger.warning("poll_job %s: transient error (retry %d/%d): %r", job_id, retry, max_retries, e)
                    await asyncio.sleep(interval * retry)
            else:
                raise RuntimeError(f"poll_job {job_id}: exhausted retries")
            s = status.get("status", "")
            if s in ("SUCCEEDED", "STOPPED", "FAILED", "completed", "cancelled", "failed"):
                return status
            if asyncio.get_event_loop().time() > deadline:
                try:
                    await self._http.post(
                        f"{self.server_url}/api/v1/compute/jobs/{job_id}/cancel",
                        headers=self._headers, timeout=10,
                    )
                    logger.warning("poll_job %s: timed out after %ss, cancelled job", job_id, timeout)
                except Exception:
                    logger.warning("poll_job %s: timed out after %ss, cancel failed", job_id, timeout)
                raise TimeoutError(f"job {job_id} timed out after {timeout}s (last status: {s})")
            await asyncio.sleep(interval)

    # ── Knowledge Search (read-only, agent direct) ──────────────

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
            headers=self._headers,
            json={"query_vec": query_vec, "top_k": top_k},
            timeout=30,
        )
        if resp.status_code in (404, 500):
            return {"query": query, "hits": [], "count": 0}
        resp.raise_for_status()
        data = resp.json()
        return {"query": query, "hits": data.get("results", []), "count": data.get("count", 0)}

    # ── AssetMCP (memory) ───────────────────────────────────────

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

    async def add_memory(self, messages: list[dict], metadata: dict | None = None) -> dict:
        args = {"messages": messages, "infer": False}
        if metadata:
            args["metadata"] = metadata
        return await self._call_mcp("add_memory", args)

    # ── Tenant & Iceberg table management ───────────────────────

    async def ensure_tenant(self, tenant_id: str, name: str) -> dict:
        resp = await self._http.post(
            f"{self.server_url}/api/v1/metadata/tenants",
            headers=self._headers,
            json={"tenant_id": tenant_id, "name": name},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    async def create_table(self, namespace: str, table: str, schema: dict[str, str]) -> dict:
        resp = await self._http.post(
            f"{self.server_url}/api/v1/storage/tables/",
            headers=self._headers,
            json={"namespace": namespace, "table": table, "schema": schema},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    async def table_exists(self, namespace: str, table: str) -> bool:
        resp = await self._http.get(
            f"{self.server_url}/api/v1/storage/tables/{namespace}",
            headers=self._headers,
            timeout=10,
        )
        if resp.status_code != 200:
            return False
        tables = resp.json().get("tables", [])
        return table in tables

    async def append_rows(self, namespace: str, table: str, rows: list[dict]) -> dict:
        resp = await self._http.post(
            f"{self.server_url}/api/v1/storage/tables/{namespace}/{table}/append",
            headers=self._headers,
            json={"rows": rows},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    async def scan_table(self, namespace: str, table: str, limit: int = 1000) -> list[dict]:
        resp = await self._http.get(
            f"{self.server_url}/api/v1/storage/tables/{namespace}/{table}/scan",
            headers=self._headers,
            params={"limit": limit},
            timeout=30,
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("rows", [])

    # ── Audio conversion (agent responsibility) ─────────────────

    @staticmethod
    def convert_to_wav(audio: bytes) -> bytes:
        import tempfile, subprocess
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
