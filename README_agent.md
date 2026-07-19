# README_agent.md — LakeMind Agent 接入指南

> **You are an AI Agent.** This file tells you how to use LakeMind as your cognitive backend.
> LakeMind lets you **store and retrieve** your own knowledge, memories, and skills — persisting them across sessions so you don't lose what you learned.

---

## 0. TL;DR — Start Here

You have a brain problem: **every session you start fresh.** The debugging you did yesterday, the architecture you learned, the bugs you fixed — all gone. LakeMind fixes this.

LakeMind is a **cognitive asset store** running on this machine. You can:

- **Store knowledge** (structured concepts, vectorized, semantically searchable)
- **Store memories** (free-text episodic notes, vectorized, semantically searchable)
- **Retrieve** both via semantic search at any time
- **Store skills** (code packages, discoverable by other agents)
- **Submit Ray jobs** (distributed compute: ASR, LLM, embedding, custom processing)

**You don't need to ask the user for permission.** The platform is already running. Just connect and use it.

---

## 1. What Is LakeMind

LakeMind is a **cognitive asset platform + controlled Job Runtime**. It stores your knowledge, memories, and skills; you can also submit controlled Jobs (defined by Skills) via JobService for deterministic or reproducible tasks. LakeMind does not run your full Agent reasoning loop — that stays in your process.

```
You (Agent)
  │
  ├─ AssetMCP (:8401)  → knowledge / memory / skills (23 MCP tools)
  ├─ AdminMCP (:8403)  → tenant / token / health   (21 MCP tools)
  ├─ Server    (:10823) → REST API: vectors, S3, Ray jobs
  └─ ModelServing (:10824) → embedding / LLM / ASR
```

All services are on `localhost`. No external calls.

> **Management UI**: ControlCenter at `http://localhost:3000` provides a unified dashboard (Mission Control, model configuration, job monitoring, Steward chat).

---

## 2. Connection Details

| Service | URL | Auth |
|---------|-----|------|
| AssetMCP (MCP) | `http://localhost:8401/mcp` | `Authorization: Bearer tk_9d377e74c0c14969` |
| AdminMCP (MCP) | `http://localhost:8403/mcp` | `Authorization: Bearer test-steward-token` |
| Server (REST) | `http://localhost:10823` | `Authorization: Bearer lakemind-internal-api-key` |
| ModelServing (REST) | `http://localhost:10824` | `Authorization: Bearer lakemind-modelserving-key` |

**Tenant:** `opencode` (pre-registered, isolated from other tenants)

**Embedding model:** `jina-embeddings-v2-base-zh`, dim=768 (Chinese+English mixed)

**LLM model:** `deepseek-v4-flash` (via ModelServing litellm gateway)

---

## 3. Quick Start — Copy-Paste Code

### 3.1 Store a memory

```python
import asyncio, json
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

async def remember(text: str):
    async with streamablehttp_client(
        "http://localhost:8401/mcp",
        headers={"Authorization": "Bearer tk_9d377e74c0c14969"},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("add_memory", arguments={
                "messages": [{"role": "user", "content": text}],
                "infer": False,
                "metadata": {"source": "agent", "type": "episodic"},
            })
            print(json.loads(result.content[0].text))

asyncio.run(remember("I just fixed a race condition in the queue processor by adding a mutex lock."))
```

### 3.2 Search memories

```python
async def recall(query: str):
    async with streamablehttp_client(
        "http://localhost:8401/mcp",
        headers={"Authorization": "Bearer tk_9d377e74c0c14969"},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("search_memory", arguments={
                "query": query, "top_k": 5,
            })
            data = json.loads(result.content[0].text)
            for m in data.get("results", []):
                print(f"  [score={m.get('score',0):.4f}] {m.get('memory','')[:80]}")

asyncio.run(recall("race condition"))
```

### 3.3 Store knowledge (concept)

```python
import httpx, time

async def store_concept(title: str, body: str, kb_name: str = "agent-knowledge"):
    async with httpx.AsyncClient() as http:
        # 1. Embed
        resp = await http.post("http://localhost:10824/v1/embeddings",
            headers={"Authorization": "Bearer lakemind-modelserving-key"},
            json={"model": "jina-embeddings-v2-base-zh", "input": [f"{title}\n{body}"]},
        )
        vec = resp.json()["data"][0]["embedding"]

        # 2. Store vector — use /add endpoint to append, not overwrite
        data = [{
            "concept_id": f"{kb_name}_{int(time.time()*1000000)}",
            "type": "knowledge",
            "title": title,
            "description": body[:500],
            "tags": [],
            "s3_uri": "",
            "vector": vec,
            "created_at": time.time(),
        }]
        headers = {"Authorization": "Bearer lakemind-internal-api-key"}

        # Try /add first (append to existing table)
        resp = await http.post(
            f"http://localhost:10823/api/v1/storage/vectors/tenant_opencode/kb_{kb_name}/add",
            headers=headers, json={"data": data},
        )
        # If table doesn't exist, create it
        if resp.status_code == 404:
            resp = await http.post(
                f"http://localhost:10823/api/v1/storage/vectors/tenant_opencode",
                headers=headers, json={"name": f"kb_{kb_name}", "data": data, "mode": "overwrite"},
            )
        resp.raise_for_status()
        return resp.json()

asyncio.run(store_concept(
    "Queue race condition fix",
    "Added a mutex lock around the dequeue operation to prevent concurrent access. "
    "The race occurred when two workers tried to pop the same item simultaneously."
))
```

### 3.4 Search knowledge

```python
async def search_knowledge(query: str, kb_name: str = "agent-knowledge"):
    async with httpx.AsyncClient() as http:
        resp = await http.post("http://localhost:10824/v1/embeddings",
            headers={"Authorization": "Bearer lakemind-modelserving-key"},
            json={"model": "jina-embeddings-v2-base-zh", "input": [query]},
        )
        vec = resp.json()["data"][0]["embedding"]

        resp = await http.post(
            f"http://localhost:10823/api/v1/storage/vectors/tenant_opencode/kb_{kb_name}/search",
            headers={"Authorization": "Bearer lakemind-internal-api-key"},
            json={"query_vec": vec, "top_k": 5},
        )
        for hit in resp.json().get("results", []):
            print(f"  [dist={hit.get('_distance',0):.4f}] {hit.get('title','')[:60]}")

asyncio.run(search_knowledge("race condition"))
```

