# Meeting Agent v0.2.0 开发方案与计划（修订版）

> **依据**：`v0.2.0.design/LakeMind_examples_meeting-agent_v0.2.0_设计方案.md` + 用户修订意见
> **当前代码**：`examples/meeting-agent/`（v0.1 技术Demo）
> **定位**：Demo / Golden Example，不是产品。安全、一致性可验证，但不做运营级兜底。
> **估算单位**：1 SP ≈ 1 人理想日

---

## 0. 修订要点（vs 初版计划）

| 修订项 | 初版 | 修订版 | 理由 |
|--------|------|--------|------|
| 回放 | audio_finalize Job 合并分片 → m4a → Range 回放 | 分片逐个播放，不合并 | 用户明确要求，不要搞复杂 |
| 数据库 | PostgreSQL meeting_agent schema | **SQLite**（应用自带） | LakeMind PG 是元数据管理，不给外面做数据库 |
| Reconciler | 启动时恢复 + 补齐 + 标记 LOST | **去掉** | Demo 不需要后台兜底 |
| 完整删除 | 异步删除 S3+Artifact+Knowledge+Memory+Chunk → Reconciler 重试 | 简单删除：删 S3 对象 + 删 SQLite 记录 | Demo 不需要生产级清理 |
| 限流/配额 | 注册限流 + 登录限流 + 并发控制 | **去掉** | Demo 不需要 |
| Memory | 用户确认后保存 | 会议结束直接保存 | Demo 先这样，有需求再说 |
| audio_finalize Job | 有 | **去掉** | 分片直接回放，不需要合并 |
| transcript_finalize Job | 有 | **简化**为可选步骤 | 分片 ASR 结果直接拼接即可 |
| Storage Range | WP0-C 平台增强 | **去掉** | 分片回放不需要 Range |
| 保留策略/隐私提示 | 30天保留 + 隐私确认 | **去掉** | Demo |

---

## 1. 现状与差距

### 1.1 当前 v0.1 代码

| 文件 | 行数 | 问题 |
|------|------|------|
| `agent.py` | 567 | 单文件、无认证、全局 SSE、内存状态、Iceberg 全表扫描 |
| `lakemind_client.py` | 286 | 旧式 API Key + X-Tenant-Id，无用户委托 |
| `static/` | 476 | Vanilla JS，无 Auth、无播放器、无模板 |
| `skills/` | 3 jobs | Prompt 写死、无证据、直接入库 |

### 1.2 平台差距（需补齐）

| 差距 | 解决方案 | WP |
|------|----------|----|
| 无 POST /principals | Server 新增创建 USER principal 端点 | WP0-A |
| 无 meeting_user 角色 | Migration 创建角色 + capability | WP0-B |
| 无 Model Profile 预置 | 部署脚本预置 4 个 profile | WP0-C |

### 1.3 数据存储分工（修订）

```text
SQLite（应用自带，零依赖）
  ├─ meeting_tasks          任务状态、标题、模板快照
  ├─ meeting_audio_chunks   分片记录（sequence、object_uri、checksum）
  ├─ meeting_stage_runs     阶段与 Job 关联
  ├─ meeting_transcript_segments  转写段落（original + edited）
  ├─ meeting_minutes_versions    纪要版本
  ├─ meeting_knowledge_items     知识草稿 + 审核状态
  ├─ meeting_templates           模板
  └─ meeting_template_versions   模板版本

LakeMind S3（通过 Server API）
  └─ audio/chunks/000001.webm, transcript.json, minutes.md

LakeMind Knowledge API
  └─ 已发布知识（用户审核后 ingest）

LakeMind Memory API
  └─ 会议记忆（会议结束直接保存）

LakeMind JobService v2
  └─ asr_chunk, minutes_generate, knowledge_extract
```

---

## 2. 工作包分解

### WP0：平台前置

> **依赖**：无。WP0-A / WP0-B / WP0-C 可并行。

#### WP0-A：Principal 创建 API

