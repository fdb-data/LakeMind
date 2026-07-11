# 会议实时知识化 Agent — 设计方案

> 位置：`examples/meeting-agent/`
> 状态：已实现并验证
> 日期：2026-07-11

---

## 1. 项目定位

**LakeMind 平台能力验证 Demo**。浏览器实时录音，Agent 编排流水线，验证 LakeMind 的存储、ASR、LLM、Embedding、向量检索、记忆等核心能力。

> **不是生产级应用**。省略了认证、持久化、并发控制、错误重试等生产必需能力。

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
│       │ WebM chunks (HTTP POST, 10s/chunk)              │
│       │ MediaRecorder per-chunk restart                 │
└───────┼──────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                  Agent (FastAPI :9100)                    │
│                                                           │
│  POST /api/chunk     ← 接收 WebM audio chunk              │
│  POST /api/start     ← 开始会议                           │
│  POST /api/stop      ← 结束会议                           │
│  GET  /api/stream    ← SSE 实时推送                       │
│  GET  /api/search    ← 知识检索                           │
│                                                           │
│  MeetingAgent 编排：                                      │
│    chunk → ffmpeg(WebM→WAV) → ASR → clean_tags → 转写    │
│    每6chunk → LLM summarize → 纪要                       │
│    每2纪要 → LLM extract → embedding → 向量入库          │
│           → retrieval self-check → 知识                  │
└──────┬──────────────────────────────────────────────────┘
       │
       ├──────────────────────┐
       ▼                      ▼
┌──────────────┐    ┌──────────────────┐
│ ModelServing │    │ LakeMindServer   │
│   :10824     │    │   :10823         │
│              │    │                  │
│ /v1/audio/   │    │ /api/v1/storage/ │
│  transcriptions│  │  objects (S3)    │
│ /v1/chat/    │    │ /api/v1/storage/ │
│  completions │    │  vectors (Lance) │
│ /v1/embeddings│   │ /api/v1/system/  │
│              │    │  health          │
└──────────────┘    └──────────────────┘
       │
       ▼
┌──────────────┐
│  AssetMCP    │
│   :8401      │
│              │
│ add_memory   │
└──────────────┘
```

### 2.1 关键设计决策

| 决策 | 原因 |
|------|------|
| Agent 直接调 ModelServing | Server Ray job 提交存在连接问题，改为直接调用 |
| host ffmpeg WebM→WAV | 容器内 ffmpeg 对部分 WebM 不稳定，host ffmpeg 可靠 |
| MediaRecorder per-chunk restart | 每个 chunk 是完整 WebM 文件，避免 EBML 头问题 |
| 知识入库绕过 AssetMCP | Server embedding endpoint 未 mount，直接用 ModelServing embeddings + Server vector API |
| FunASR 标签清理 | SenseVoice 输出含 `<\|zh\|> <|EMO|>` 等标签，用正则清理 |
| 验收日志 `[OK]/[FAIL]` | 验证者看控制台即可确认每个环节状态 |
| 检索自检 | 入库后自动 search 验证索引即时生效 |

---

## 3. 实时流水线

### 3.1 数据流

```
浏览器录音
  │  MediaRecorder 每 10s 生成完整 WebM chunk
  │  POST /api/chunk (binary body)
  ▼
Agent 接收 chunk
  │  s3_put 上传原始 WebM 到 S3
  │  ffmpeg WebM → WAV (16kHz mono)
  │  POST ModelServing /v1/audio/transcriptions → ASR
  │  clean_asr_text() 清理 FunASR 标签
  │  → SSE 推送纯文本转写到浏览器
  │  → 累积到 transcript buffer
  ▼
每 6 个 chunk
  │  POST ModelServing /v1/chat/completions → LLM 摘要
  │  → minutes (markdown)
  │  → S3 存储纪要
  │  → SSE 推送到浏览器
  ▼
每 2 次摘要
  │  POST ModelServing /v1/chat/completions → LLM 萃取知识点 (JSON)
  │  for each concept:
  │    POST ModelServing /v1/embeddings → 向量化
  │  POST Server /api/v1/storage/vectors → 批量入库
  │  → 检索自检 (search → log hits)
  │  → SSE 推送知识到浏览器
  ▼
用户停止录音
  │  最终 summarize + extract + 入库
  │  AssetMCP add_memory 记录会议历史
  ▼
完成
```

### 3.2 异步编排

```python
class MeetingAgent:
    async def on_chunk(self, meeting_id: str, audio: bytes):
        # 1. 上传 S3
        await self.client.s3_put(chunk_uri, audio)

        # 2. ASR (WebM → ffmpeg → WAV → ModelServing)
        result = await self.client.asr(audio)
        text = clean_asr_text(result["text"])

        # 3. SSE 推送 + 累积
        await self.sse.broadcast("transcript", {"text": text, ...})

        # 4. 每 6 chunk 触发摘要
        if chunk_num % 6 == 0:
            asyncio.create_task(self._summarize(meeting_id))

    async def _summarize(self, meeting_id):
        minutes = await self.client.llm_chat(SUMMARIZE_PROMPT, transcript)
        await self.client.s3_put(minutes_uri, minutes.encode())
        await self.sse.broadcast("minutes", {"minutes": minutes})

        # 每 2 次摘要触发萃取
        if summary_num % 2 == 0:
            asyncio.create_task(self._extract(meeting_id, minutes))

    async def _extract(self, meeting_id, minutes):
        concepts = json.loads(await self.client.llm_chat(EXTRACT_PROMPT, minutes))
        await self.client.ingest_knowledge("meetings", concepts)

        # 检索自检
        check = await self.client.search_knowledge(concepts[0]["title"])
        logger.info("[OK] Retrieval self-check: hits=%d", len(check["hits"]))

        await self.sse.broadcast("knowledge", {"concepts": concepts})
