# 会议实时知识化 Agent — 设计方案

> 位置：`examples/meeting-agent/`
> 状态：已实现并验证
> 日期：2026-07-12

---

## 1. 项目定位

**LakeMind 平台能力验证 Demo**。浏览器实时录音，Agent 编排流水线，通过 Ray job 执行 ASR/摘要/萃取，验证 LakeMind 的存储、Ray 分布式计算、Skill 管理、ASR、LLM、Embedding、向量检索、记忆等核心能力。

> **不是生产级应用**。省略了认证、持久化、并发控制、错误重试等生产必需能力。

---

## 2. 架构

```
┌─────────────────────────────────────────────────────────┐
│                    浏览器 (Web UI)                        │
│  MediaRecorder per-chunk restart (10s/chunk)             │
│  POST /api/chunk (WebM binary) + SSE 消费                │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Agent (FastAPI :9100)                        │
│                                                           │
│  职责：输入归一化 + job 编排 + 结果分发                    │
│    chunk → ffmpeg WAV → S3 → submit Ray job(asr)         │
│         → poll → S3 下载 → SSE 推送                       │
│    每6chunk → S3 → submit Ray job(summarize) → poll      │
│    每2纪要 → S3 → submit Ray job(extract) → poll         │
│           → retrieval self-check → SSE 推送               │
│                                                           │
│  不直接调用 ModelServing（ASR/LLM/embed 全在 Ray job 内）  │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              LakeMind Server (:10823)                     │
│  /api/v1/compute/jobs/submit → Ray 集群                   │
│  /api/v1/storage/objects → S3 (SeaweedFS)                │
│  /api/v1/storage/vectors → LanceDB                        │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Ray Cluster (3 nodes, 12 CPU)               │
│                                                           │
│  jobs/asr/main.py:     WAV → ModelServing ASR → S3       │
│  jobs/summarize/main.py: transcript → LLM → S3           │
│  jobs/extract/main.py: minutes → LLM → embed → 入库 → S3 │
│                                                           │
│  共享: lakemind_utils.py (S3/LLM/ASR/embed/ingest)       │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 层次划分

| 层 | 位置 | 职责 | 复用性 |
|----|------|------|--------|
| **Web** | `static/` | 录音 UI + SSE 消费 | 仅本 demo |
| **Agent** | `agent.py` + `lakemind_client.py` | 编排：S3 存取 + Ray job 提交/轮询 + SSE 分发 | demo 专属 |
| **Skill** | `skills/meeting-processing/` | 可复用业务逻辑包 | 可被其他 Agent 复用 |
| **Job** | `skills/.../jobs/{name}/main.py` | 最小执行单元 | 可独立提交到任何 Ray 集群 |

### 关键原则

- **Agent 不直接调用 ModelServing** — ASR/LLM/embed 全部在 Ray job 内执行
- **Agent 只做编排** — 上传 S3、提交 job、轮询状态、下载结果、SSE 推送
- **Job 是自包含的** — 每个 `main.py` 通过 `lakemind_utils.py` 调用 ModelServing/Server，不依赖 Agent
- **Skill 可复用** — 其他 Agent 可通过 `ray_submit_job("lake://skills/meeting-processing", "asr", ...)` 提交相同的 job

---

## 4. 数据流

### 4.1 ASR

```
Agent                          Server                    Ray Worker
  │                               │                          │
  ├─ ffmpeg WebM → WAV            │                          │
  ├─ S3 PUT chunk.wav ──────────→ │                          │
  ├─ POST /jobs/submit ─────────→ │                          │
  │   {skill_uri, job=asr,        │                          │
  │    params={chunk_uri,         │                          │
  │            result_uri}}       │                          │
  │                               ├─ fetch skill zip from S3 │
  │                               ├─ parse ray.yaml          │
  │                               ├─ inject RAY_JOB_PARAMS   │
  │                               ├─ submit to Ray ────────→ │
  │                               │                          ├─ download WAV from S3
  │                               │                          ├─ POST ModelServing ASR
  │                               │                          ├─ S3 PUT result.json
  │                               │                          ├─ (job SUCCEEDED)
  │ ← poll status ────────────── │ ← get_job_status ────── │
  ├─ S3 GET result.json ────────→│                          │
  ├─ clean_asr_text()             │                          │
  └─ SSE broadcast transcript     │                          │
```

### 4.2 Summarize / Extract

同上模式：Agent 上传输入到 S3 → submit job → poll → 下载结果 → SSE 推送。

---

## 5. Skill 包结构

```
meeting-processing/
├── SKILL.md                    ← Skill 声明（jobs 列表 + 模型服务说明）
├── lakemind_utils.py           ← 共享工具
│   ├── download_from_s3()
│   ├── upload_to_s3()
│   ├── llm_chat()
│   ├── asr()
│   ├── embed()
│   └── ingest_knowledge()
└── jobs/
    ├── asr/
    │   ├── ray.yaml            ← entrypoint: "python jobs/asr/main.py"
    │   ├── requirements.txt    ← httpx
    │   └── main.py             ← ASR job entrypoint
    ├── summarize/
    │   ├── ray.yaml
    │   ├── requirements.txt
    │   └── main.py             ← 摘要 job entrypoint
    └── extract/
        ├── ray.yaml
        ├── requirements.txt
        └── main.py             ← 萃取 job entrypoint
```

### ray.yaml 格式

```yaml
entrypoint: "python jobs/asr/main.py"   # 相对于 skill root
dependencies: []                         # pip 依赖（httpx 已在 requirements.txt）
resources:
  num_cpus: 1                            # Ray 资源声明
```

### RAY_JOB_PARAMS

Server 将 `submit` 请求中的 `params` 字段序列化为 `RAY_JOB_PARAMS` 环境变量注入到 Ray job。Job 代码通过 `json.loads(os.environ["RAY_JOB_PARAMS"])` 读取参数。

---

## 6. S3 路径约定

```
s3://lakemind-filesets/{tenant}/meetings/{meeting_id}/
  ├── audio/chunk-001.wav          ← Agent 上传的 WAV 音频
  ├── audio/chunk-002.wav
  ├── transcript.json              ← Agent 上传的转写文本
  ├── minutes.md                   ← Summarize job 输出的纪要
  └── results/
      ├── asr-001.json             ← ASR job 结果
      ├── summarize-001.json       ← Summarize job 结果
      └── extract-001.json         ← Extract job 结果
```

---

## 7. 向量 schema

- DB: `tenant_{tenant_id}`
- Table: `kb_meetings`
- Fields: `concept_id`, `type`, `title`, `description`, `tags`, `s3_uri`, `vector(dim=768)`, `created_at`

---

## 8. 已知限制

| 限制 | 说明 |
|------|------|
| 内存存储 | 会议状态在 Agent 内存中，重启丢失 |
| 无认证 | Web UI 和 API 无认证 |
| 无并发控制 | 单会议串行处理 |
| 无错误重试 | Ray job 失败后不重试 |
| 单租户 | 硬编码 `retail` 租户 |
| 轮询模式 | Agent 轮询 job 状态（非回调），增加延迟 |