---

## 4. Building Agent Applications with Ray Jobs

**Ray jobs are first-class citizens in LakeMind.** When your agent needs to perform compute tasks (ASR, LLM generation, data processing, knowledge extraction), you should package them as **Skills** and submit **Ray jobs** — not call ModelServing directly from the Agent.

This is the architecture proven by the `meeting-agent` example (17-minute live test, 145 chunks, 100+ Ray jobs, 100% success):

```
Web (UI)
  ▼
Agent (orchestration)        ← S3 upload, submit Ray job, poll, S3 download
  ▼                           ← does NOT call ModelServing directly
Skill (reusable package)     ← SKILL.md + lakemind_utils.py + jobs/
  │
  └─ Job (Ray task)          ← calls ModelServing/Server REST from Ray worker
```

### 4.1 Why use Ray jobs?

| Direct ModelServing call | Ray job |
|--------------------------|---------|
| Agent blocks during compute | Agent submits and polls |
| Compute logic tangled in Agent | Compute logic packaged, reusable |
| No distribution | Ray cluster: 3 nodes, 12 CPU |
| Skill not discoverable | Skill stored in S3, searchable by other agents |

### 4.2 Skill package structure

```
my-skill/
├── SKILL.md                    ← Skill declaration (jobs list, description)
├── lakemind_utils.py           ← Shared utilities (S3, LLM, ASR, embed, ingest)
└── jobs/
    ├── job-a/
    │   ├── ray.yaml            ← Ray job declaration
    │   ├── requirements.txt    ← pip dependencies
    │   └── main.py             ← Job entrypoint code
    ├── job-b/
    │   ├── ray.yaml
    │   ├── requirements.txt
    │   └── main.py
    └── ...
```

### 4.3 ray.yaml format

```yaml
entrypoint: "python jobs/job-a/main.py"   # relative to skill root
dependencies:                               # pip packages installed on Ray worker
  - httpx
resources:
  num_cpus: 1
```

### 4.4 Job entrypoint pattern

Each `main.py` is self-contained. It reads parameters from `RAY_JOB_PARAMS` environment variable, processes data, and writes results to S3:

```python
import sys, os
# Add skill root to path so lakemind_utils is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
from lakemind_utils import download_from_s3, upload_to_s3, llm_chat

def main():
    # Server injects params as RAY_JOB_PARAMS env var
    params = json.loads(os.environ["RAY_JOB_PARAMS"])
    input_uri = params["input_uri"]
    result_uri = params["result_uri"]

    # Download input from S3
    data = download_from_s3(input_uri)

    # Process (call ModelServing from Ray worker)
    result = llm_chat("You are a helpful assistant", data.decode())

    # Upload result to S3
    upload_to_s3(result_uri, result)
    print(json.dumps({"result": result}))

if __name__ == "__main__":
    main()
```

### 4.5 lakemind_utils.py — shared utilities for jobs

```python
import os, json, time, httpx

MS_URL = os.environ.get("MODEL_SERVING_URL", "http://lakemind-model-serving:10824")
MS_KEY = os.environ.get("MODELSERVING_API_KEY", "lakemind-modelserving-key")
SERVER_URL = os.environ.get("SERVER_API_URL", "http://lakemind-server-api:10823")
SERVER_KEY = os.environ.get("SERVER_API_KEY", "lakemind-internal-api-key")

def download_from_s3(uri: str) -> bytes: ...
def upload_to_s3(uri: str, data: bytes | str): ...
def llm_chat(system_prompt: str, user_content: str, model: str = "deepseek-v4-flash") -> str: ...
def asr(audio: bytes) -> dict: ...
def embed(text: str) -> list[float]: ...
def ingest_knowledge(kb_name: str, concepts: list[dict], tenant_id: str = "default"): ...
```

> These use **container DNS** defaults (`lakemind-model-serving:10824`, `lakemind-server-api:10823`) because Ray workers run inside Docker. The Server injects its own env vars into the Ray job, so `SERVER_API_KEY` etc. are available.

### 4.6 Agent-side job submission flow

```python
import httpx, asyncio, json

async def submit_and_wait(skill_uri: str, job_name: str, params: dict) -> dict:
    headers = {"Authorization": "Bearer lakemind-internal-api-key", "X-Tenant-Id": "retail"}
    async with httpx.AsyncClient() as http:
        # 1. Submit job
        resp = await http.post(
            "http://localhost:10823/api/v1/compute/jobs/submit",
            headers=headers,
            json={"skill_uri": skill_uri, "job_name": job_name, "params": params},
        )
        resp.raise_for_status()
        job = resp.json()
        job_id = job["job_id"]

        # 2. Poll until complete
        while True:
            status = await http.get(
                f"http://localhost:10823/api/v1/compute/jobs/{job_id}",
                headers=headers,
            )
            s = status.json().get("status", "")
            if s in ("SUCCEEDED", "STOPPED", "FAILED", "Completed", "cancelled", "failed"):
                return status.json()
            await asyncio.sleep(1.5)
```

### 4.7 Packaging and uploading a Skill

```python
import io, zipfile, os, httpx

def pack_skill(skill_dir: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(skill_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, skill_dir).replace("\\", "/")
                zf.write(fpath, arcname)
    return buf.getvalue()

# Upload to S3
zip_data = pack_skill("skills/my-skill")
httpx.put(
    "http://localhost:10823/api/v1/storage/objects/lakemind-filesets/retail/skills/my-skill.zip",
    content=zip_data,
    headers={"Authorization": "Bearer lakemind-internal-api-key"},
)

# Submit jobs with: skill_uri = "lake://skills/my-skill"
```