```

---

## 4. Web UI 设计

### 4.1 录音机制

```
MediaRecorder per-chunk restart:
  1. new MediaRecorder(stream, {mimeType: 'audio/webm'})
  2. recorder.start()
  3. setTimeout(10s) → recorder.stop()
  4. onstop: blob = new Blob(chunks) → pendingChunks.push(blob)
  5. 立即 new MediaRecorder 开始下一个 chunk
  6. setInterval(2s) 检查 pendingChunks → fetch POST /api/chunk
```

每个 chunk 是完整的 WebM 文件（有合法 EBML 头），避免分段问题。

### 4.2 页面布局

```
┌─────────────────────────────────────────────────────────┐
│  LakeMind Meeting Agent                    [知识检索]     │
├─────────────────────────────────────────────────────────┤
│  会议标题: [项目评审会]  参会人: [张三,李四]              │
│  [● 录音]  状态: 录音中  00:03:24  chunks: 20            │
│                                                          │
│  ┌─ 实时转写 ─────────┐  ┌─ 实时纪要 ─────────┐         │
│  │ [00:10] 大家好...  │  │ ## 会议摘要         │         │
│  │ [00:20] 我们决定...│  │ ## 关键决策         │         │
│  └────────────────────┘  └────────────────────┘         │
│                                                          │
│  ┌─ 已发现知识 (8) ────────────────────────────────────┐ │
│  │ • v1.0 发布计划变更 → 推迟至下周三                   │ │
│  │ • 认证模块存在未修复 bug                             │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Agent 与 LakeMind 接口

```python
class LakeMindClient:
    # S3 对象存储 (Server REST API)
    async def s3_put(self, uri: str, data: bytes) -> dict
    async def s3_get(self, uri: str) -> bytes
    async def s3_exists(self, uri: str) -> bool

    # ASR (ModelServing, 内含 ffmpeg WebM→WAV 转换)
    async def asr(self, audio: bytes) -> dict

    # LLM (ModelServing litellm)
    async def llm_chat(self, system_prompt: str, user_content: str) -> str

    # 知识向量 (ModelServing embeddings + Server vector API)
    async def search_knowledge(self, query: str, kb_name: str, top_k: int) -> dict
    async def ingest_knowledge(self, kb_name: str, concepts: list[dict]) -> dict

    # 记忆 (AssetMCP)
    async def add_memory(self, messages: list[dict], metadata: dict) -> dict
```

---

## 6. 验收日志设计

每个环节输出显式 `[OK]` / `[FAIL]` 标记：

| 环节 | 日志格式 |
|------|---------|
| ASR | `[OK] ASR chunk {n}: size={bytes}, text_len={len}, text={preview}` |
| 摘要 | `[OK] Summarize #{n}: text_len={len}` |
| 纪要存储 | `[OK] Minutes saved to S3: {uri}` |
| 萃取 LLM | `[OK] Extract #{n}: LLM response_len={len}` |
| 萃取解析 | `[OK] Extract #{n}: parsed {count} concepts` |
| 知识入库 | `[OK] Knowledge ingest: {count} concepts -> kb_{name}` |
| 检索自检 | `[OK] Retrieval self-check: query={q}, hits={n}` |
| 会议结束 | `[OK] Meeting stopped: chunks={n}, summaries={n}, extracts={n}, duration={s}s` |

---

## 7. 数据模型

### 7.1 S3 路径约定

```
s3://lakemind-filesets/{tenant}/meetings/{meeting_id}/
  ├── audio/
  │   ├── chunk-001.wav    ← 原始 WebM (保留)
  │   ├── chunk-002.wav
  │   └── ...
  └── minutes.md           ← 最新纪要
```

### 7.2 向量存储

```
DB: tenant_{tenant_id}
Table: kb_meetings
Schema:
  - concept_id: str
  - type: str (meeting_decision | meeting_action | meeting_fact)
  - title: str
  - description: str
  - tags: list[str]
  - s3_uri: str
  - vector: list[float] (dim=768, jina-embeddings-v2-base-zh)
  - created_at: float
```

---

## 8. Skill 包（参考）

Skill 包源码保留在 `skills/meeting-processing/`，包含 Ray job 定义（asr/summarize/extract）。运行时未使用（Agent 直接调 ModelServing），但展示了如何将业务逻辑封装为 LakeMind Skill。

---

## 9. 已知限制

| 限制 | 说明 |
|------|------|
| 内存存储 | 会议状态在 Agent 内存中，重启丢失 |
| 无认证 | Web UI 和 API 无认证 |
| 无并发控制 | 单会议串行处理 |
| 无错误重试 | ASR/LLM 失败仅记录，不重试 |
| 单租户 | 硬编码 `retail` 租户 |
| Skill 未启用 | 保留供参考，实际通过 ModelServing 直接调用 |