| Task | 描述 | SP |
|------|------|----|
| WP0-A-1 | api/security.py 新增 POST /api/v1/security/principals：创建 USER principal + membership | 2 |
| WP0-A-2 | 权限：tenant_admin 或 platform_admin 可调，只能创建 USER 类型 | 1 |
| WP0-A-3 | 请求 {username, password_hash, display_name?, tenant_id, role_name?} → 响应 {principal_id, status} | 1 |
| WP0-A-4 | 用户名唯一校验 + 测试 | 1 |

**估算**：5 SP

#### WP0-B：meeting_user 角色

| Task | 描述 | SP |
|------|------|----|
| WP0-B-1 | Migration 010：创建 meeting_user 角色 | 1 |
| WP0-B-2 | Capability：asset:create, job:submit, job:read, knowledge:ingest, knowledge:search, memory:add, memory:read | 1 |
| WP0-B-3 | 在 security/actions.py 注册 + 测试 | 1 |

**估算**：3 SP

#### WP0-C：Model Profile 预置

| Task | 描述 | SP |
|------|------|----|
| WP0-C-1 | 部署脚本预置 4 profile：meeting-asr / meeting-minutes / meeting-knowledge-extract / meeting-embedding | 2 |
| WP0-C-2 | 每个 profile 创建 route + 绑定 deployment + 验证 resolve | 1 |

**估算**：3 SP

**WP0 总计**：11 SP

---

### WP1：身份与任务隔离

> **依赖**：WP0-A, WP0-B

#### WP1-A：后端身份

| Task | 描述 | SP |
|------|------|----|
| WP1-A-1 | backend/app/security/：Session 管理（HttpOnly Cookie） | 2 |
| WP1-A-2 | POST /api/auth/register：调 Server POST /security/principals + 自动加入 meeting-agent-demo 租户 | 2 |
| WP1-A-3 | POST /api/auth/login：调 Server /auth/login 获取 token → 设 HttpOnly Cookie | 1 |
| WP1-A-4 | POST /api/auth/logout + GET /api/auth/me | 1 |
| WP1-A-5 | SecurityContext middleware：Cookie → token → Server /auth/me → 注入 ctx | 2 |
| WP1-A-6 | 密码 bcrypt + 弱密码拒绝 | 1 |
| WP1-A-7 | 测试 | 1 |

**估算**：10 SP

#### WP1-B：SQLite Schema

| Task | 描述 | SP |
|------|------|----|
| WP1-B-1 | SQLite 初始化 + 8 张表建表（meeting_tasks, meeting_audio_chunks, meeting_stage_runs, meeting_transcript_segments, meeting_minutes_versions, meeting_knowledge_items, meeting_templates, meeting_template_versions） | 2 |
| WP1-B-2 | 索引：owner_principal_id + status + created_at | 1 |
| WP1-B-3 | Repository 层：每张表 CRUD + owner 过滤 | 2 |
| WP1-B-4 | 测试 | 1 |

**估算**：6 SP

#### WP1-C：Task-scoped SSE

| Task | 描述 | SP |
|------|------|----|
| WP1-C-1 | SSEBroker 重写：按 task_id 分组，连接时验证 owner | 2 |
| WP1-C-2 | GET /api/tasks/{task_id}/events：SSE 端点 | 1 |
| WP1-C-3 | 事件类型：task.status_changed, chunk.uploaded, transcript.segment_ready, minutes.preview_ready, knowledge.draft_ready, error | 1 |
| WP1-C-4 | 安全测试：用户 A 无法订阅用户 B 的 SSE | 1 |

**估算**：5 SP

**WP1 总计**：21 SP

---

### WP2：任务、模板与新 UI

> **依赖**：WP1

#### WP2-A：React 前端骨架

