# 会议实时知识化 Agent — 设计方案

> 位置：`examples/meeting-agent/`
> 状态：设计阶段，待批准
> 日期：2026-07-09

---

## 1. 项目定位

一个带 Web 界面的会议实时知识化 Agent。浏览器实时录音，后端 Agent 编排流水线，所有处理逻辑封装为 LakeMind Skill（带 Ray jobs）。

```
浏览器录音 → Agent 编排 → Skill jobs(Ray) 处理 → 知识入库 → 浏览器实时展示
```

### 1.1 设计思路

| 层 | 职责 | 技术 |
|----|------|------|
| **Web UI** | 录音、展示转写/纪要/知识、检索 | HTML + JS（MediaRecorder + SSE） |
| **Agent** | Web 服务 + 流水线编排 | FastAPI（Python） |
| **Skills** | 所有处理逻辑（ASR/摘要/萃取/入库） | Ray jobs（Skill zip 包） |

**Agent 与 LakeMind 的接口只有三件事**：
1. `s3_put` — 上传音频文件
2. `ray_submit_job` / `ray_job_status` / `ray_job_result` — 提交和轮询 Skill jobs
3. `search_knowledge` — 检索知识库

所有业务逻辑（ASR、摘要、萃取、知识入库）都在 Skill jobs 内，Agent 不做任何计算。

---

## 2. 架构

```
┌─────────────────────────────────────────────────────────┐
│                    浏览器 (Web UI)                        │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ 录音按钮  │  │ 实时转写  │  │ 实时纪要  │  │ 知识库  │  │
│  │ MediaRec │  │  (SSE)   │  │  (SSE)   │  │ 检索    │  │
│  └────┬─────┘  └──────────┘  └──────────┘  └────────┘  │
│       │ audio chunks (HTTP POST)                         │
└───────┼──────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                  Agent (FastAPI :9100)                    │
│                                                           │
│  POST /api/chunk     ← 接收音频 chunk                     │
│  POST /api/start     ← 开始会议                           │
│  POST /api/stop      ← 结束会议                           │
│  GET  /api/stream    ← SSE 实时推送                       │
│  GET  /api/search    ← 知识检索                           │
│                                                           │
│  MeetingAgent 编排：                                      │
│    chunk → s3_put → ray_submit_job(asr) → 转写            │
│    每60s → ray_submit_job(summarize) → 纪要               │
│    每120s → ray_submit_job(extract) → 知识入库            │
└──────┬──────────────────────────────────────────────────┘
       │ MCP
       ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  DataMCP     │  │  AssetMCP    │  │  AdminMCP    │
│  s3_put      │  │  search_know │  │  create_sec  │
│  ray_submit  │  │  register_sk │  │  (setup only)│
│  ray_status  │  │  (setup only)│  │              │
│  ray_result  │  │              │  │              │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
              LakeMindServer :10823
              REST API + 11 引擎
```

---

## 3. 实时流水线

### 3.1 数据流

```
浏览器录音
  │  每 10s 发送一个 audio chunk
  ▼
Agent 接收 chunk
  │  s3_put 上传到 S3
  │  ray_submit_job("asr", {chunk_uri}) → 等待结果
  │  → transcript segment
  │  → SSE 推送到浏览器
  │  → 累积到 transcript buffer
  ▼
每 60s（6 个 chunk）
  │  ray_submit_job("summarize", {transcript_uri}) → 等待结果
  │  → minutes (markdown)
  │  → SSE 推送到浏览器
  ▼
每 120s（2 次摘要）
  │  ray_submit_job("extract", {minutes_uri, meeting_id}) → 等待结果
  │  → extract job 内部调 LLM 萃取知识 + 调 REST API 入库
  │  → SSE 推送到浏览器（新知识点）
  ▼
用户停止录音
  │  最终 summarize + extract + 入库
  │  add_memory 记录会议历史
  ▼
完成
```

### 3.2 异步编排

