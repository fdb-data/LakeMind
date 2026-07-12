# Meeting Agent — LakeMind 平台能力验证 Demo

> **这是一个用于验证 LakeMind 平台认知资产存取能力的示例程序，不是生产级应用。**
>
> 它演示了 LakeMind 的核心能力链路：**音频存储 → Ray job ASR → Ray job 摘要 → Ray job 知识萃取 → 向量入库 → 语义检索**。
> 程序刻意保持轻量，省略了认证、持久化、并发控制、错误重试等生产必需能力。

---

## 1. 它验证了什么

| LakeMind 能力 | Demo 中的体现 | 调用方式 |
|---------------|--------------|----------|
| **对象存储** (SeaweedFS) | 音频 chunk、会议纪要、job 结果存取 | Server REST API `/api/v1/storage/objects` |
| **Ray 分布式计算** | ASR/摘要/萃取全部通过 Ray job 执行 | Server REST API `/api/v1/compute/jobs/submit` |
| **Skill 包管理** | meeting-processing Skill 打包上传 | S3 存储 + `ray.yaml` 声明 |
| **ASR 语音识别** (FunASR) | Ray job: 音频 → 转写文本 | ModelServing `/v1/audio/transcriptions` |
| **LLM 对话** (litellm) | Ray job: 转写 → 结构化纪要 + 知识萃取 | ModelServing `/v1/chat/completions` |
| **Embedding** (fastembed) | Ray job: 知识向量化 + 入库 | ModelServing `/v1/embeddings` |
| **向量存储** (LanceDB) | 知识点入库 + 相似度搜索 | Server REST API `/api/v1/storage/vectors` |
| **记忆** (AssetMCP) | 会议结束记录 | AssetMCP `add_memory` |

---

## 2. 架构

```
浏览器 (Web UI)
  │  MediaRecorder 每 10s 生成 WebM chunk
  │  POST /api/chunk (binary body)
  ▼
Agent (FastAPI :9100)
  │  职责：输入归一化 + job 编排 + 结果分发
  │
  ├─ ffmpeg WebM → WAV (host ffmpeg, 16kHz mono)
  ├─ S3 上传 WAV
  ├─ Server /api/v1/compute/jobs/submit (skill=meeting-processing, job=asr)
  ├─ 轮询 job 状态 → S3 下载结果 → SSE 推送转写
  │
  ├─ 每 6 chunk: S3 上传 transcript → submit job=summarize → 轮询 → SSE 推送纪要
  │
  ├─ 每 2 次纪要: S3 上传 minutes → submit job=extract → 轮询 → SSE 推送知识
  │
  └─ 停止: 最终纪要 + AssetMCP add_memory
```

### 2.1 层次划分

```
Web (static/)
  │  录音 UI + SSE 消费
  ▼
Agent (agent.py + lakemind_client.py)
  │  编排：上传 S3 → 提交 Ray job → 轮询 → 下载 S3 → SSE 推送
  │  不直接调用 ModelServing（ASR/LLM/embed 全在 Ray job 内）
  ▼
Skill (skills/meeting-processing/)
  │  SKILL.md + lakemind_utils.py (共享工具)
  │
  ├─ jobs/asr/main.py       Ray job: WAV → ModelServing ASR → S3
  ├─ jobs/summarize/main.py Ray job: transcript → ModelServing LLM → S3
  └─ jobs/extract/main.py   Ray job: minutes → LLM → embed → 向量入库 → S3
```

- **Web**: 浏览器录音 + SSE 显示，无业务逻辑
- **Agent**: 编排层，只做 S3 存取 + Ray job 提交/轮询 + SSE 分发，不直接调用 ModelServing
- **Skill**: 可复用的业务逻辑包，每个 job 是独立的 Ray 任务，通过 `ray.yaml` 声明 entrypoint
- **Job**: 最小执行单元，调用 ModelServing/Server REST API 完成具体计算

### 2.2 为什么用 host ffmpeg

浏览器 `MediaRecorder` 生成 WebM 格式。Ray worker 容器内无 ffmpeg，因此在 Agent 侧用 **host ffmpeg** 将 WebM 转为标准 WAV (16kHz mono) 再上传 S3，Ray job 直接处理 WAV。

---

## 3. 前置条件

- **LakeMind 全栈运行**（13 容器，含 Server :10823 + ModelServing :10824 + Ray 3 节点 + AssetMCP :8401）
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
export SKILL_URI=lake://skills/meeting-processing
export FFMPEG_PATH=ffmpeg
export PORT=9100

# 1. 打包 Skill + 健康检查 + 上传 S3（一次性）
python scripts/setup.py

# 2. 启动 Agent
python agent.py

# 3. 浏览器打开 http://localhost:9100
#    输入会议标题，点击录音，开始说话
```

### 4.1 setup.py 健康检查

```
--- Health Checks ---
  [OK] ModelServing /v1/models: 5 models available
  [OK] LakeMindServer health: distributed=True
