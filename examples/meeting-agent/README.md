# Meeting Agent — LakeMind 平台能力验证 Demo

> **这是一个用于验证 LakeMind 平台认知资产存取能力的示例程序，不是生产级应用。**
>
> 它演示了 LakeMind 的核心能力链路：**音频存储 → ASR 语音识别 → LLM 摘要 → 知识萃取 → 向量入库 → 语义检索**。
> 程序刻意保持轻量，省略了认证、持久化、并发控制、错误重试等生产必需能力。

---

## 1. 它验证了什么

| LakeMind 能力 | Demo 中的体现 | 调用方式 |
|---------------|--------------|----------|
| **对象存储** (SeaweedFS) | 音频 chunk、会议纪要存取 | Server REST API `/api/v1/storage/objects` |
| **ASR 语音识别** (FunASR) | 浏览器录音 → 实时转写 | ModelServing `/v1/audio/transcriptions` |
| **LLM 对话** (litellm) | 转写文本 → 结构化会议纪要 | ModelServing `/v1/chat/completions` |
| **Embedding** (fastembed) | 知识向量化 + 语义检索 | ModelServing `/v1/embeddings` |
| **向量存储** (LanceDB) | 知识点入库 + 相似度搜索 | Server REST API `/api/v1/storage/vectors` |
| **记忆** (AssetMCP) | 会议结束记录 | AssetMCP `add_memory` |
| **S3 Skill 存储** | Skill zip 上传 | Server REST API |

---

## 2. 架构

```
浏览器 (Web UI)
  │  MediaRecorder 每 10s 生成完整 WebM chunk
  │  POST /api/chunk (binary body)
  ▼
Agent (FastAPI :9100)
  │
  ├─ ffmpeg WebM → WAV (host ffmpeg, 16kHz mono)
  ├─ POST ModelServing /v1/audio/transcriptions  → ASR 转写
  ├─ 清理 FunASR 标签 (<|zh|> <|EMO|> 等) → 纯文本
  ├─ SSE 推送转写到浏览器
  │
  ├─ 每 6 chunk: POST ModelServing /v1/chat/completions → 会议纪要
  ├─ S3 存储纪要 → SSE 推送
  │
  ├─ 每 2 次纪要: LLM 萃取知识点 (JSON)
  ├─ ModelServing /v1/embeddings → 向量化
  ├─ Server /api/v1/storage/vectors → 入库
  ├─ 自动检索自检 (search → log hits)
  └─ SSE 推送知识到浏览器
```

### 2.1 Ray jobs（一等公民）

Ray jobs 是 LakeMind 的一等公民。Agent 通过 DataMCP `ray_submit_job` 提交 Skill-based Ray jobs 执行 ASR/摘要/萃取等计算任务。Skill 包含 `jobs/{job_name}/ray.yaml` 定义 entrypoint 和依赖，Server 自动从 S3 拉取 Skill zip、解析 ray.yaml、注入租户密钥作为环境变量、提交到 Ray 集群。

当前 meeting-agent example 为简化演示，直接调用 ModelServing + Server REST API。Skill 包中的 `jobs/` 目录定义了 ASR/summarize/extract 三个 Ray job，可通过 DataMCP `ray_submit_job` 提交执行。

### 2.2 为什么用 host ffmpeg 转换

浏览器 `MediaRecorder` 生成 WebM 格式。ModelServing 的 FunASR 内部用 ffmpeg 加载音频，但容器内 ffmpeg 对部分 WebM 处理不稳定。因此在 Agent 侧用 **host ffmpeg** 将 WebM 转为标准 WAV (16kHz mono) 再发送，确保 ASR 稳定。

---

## 3. 前置条件

- **LakeMind 全栈运行**（13 容器，含 Server :10823 + ModelServing :10824 + AssetMCP :8401）
- **Python 3.12+**，已安装 `fastapi`、`uvicorn`、`httpx`、`mcp`
- **host ffmpeg**（用于 WebM → WAV 转换）
- **浏览器** 支持 MediaRecorder API（Chrome / Edge / Firefox）

---

## 4. 快速开始

```bash
cd examples/meeting-agent

# 设置环境变量（按需修改 .env.example）
export SERVER_API_URL=http://localhost:10823
export SERVER_API_KEY=lakemind-internal-api-key
export MODEL_SERVING_URL=http://localhost:10824
export MODELSERVING_API_KEY=lakemind-modelserving-key
export ASSET_MCP_URL=http://localhost:8401/mcp
export ASSET_TOKEN=test-business-token
export TENANT_ID=retail
export FFMPEG_PATH=ffmpeg          # 或 ffmpeg 的完整路径
export PORT=9100

# 1. 注册 Skill + 健康检查（一次性）
python scripts/setup.py

# 2. 启动 Agent
python agent.py

# 3. 浏览器打开
#    http://localhost:9100
#    输入会议标题，点击录音，开始说话
```

### 4.1 setup.py 健康检查

`setup.py` 在上传 Skill 之前会自动检查依赖服务：

```
--- Health Checks ---
  [OK] ModelServing /v1/models: 5 models available
  [OK] LakeMindServer /api/v1/system/health: healthy
--- Health Checks Passed ---
```

如果服务未就绪，脚本会退出并提示。

---

## 5. 实时流水线