| Task | 描述 | SP |
|------|------|----|
| WP2-A-1 | Vite + React + TypeScript + Ant Design 初始化 | 1 |
| WP2-A-2 | API client（axios + Cookie auth） + 路由结构 | 2 |
| WP2-A-3 | Auth pages：登录 + 注册 | 2 |
| WP2-A-4 | AppLayout：导航 + 用户菜单 + 路由守卫 | 2 |
| WP2-A-5 | 全局 error handling + loading | 1 |

**估算**：8 SP

#### WP2-B：任务列表与创建

| Task | 描述 | SP |
|------|------|----|
| WP2-B-1 | GET /api/tasks（分页 + owner 过滤 + status/source_type/q 查询） | 2 |
| WP2-B-2 | POST /api/tasks（Idempotency-Key） + GET /api/tasks/{id} + PATCH + DELETE | 2 |
| WP2-B-3 | 前端"我的会议"页面：卡片列表 + 过滤 + 搜索 | 3 |
| WP2-B-4 | 前端"新建会议"三步向导：基本信息 → 选模板 → 快速调整 | 3 |
| WP2-B-5 | 测试 | 2 |

**估算**：12 SP

#### WP2-C：模板系统

| Task | 描述 | SP |
|------|------|----|
| WP2-C-1 | 5 个内置模板 seed（通用/项目评审/需求访谈/客户沟通/事故复盘） | 2 |
| WP2-C-2 | GET /api/templates + POST + POST /clone + POST /versions + POST /archive | 2 |
| WP2-C-3 | Template Snapshot：任务创建时冻结 | 1 |
| WP2-C-4 | 前端"我的模板"页面 | 3 |
| WP2-C-5 | 测试 | 1 |

**估算**：9 SP

**WP2 总计**：29 SP

---

### WP3：录音与分片回放

> **依赖**：WP1, WP2
> **关键修订**：不做 audio_finalize，分片直接逐个回放。

#### WP3-A：录音上传

| Task | 描述 | SP |
|------|------|----|
| WP3-A-1 | POST /api/tasks/{id}/start：状态 → RECORDING | 1 |
| WP3-A-2 | PUT /api/tasks/{id}/audio/chunks/{sequence}：幂等上传（同 sequence+checksum 返回已有，不同 checksum 返回 409） | 3 |
| WP3-A-3 | S3 路径服务端生成：meeting-agent-demo/users/{pid}/meetings/{tid}/audio/chunks/000001.webm | 1 |
| WP3-A-4 | POST /api/tasks/{id}/stop：状态 → FINALIZING → 触发最终处理 | 1 |
| WP3-A-5 | POST /api/tasks/{id}/audio/upload：上传已有录音（整文件作为一个 chunk） | 1 |
| WP3-A-6 | GET /api/tasks/{id}/audio/manifest：返回分片清单（sequence, object_uri, duration_ms） | 1 |
| WP3-A-7 | 前端录音工作台：MediaRecorder(10000ms) + 分片上传 + 计时器 + 网络状态 | 4 |

**估算**：12 SP

#### WP3-B：分片回放（不合并）

| Task | 描述 | SP |
|------|------|----|
| WP3-B-1 | GET /api/tasks/{id}/audio/chunks/{sequence}：代理分片字节流（验证 owner） | 2 |
| WP3-B-2 | 前端分片播放器：加载 manifest → 逐个播放分片 → 播完自动下一个 → 进度条（累计时间） | 3 |
| WP3-B-3 | 播放控制：play/pause + 速度（1x/1.5x/2x） + 前后 10s（跨分片跳转） | 2 |
| WP3-B-4 | 测试：分片可播放、用户 B 无法播放用户 A 的分片 | 1 |

**估算**：8 SP

#### WP3-C：转写与回放同步

| Task | 描述 | SP |
|------|------|----|
| WP3-C-1 | GET /api/tasks/{id}/transcript：返回 segment 列表（含 chunk_sequence + start_ms + end_ms） | 1 |
| WP3-C-2 | PATCH /api/tasks/{id}/transcript/segments/{segment_id}：编辑（保留 original + edited） | 2 |
| WP3-C-3 | 前端联动：当前播放位置高亮 segment + 点击 segment 跳转到对应分片+时间 | 3 |
| WP3-C-4 | 测试 | 1 |