--- Health Checks Passed ---
```

---

## 5. 实时流水线

```
录音开始
  │
  ├─ 每 10s: 浏览器 → WebM chunk → Agent
  │    └─ ffmpeg WAV → S3 → Ray job(asr) → 轮询 → S3 结果 → SSE 推送转写
  │
  ├─ 每 60s (6 chunk): Agent
  │    └─ S3 transcript → Ray job(summarize) → 轮询 → S3 结果 → SSE 推送纪要
  │
  ├─ 每 120s (2 次纪要): Agent
  │    └─ S3 minutes → Ray job(extract) → 轮询 → S3 结果
  │       └─ 检索自检 (search 验证入库生效) → SSE 推送知识
  │
  └─ 停止录音: 最终纪要 + AssetMCP 记忆
```

### 5.1 验收日志

```
[SUBMIT] ASR chunk 1 -> job job_a1b2c3d4
[OK] ASR chunk 1: text_len=12, text=大家好今天开会。
[SUBMIT] Summarize #1 -> job job_e5f6g7h8
[OK] Summarize #1: text_len=350
[SUBMIT] Extract #1 -> job job_i9j0k1l2
[OK] Extract #1: 3 concepts
[OK] Retrieval self-check: query='发布日期推迟', hits=2
[OK] Meeting stopped: chunks=12, summaries=3, extracts=1, duration=52s
```

---

## 6. API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/start` | 开始会议 `{title, participants}` → `{meeting_id}` |
| POST | `/api/chunk?meeting_id=xxx` | 上传音频 chunk（WebM binary body） → `{text, segments}` |
| POST | `/api/stop` | 结束会议 `{meeting_id}` → `{duration, chunks, summaries}` |
| GET | `/api/stream` | SSE 实时推送（transcript / minutes / knowledge / status） |
| GET | `/api/search?query=xxx&top_k=5` | 知识语义检索 |
| GET | `/api/history` | 历史会议列表 |

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
| `SKILL_URI` | `lake://skills/meeting-processing` | Skill URI（Ray job 提交用） |
| `FFMPEG_PATH` | `ffmpeg` | host ffmpeg 路径 |
| `PORT` | `9100` | Agent Web 服务端口 |
| `SUMMARIZE_INTERVAL` | `6` | 每 N 个 chunk 触发摘要 |

---

## 8. 文件结构

```
examples/meeting-agent/
├── agent.py                            ← Web + Agent 编排层
├── lakemind_client.py                  ← LakeMind 客户端 (S3 + Ray job + 检索 + 记忆)
├── pyproject.toml
├── .env.example
│
├── static/                             ← Web 层
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── skills/                             ← Skill 层
│   └── meeting-processing/
│       ├── SKILL.md                    ← Skill 声明
│       ├── lakemind_utils.py           ← 共享工具 (S3/LLM/ASR/embed/ingest)
│       └── jobs/                       ← Job 层
│           ├── asr/
│           │   ├── ray.yaml            ← Ray job 声明
│           │   ├── requirements.txt
│           │   └── main.py             ← ASR entrypoint
│           ├── summarize/
│           │   ├── ray.yaml
│           │   ├── requirements.txt
│           │   └── main.py             ← 摘要 entrypoint
│           └── extract/
│               ├── ray.yaml
│               ├── requirements.txt
│               └── main.py             ← 萃取 entrypoint
│
└── scripts/
    ├── setup.py                        ← 健康检查 + Skill 打包上传
    └── pack_skill.py                   ← 独立打包工具
```

---

## 9. 已知限制（Demo 级别）

| 限制 | 说明 |
|------|------|
| **内存存储** | 会议状态在 Agent 内存中，重启丢失 |
| **无认证** | Web UI 和 API 无任何认证 |
| **无并发控制** | 单会议串行处理，多会议并发未测试 |
| **无错误重试** | Ray job 失败后不重试，仅记录错误 |
| **单租户** | 硬编码 `retail` 租户 |
| **WebM 依赖** | 需要浏览器支持 MediaRecorder + host ffmpeg |

---

## 10. 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| Ray job 提交 500 | Ray 集群未启动 | 检查 `docker ps` 含 ray-head + 2 workers |
| Ray job 超时 | job 执行超过 120s | 检查 ModelServing 可达性，调整 `poll_job` timeout |
| ASR 结果为空 | WAV 格式无效 | 确认 `FFMPEG_PATH` 指向可用 ffmpeg |
| 转写包含 `<\|zh\|>` 等标签 | FunASR 原始输出 | Agent 已自动清理 |
| 知识检索无结果 | 向量表未创建 | 首次入库时自动创建，检查 Server 日志 |
| setup.py 健康检查失败 | 依赖服务未启动 | 先启动 LakeMind 全栈 |