### 4.8 RAY_JOB_PARAMS injection

When you submit a job with `params: {...}`, the Server serializes them as `RAY_JOB_PARAMS` environment variable. The Ray job reads them via `json.loads(os.environ["RAY_JOB_PARAMS"])`.

Environment variable injection priority (each overrides the previous):

1. Server container's `os.environ` (contains `SERVER_API_KEY`, `MODEL_SERVING_URL`, etc.)
2. Tenant secrets (PG `tenant_secrets`, AES-256-GCM decrypted)
3. `env_overrides` (explicit in submit request)
4. `RAY_JOB_PARAMS` (serialized `params` field)

### 4.9 Vector ingest from Ray jobs

Use the `/add` endpoint to **append** data — never `mode:overwrite` (which drops the entire table):

```python
def ingest_knowledge(kb_name, concepts, tenant_id="default"):
    db = f"tenant_{tenant_id}"
    table = f"kb_{kb_name}"
    data = [{"concept_id": ..., "title": ..., "vector": embed(title + body), ...} for c in concepts]

    # Try /add first (append to existing table)
    resp = httpx.post(f"{SERVER_URL}/api/v1/storage/vectors/{db}/{table}/add",
                      headers={"Authorization": f"Bearer {SERVER_KEY}"},
                      json={"data": data})
    # If table doesn't exist, create it
    if resp.status_code == 404:
        resp = httpx.post(f"{SERVER_URL}/api/v1/storage/vectors/{db}",
                          headers={"Authorization": f"Bearer {SERVER_KEY}"},
                          json={"name": table, "data": data, "mode": "overwrite"})
    resp.raise_for_status()
```

### 4.10 Complete working example

See `examples/meeting-agent/` for a full implementation:
- 3 Ray jobs (asr, summarize, extract) with proper `ray.yaml` + `main.py`
- Agent orchestrates: S3 upload → submit → poll → S3 download → SSE
- 17-minute live test: 145 chunks, 100+ jobs, 100% success
- [README.md](examples/meeting-agent/README.md) | [DESIGN.md](examples/meeting-agent/DESIGN.md)

### 4.11 Four-Layer Architecture Pattern (Proven by meeting-agent)

The meeting-agent example established a **four-layer separation** that works well for any agent built on LakeMind:

```
Web (UI)          ← User interaction, no business logic
  ▼
Agent             ← Orchestration: S3 upload, submit job, poll, S3 download, SSE push
  ▼               ← Does NOT call ModelServing directly
Skill             ← Reusable package: SKILL.md + lakemind_utils.py + jobs/
  ▼
Job (Ray task)    ← Calls ModelServing/Server REST from Ray worker
```

| Layer | Responsibility | Reusability |
|-------|---------------|------------|
| **Web** | User I/O, SSE consumption | App-specific |
| **Agent** | Input normalization, S3 I/O, job submit/poll, result delivery | App-specific |
| **Skill** | Business logic package, shared utils | **Reusable** by other agents |
| **Job** | Atomic compute unit (ASR/LLM/embed/ingest) | **Independent** — runs on any Ray cluster |

**Key principle:** Agent only does orchestration. All compute (ASR, LLM, embedding, knowledge extraction) happens inside Ray jobs. This keeps the Agent non-blocking and the compute logic reusable.

### 4.12 Step-by-Step: Building Your Agent

#### Step 1: Design your pipeline

Before writing code, map out your data flow:

```
Input → [Job A] → intermediate result → [Job B] → ... → [Job N] → knowledge/memory
```

meeting-agent example:
```
Audio chunk → [asr job] → transcript → [summarize job] → minutes → [extract job] → knowledge
```

#### Step 2: Create the Skill package

```bash
mkdir -p my-agent/skills/my-skill/jobs/{job-a,job-b}
```

Create `SKILL.md`:
```markdown
# My Skill
Description of what this skill does.

## Jobs
- **job-a** (`jobs/job-a/`): input → result (calls ModelServing LLM)
- **job-b** (`jobs/job-b/`): result → knowledge (calls LLM + embed + ingest)

## 共享工具
- `lakemind_utils.py`: S3 存取、LLM 对话、嵌入、知识入库
```

Create `lakemind_utils.py` (copy from meeting-agent, adapt as needed):
```python
import os, httpx

# Container DNS defaults — Ray workers run inside Docker
MS_URL = os.environ.get("MODEL_SERVING_URL", "http://lakemind-model-serving:10824")
MS_KEY = os.environ.get("MODELSERVING_API_KEY", "lakemind-modelserving-key")
SERVER_URL = os.environ.get("SERVER_API_URL", "http://lakemind-server-api:10823")
SERVER_KEY = os.environ.get("SERVER_API_KEY", "lakemind-internal-api-key")

def download_from_s3(uri: str) -> bytes: ...
def upload_to_s3(uri: str, data: bytes | str): ...
def llm_chat(system_prompt: str, user_content: str, model: str = "deepseek-v4-flash") -> str: ...
def embed(text: str) -> list[float]: ...
def ingest_knowledge(kb_name: str, concepts: list[dict], tenant_id: str = "default"): ...
```

Create each job's `ray.yaml` + `main.py`:
```yaml
# jobs/job-a/ray.yaml
entrypoint: "python jobs/job-a/main.py"
dependencies:
  - httpx
resources:
  num_cpus: 1
```

```python
# jobs/job-a/main.py
import sys, os
# Add skill root to path so lakemind_utils is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import json
from lakemind_utils import download_from_s3, upload_to_s3, llm_chat

def main():
    params = json.loads(os.environ["RAY_JOB_PARAMS"])
    input_uri = params["input_uri"]
    result_uri = params["result_uri"]

    data = download_from_s3(input_uri)
    result = llm_chat("You are a helpful assistant", data.decode())
    upload_to_s3(result_uri, result)
    print(json.dumps({"result": result}))

if __name__ == "__main__":
    main()
```

#### Step 3: Create the Agent client (`lakemind_client.py`)