**估算**：7 SP

**WP3 总计**：27 SP

---

### WP4：正式流水线

> **依赖**：WP1, WP2, WP3, WP0-C
> **关键修订**：去掉 audio_finalize，Memory 直接保存，简化 Lineage。

#### WP4-A：Skill 升级

| Task | 描述 | SP |
|------|------|----|
| WP4-A-1 | asr_chunk Job：接收 language + hotwords（从 template_snapshot），调 ModelServing ASR | 2 |
| WP4-A-2 | minutes_generate Job：接收 transcript + template_snapshot，生成纪要 Markdown + 结构化 JSON | 2 |
| WP4-A-3 | knowledge_extract Job：接收 transcript + minutes + extraction_policy，输出结构化 JSON（含 evidence segment_ids + quote + confidence） | 3 |
| WP4-A-4 | Skill manifest：3 个 job + 3 个 model_profile + input/output schema | 1 |
| WP4-A-5 | 通过 Server POST /skills/register + /publish 发布 | 1 |
| WP4-A-6 | 测试每个 Job | 2 |

**估算**：11 SP

#### WP4-B：流水线编排

| Task | 描述 | SP |
|------|------|----|
| WP4-B-1 | PipelineService 实时阶段：ASR per chunk → SSE 推送 segment | 2 |
| WP4-B-2 | PipelineService 最终阶段：minutes_generate → knowledge_extract → memory_save | 2 |
| WP4-B-3 | JobService v2 调用：POST /api/v1/jobs with skill_ref + inputs + model_profile + idempotency_key | 2 |
| WP4-B-4 | Job 轮询：GET /api/v1/jobs/{id} → 完成后读取 result → 写 SQLite | 2 |
| WP4-B-5 | Stage Run 记录：meeting_stage_runs 关联 job_id + skill_version | 1 |
| WP4-B-6 | 错误处理：单分片 ASR 失败标记 failed，不终止整场会议 | 1 |

**估算**：10 SP

#### WP4-C：Memory 直接保存

| Task | 描述 | SP |
|------|------|----|
| WP4-C-1 | 会议结束后调 Server POST /api/v1/memories/add 保存摘要（标题、时间、关键结论、行动项） | 2 |
| WP4-C-2 | 前端"处理过程"Tab：展示阶段 + 状态 + Job ID + 时间 | 1 |

**估算**：3 SP

**WP4 总计**：24 SP

---

### WP5：知识审核与发布

> **依赖**：WP4
> **说明**：知识萃取后存为草稿，用户审核后发布到 LakeMind Knowledge。

#### WP5-A：知识审核 API + 发布

| Task | 描述 | SP |
|------|------|----|
| WP5-A-1 | GET /api/tasks/{id}/knowledge：返回草稿列表 | 1 |
| WP5-A-2 | PATCH /api/tasks/{id}/knowledge/{item_id}：编辑（title, body, tags） | 1 |
| WP5-A-3 | POST /api/tasks/{id}/knowledge/{item_id}/accept | 1 |
| WP5-A-4 | POST /api/tasks/{id}/knowledge/{item_id}/reject | 1 |
| WP5-A-5 | POST /api/tasks/{id}/knowledge/publish：批量发布 → 调 Server POST /knowledge/ingest | 2 |
| WP5-A-6 | 测试 | 1 |

**估算**：7 SP

#### WP5-B：前端审核 UI

| Task | 描述 | SP |
|------|------|----|
| WP5-B-1 | 前端"知识草稿"Tab：type/title/body/tags/confidence/证据/状态 | 2 |
| WP5-B-2 | 操作：编辑/接受/拒绝/批量发布 | 2 |
| WP5-B-3 | 证据展示：点击跳转到对应分片+时间 | 2 |
| WP5-B-4 | 前端"我的知识"页面：跨会议检索（调 Server /knowledge/search） | 1 |