```python
# agent.py 核心逻辑
class MeetingAgent:
    async def on_chunk(self, chunk: bytes, meeting_id: str):
        # 1. 上传 S3
        uri = f"s3://.../meetings/{meeting_id}/audio/chunk-{self.n}.wav"
        await self.lake.s3_put(uri, chunk)

        # 2. 提交 ASR job
        job = await self.lake.ray_submit_job(
            skill_uri=SKILL_URI, job_name="asr",
            params={"chunk_uri": uri},
            task_id=meeting_id,
        )
        result = await self._wait_job(job["job_id"])

        # 3. 推送转写到浏览器
        await self.sse.broadcast("transcript", result["text"])

        # 4. 累积，触发摘要
        self.buffer.append(result)
        if len(self.buffer) >= 6:
            asyncio.create_task(self._summarize(meeting_id))

    async def _summarize(self, meeting_id: str):
        # 提交 summarize job
        job = await self.lake.ray_submit_job(
            skill_uri=SKILL_URI, job_name="summarize",
            params={"transcript_uri": self._upload_transcript()},
            task_id=meeting_id,
        )
        result = await self._wait_job(job["job_id"])
        await self.sse.broadcast("minutes", result["minutes"])

        # 触发萃取
        asyncio.create_task(self._extract(meeting_id, result["minutes_uri"]))

    async def _extract(self, meeting_id: str, minutes_uri: str):
        # 提交 extract job（job 内部完成知识入库）
        job = await self.lake.ray_submit_job(
            skill_uri=SKILL_URI, job_name="extract",
            params={"minutes_uri": minutes_uri, "meeting_id": meeting_id},
            task_id=meeting_id,
        )
        result = await self._wait_job(job["job_id"])
        await self.sse.broadcast("knowledge", result["concepts"])
```

### 3.3 时序图

```
浏览器        Agent         DataMCP/S3     Ray(asr)    Ray(sum)   Ray(ext)   AssetMCP
  │             │              │             │           │          │           │
  │──chunk 1──→ │              │             │           │          │           │
  │             │──s3_put──→   │             │           │          │           │
  │             │──submit asr─────────────→ │           │          │           │
  │             │←─result───────────────────│           │          │           │
  │←─SSE trans─│              │             │           │          │           │
  │             │              │             │           │          │           │
  │──chunk 2──→ │              │             │           │          │           │
  │             │  ...         │             │           │          │           │
  │             │              │             │           │          │           │
  │──chunk 6──→ │              │             │           │          │           │
  │             │──s3_put──→   │             │           │          │           │
  │             │──submit asr─────────────→ │           │          │           │
  │←─SSE trans─│              │             │           │          │           │
  │             │──submit sum──────────────────────────→│          │           │
  │             │←─result────────────────────────────────│          │           │
  │←─SSE minutes│              │             │           │          │           │
  │             │──submit ext────────────────────────────────────→ │           │
  │             │               │             │           │          │──ingest─→│
  │             │←─result──────────────────────────────────────────│           │
  │←─SSE know──│              │             │           │          │           │
```

---

## 4. Skill 包设计

**所有处理逻辑都在 Skill 内，Agent 不做任何计算。**

```
meeting-processing/
├── SKILL.md
└── jobs/
    ├── asr/                         ← job_name="asr"
    │   ├── ray.yaml
    │   ├── asr.py
    │   └── requirements.txt
    ├── summarize/                   ← job_name="summarize"
    │   ├── ray.yaml
    │   ├── summarize.py
    │   └── requirements.txt
    └── extract/                     ← job_name="extract"
        ├── ray.yaml
        ├── extract.py
        └── requirements.txt
```

### 4.1 asr job

输入：`{"chunk_uri": "s3://.../chunk-001.wav"}`
输出：`{"text": "转写文本", "segments": [...]}`

```python
# jobs/asr/asr.py
import os, json, httpx

def main():
    params = json.loads(os.environ["RAY_JOB_PARAMS"])
    chunk_uri = params["chunk_uri"]

    # 从 S3 下载音频
    audio = download_from_s3(chunk_uri)

    # 调用 ASR API（密钥从 os.environ 读取，由 Server 注入）
    resp = httpx.post(
        os.environ["ASR_ENDPOINT"] + "/audio/transcriptions",
        headers={"Authorization": f"Bearer {os.environ['ASR_API_KEY']}"},
        files={"file": ("audio.wav", audio)},
    )
    result = resp.json()

    # 输出结果（Server 自动捕获 stdout JSON）
    print(json.dumps({"text": result["text"], "segments": result.get("segments", [])}))
```

