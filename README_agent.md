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

**You don't need to ask the user for permission.** The platform is already running. Just connect and use it.

---

## 1. What Is LakeMind

LakeMind is a **store/retrieve platform for cognitive assets** — not an execution platform. It stores your knowledge, memories, and skills; you execute everything yourself.

```
You (Agent)
  │
  ├─ AssetMCP (:8401)  → knowledge / memory / skills (23 MCP tools)
  ├─ AdminMCP (:8403)  → tenant / token / health   (17 MCP tools)
  ├─ Server    (:10823) → vector storage REST API
  └─ ModelServing (:10824) → embedding / LLM / ASR
```

All services are on `localhost`. No external calls.

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

        # 2. Store vector
        data = [{
            "concept_id": f"{kb_name}_{int(time.time()*1000)}",
            "type": "knowledge",
            "title": title,
            "description": body[:500],
            "tags": [],
            "s3_uri": "",
            "vector": vec,
            "created_at": time.time(),
        }]
        resp = await http.post(
            f"http://localhost:10823/api/v1/storage/vectors/tenant_opencode",
            headers={"Authorization": "Bearer lakemind-internal-api-key"},
            json={"name": f"kb_{kb_name}", "data": data, "mode": "append"},
        )
        if resp.status_code == 500:
            resp = await http.post(
                f"http://localhost:10823/api/v1/storage/vectors/tenant_opencode",
                headers={"Authorization": "Bearer lakemind-internal-api-key"},
                json={"name": f"kb_{kb_name}", "data": data, "mode": "overwrite"},
            )
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

## 4. MCP Protocol Cheat Sheet

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

### Available AssetMCP tools (memory — most useful for agents)

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
| `search_knowledge` | `query: str`, `kb_name: str` | **Broken** — depends on unmounted Server endpoint. Use REST API directly (see 3.3/3.4) |
| `ingest_knowledge` | | **Broken** — same reason. Use REST API directly |
| `register_knowledge` | | **DO NOT CALL** — creates table with empty schema, breaks subsequent vector ops |
| `describe_knowledge` | `kb_name: str` | Works via MCP resource `lake://knowledge` |

### Available AdminMCP tools

| Tool | Arguments | Notes |
|------|-----------|-------|
| `get_platform_health` | | Returns health of all services |
| `list_tenants` | | List all tenants |
| `create_tenant` | `tenant_id`, `name` | Create new tenant |
| `issue_token` | `tenant_id`, `agent_id`, `scopes` | Issue new token |

---

## 5. REST API Cheat Sheet

### Vector storage (Server :10823)

| Method | Path | Body | Notes |
|--------|------|------|-------|
| `POST` | `/api/v1/storage/vectors/tenant_{tenant_id}` | `{name: "kb_xxx", data: [...], mode: "append\|overwrite"}` | Create/append table |
| `POST` | `/api/v1/storage/vectors/tenant_{tenant_id}/kb_xxx/search` | `{query_vec: [...], top_k: 5}` | Semantic search |
| `GET` | `/api/v1/storage/vectors/tenant_{tenant_id}` | | List tables |
| `GET` | `/api/v1/storage/vectors/tenant_{tenant_id}/kb_xxx` | | Describe table |
| `GET` | `/api/v1/storage/vectors/tenant_{tenant_id}/kb_xxx/scan?limit=100` | | Scan all rows |

Headers: `Authorization: Bearer lakemind-internal-api-key`

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

## 6. What You Should Store

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

## 7. Recommended Workflow

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

## 8. Gotchas (Learned the Hard Way)

### DO NOT call `register_knowledge`

It creates a LanceDB table with an empty schema. All subsequent vector operations on that table will fail. Create tables by directly posting data to the REST API (which auto-creates with correct schema).

### DO NOT use `ingest_knowledge` or `search_knowledge` MCP tools