**估算**：7 SP

**WP5 总计**：14 SP

---

### WP6：验收

> **依赖**：WP1~WP5
> **关键修订**：去掉 Reconciler、去掉完整删除兜底，保留基本 Golden Path。

#### WP6-A：基本删除 + Retry

| Task | 描述 | SP |
|------|------|----|
| WP6-A-1 | DELETE /api/tasks/{id}：删 S3 分片 + 删 SQLite 记录（同步，简单删） | 2 |
| WP6-A-2 | POST /api/tasks/{id}/stages/{stage}/retry：调 JobService retry | 1 |
| WP6-A-3 | 前端 Retry 按钮 + 删除确认 | 1 |

**估算**：4 SP

#### WP6-B：Golden Path 验收

| Task | 描述 | SP |
|------|------|----|
| WP6-B-1 | E2E：注册→登录→创建→选模板→录音→分片上传→ASR→实时转写→停止→分片回放→查看纪要→知识草稿→审核→发布→Memory→检索→Control Center 观察→删除 | 4 |
| WP6-B-2 | 安全测试：用户隔离（任务/SSE/录音/知识）、伪造 Owner 无效 | 2 |
| WP6-B-3 | 一致性测试：分片幂等、冲突检测 | 1 |
| WP6-B-4 | 验收报告 | 1 |

**估算**：8 SP

**WP6 总计**：12 SP

---

## 3. 依赖与执行顺序

```text
WP0 (平台前置)
  ├─ WP0-A (Principal API)
  ├─ WP0-B (meeting_user 角色)
  └─ WP0-C (Model Profile)
       │
       ▼
WP1 (身份与隔离)
  ├─ WP1-A (后端身份) ← WP0-A, WP0-B
  ├─ WP1-B (SQLite Schema)
  └─ WP1-C (Task SSE) ← WP1-A, WP1-B
       │
       ▼
WP2 (任务与模板)
  ├─ WP2-A (前端骨架) ← WP1-A
  ├─ WP2-B (任务 CRUD) ← WP1-B, WP2-A
  └─ WP2-C (模板) ← WP1-B, WP2-A
       │
       ▼
WP3 (录音与分片回放)
  ├─ WP3-A (录音上传) ← WP1, WP2
  ├─ WP3-B (分片回放) ← WP3-A
  └─ WP3-C (转写同步) ← WP3-A, WP3-B
       │
       ▼
WP4 (流水线)
  ├─ WP4-A (Skill) ← WP3, WP0-C
  ├─ WP4-B (编排) ← WP4-A, WP3
  └─ WP4-C (Memory) ← WP4-B
       │
       ▼
WP5 (知识审核)
  ├─ WP5-A (API + 发布) ← WP4
  └─ WP5-B (UI) ← WP5-A
       │
       ▼
WP6 (验收)
  ├─ WP6-A (删除 + Retry) ← WP4, WP5
  └─ WP6-B (Golden Path) ← ALL
```

### 时间线

```text
（周）  1    2    3    4    5    6    7    8    9
WP0    ████
WP1         ████ ████
WP2               ████ ████ ████
WP3                     ████ ████ ████
WP4                           ████ ████ ████
WP5                                 ████ ████
WP6                                       ████ ████
```

---

## 4. 总估算

| WP | 描述 | SP | 累计 |
|----|------|----|------|
| WP0 | 平台前置 | 11 | 11 |
| WP1 | 身份与隔离 | 21 | 32 |
| WP2 | 任务与模板 | 29 | 61 |
| WP3 | 录音与分片回放 | 27 | 88 |
| WP4 | 流水线 | 24 | 112 |
| WP5 | 知识审核 | 14 | 126 |
| WP6 | 验收 | 12 | 138 |
| **总计** | | **138 SP** | |

> **138 SP ≈ 138 人理想日**
> - 1 人：~7 周
> - 2 人（前后端）：~4 周
> - 3 人（平台+后端+前端）：~3 周