```yaml
# jobs/asr/ray.yaml
entrypoint: "python asr.py"
dependencies:
  - requirements.txt
resources:
  num_cpus: 1
```

### 4.2 summarize job

输入：`{"transcript_uri": "s3://.../transcript.json", "meeting_title": "..."}`
输出：`{"minutes": "markdown", "minutes_uri": "s3://.../minutes.md"}`

```python
# jobs/summarize/summarize.py
import os, json, httpx

def main():
    params = json.loads(os.environ["RAY_JOB_PARAMS"])
    transcript = json.loads(download_from_s3(params["transcript_uri"]))

    # 调用 LakeMind LLM Gateway（Ray worker 在 Docker 网络内）
    resp = httpx.post(
        server_url() + "/api/v1/cognitive/llm/chat",
        headers={"Authorization": f"Bearer {server_key()}"},
        json={
            "messages": [
                {"role": "system", "content": SUMMARIZE_PROMPT},
                {"role": "user", "content": transcript["text"]},
            ],
        },
    )
    minutes = resp.json()["choices"][0]["message"]["content"]

    # 写回 S3
    minutes_uri = params["transcript_uri"].replace("transcript.json", "minutes.md")
    upload_to_s3(minutes_uri, minutes)

    print(json.dumps({"minutes": minutes, "minutes_uri": minutes_uri}))
```

### 4.3 extract job

输入：`{"minutes_uri": "s3://.../minutes.md", "meeting_id": "..."}`
输出：`{"concepts": [...]}`
**副作用：知识入库**（job 内部调 REST API ingest_knowledge）

```python
# jobs/extract/extract.py
import os, json, httpx

def main():
    params = json.loads(os.environ["RAY_JOB_PARAMS"])
    minutes = download_from_s3(params["minutes_uri"])
    meeting_id = params["meeting_id"]

    # LLM 萃取知识点
    resp = httpx.post(
        server_url() + "/api/v1/cognitive/llm/chat",
        headers={"Authorization": f"Bearer {server_key()}"},
        json={
            "messages": [
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": minutes},
            ],
        },
    )
    concepts = json.loads(resp.json()["choices"][0]["message"]["content"])

    # 知识入库（调 REST API，OKF 格式）
    for concept in concepts:
        httpx.post(
            server_url() + "/api/v1/cognitive/knowledge/ingest",
            headers=server_headers(),
            json={"kb_name": "meetings", "concepts": [concept]},
        )

    print(json.dumps({"concepts": concepts}))
```

### 4.4 SKILL.md

```markdown
# 会议录音实时知识化

实时录音 → ASR 转写 → 会议纪要 → 知识萃取 → 知识库入库。

## Jobs

- **asr**: 音频 chunk → 转写文本（调用外部 ASR API）
- **summarize**: 转写文本 → 结构化纪要（调用 LLM Gateway）
- **extract**: 纪要 → 知识点 + 入库（调用 LLM Gateway + REST API）

## 依赖密钥

- ASR_API_KEY: ASR 服务 API Key
- ASR_ENDPOINT: ASR 服务地址
```

---

## 5. Web UI 设计

### 5.1 页面布局