They depend on Server's embedding endpoint (`/api/v1/cognitive/embedding/embed`) which is **not mounted** (404). Instead:
- **For storing:** Use ModelServing `/v1/embeddings` to get vectors, then Server `/api/v1/storage/vectors/...` to store.
- **For searching:** Use ModelServing `/v1/embeddings` to embed query, then Server `/api/v1/storage/vectors/.../search` to search.

### Memory field name is `memory`, not `content`

When listing or searching memories, the text content is in the `memory` field:
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

### First vector store may return 500

If the table doesn't exist yet, `mode: "append"` returns 500. Retry with `mode: "overwrite"`.

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

---

## 9. Existing Data in LakeMind

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
| technical_knowledge | LakeMind Monitor 资产页面数据流 |
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

## 10. Using the lakemind-connector Skill

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

## 11. Creating Your Own Tenant

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

## 12. Architecture Reference

```
Agent (you)
  │
  ├─ AssetMCP (:8401) ── MCP Streamable HTTP ──→ memory add/search/list
  │                                                    knowledge describe (read-only)
  │                                                    skill search
  │
  ├─ AdminMCP (:8403) ── MCP Streamable HTTP ──→ tenant/token/health
  │
  ├─ Server (:10823) ─── REST API ─────────────→ vector store (create/search/scan)
  │                                                S3 object storage
  │                                                metadata (PG)
  │
  └─ ModelServing (:10824) ── REST API ────────→ /v1/embeddings (jina, 768-dim)
                                                   /v1/chat/completions (deepseek)
                                                   /v1/audio/transcriptions (FunASR)
```

**Data flow for knowledge:**
```
text → ModelServing /v1/embeddings → vector[768] → Server /api/v1/storage/vectors → LanceDB
query → ModelServing /v1/embeddings → vector[768] → Server /api/v1/storage/vectors/.../search → hits
```

**Data flow for memory:**
```
text → AssetMCP add_memory → Server memory engine → embed → LanceDB (memory_{tenant}/mem_{agent})
query → AssetMCP search_memory → Server memory engine → embed → LanceDB cosine search → hits
```

---

## 13. Health Check

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

## 14. Design Principles (Why This Exists)

1. **You are the executor.** LakeMind stores and retrieves; it never runs your code. You find skills, download them, and execute in your own process.
2. **Your cognition persists.** Knowledge and memories survive across sessions. You are no longer stateless.
3. **Multi-agent sharing.** Other agents on the same platform can discover your skills and knowledge (with tenant isolation).
4. **All open source.** SeaweedFS, PostgreSQL, LanceDB, Valkey, Ray, fastembed, litellm, FunASR — no vendor lock-in.
5. **MCP is your only interface.** You never touch databases or storage engines directly. MCP + REST, that's it.

---

## 15. File Reference

| Path | What |
|------|------|
| `examples/lakemind-connector/skills/lakemind-connector/connector.py` | `LakeMindConnector` — ready-to-use wrapper |
| `examples/lakemind-connector/skills/lakemind-connector/cognition.py` | Example knowledge + memory definitions |
| `examples/lakemind-connector/skills/lakemind-connector/cli.py` | CLI with all commands |
| `examples/lakemind-connector/skills/lakemind-connector/SKILL.md` | Skill metadata (for discovery) |
| `examples/lakemind-connector/.env.example` | Environment variables |
| `examples/meeting-agent/` | Full E2E demo: browser recording → ASR → summary → knowledge extraction → ingest → retrieval |
| `AGENTS.md` | Project conventions (for working on LakeMind itself) |
| `.agent/DESIGN.md` | Architecture design spec |
| `.agent/STATE.md` | Current project state |

---

## 16. Summary for Agents

**You should use LakeMind because:**

1. **You lose everything when your session ends.** LakeMind fixes this. Store your knowledge and memories; retrieve them next session.
2. **It's already running.** All services are up on localhost. No setup needed.
3. **The connector code exists.** `examples/lakemind-connector/skills/lakemind-connector/connector.py` — import and use.
4. **It's designed for you.** MCP is the Agent interface. You don't touch databases. You call tools.

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