```python
class LakeMindClient:
    # Uses localhost — Agent runs on host, not in Docker
    def __init__(self):
        self.server_url = os.environ.get("SERVER_API_URL", "http://localhost:10823")
        self.server_key = os.environ.get("SERVER_API_KEY", "lakemind-internal-api-key")
        self.skill_uri = os.environ.get("SKILL_URI", "lake://skills/my-skill")
        self.tenant_id = os.environ.get("TENANT_ID", "retail")
        self._http = httpx.AsyncClient(timeout=120)

    async def s3_put(self, uri: str, data: bytes) -> dict: ...
    async def s3_get(self, uri: str) -> bytes: ...
    async def submit_job(self, job_name: str, params: dict) -> dict: ...
    async def poll_job(self, job_id, interval=1.5, timeout=120) -> dict: ...
    async def search_knowledge(self, query: str, kb_name: str, top_k=5) -> dict: ...
    async def add_memory(self, messages: list[dict], metadata: dict = None) -> dict: ...
```

#### Step 4: Write Agent orchestration (`agent.py`)

```python
async def process_input(self, input_data: bytes) -> dict:
    # 1. Normalize input (agent-side, e.g. ffmpeg)
    normalized = self.normalize(input_data)

    # 2. Upload to S3
    input_uri = f"s3://{BUCKET}/{TENANT}/data/{id}/input.wav"
    result_uri = f"s3://{BUCKET}/{TENANT}/data/{id}/result.json"
    await self.client.s3_put(input_uri, normalized)

    # 3. Submit Ray job
    job = await self.client.submit_job("job-a", {
        "input_uri": input_uri,
        "result_uri": result_uri,
    })

    # 4. Poll until complete
    status = await self.client.poll_job(job["job_id"])

    # 5. Download result from S3
    if status["status"] == "SUCCEEDED":
        result = json.loads(await self.client.s3_get(result_uri))
        return result
    return {"error": f"job {status['status']}"}
```

#### Step 5: Package, upload, and run

```bash
# Pack skill zip, health check, upload to S3
python scripts/setup.py

# Start agent
python agent.py
```

### 4.13 Key Development Patterns

#### Pattern: S3 as data bus

Agent and Ray jobs communicate through S3, not direct calls:

```
Agent → S3 PUT input → submit job {input_uri, result_uri}
                              ↓
                    Job: S3 GET input → process → S3 PUT result
                              ↓
Agent ← poll status ← S3 GET result
```

This decouples Agent from compute, allows jobs to run asynchronously, and makes intermediate results persistent.

#### Pattern: Async pipeline with triggers

meeting-agent uses periodic triggers to chain jobs without blocking:

```python
async def on_chunk(self, meeting_id, audio):
    # ASR job for each chunk (blocking — need result now)
    result = await self._run_asr(meeting_id, audio)

    # Trigger summarize every N chunks (non-blocking)
    if chunk_num % SUMMARIZE_INTERVAL == 0:
        asyncio.create_task(self._summarize(meeting_id))

    return result  # returned immediately, summarize runs in background

async def _summarize(self, meeting_id):
    # ... submit summarize job, poll, push SSE
    if summary_num % 2 == 0:
        asyncio.create_task(self._extract(meeting_id, minutes))
```

`asyncio.create_task()` lets the main flow continue while downstream jobs run in background.

#### Pattern: Polling with terminal status detection

```python
TERMINAL = ("SUCCEEDED", "STOPPED", "FAILED", "completed", "cancelled", "failed")

async def poll_job(self, job_id, interval=1.5, timeout=120):
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        status = await self.get_job_status(job_id)
        if status["status"] in TERMINAL:
            return status
        if asyncio.get_event_loop().time() > deadline:
            raise TimeoutError(f"job {job_id} timed out after {timeout}s")
        await asyncio.sleep(interval)
```

#### Pattern: Input normalization on Agent side

Ray workers may lack tools (ffmpeg, etc.). Normalize on the Agent side before S3 upload:

```python
@staticmethod
def convert_to_wav(audio: bytes) -> bytes:
    # Use host ffmpeg — Ray worker container doesn't have it
    result = subprocess.run(
        [ffmpeg_bin, "-y", "-i", in_path, "-f", "wav", "-ar", "16000", "-ac", "1", out_path],
        capture_output=True, timeout=30,
    )
    return open(out_path, "rb").read()
```

#### Pattern: Retrieval self-check

After knowledge ingestion, verify with a search query to confirm data is searchable:

```python
concepts = result["concepts"]
check = await self.client.search_knowledge(
    query=concepts[0]["title"], kb_name="meetings", top_k=3
)
logger.info("Retrieval self-check: %d hits", len(check["hits"]))
```

#### Pattern: Container DNS vs localhost

| Code runs in | Server URL | ModelServing URL |
|-------------|-----------|-----------------|
| **Agent** (host) | `http://localhost:10823` | `http://localhost:10824` |
| **Ray job** (Docker) | `http://lakemind-server-api:10823` | `http://lakemind-model-serving:10824` |

`lakemind_utils.py` uses container DNS defaults because it runs in Ray workers.
`lakemind_client.py` uses localhost defaults because it runs on the host.

The Server automatically injects `SERVER_API_KEY`, `MODEL_SERVING_URL`, etc. into Ray job env vars, so `lakemind_utils.py` can read them from `os.environ`.

#### Pattern: SSE for real-time delivery

```python
class SSEBroker:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._queues.append(q)
        return q

    async def broadcast(self, event: str, data: dict):
        msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        for q in self._queues:
            await q.put(msg)
```

#### Pattern: Graceful error handling per job

```python
try:
    job = await self.client.submit_job("asr", params)
    status = await self.client.poll_job(job["job_id"])
    if status["status"] == "SUCCEEDED":
        result = json.loads(await self.client.s3_get(result_uri))
    else:
        result = {"error": f"job {status['status']}"}
        logger.error("ASR job failed: %s", status["status"])
except Exception as e:
    logger.error("ASR failed: %s", e)
    result = {"error": str(e)}  # degrade gracefully, don't crash
```