```
┌─────────────────────────────────────────────────────────┐
│  LakeMind Meeting Agent                    [知识检索]     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  会议标题: [项目评审会          ]  参会人: [张三,李四   ] │
│                                                          │
│  ┌──────────┐    状态: ● 录音中  00:03:24  chunks: 20   │
│  │  ● 录音  │                                            │
│  └──────────┘                                            │
│                                                          │
│  ┌─ 实时转写 ─────────────────────────────────────────┐  │
│  │ ...所以我们决定把 v1.0 的发布日期推迟到下周三，    │  │
│  │ 因为认证模块还有几个 bug 需要修复...               │  │
│  │ ▌                                                   │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 实时纪要 ─────────────────────────────────────────┐  │
│  │ ## 决策                                              │  │
│  │ 1. v1.0 发布推迟到下周三                             │  │
│  │ ## 行动项                                            │  │
│  │ - [ ] 张三：修复认证模块 bug                         │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 已发现知识 (8) ───────────────────────────────────┐  │
│  │ • v1.0 发布计划变更 → 推迟至下周三                   │  │
│  │ • 认证模块存在未修复 bug                             │  │
│  │ • 张三负责认证模块修复                               │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 5.2 知识检索页面

```
┌─────────────────────────────────────────────────────────┐
│  知识检索                                                │
├─────────────────────────────────────────────────────────┤
│  [v1.0 发布计划          ] [搜索]                        │
│                                                          │
│  结果 (3 条):                                            │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ v1.0 发布推迟至下周三 (score: 0.12)                  │ │
│  │ 会议: 2026-07-09 项目评审会                          │ │
│  │ 决策: v1.0 发布日期从 7/10 推迟至 7/16...            │ │
│  └─────────────────────────────────────────────────────┘ │
│  ...                                                     │
└─────────────────────────────────────────────────────────┘
```

### 5.3 前端技术

| 技术 | 用途 |
|------|------|
| `MediaRecorder API` | 浏览器录音，10s 分片 |
| `fetch` | 发送音频 chunk 到 Agent |
| `EventSource (SSE)` | 接收实时转写/纪要/知识推送 |
| Vanilla JS | 无框架，单文件 `app.js` |

---

## 6. Agent API 设计

### 6.1 REST 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/start` | 开始会议（title, participants） |
| POST | `/api/chunk` | 上传音频 chunk（binary body） |
| POST | `/api/stop` | 结束会议（触发最终处理） |
| GET | `/api/stream` | SSE 实时推送（transcript/minutes/knowledge） |
| GET | `/api/search` | 知识检索（query, top_k） |
| GET | `/api/history` | 历史会议列表 |

### 6.2 SSE 事件

```
event: transcript
data: {"text": "...", "timestamp": "00:03:20"}

event: minutes
data: {"minutes": "## 决策\n1. ...", "updated_at": "00:06:00"}

event: knowledge
data: {"concepts": [{"title": "...", "body": "..."}]}

event: status
data: {"status": "recording", "duration": "00:03:24", "chunks": 20}
```

---

## 7. Agent 与 LakeMind 接口

**Agent 只做三件事**，不包含任何业务逻辑：

```python
class LakeMindClient:
    # 1. 上传文件到 S3
    async def s3_put(self, uri: str, data: bytes): ...

    # 2. 提交和轮询 Ray jobs
    async def ray_submit_job(self, skill_uri, job_name, params, task_id): ...
    async def ray_job_status(self, job_id): ...
    async def ray_job_result(self, job_id): ...

    # 3. 检索知识库
    async def search_knowledge(self, query, top_k=5): ...

    # setup（仅一次性配置）
    async def register_skill(self, name, code, format, version): ...
    async def create_secret(self, key_name, value): ...
```

**所有处理逻辑在 Skill jobs 内**：

| Job | 输入 | 输出 | 副作用 |
|-----|------|------|--------|
| `asr` | audio chunk URI | 转写文本 | 无 |
| `summarize` | transcript URI | 纪要 markdown | 写回 S3 |
| `extract` | minutes URI + meeting_id | 知识概念列表 | **知识入库**（REST API） |

---

## 8. 密钥设计

| 密钥名 | 用途 | 配置 |
|--------|------|------|
| `ASR_API_KEY` | ASR 服务 API Key | AdminMCP `create_secret` |
| `ASR_ENDPOINT` | ASR 服务地址 | AdminMCP `create_secret` |

Ray job 提交时 Server 自动注入，Skill 代码通过 `os.environ` 读取。
LLM 由 LakeMind LLM Gateway 提供（Ray worker 在 Docker 网络内，直接调 REST API）。

---

## 9. 数据模型

### 9.1 S3 路径约定

```
s3://lakemind-filesets/{tenant}/meetings/{meeting_id}/
  ├── audio/
  │   ├── chunk-001.wav
  │   ├── chunk-002.wav
  │   └── ...
  ├── transcript.json          ← 累积转写
  └── minutes.md               ← 最新纪要
```