**vs 初版 221 SP，减少 83 SP（-38%）**，主要来自：
- 去掉 audio_finalize Job + Recording Artifact + Range（-16 SP）
- PostgreSQL → SQLite（-5 SP）
- 去掉 Reconciler + 完整删除兜底（-19 SP）
- 去掉限流/配额/保留策略（-8 SP）
- 简化 Memory/Lineage/测试（-35 SP）

---

## 5. 技术选型

### 5.1 后端

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 已用 |
| 数据库 | **SQLite**（aiosqlite） | 应用自带，零依赖，Demo 够用 |
| HTTP 客户端 | httpx | 已用 |
| Session | HttpOnly Cookie | 安全优先 |
| 密码 | bcrypt | 标准 |

### 5.2 前端

| 组件 | 选型 |
|------|------|
| 框架 | React 18 + TypeScript |
| 构建 | Vite 5 |
| UI | Ant Design 5 |
| 路由 | React Router 6 |
| 状态 | Zustand |
| 录音 | MediaRecorder API |
| SSE | EventSource |

### 5.3 Skill Jobs（3 个，不是 6 个）

| Job | Model Profile | 输入 | 输出 |
|-----|-------------|------|------|
| asr_chunk | meeting-asr | chunk_uri, language, hotwords | segments[] |
| minutes_generate | meeting-minutes | transcript, template_snapshot | minutes_md |
| knowledge_extract | meeting-knowledge-extract | transcript, minutes, extraction_policy | knowledge_items[] with evidence |

---

## 6. SQLite Schema

```sql
-- 8 张表，应用自带，零依赖

meeting_tasks (
  task_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  owner_principal_id TEXT NOT NULL,
  title TEXT NOT NULL,
  participants TEXT,           -- JSON array
  source_type TEXT NOT NULL,   -- LIVE | UPLOAD
  status TEXT NOT NULL,        -- DRAFT|READY|RECORDING|FINALIZING|REVIEW_REQUIRED|COMPLETED|FAILED|DELETED
  current_stage TEXT,
  template_id TEXT,
  template_snapshot TEXT,      -- JSON
  started_at TEXT,
  stopped_at TEXT,
  duration_ms INTEGER,
  recording_artifact_id TEXT,  -- LakeMind Asset ID（可选）
  error_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)

meeting_audio_chunks (
  chunk_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  sequence_no INTEGER NOT NULL,
  duration_ms INTEGER,
  mime_type TEXT,
  size_bytes INTEGER,
  checksum TEXT NOT NULL,
  object_uri TEXT NOT NULL,    -- S3 URI
  upload_status TEXT,          -- UPLOADING|UPLOADED|FAILED
  asr_status TEXT,             -- PENDING|RUNNING|SUCCEEDED|FAILED
  created_at TEXT,
  UNIQUE(task_id, sequence_no)
)

meeting_stage_runs (
  stage_run_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  stage TEXT NOT NULL,         -- asr|minutes_generate|knowledge_extract|memory_save
  status TEXT NOT NULL,
  job_id TEXT,                 -- LakeMind Job ID
  skill_version TEXT,
  model_profile TEXT,
  error_message TEXT,
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT
)

meeting_transcript_segments (
  segment_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  chunk_sequence INTEGER,
  start_ms INTEGER,
  end_ms INTEGER,
  speaker_label TEXT,
  original_text TEXT NOT NULL,
  edited_text TEXT,
  confidence REAL,
  revision INTEGER DEFAULT 1,
  created_at TEXT,
  updated_at TEXT
)

meeting_minutes_versions (
  minutes_version_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  content_markdown TEXT NOT NULL,
  status TEXT,                 -- PREVIEW|FINAL
  created_at TEXT,
  UNIQUE(task_id, version)
)

meeting_knowledge_items (
  item_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  item_type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  tags TEXT,                   -- JSON array
  evidence_segment_ids TEXT,   -- JSON array
  evidence_start_ms INTEGER,
  evidence_end_ms INTEGER,
  confidence REAL,
  review_status TEXT,          -- DRAFT|ACCEPTED|REJECTED|PUBLISHED
  reviewed_at TEXT,
  created_at TEXT,
  updated_at TEXT
)

meeting_templates (
  template_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  owner_principal_id TEXT,     -- NULL = 内置
  name TEXT NOT NULL,
  status TEXT,                 -- ACTIVE|ARCHIVED
  is_builtin INTEGER,
  created_at TEXT,
  updated_at TEXT
)

meeting_template_versions (
  template_version_id TEXT PRIMARY KEY,
  template_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  config_json TEXT NOT NULL,   -- JSON
  created_at TEXT,
  UNIQUE(template_id, version)
)
```