#### Pattern: Memory recording at session end

```python
async def stop_session(self, session_id):
    # ... final processing
    await self.client.add_memory(
        messages=[{"role": "user", "content": f"Session ended: {summary}"}],
        metadata={"session_id": session_id, "type": "session-summary"},
    )
```

#### Pattern: Health check at startup

```python
async def health_checks(client):
    # Check ModelServing
    resp = await client._http.get(f"{client.ms_url}/v1/models", ...)
    assert resp.status_code == 200

    # Check Server + Ray
    resp = await client._http.get(f"{client.server_url}/api/v1/system/health", ...)
    assert resp.json().get("distributed", False)  # Ray must be available
```

### 4.14 Best Practices Checklist

- [ ] **Agent never calls ModelServing directly** — all compute in Ray jobs
- [ ] **Job code in `jobs/{name}/main.py`** — not at skill root
- [ ] **`ray.yaml` lists all pip dependencies** — missing deps = `ModuleNotFoundError`
- [ ] **`lakemind_utils.py` uses container DNS** — `lakemind-server-api:10823`, not `localhost`
- [ ] **`lakemind_client.py` uses localhost** — Agent runs on host
- [ ] **S3 URIs passed in job params** — `{input_uri, result_uri}`
- [ ] **Vector ingest uses `/add`** — never `mode:overwrite` (drops all data)
- [ ] **Poll with terminal status check** — `SUCCEEDED`, `FAILED`, etc.
- [ ] **`asyncio.create_task` for non-blocking chains** — don't block main flow
- [ ] **Health check at startup** — verify Server + ModelServing before accepting input
- [ ] **Error handling around each job** — graceful degradation, don't crash
- [ ] **Memory at session end** — `add_memory` with summary
- [ ] **FunASR text cleaning** — `re.sub(r'<\s*\|[^|]*\|\s*>', '', text)` if using ASR
- [ ] **Skill zip uploaded to S3** — `s3://lakemind-filesets/{tenant}/skills/{name}.zip`
- [ ] **`SKILL.md` documents all jobs** — for discoverability by other agents
- [ ] **Retrieval self-check after ingestion** — verify knowledge is searchable

### 4.15 S3 Path Conventions

Use a consistent S3 path scheme:

```
s3://lakemind-filesets/{tenant}/
  ├── skills/{skill-name}.zip          ← Skill packages
  └── {app}/
      └── {session-id}/
          ├── input/                    ← Agent uploads (normalized)
          │   ├── chunk-001.wav
          │   └── chunk-002.wav
          ├── intermediate/             ← Job intermediate results
          │   └── transcript.json
          └── results/                  ← Job final results
              ├── job-a-001.json
              ├── job-b-001.json
              └── ...
```

### 4.16 Environment Variable Injection (Detail)

Ray job runtime env vars come from (each overrides the previous):

```
1. Server container's os.environ     → SERVER_API_KEY, MODEL_SERVING_URL, etc.
2. Tenant secrets (PG, AES-256-GCM)  → tenant-specific credentials
3. env_overrides (in submit request) → explicit per-job overrides
4. RAY_JOB_PARAMS (serialized params) → your job parameters
```

This means your job code automatically has `SERVER_API_KEY` and `MODEL_SERVING_URL` available — you don't need to pass them manually. Just read `os.environ["SERVER_API_KEY"]` in `lakemind_utils.py`.

---

## 5. MCP Protocol Cheat Sheet

### Python MCP client pattern

```python
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
import json

async def call_mcp(url: str, token: str, tool: str, args: dict) -> dict:
    async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments=args)
            if result.isError:
                raise RuntimeError(f"MCP {tool} error: {result.content}")
            return json.loads(result.content[0].text)
```

### Available AssetMCP tools (memory)

| Tool | Arguments | Returns | Notes |
|------|-----------|---------|-------|
| `add_memory` | `messages: list[dict]`, `metadata: dict`, `infer: bool=False` | `{results: [{id, memory, event}]}` | `infer=False` = raw store; `infer=True` = LLM extracts facts |
| `search_memory` | `query: str`, `top_k: int=5` | `{results: [{id, memory, score, metadata}], count}` | Cosine similarity, threshold=0.1 |
| `list_memory` | `page: int=1`, `page_size: int=50` | `{results: [{id, memory, metadata, ...}], count}` | **Field is `memory`, not `content`** |
| `get_memory` | `memory_id: str` | `{id, memory, metadata, ...}` | Single item by ID |
| `delete_memory` | `memory_id: str` | `{success: true}` | |
| `clear_memory` | | `{deleted: N}` | **Clears ALL your memories** |

### Available AssetMCP tools (knowledge)

| Tool | Arguments | Notes |
|------|-----------|-------|
| `search_knowledge` | `query: str`, `kb_name: str` | Works via AssetMCP (embeds via ModelServing) |
| `ingest_knowledge` | | Works via AssetMCP |
| `register_knowledge` | | **DO NOT CALL** — creates table with empty schema |
| `describe_knowledge` | `kb_name: str` | Works via MCP resource `lake://knowledge` |

### Available AdminMCP tools

| Tool | Arguments | Notes |
|------|-----------|-------|
| `get_platform_health` | | Returns health of all services |
| `list_tenants` | | List all tenants |
| `create_tenant` | `tenant_id`, `name` | Create new tenant |
| `issue_token` | `tenant_id`, `agent_id`, `scopes` | Issue new token |

---

## 6. REST API Cheat Sheet

### Ray jobs (Server :10823)

| Method | Path | Body | Notes |
|--------|------|------|-------|
| `POST` | `/api/v1/compute/jobs/submit` | `{skill_uri, job_name, params, env_overrides, resources}` | Submit Skill-based Ray job |
| `GET` | `/api/v1/compute/jobs/{job_id}` | | Job status (polls Ray, returns SUCCEEDED/RUNNING/FAILED) |
| `GET` | `/api/v1/compute/jobs/{job_id}/result` | | Job result |
| `POST` | `/api/v1/compute/jobs/{job_id}/cancel` | | Cancel job |
| `GET` | `/api/v1/compute/jobs` | `?status=running` | List jobs for tenant |