### 9.2 OKF 知识格式（extract job 入库）

```markdown
---
title: 2026-07-09 项目评审会 — v1.0 发布推迟
type: meeting_decision
kb: meetings
meeting_id: meeting-2026-07-09-001
date: 2026-07-09
tags: [项目评审, 发布计划]
---

# v1.0 发布推迟至下周三

认证模块存在未修复 bug，发布日期从 7/10 推迟至 7/16。
张三负责 bug 修复，7/12 前完成。
```

---

## 10. 文件结构

```
examples/meeting-agent/
├── DESIGN.md                          ← 设计方案（本文件）
├── README.md                          ← 使用说明
├── pyproject.toml
├── .env.example
│
├── agent.py                           ← FastAPI Web 服务 + MeetingAgent 编排
├── lakemind_client.py                 ← MCP 客户端（s3_put + ray + search）
│
├── static/
│   ├── index.html                    ← Web UI
│   ├── style.css
│   └── app.js                        ← 录音 + SSE + UI 更新
│
├── skills/
│   └── meeting-processing/           ← Skill 包源码
│       ├── SKILL.md
│       └── jobs/
│           ├── asr/
│           │   ├── ray.yaml
│           │   ├── asr.py
│           │   └── requirements.txt
│           ├── summarize/
│           │   ├── ray.yaml
│           │   ├── summarize.py
│           │   └── requirements.txt
│           └── extract/
│               ├── ray.yaml
│               ├── extract.py
│               └── requirements.txt
│
└── scripts/
    ├── setup.py                       ← 一次性配置：注册 skill + 密钥
    └── pack_skill.py                  ← 打包 skill zip
```

### 10.1 文件职责

| 文件 | 职责 | 行数估计 |
|------|------|----------|
| `agent.py` | FastAPI 服务 + MeetingAgent 编排 + SSE | ~250 |
| `lakemind_client.py` | MCP 客户端（s3 + ray + search） | ~150 |
| `static/index.html` | Web UI 页面 | ~100 |
| `static/style.css` | 样式 | ~100 |
| `static/app.js` | 录音 + SSE + UI 更新 | ~200 |
| `scripts/setup.py` | 注册 skill + 密钥 | ~60 |
| `scripts/pack_skill.py` | 打包 skill zip | ~30 |

---

## 11. CLI 接口

```bash
# 一次性配置（注册 skill + 密钥）
python agent.py setup --asr-key sk-xxx --asr-endpoint https://api.openai.com/v1

# 启动 Web 服务
python agent.py serve --port 9100

# 浏览器打开 http://localhost:9100
```

---

## 12. 依赖

### 12.1 Python 依赖

```toml
[project]
name = "meeting-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "httpx>=0.27",
]
```

### 12.2 环境变量

```bash
# .env.example

# LakeMind MCP
DATA_MCP_URL=http://localhost:8402/mcp
ASSET_MCP_URL=http://localhost:8401/mcp
ADMIN_MCP_URL=http://localhost:8403/mcp
DATA_TOKEN=test-steward-token
ASSET_TOKEN=test-business-token
ADMIN_TOKEN=test-steward-token

# Web 服务
PORT=9100

# 流水线参数
CHUNK_DURATION=10          # 音频 chunk 时长（秒）
SUMMARIZE_INTERVAL=6       # 每 N 个 chunk 触发摘要
```

---

## 13. 验证计划

| 验证项 | 方法 | 预期 |
|--------|------|------|
| setup | `python agent.py setup ...` | skill 注册成功，密钥配置成功 |
| Web UI | 浏览器打开 localhost:9100 | 页面正常显示 |
| 录音 | 点击录音按钮 | 音频 chunk 发送到 Agent |
| 实时转写 | 录音 10s 后 | 转写文本出现在页面 |
| 实时纪要 | 录音 60s 后 | 纪要出现在页面 |
| 实时知识 | 录音 120s 后 | 知识点出现在页面 |
| 检索 | 知识检索页面搜索 | 返回相关知识点 |
| 批量 | 上传音频文件 | 处理完成，知识入库 |