---

## 7. API 端点

```text
Auth:
  POST   /api/auth/register
  POST   /api/auth/login
  POST   /api/auth/logout
  GET    /api/auth/me

Tasks:
  GET    /api/tasks
  POST   /api/tasks
  GET    /api/tasks/{id}
  PATCH  /api/tasks/{id}
  DELETE /api/tasks/{id}

Recording:
  POST   /api/tasks/{id}/start
  PUT    /api/tasks/{id}/audio/chunks/{sequence}
  POST   /api/tasks/{id}/stop
  POST   /api/tasks/{id}/audio/upload
  GET    /api/tasks/{id}/audio/manifest
  GET    /api/tasks/{id}/audio/chunks/{sequence}   (分片字节流)

Events:
  GET    /api/tasks/{id}/events    (SSE)

Transcript:
  GET    /api/tasks/{id}/transcript
  PATCH  /api/tasks/{id}/transcript/segments/{segment_id}

Minutes:
  GET    /api/tasks/{id}/minutes
  PATCH  /api/tasks/{id}/minutes

Knowledge:
  GET    /api/tasks/{id}/knowledge
  PATCH  /api/tasks/{id}/knowledge/{item_id}
  POST   /api/tasks/{id}/knowledge/{item_id}/accept
  POST   /api/tasks/{id}/knowledge/{item_id}/reject
  POST   /api/tasks/{id}/knowledge/publish

Retry:
  POST   /api/tasks/{id}/stages/{stage}/retry

Templates:
  GET    /api/templates
  POST   /api/templates
  POST   /api/templates/{id}/clone
  POST   /api/templates/{id}/versions
  POST   /api/templates/{id}/archive
```

---

## 8. 分片回放设计（关键修订）

```text
前端播放器
  │
  ├─ 1. GET /api/tasks/{id}/audio/manifest
  │     → [{sequence: 1, duration_ms: 10000}, {sequence: 2, ...}, ...]
  │
  ├─ 2. 逐个加载分片
  │     GET /api/tasks/{id}/audio/chunks/1 → blob → URL.createObjectURL
  │     audio.src = blobURL
  │     audio.play()
  │
  ├─ 3. 当前分片播完
  │     → 加载下一个分片 → 继续
  │
  ├─ 4. 进度条
  │     累计时间 = sum(前 N-1 分片 duration) + audio.currentTime
  │     总时长 = sum(所有分片 duration)
  │
  ├─ 5. 跳转
  │     点击 segment → 计算对应分片 sequence + 分片内 offset
  │     → 加载该分片 → audio.currentTime = offset
  │
  └─ 6. 速度/前后 10s
        跨分片计算，简单实现
```

**不做的事**：
- 不合并分片
- 不转 m4a
- 不创建 Recording Artifact（可选，后续需要再加）
- 不需要 HTTP Range

---

## 9. 目录结构