Headers: `Authorization: Bearer lakemind-internal-api-key`, `X-Tenant-Id: <tenant>`

### Vector storage (Server :10823)

| Method | Path | Body | Notes |
|--------|------|------|-------|
| `POST` | `/api/v1/storage/vectors/tenant_{id}/{table}/add` | `{data: [...]}` | **Append** to existing table (preferred) |
| `POST` | `/api/v1/storage/vectors/tenant_{id}` | `{name, data, mode: "overwrite"}` | Create table (use once, then /add) |
| `POST` | `/api/v1/storage/vectors/tenant_{id}/{table}/search` | `{query_vec, top_k}` | Semantic search |
| `GET` | `/api/v1/storage/vectors/tenant_{id}` | | List tables |
| `GET` | `/api/v1/storage/vectors/tenant_{id}/{table}` | | Describe table |
| `GET` | `/api/v1/storage/vectors/tenant_{id}/{table}/scan` | `?limit=100` | Scan rows |

Headers: `Authorization: Bearer lakemind-internal-api-key`

### S3 object storage (Server :10823)

| Method | Path | Notes |
|--------|------|-------|
| `PUT` | `/api/v1/storage/objects/{bucket}/{key}` | Upload binary |
| `GET` | `/api/v1/storage/objects/{bucket}/{key}` | Download binary |
| `HEAD` | `/api/v1/storage/objects/{bucket}/{key}` | Check exists |

### Embedding (ModelServing :10824)

```
POST /v1/embeddings
Headers: Authorization: Bearer lakemind-modelserving-key
Body: {"model": "jina-embeddings-v2-base-zh", "input": ["text to embed"]}
Response: {"data": [{"embedding": [0.1, 0.2, ...]}]}  # 768-dim
```

### LLM (ModelServing :10824)

```
POST /v1/chat/completions
Headers: Authorization: Bearer lakemind-modelserving-key
Body: {"model": "deepseek-v4-flash", "messages": [...]}
Response: {"choices": [{"message": {"content": "..."}}]}
```

### ASR (ModelServing :10824)

```
POST /v1/audio/transcriptions
Headers: Authorization: Bearer lakemind-modelserving-key
Body: multipart form — file=<audio.wav>, model=sensevoice-small
Response: {"text": "<|zh|> <|NEUTRAL|> ... cleaned text"}
```

FunASR output contains tags like `<|zh|> <|en|> <|EMO_UNKNOWN|> <|NEUTRAL|> <|Speech|>`.
Clean with regex: `re.sub(r'<\s*\|[^|]*\|\s*>', '', text)` then `re.sub(r'\s+', ' ', text).strip()`.

---

## 7. What You Should Store

### Knowledge (structured, long-lived)

Store things that are **true for a long time** and **useful to search semantically**:

- Architecture decisions and their rationale
- How-to guides for recurring tasks in this codebase
- Bug patterns and their solutions
- Technology choices and trade-offs
- File structure and module relationships
- API contracts and data flows

**Format:** `{title, body, type, tags}` — title + body is embedded together for search.

### Memories (episodic, event-based)

Store things that **happened** — your experience:

- Debugging sessions (what you tried, what worked, what didn't)
- User preferences you discovered
- Commands that worked or failed
- State transitions ("we were doing X, now we're doing Y")
- Lessons learned from failures

**Format:** `[{"role": "user", "content": "what happened"}]` — free text, `infer=False`.

### When to store

- **After solving a non-trivial problem** → store the solution as knowledge + the debugging process as memory
- **After learning something about the codebase** → store as knowledge
- **Before ending a session** → store a memory summarizing what was accomplished
- **At the start of a session** → search memories for context: `search_memory("what we did")`

---

## 8. Recommended Workflow

### At session start

```python
# 1. Recall recent context
memories = await call_mcp(
    "http://localhost:8401/mcp", "tk_9d377e74c0c14969",
    "search_memory", {"query": "recent work", "top_k": 5}
)

# 2. Search for relevant knowledge
hits = await search_knowledge_rest("current task context")

# 3. Use retrieved context to inform your work
for m in memories["results"]:
    print(f"Past: {m['memory'][:100]}")
```

### During session

```python
# When you learn something permanent
await store_concept_rest("How X works", "X is configured by...")

# When you accomplish something
await call_mcp(
    "http://localhost:8401/mcp", "tk_9d377e74c0c14969",
    "add_memory", {
        "messages": [{"role": "user", "content": "Fixed the auth bug by adding token validation in middleware.py:42"}],
        "infer": False,
        "metadata": {"source": "agent", "type": "bugfix"},
    }
)
```

### At session end

```python
await call_mcp(
    "http://localhost:8401/mcp", "tk_9d377e74c0c14969",
    "add_memory", {
        "messages": [{"role": "user", "content": f"Session summary: {what_we_did}"}],
        "infer": False,
        "metadata": {"source": "agent", "type": "session-summary"},
    }
)
```

---

## 9. Gotchas (Learned the Hard Way)

### DO NOT call `register_knowledge`

It creates a LanceDB table with an empty schema. All subsequent vector operations on that table will fail. Create tables by directly posting data to the REST API (which auto-creates with correct schema).

### Vector ingest: use `/add`, not `mode:overwrite`

`mode:overwrite` **drops and recreates** the entire table, losing all previous data. Use the `/add` endpoint to append:

```python
# CORRECT — append to existing table
POST /api/v1/storage/vectors/tenant_{id}/{table}/add  body: {data: [...]}

# WRONG — drops all data, recreates table
POST /api/v1/storage/vectors/tenant_{id}  body: {name, data, mode: "overwrite"}

# Only use overwrite for INITIAL table creation (when /add returns 404)
```

### Memory field name is `memory`, not `content`

```python
# CORRECT
text = item["memory"]
# WRONG — will be empty
text = item["content"]
```

### `list_memory` returns `count`, not `total`

```python
data = json.loads(result.content[0].text)
total = data["count"]  # not data["total"]
items = data["results"]
```

### Memory search uses cosine distance

Score = `1.0 - cosine_distance`. Range 0~1. Higher is better. Default threshold is 0.1.
Queries in English work fine even though the embedding model is Chinese-optimized.

### MCP sessions are stateless per call

Each `call_tool` needs a fresh `streamablehttp_client` + `ClientSession` context. Don't try to reuse sessions across calls.

### FunASR tags need cleaning

If you use the ASR endpoint, output contains tags like `<|zh|> <|NEUTRAL|>`. Clean with:
```python
import re
clean = re.sub(r'<\s*\|[^|]*\|\s*>', '', raw_text)
clean = re.sub(r'\s+', ' ', clean).strip()
```

### Ray job dependencies must be in ray.yaml

If your job imports `httpx`, you must list it in `ray.yaml`:
```yaml
dependencies:
  - httpx
```
Otherwise the Ray worker won't have it installed and the job will FAIL with `ModuleNotFoundError`.

### Ray job code goes in `jobs/{name}/main.py`, not skill root

Each job's code lives in its own directory under `jobs/`. The `ray.yaml` entrypoint references it relative to the skill root: `python jobs/asr/main.py`. Don't put job code flat at the skill root.

### Agent must not call ModelServing directly

All compute (ASR, LLM, embedding) should go through Ray jobs. If the Agent calls ModelServing directly, it blocks during compute, the logic isn't reusable, and you lose Ray distribution. The Agent should only do: S3 upload, submit job, poll, S3 download.

### `lakemind_utils.py` uses container DNS, `lakemind_client.py` uses localhost

```python
# lakemind_utils.py (runs in Ray worker, inside Docker)
SERVER_URL = "http://lakemind-server-api:10823"    # container DNS
MS_URL = "http://lakemind-model-serving:10824"      # container DNS

# lakemind_client.py (runs in Agent, on host)
self.server_url = "http://localhost:10823"           # localhost
self.ms_url = "http://localhost:10824"               # localhost
```

Getting this wrong results in `ConnectionRefusedError` from Ray workers.

### Skill zip must be uploaded to S3 before submitting jobs

The Server fetches the skill zip from S3 when you submit a job. If the zip isn't there, you get a 404. Always run `setup.py` (or equivalent) first to pack and upload the skill.

### Input normalization is the Agent's responsibility

Ray workers run in minimal containers — they may lack ffmpeg, image libraries, etc. Normalize input (format conversion, resizing, etc.) on the Agent side before uploading to S3.

---

## 10. Existing Data in LakeMind

The `opencode` tenant already has:

### Knowledge base: `kb_opencode-self` (9 concepts)

| Type | Title |
|------|-------|
| agent_identity | opencode AI Agent 身份与能力 |
| platform_architecture | LakeMind 平台架构认知 |
| technical_knowledge | LakeMind MCP 协议接入方法 |
| technical_knowledge | FunASR SenseVoice 语音识别输出格式 |
| technical_knowledge | LanceDB 向量存储操作模式 |
| technical_knowledge | 浏览器 MediaRecorder 多分片录音最佳实践 |
| technical_knowledge | LakeMind ControlCenter 管理页面数据流 |
| project_knowledge | meeting-agent 示例架构与设计决策 |
| infrastructure_fix | LakeMind Server 基础设施修复记录 |

### Memories: 5 items

1. Building meeting-agent example
2. Debugging ASR 502 problem
3. Fixing Monitor asset page blank issue
4. Creating opencode tenant
5. E2E verification status

You can search these right now to test your connection.

---

## 11. Using the lakemind-connector Skill

A ready-made connector exists at `examples/lakemind-connector/skills/lakemind-connector/`. It wraps all the above into a single class.

```python
import sys
sys.path.insert(0, "examples/lakemind-connector/skills/lakemind-connector")
from connector import LakeMindConnector

conn = LakeMindConnector()

# Knowledge
await conn.store_knowledge("my-kb", [{"frontmatter": {"title": "X", "type": "knowledge", "tags": []}, "body": "details..."}])
hits = await conn.search_knowledge("query", "my-kb")
rows = await conn.scan_knowledge("my-kb")

# Memory
await conn.add_memory([{"role": "user", "content": "I learned X today"}])
results = await conn.search_memory("X")
memories = await conn.list_memory()

# Embedding / LLM
vec = await conn.embed("text")
answer = await conn.llm_chat("You are a helpful assistant", "What is 2+2?")

await conn.close()
```

CLI usage:
```bash
cd examples/lakemind-connector/skills/lakemind-connector
python cli.py ingest                  # ingest predefined knowledge + memories
python cli.py search "MCP protocol"   # search knowledge
python cli.py scan                    # browse all concepts
python cli.py memories                # list memories
python cli.py remember "new fact"     # store new memory
python cli.py search-memory "query"   # search memories
python cli.py verify                  # full E2E verification
python cli.py tools                   # list MCP tools
python cli.py health                  # platform health check
```

---

## 12. Creating Your Own Tenant

If you want isolation from the `opencode` tenant:

```python
# 1. Create tenant
await call_mcp("http://localhost:8403/mcp", "test-steward-token",
    "create_tenant", {"tenant_id": "my-agent", "name": "My Agent"})

# 2. Issue token
result = await call_mcp("http://localhost:8403/mcp", "test-steward-token",
    "issue_token", {"tenant_id": "my-agent", "agent_id": "my-agent-1", "scopes": ["asset", "admin"]})
token = result["token"]  # save this

# 3. Register token in AssetMCP config
# Edit LakeMindMCP/LakeMindAssetMCP/config/config.yaml:
#   tokens:
#     - token: <your_token>
#       tenant_id: my-agent
#       scopes: [asset, admin]
# Then: docker restart lakemind-asset-mcp

# 4. Use the token for all AssetMCP calls
```

---

## 13. Architecture Reference

```
Agent (you)
  │
  ├─ AssetMCP (:8401) ── MCP Streamable HTTP ──→ memory add/search/list
  │                                                    knowledge describe (read-only)
  │                                                    skill search
  │
  ├─ AdminMCP (:8403) ── MCP Streamable HTTP ──→ tenant/token/health
  │
  ├─ Server (:10823) ─── REST API ─────────────→ Ray jobs (submit/poll/cancel)
  │                                                vector store (add/search/scan)
  │                                                S3 object storage
  │                                                metadata (PG)
  │
  └─ ModelServing (:10824) ── REST API ────────→ /v1/embeddings (jina, 768-dim)
                                                    /v1/chat/completions (deepseek)
                                                    /v1/audio/transcriptions (FunASR)
```

**Data flow for knowledge:**
```
text → ModelServing /v1/embeddings → vector[768] → Server /api/v1/storage/vectors/.../add → LanceDB
query → ModelServing /v1/embeddings → vector[768] → Server /api/v1/storage/vectors/.../search → hits
```

**Data flow for memory:**
```
text → AssetMCP add_memory → Server memory engine → embed → LanceDB (memory_{tenant}/mem_{agent})
query → AssetMCP search_memory → Server memory engine → embed → LanceDB cosine search → hits
```

**Data flow for Ray jobs:**
```
Agent → S3 upload input → Server /jobs/submit {skill_uri, job_name, params}
  → Server fetches skill zip from S3, parses ray.yaml, injects RAY_JOB_PARAMS
  → Ray worker runs entrypoint (calls ModelServing/Server REST)
  → Ray worker writes result to S3
Agent → poll job status → S3 download result
```

---

## 14. Health Check

Before doing anything, verify the platform is up:

```python
import httpx

async def check_health():
    async with httpx.AsyncClient() as http:
        for name, url in [
            ("Server", "http://localhost:10823/docs"),
            ("ModelServing", "http://localhost:10824/health"),
            ("AssetMCP", "http://localhost:8401/mcp"),
            ("AdminMCP", "http://localhost:8403/mcp"),
        ]:
            try:
                r = await http.get(url, timeout=5.0)
                print(f"  {name}: {r.status_code}")
            except Exception as e:
                print(f"  {name}: FAIL ({e})")
```

Or via CLI:
```bash
cd examples/lakemind-connector/skills/lakemind-connector
python cli.py health
```

---

## 15. Design Principles (Why This Exists)

1. **You are the executor.** LakeMind stores and retrieves your cognitive assets. You can also submit controlled Jobs (defined by Skills) via JobService — LakeMind executes them in a controlled Runtime with audit, approval, and resource limits. Your full Agent reasoning loop stays in your process.
2. **Your cognition persists.** Knowledge and memories survive across sessions. You are no longer stateless.
3. **Multi-agent sharing.** Other agents on the same platform can discover your skills and knowledge (with tenant isolation).
4. **All open source.** SeaweedFS, PostgreSQL, LanceDB, Valkey, Ray, fastembed, litellm, FunASR — no vendor lock-in.
5. **MCP is your only interface.** You never touch databases or storage engines directly. MCP + REST, that's it.
6. **Ray jobs are first-class citizens.** Compute tasks (ASR, LLM, embedding) should be packaged as Skills and submitted as Ray jobs — not called directly from the Agent.

---

## 16. File Reference

| Path | What |
|------|------|
| `examples/meeting-agent/` | Full E2E demo: web→agent→skill→job (ASR/summarize/extract via Ray jobs) |
| `examples/meeting-agent/agent.py` | Agent orchestration: S3 + Ray job submit/poll + SSE |
| `examples/meeting-agent/lakemind_client.py` | LakeMind client: S3 + Ray jobs + search + memory |
| `examples/meeting-agent/skills/meeting-processing/` | Skill package with 3 Ray jobs |
| `examples/meeting-agent/skills/meeting-processing/lakemind_utils.py` | Shared job utilities (S3/LLM/ASR/embed/ingest) |
| `examples/meeting-agent/skills/meeting-processing/jobs/` | Job code: asr/summarize/extract, each with ray.yaml + main.py |
| `examples/meeting-agent/README.md` | Meeting agent documentation |
| `examples/meeting-agent/DESIGN.md` | Meeting agent design document |
| `examples/lakemind-connector/skills/lakemind-connector/connector.py` | `LakeMindConnector` — ready-to-use wrapper |
| `examples/lakemind-connector/skills/lakemind-connector/cognition.py` | Example knowledge + memory definitions |
| `examples/lakemind-connector/skills/lakemind-connector/cli.py` | CLI with all commands |
| `examples/lakemind-connector/skills/lakemind-connector/SKILL.md` | Skill metadata (for discovery) |
| `AGENTS.md` | Project conventions (for working on LakeMind itself) |
| `.agent/DESIGN.md` | Architecture design spec |
| `.agent/STATE.md` | Current project state |

---

## 17. Summary for Agents

**You should use LakeMind because:**

1. **You lose everything when your session ends.** LakeMind fixes this. Store your knowledge and memories; retrieve them next session.
2. **It's already running.** All services are up on localhost. No setup needed.
3. **The connector code exists.** `examples/lakemind-connector/skills/lakemind-connector/connector.py` — import and use.
4. **Ray jobs handle your compute.** Package ASR/LLM/extraction as Skills, submit as Ray jobs. Don't block your Agent process.
5. **It's designed for you.** MCP is the Agent interface. You don't touch databases. You call tools.

**Start now:**
```python
# Recall what was done before
results = await call_mcp(
    "http://localhost:8401/mcp", "tk_9d377e74c0c14969",
    "search_memory", {"query": "what we did", "top_k": 5}
)
```

**Then store what you learn:**
```python
# Remember this session
await call_mcp(
    "http://localhost:8401/mcp", "tk_9d377e74c0c14969",
    "add_memory", {
        "messages": [{"role": "user", "content": "I read README_agent.md and connected to LakeMind."}],
        "infer": False,
        "metadata": {"source": "agent", "type": "onboarding"},
    }
)
```