```
录音开始
  │
  ├─ 每 10s: 浏览器生成 WebM chunk → Agent
  │    └─ ffmpeg 转 WAV → ModelServing ASR → 清理标签 → SSE 推送转写
  │
  ├─ 每 60s (6 chunk): Agent
  │    └─ ModelServing LLM 生成纪要 → S3 存储 → SSE 推送纪要
  │
  ├─ 每 120s (2 次纪要): Agent
  │    └─ LLM 萃取知识点 → Embedding 向量化 → 向量入库
  │       └─ 检索自检 (search 验证入库生效) → SSE 推送知识
  │
  └─ 停止录音: 最终纪要 + 知识萃取 + AssetMCP 记忆
```

### 5.1 验收日志

Agent 控制台输出每个环节的 `[OK]` / `[FAIL]` 标记，无需盯浏览器即可确认管线状态：

```
[OK] ASR chunk 1: size=27848, text_len=12, text=大家好今天开会。
[OK] ASR chunk 2: size=27848, text_len=8, text=我们讨论。
...
[OK] Summarize #1: text_len=350
[OK] Minutes saved to S3: s3://lakemind-filesets/retail/meetings/.../minutes.md
[OK] Extract #1: parsed 3 concepts
[OK] Knowledge ingest: 3 concepts -> kb_meetings
[OK] Retrieval self-check: query='发布日期推迟', hits=2
  hit: title='v1.0发布推迟至下周三', distance=0.12
  hit: title='认证模块存在bug', distance=0.34
[OK] Meeting stopped: chunks=12, summaries=3, extracts=1, duration=52s
```

---

## 6. API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/start` | 开始会议 `{title, participants}` → `{meeting_id}` |
| POST | `/api/chunk?meeting_id=xxx` | 上传音频 chunk（WebM binary body） → `{text, model}` |
| POST | `/api/stop` | 结束会议 `{meeting_id}` → `{duration, chunks, summaries}` |
| GET | `/api/stream` | SSE 实时推送（transcript / minutes / knowledge / status） |
| GET | `/api/search?query=xxx&top_k=5` | 知识语义检索 |
| GET | `/api/history` | 历史会议列表 |

### SSE 事件

```
event: transcript
data: {"text": "大家好今天开会。", "chunk": 1, "timestamp": "00:10"}

event: minutes
data: {"minutes": "## 会议摘要\n...", "updated_at": "01:00"}

event: knowledge
data: {"concepts": [{"title": "...", "body": "...", "type": "meeting_decision"}]}

event: status
data: {"status": "recording", "chunks": 6, "meeting_id": "..."}
```

---

## 7. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SERVER_API_URL` | `http://localhost:10823` | LakeMind Server REST API |
| `SERVER_API_KEY` | `lakemind-internal-api-key` | Server 认证密钥 |
| `MODEL_SERVING_URL` | `http://localhost:10824` | LakeMindModelServing |
| `MODELSERVING_API_KEY` | `lakemind-modelserving-key` | ModelServing 认证密钥 |
| `ASSET_MCP_URL` | `http://localhost:8401/mcp` | AssetMCP 端点 |
| `ASSET_TOKEN` | `test-business-token` | AssetMCP 认证 Token |
| `TENANT_ID` | `retail` | 租户 ID |
| `FFMPEG_PATH` | `ffmpeg` | host ffmpeg 路径 |
| `PORT` | `9100` | Agent Web 服务端口 |
| `SUMMARIZE_INTERVAL` | `6` | 每 N 个 chunk 触发摘要 |

---

## 8. 文件结构

```
examples/meeting-agent/
├── README.md                           ← 本文件
├── DESIGN.md                           ← 设计方案
├── pyproject.toml
├── .env.example
│
├── agent.py                            ← FastAPI 服务 + MeetingAgent 编排 + SSE
├── lakemind_client.py                  ← LakeMind 客户端 (S3 + ASR + LLM + 向量 + 记忆)
│
├── static/
│   ├── index.html                     ← Web UI
│   ├── style.css
│   └── app.js                         ← MediaRecorder 录音 + SSE + UI
│
├── skills/
│   └── meeting-processing/            ← Skill 包源码（参考，运行时未使用）
│       ├── SKILL.md
│       ├── lakemind_utils.py
│       └── jobs/
│           ├── asr/                    ← ASR job (ray.yaml + asr.py)
│           ├── summarize/             ← 摘要 job
│           └── extract/               ← 萃取 job
│
└── scripts/
    └── setup.py                       ← 健康检查 + Skill 打包上传
```

---

## 9. 已知限制（Demo 级别）

| 限制 | 说明 |
|------|------|
| **内存存储** | 会议状态在 Agent 内存中，重启丢失 |
| **无认证** | Web UI 和 API 无任何认证 |
| **无并发控制** | 单会议串行处理，多会议并发未测试 |
| **无错误重试** | ASR/LLM 失败后不重试，仅记录错误 |
| **单租户** | 硬编码 `retail` 租户 |
| **WebM 依赖** | 需要浏览器支持 MediaRecorder + host ffmpeg |
| **Skill 未启用** | Skill 包保留供参考，实际通过 ModelServing 直接调用 |

---

## 10. 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| ASR 502 Bad Gateway | WebM 格式无效或 ffmpeg 缺失 | 确认 `FFMPEG_PATH` 指向可用 ffmpeg |
| 转写包含 `<\|zh\|>` 等标签 | FunASR 原始输出 | Agent 已自动清理，如仍出现请检查 `clean_asr_text()` |
| 知识检索无结果 | 向量表未创建 | 首次入库时自动创建，检查 Server 日志 |
| setup.py 健康检查失败 | 依赖服务未启动 | 先启动 LakeMind 全栈 |
| 浏览器录音无声音 | 浏览器未授权麦克风 | 检查浏览器麦克风权限 |