```text
examples/meeting-agent/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── tasks.py
│   │   │   ├── recording.py
│   │   │   ├── transcript.py
│   │   │   ├── minutes.py
│   │   │   ├── knowledge.py
│   │   │   └── templates.py
│   │   ├── services/
│   │   │   ├── task_service.py
│   │   │   ├── recording_service.py
│   │   │   ├── pipeline_service.py
│   │   │   ├── template_service.py
│   │   │   └── lake_client.py
│   │   ├── repositories/
│   │   ├── models/
│   │   └── security/
│   └── db_init.py
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   │   └── ChunkPlayer.tsx      (分片播放器)
│   │   ├── api/
│   │   └── state/
│   └── vite.config.ts
│
├── skills/
│   └── meeting-processing/
│       ├── manifest.yaml
│       └── jobs/
│           ├── asr_chunk/
│           ├── minutes_generate/
│           └── knowledge_extract/
│
├── scripts/
│   ├── setup.py
│   ├── seed_templates.py
│   └── verify.py
│
├── tests/
│   └── e2e/
│
├── docker-compose.yml
└── README.md
```

---

## 10. 验收标准

### Golden Path（15 步）

```text
1.  用户注册 → 自动加入 meeting-agent-demo
2.  用户登录
3.  创建会议任务 + 选模板
4.  开始录音
5.  上传多个分片
6.  ASR Job 完成 → 实时转写显示
7.  停止录音
8.  分片回放（逐个播放，不合并）
9.  查看纪要
10. 知识草稿生成
11. 用户审核知识 → 接受 → 发布
12. Memory 自动保存
13. 知识检索可查到
14. Control Center 可看到 Job
15. 删除任务 → S3 + SQLite 清理
```

### 安全验收

- [ ] 用户 A 看不到用户 B 的任务
- [ ] 用户 A 无法播放用户 B 的分片
- [ ] 用户 A 无法订阅用户 B 的 SSE
- [ ] 伪造 Owner 无效

### 一致性验收

- [ ] 分片重复上传不重复处理
- [ ] 同 sequence 不同 checksum 返回 409

---

## 11. 里程碑

| 里程碑 | 完成条件 | 预计周 |
|--------|----------|--------|
| M0 | WP0 完成，平台就绪 | 第 1 周 |
| M1 | WP1 完成，可注册/登录/隔离 | 第 2 周 |
| M2 | WP2 完成，可创建任务/选模板 | 第 3 周 |
| M3 | WP3 完成，可录音/分片回放 | 第 5 周 |
| M4 | WP4 完成，正式 Skill/Job/Memory | 第 6 周 |
| M5 | WP5 完成，知识审核/发布 | 第 7 周 |
| M6 | WP6 完成，Golden Path 通过 | 第 8 周 |

---

## 12. 与设计方案对齐

| 设计章节 | 对应 WP | 覆盖 |
|----------|---------|------|
| §2 设计准则 | WP1（Owner 隔离） | ✅ |
| §3 用户旅程 | WP1~WP5 | ✅ 简化 |
| §4 页面设计 | WP2-A, WP2-B, WP3-A, WP5-B | ✅ |
| §5 权限 | WP0-B, WP1-A | ✅ 去掉限流 |
| §6 数据模型 | WP1-B（SQLite 非 PG） | ✅ 修订 |
| §7 模板 | WP2-C | ✅ |
| §8 录音回放 | WP3-B（分片回放非合并） | ✅ 修订 |
| §9 流水线 | WP4（3 Job 非 6 Job） | ✅ 简化 |
| §10 状态机 | WP1-B | ✅ |
| §11 API | §7 | ✅ |
| §12 能力映射 | WP4 | ✅ |
| §13 代码改造 | 全部 | ✅ |
| §14 一致性恢复 | WP3-A（幂等），去掉 Reconciler | ✅ 简化 |
| §15 删除 | WP6-A（简单删） | ✅ 简化 |
| §16 Control Center | WP6-B | ✅ |
| §17 Skill 结构 | §9 | ✅ |
| §18 工作包 | 1:1 映射 | ✅ |
| §19 优先级 | §3 依赖 | ✅ |
| §20 Golden Path | WP6-B（15 步非 22 步） | ✅ 简化 |
