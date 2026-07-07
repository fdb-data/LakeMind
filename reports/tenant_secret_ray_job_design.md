# 租户密钥管理与 Ray Job 提交方案

> 编号 `LM-SECRET-RAY-1`。待批准后开发。
>
> 核心变更：
> 1. 新增**租户密钥仓库**（PostgreSQL + AES-256-GCM），支持 system / tenant 两级持久 scope + task 级 inline 覆盖。
> 2. **扩展 Skill 资产结构**：新增 `jobs/{job_name}/` 目录 + `ray.yaml` 执行清单，一个 Skill 可包含多个 Ray job。
> 3. 改造 **Ray Job 提交链路**：Agent 通过 `ray_submit_job(skill_uri, job_name, ...)` 触发，Server 内部拉取 Skill 包 → 读 `ray.yaml` → 解析密钥 → 注入 env_vars → 提交 Ray。
> 4. 新增**日志脱敏**机制，Ray worker 输出经 Server 清洗后存储。

---

## 1. 背景与动机

### 1.1 问题场景

以"会议录音处理"需求为例：

```
上传录音 → Ray 批量 ASR 解析 → 生成纪要 → 萃取知识 → 入库
```

Ray worker 运行业务代码，业务代码需调用外部 ASR 服务（如阿里云、讯飞）。ASR API Key **不应硬编码在业务代码中**，也不应出现在 Ray 日志中。

### 1.2 现状问题

| 问题 | 说明 |
|------|------|
| 无密钥管理 | LakeMindServer 无租户级密钥存储，外部服务凭证只能硬编码在代码或 Server env 中 |
| Ray 提交链路原始 | `ray_compute.py` 的 `submit(func, args)` 只支持预定义 func 名（map/sum/embed_batch 等），不支持提交任意业务代码 |
| 无密钥注入机制 | Ray worker 无法按租户/任务获取密钥，`os.environ` 只有 Server 进程的环境变量 |
| 无日志脱敏 | Ray worker stdout/stderr 原样存储，可能泄露密钥 |

### 1.3 改造目标

1. **租户密钥仓库** — 密钥加密存储在 PG，按 tenant 隔离，通过 AdminMCP / Monitor UI 管理
2. **Skill 扩展 jobs/ 目录** — Skill 包新增 `jobs/{job_name}/` 目录，内含 `ray.yaml` 执行清单 + 业务代码 + 依赖，一个 Skill 支持多个 job
3. **密钥自动注入** — Server 在提交 Ray job 时解析密钥（system → tenant → task inline），注入为 `runtime_env.env_vars`
4. **日志脱敏** — Server 捕获 Ray worker 输出后，用已知密钥值做 redaction

---

## 2. 关键设计决策

### 2.1 业务代码如何传给 Ray

**决策：扩展 Skill 资产新增 `jobs/` 目录 + DataMCP 新增 `ray_submit_job` 工具传 URI 引用。**

排除的方案：

| 方案 | 排除原因 |
|------|----------|
| 打进 Ray worker 镜像 | LakeMind 是平台，不可能把租户业务代码打进平台镜像 |
| 存 SeaweedFS 让 Ray job 自行拉取 | Ray worker 直接访问 S3 有安全风险，且需额外凭证管理 |
| 新建 "RayJob" 资产类型 | 需新建 MCP tools + REST API + PG 表 + LanceDB 索引，工作量大，且代码与 Ray 配置耦合 |

#### 2.1.1 Skill 包结构扩展

在现有 Skill 结构基础上新增 `jobs/` 目录：

```
meeting-processing/              ← 一个 Skill（zip 包）
├── SKILL.md                     ← 给 Agent：自然语言描述（不变）
├── scripts/                     ← 给 Agent：辅助脚本（不变）
└── jobs/                        ← 给 Ray：可执行作业（新增）
    ├── asr/                     ← job_name = "asr"
    │   ├── ray.yaml             ← 执行清单（entrypoint + 依赖 + 资源）
    │   ├── asr_batch.py
    │   ├── utils.py
    │   └── requirements.txt
    ├── summarize/               ← job_name = "summarize"
    │   ├── ray.yaml
    │   ├── summarize.py
    │   └── requirements.txt
    └── extract/                 ← job_name = "extract"
        ├── ray.yaml
        ├── extract.py
        └── requirements.txt
```

**`ray.yaml` 执行清单格式**：

```yaml
entrypoint: "python -m asr_batch"       # Ray worker 执行命令
dependencies:                            # pip 依赖
  - requirements.txt
resources:                               # Ray 资源配额
  num_cpus: 4
  num_gpus: 0
```

**设计要点**：
- `jobs/` 是可选的 — 没有 `jobs/` 的 Skill 仍是普通 Skill，给 Agent 检索执行
- 一个 Skill 可包含**多个 job**（`jobs/{job_name}/`），用 `job_name` 区分
- `ray.yaml` 是 Skill 与 Ray 之间的**执行契约** — Skill 灵活（SKILL.md 自然语言），Ray 严格（ray.yaml 机器可读）
- 同一个 Skill 包内的多个 job 共享上下文（如 asr → summarize → extract pipeline）

#### 2.1.2 Skill 存储格式扩展

当前 Skill 存单 `.py` 文件，扩展为两种格式：

| 格式 | S3 key | 场景 |
|------|--------|------|
| `.py`（现有，保留） | `{tenant}/skills/{name}.py` | 简单 Skill，单文件，无 jobs/ |
| `.zip`（新增） | `{tenant}/skills/{name}.zip` | 包含 jobs/ 的多文件包 |

`register_skill` 新增 `format` 参数区分，向后兼容。

#### 2.1.3 提交流程

```
开发人员 → Python 代码 + ray.yaml → 打成 zip → register_skill(format="zip") via AssetMCP
→ 存入 S3 + PG + LanceDB（已有 Skill 基础设施）

Agent → ray_submit_job(
    skill_uri = "lake://skills/meeting-processing@v1",
    job_name  = "asr",                       ← 指定 jobs/ 下的哪个 job
    params    = {"file_uris": [...]},
    task_id   = "meeting-001",
    env_overrides = {"ASR_API_KEY": "sk-temp"}  ← 可选，task 级临时覆盖
) via DataMCP
→ Server 内部：
    a. 按 skill_uri 从 S3 拉取 zip 包
    b. 解压 → 读 jobs/asr/ray.yaml → 得到 entrypoint / dependencies / resources
    c. 解析密钥：system env → tenant secrets → env_overrides
    d. 提交 Ray job：runtime_env = { env_vars, py_modules = [zip], pip = [deps] }
→ 返回 ray_job_id
```

**关键点**：
- 代码不经过 Agent payload — Agent 只传 URI 引用 + job_name，Server 内部从 S3 拉取
- `ray.yaml` 是机器可读的执行契约，`SKILL.md` 是人类可读的描述 — 两者各司其职
- Skill 是纯存储载体，`ray_submit_job` 是计算触发器 — **存储与计算分离**（设计原则 4）
- 不违反"存取不执行" — Agent 决定跑什么、何时跑、用什么参数，Server 只提供 Ray 计算资源

### 2.2 Scope 设计

**决策：两级持久 scope（system + tenant）存 PG，一级临时 scope（task）走 inline 参数。**

| scope | 存放位置 | 生命周期 | 管理者 | 用途 |
|-------|---------|----------|--------|------|
| `system` | Server 进程环境变量 | 平台级，永久 | 平台运维 | 全局默认值 / fallback |
| `tenant` | PG `tenant_secrets` 表 | 租户级，持久 | 租户管理员 | **最常用**，配一次所有任务复用 |
| `task` | `ray_submit_job` 的 `env_overrides` 参数 | 单次 job，job 结束即消失 | Agent / 业务代码 | 临时覆盖 |

**task 级不存 PG 的原因**：

task 是临时的，执行完就没了。在 PG 里存 task 级密钥然后清理，既麻烦又没必要。task 级密钥的本质是"这次例外"，不是"持久配置"。持久配置走 tenant，临时例外走 inline。**PG 只存持久的东西。**

解析优先级：

```
final_env = {}
final_env.update(system_env)          # 1. system（最低）
final_env.update(tenant_secrets)      # 2. tenant（覆盖 system）
final_env.update(env_overrides)       # 3. task inline（最高，覆盖 tenant）
→ 注入 Ray job runtime_env.env_vars
```

### 2.3 密钥如何到达 Ray worker

**决策：Server 解密后注入 Ray job `runtime_env.env_vars`，业务代码读 `os.environ`。**

```
PG (加密) → Server (解密) → Ray job env_vars → worker os.environ → 业务代码
```

密钥永远不出现在：业务代码源码、Git 仓库、MCP 返回值。Ray worker 不是 MCP 客户端，它只是读 `os.environ` 的普通 Python 函数，与 LakeMind 完全解耦。

### 2.4 加密方案

**决策：AES-256-GCM + 平台主密钥（单层 KEK）。**

```
KEK (平台主密钥):
  来源: 环境变量 LAKEMIND_MASTER_KEY (32 bytes, base64)
  存放: Server 容器环境变量 / docker secret

加密:
  AAD = f"{tenant_id}:{key_name}"        # 绑定租户 + key_name，防替换攻击
  iv = random(12 bytes)
  (ciphertext, auth_tag) = AES_256_GCM.encrypt(KEK, plaintext, iv, AAD)

解密:
  plaintext = AES_256_GCM.decrypt(KEK, ciphertext, iv, auth_tag, AAD)
  # AAD 不匹配 → 解密失败（跨租户篡改防护）
```

不引入 KMS 或 envelope encryption 二层密钥 — MVP 阶段单层 KEK 足够，生产轮换时再升级。

---

## 3. 数据模型

### 3.1 PostgreSQL 新增表

```sql
-- 租户密钥表
CREATE TABLE IF NOT EXISTS tenant_secrets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    key_name        VARCHAR(100) NOT NULL,
    encrypted_value BYTEA NOT NULL,           -- AES-256-GCM 密文
    iv              BYTEA NOT NULL,           -- GCM nonce (12 bytes)
    auth_tag        BYTEA NOT NULL,           -- GCM 认证标签 (16 bytes)
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    created_by      TEXT,

    UNIQUE(tenant_id, key_name)
);

CREATE INDEX IF NOT EXISTS idx_secrets_tenant ON tenant_secrets(tenant_id);

-- 密钥读取审计日志
CREATE TABLE IF NOT EXISTS secret_access_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL,
    key_name    VARCHAR(100) NOT NULL,
    task_id     TEXT,
    ray_job_id  TEXT,
    accessed_by TEXT NOT NULL,               -- agent_id
    accessed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_secret_log_tenant ON secret_access_log(tenant_id, accessed_at);
```

### 3.2 Ray Job 记录表

```sql
-- Ray Job 记录（替代内存中的 _refs dict，支持持久化查询）
CREATE TABLE IF NOT EXISTS ray_jobs (
    job_id          TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    agent_id        TEXT NOT NULL,
    skill_uri       TEXT NOT NULL,
    entrypoint      TEXT,
    params          JSONB DEFAULT '{}',
    task_id         TEXT,
    status          TEXT DEFAULT 'submitted',  -- submitted/running/completed/failed/cancelled
    ray_job_id      TEXT,                       -- Ray 原生 job_id
    result_uri      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ray_jobs_tenant ON ray_jobs(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_ray_jobs_task ON ray_jobs(tenant_id, task_id);
```

---

## 4. 架构设计

### 4.1 在引擎体系中的位置

```
storage:
  object:     SeaweedFS       # 已有
  tabular:    Iceberg         # 已有
  vector:     Lance/LanceDB   # 已有
  kv:         Valkey          # 已有
  graph:      Postgres        # 已有
  metadata:   Postgres        # 已有 → 扩展：tenant_secrets + ray_jobs + secret_access_log
  secret:     Postgres        # 新增：密钥存储（复用 PG 连接池）
compute:
  sql:        DuckDB          # 已有
  distributed: Ray            # 已有 → 改造：submit_skill_job() 新方法
cognitive:
  embedding:  fastembed       # 已有
  memory:     mem0            # 已有
  llm:        GatewayLLM      # 已有
```

密钥存储复用 PG 连接池，不引入新引擎。Ray 改造在现有 `RayCompute` 类上新增方法。

### 4.2 完整数据流

```
┌──────────────────────────────────────────────────────────────────┐
│ 配置阶段（租户管理员，一次性）                                      │
│                                                                    │
│  Monitor UI / AdminMCP                                             │
│    create_secret("ASR_API_KEY", "sk-xxx", description="阿里云ASR") │
│    create_secret("ASR_ENDPOINT", "https://...")                    │
│    → PG tenant_secrets（AES-256-GCM 加密）                          │
│                                                                    │
│  开发人员                                                           │
│    写 Python 代码 + ray.yaml → 打成 zip                              │
│    → register_skill(format="zip") via AssetMCP                       │
│    → SeaweedFS + PG + LanceDB（已有 Skill 基础设施）                 │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ 运行阶段（每次任务）                                                │
│                                                                    │
│  Agent                                                             │
│    1. 上传录音 → SeaweedFS → file_uris                             │
│    2. ray_submit_job(                                              │
│         skill_uri = "lake://skills/meeting-processing@v1",          │
│         job_name  = "asr",                                          │
│         params    = {"file_uris": file_uris},                       │
│         task_id   = "meeting-001"                                   │
│       ) via DataMCP → Server                                       │
│                                                                    │
│  Server                                                            │
│    a. 从 SeaweedFS 拉 skill zip 包                                  │
│    b. 解压 → 读 jobs/asr/ray.yaml → entrypoint / deps / resources   │
│    c. 解析密钥：system env → tenant secrets → 合并                  │
│    d. 日志 redaction 列表 = 解析出的密钥值                           │
│    e. ray.job_submission.submit(                                   │
│         entrypoint = ray_yaml["entrypoint"],                        │
│         runtime_env = {                                            │
│           env_vars: 合并后的密钥,                                   │
│           py_modules: [zip 包],                                     │
│           pip: ray_yaml["dependencies"],                            │
│         }                                                          │
│       )                                                            │
│    f. 写 ray_jobs 记录                                             │
│    g. 返回 job_id 给 Agent                                         │
│                                                                    │
│  Ray worker                                                        │
│    代码里：                                                         │
│      key = os.environ["ASR_API_KEY"]     ← Server 注入的            │
│      result = asr.transcribe(audio, key)                           │
│      → 结果写回 SeaweedFS / REST API                               │
│    日志：                                                           │
│      Server 捕获 stdout/stderr → redact → 存储                     │
│                                                                    │
│  Agent                                                             │
│    3. ray_job_status(job_id) → "DONE"                             │
│    4. ray_job_result(job_id) → transcript_uris                     │
│    5. 后续：ray_submit_job(job_name="summarize") → 萃取 → 入库      │
└──────────────────────────────────────────────────────────────────┘
```

### 4.3 密钥流向

```
PG(加密) → Server(解密) → Ray job env_vars → worker os.environ → 业务代码
```

密钥永不经过：Agent、MCP 返回值、Git 仓库、业务代码源码。

---

## 5. REST API 设计

### 5.1 密钥管理 API

```
POST   /api/v1/metadata/secrets              — 创建密钥
PUT    /api/v1/metadata/secrets/{key_name}   — 更新密钥
DELETE /api/v1/metadata/secrets/{key_name}   — 删除密钥
GET    /api/v1/metadata/secrets              — 列出密钥（metadata only，不返回值）
```

请求体（POST）：

```json
{
    "key_name": "ASR_API_KEY",
    "value": "sk-xxxxxxxx",
    "description": "阿里云 ASR API Key"
}
```

响应（GET list）：

```json
{
    "secrets": [
        {"key_name": "ASR_API_KEY", "description": "阿里云 ASR API Key", "updated_at": "..."},
        {"key_name": "ASR_ENDPOINT", "description": "ASR 服务地址", "updated_at": "..."}
    ],
    "count": 2
}
```

**list 永不返回密钥值**，只返回 key_name + description + updated_at。

Authorization: Bearer token（tenant-scoped，tenant_id 从 `X-Tenant-Id` header 获取）。

### 5.2 Ray Job API（改造现有）

```
POST   /api/v1/compute/jobs/submit           — 提交 Skill-based Ray job
GET    /api/v1/compute/jobs/{job_id}         — 查询状态（已有，保留）
GET    /api/v1/compute/jobs/{job_id}/result  — 获取结果（已有，保留）
POST   /api/v1/compute/jobs/{job_id}/cancel  — 取消 job（新增）
GET    /api/v1/compute/jobs                  — 列出 jobs（新增，按 tenant 过滤）
```

请求体（POST submit）：

```json
{
    "skill_uri": "lake://skills/meeting-processing@v1",
    "job_name": "asr",
    "params": {"file_uris": ["s3://lakemind-filesets/tenant-a/meetings/m001.wav"]},
    "task_id": "meeting-001",
    "env_overrides": {"ASR_API_KEY": "sk-temp"},
    "resources": {"num_cpus": 8}
}
```

- `job_name`（必填）：指定 `jobs/{job_name}/` 下的哪个 job
- `resources`（可选）：覆盖 `ray.yaml` 中的资源配额
- `entrypoint` 不再由调用方指定 — 从 `jobs/{job_name}/ray.yaml` 读取

响应：

```json
{
    "job_id": "job_a1b2c3d4",
    "status": "submitted",
    "ray_job_id": "ray_job_xxx"
}
```

### 5.3 现有 Job API 兼容

现有 `POST /api/v1/compute/jobs/`（func + args 模式）保留，用于内置 func（map/embed_batch 等）。新 `submit` 端点用于 Skill-based job。

---

## 6. MCP 工具设计

### 6.1 AdminMCP 新增工具（密钥管理）

| 工具 | 签名 | 说明 |
|------|------|------|
| `create_secret` | `(key_name: str, value: str, description: str = "") → dict` | 创建租户密钥（加密存储） |
| `update_secret` | `(key_name: str, value: str, description: str = "") → dict` | 更新密钥 |
| `delete_secret` | `(key_name: str) → dict` | 删除密钥 |
| `list_secrets` | `() → dict` | 列出密钥名 + metadata（**不返回值**） |

### 6.2 DataMCP 新增工具（Ray job）

| 工具 | 签名 | 说明 |
|------|------|------|
| `ray_submit_job` | `(skill_uri: str, job_name: str, params: dict = {}, task_id: str = "", env_overrides: dict = {}, resources: dict = {}) → dict` | 提交 Skill-based Ray job |
| `ray_job_status` | `(job_id: str) → dict` | 查询 job 状态（改造现有 job_status） |
| `ray_job_result` | `(job_id: str) → dict` | 获取 job 结果（改造现有 job_result） |
| `ray_job_cancel` | `(job_id: str) → dict` | 取消 job |
| `ray_job_list` | `(status: str = "") → dict` | 列出当前租户的 jobs |
| `list_skill_jobs` | `(skill_uri: str) → dict` | 列出 Skill 包中 `jobs/` 下的可用 job_name |

### 6.3 AssetMCP Skill 工具扩展

| 工具 | 变更 | 说明 |
|------|------|------|
| `register_skill` | 修改 | 新增 `format: str = "py"` 参数，`"zip"` 时存为 zip 包 |
| `get_skill` | 修改 | 返回 `format` 字段；zip 包时返回包内容列表 |

### 6.4 现有 DataMCP job 工具处理

现有 `job_submit` / `job_status` / `job_result` 三个工具保留（用于内置 func），新增上述 6 个 `ray_*` / `list_skill_jobs` 工具。后续可考虑合并。

---

## 7. 日志脱敏

### 7.1 机制

```python
def redact_logs(log_text: str, secret_values: list[str]) -> str:
    for sv in secret_values:
        if sv and len(sv) >= 4:
            log_text = log_text.replace(sv, "***REDACTED***")
    return log_text
```

Server 在捕获 Ray worker stdout/stderr 后，用该 job 注入的密钥值做字符串替换，再存储/展示。

### 7.2 防护层次

| 层 | 措施 |
|----|------|
| 业务代码 | 代码规范：禁止 `log.info(os.environ)` 或 `log.info(f"key={key}")` |
| Server 日志清洗 | 捕获 Ray worker 输出后 redaction |
| PG 存储 | 密钥加密存储，list 不返回值 |
| 传输 | REST API 走 HTTPS（生产） |
| 审计 | `secret_access_log` 记录谁在何时读取了哪个密钥 |

---

## 8. 实现清单

### 8.1 LakeMindServer

| 文件 | 变更 | 说明 |
|------|------|------|
| `docker/postgres-age/init/01-age.sql` | 修改 | 新增 `tenant_secrets` / `secret_access_log` / `ray_jobs` 表 |
| `src/lakemind_server/plugins/protocols.py` | 修改 | `MetadataStorePlugin` 新增密钥 CRUD 方法签名；`DistributedComputePlugin` 新增 `submit_skill_job` / `cancel` / `list_jobs` 签名 |
| `src/lakemind_server/plugins/storage/metadata/postgres.py` | 修改 | 实现密钥 CRUD（加密/解密） |
| `src/lakemind_server/plugins/compute/distributed/ray_compute.py` | 修改 | 新增 `submit_skill_job(skill_zip, job_name, env_vars, resources)` 方法：解压 zip → 读 `jobs/{job_name}/ray.yaml` → Ray job_submission.submit → 记录到 PG |
| `src/lakemind_server/utils/crypto.py` | **新增** | AES-256-GCM 加密/解密模块 |
| `src/lakemind_server/utils/log_redact.py` | **新增** | 日志脱敏工具 |
| `src/lakemind_server/utils/ray_yaml.py` | **新增** | ray.yaml 解析工具（从 zip 包提取 `jobs/{job_name}/ray.yaml` 并解析） |
| `src/lakemind_server/api/secrets.py` | **新增** | 密钥管理 REST API router |
| `src/lakemind_server/api/jobs.py` | 修改 | 新增 `POST /submit` 端点 + `POST /{job_id}/cancel` + `GET /` 列表 |
| `src/lakemind_server/app.py` | 修改 | 注册 secrets router |
| `src/lakemind_server/config.py` | 修改 | `ServerConfig` 新增 `master_key` 字段（从 `LAKEMIND_MASTER_KEY` env 读取） |
| `src/lakemind_server/engines.py` | 修改 | 传递 master_key 到 metadata engine |
| `config/engines.yaml` | 修改 | metadata config 新增 `master_key: ${LAKEMIND_MASTER_KEY}` |

### 8.2 LakeMindAdminMCP

| 文件 | 变更 | 说明 |
|------|------|------|
| `src/lakemind_admin_mcp/tools/admin.py` | 修改 | 新增 `create_secret` / `update_secret` / `delete_secret` / `list_secrets` 4 个工具 |
| `src/lakemind_admin_mcp/server_client.py` | 修改 | 新增密钥管理 REST API 客户端方法 |

### 8.3 LakeMindDataMCP

| 文件 | 变更 | 说明 |
|------|------|------|
| `src/lakemind_data_mcp/tools/data.py` | 修改 | 新增 `ray_submit_job` / `ray_job_cancel` / `ray_job_list` / `list_skill_jobs` 4 个工具（`ray_job_status` / `ray_job_result` 改造现有） |
| `src/lakemind_data_mcp/server_client.py` | 修改 | 新增 `job_submit_skill` / `job_cancel` / `job_list` REST API 客户端方法 |

### 8.4 LakeMindAssetMCP

| 文件 | 变更 | 说明 |
|------|------|------|
| `src/lakemind_asset_mcp/tools/skill.py` | 修改 | `register_skill` 新增 `format` 参数（`"py"` / `"zip"`）；`get_skill` 返回 `format` 字段；zip 格式时 S3 key 用 `.zip` 后缀 |

### 8.5 Docker / 配置

| 文件 | 变更 | 说明 |
|------|------|------|
| `docker-compose.yml`（Server） | 修改 | 新增 `LAKEMIND_MASTER_KEY` 环境变量 |
| `.env.example` | 修改 | 新增 `LAKEMIND_MASTER_KEY=` 示例 |

### 8.6 验证

| 文件 | 变更 | 说明 |
|------|------|------|
| `scripts/verify_full.py` | 修改 | 新增 L 级别验证：密钥 CRUD + 加解密 + Ray skill job 提交 + 日志脱敏 |

---

## 9. 接口细节

### 9.1 加密模块 `utils/crypto.py`

```python
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class SecretCrypto:
    def __init__(self, master_key_b64: str):
        self._key = base64.b64decode(master_key_b64)  # 32 bytes

    def encrypt(self, tenant_id: str, key_name: str, plaintext: str) -> dict:
        aad = f"{tenant_id}:{key_name}".encode()
        iv = os.urandom(12)
        aesgcm = AESGCM(self._key)
        ct = aesgcm.encrypt(iv, plaintext.encode(), aad)
        ciphertext = ct[:-16]
        auth_tag = ct[-16:]
        return {"encrypted_value": ciphertext, "iv": iv, "auth_tag": auth_tag}

    def decrypt(self, tenant_id: str, key_name: str, encrypted_value: bytes, iv: bytes, auth_tag: bytes) -> str:
        aad = f"{tenant_id}:{key_name}".encode()
        aesgcm = AESGCM(self._key)
        plaintext = aesgcm.decrypt(iv, encrypted_value + auth_tag, aad)
        return plaintext.decode()
```

### 9.2 ray.yaml 解析 `utils/ray_yaml.py`

```python
import zipfile
import yaml

def parse_ray_yaml(skill_zip: bytes, job_name: str) -> dict:
    """从 Skill zip 包中提取 jobs/{job_name}/ray.yaml 并解析。"""
    with zipfile.ZipFile(io.BytesIO(skill_zip)) as zf:
        yaml_path = f"jobs/{job_name}/ray.yaml"
        if yaml_path not in zf.namelist():
            raise ValueError(f"job '{job_name}' not found (missing {yaml_path})")
        ray_yaml = yaml.safe_load(zf.read(yaml_path))
    return {
        "entrypoint": ray_yaml["entrypoint"],
        "dependencies": ray_yaml.get("dependencies", []),
        "resources": ray_yaml.get("resources", {}),
    }

def list_jobs(skill_zip: bytes) -> list[str]:
    """列出 Skill zip 包中 jobs/ 下的可用 job_name。"""
    job_names = set()
    with zipfile.ZipFile(io.BytesIO(skill_zip)) as zf:
        for name in zf.namelist():
            if name.startswith("jobs/") and "/" in name[5:]:
                job_names.add(name[5:].split("/")[0])
    return sorted(job_names)
```

### 9.3 RayCompute 新增方法

```python
def submit_skill_job(
    self,
    skill_zip: bytes,          # 从 S3 拉取的 Skill zip 包
    job_name: str,             # jobs/{job_name}/
    env_vars: dict[str, str],  # 解析后的密钥
    resources_override: dict,  # 调用方覆盖的资源配额
    job_id: str,               # Server 生成的 job_id
) -> str:
    """提交 Skill-based Ray job，返回 Ray 原生 job_id。"""
    import ray, tempfile
    self._ensure()

    # 解析 ray.yaml
    ray_cfg = parse_ray_yaml(skill_zip, job_name)

    # 写 zip 包到临时文件
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        f.write(skill_zip)
        code_path = f.name

    # 合并资源配额（调用方覆盖 ray.yaml）
    resources = {**ray_cfg["resources"], **resources_override}

    runtime_env = {
        "env_vars": env_vars,
        "py_modules": [code_path],
        "pip": ray_cfg["dependencies"],
    }

    submission_client = ray.job_submission.JobSubmissionClient(self._address)
    ray_job_id = submission_client.submit_job(
        entrypoint=ray_cfg["entrypoint"],
        runtime_env=runtime_env,
    )
    return ray_job_id
```

### 9.4 密钥解析

```python
def resolve_env_vars(
    tenant_id: str,
    secret_keys: list[str] | None,   # 指定要解析的 key_name 列表，None = 全部
    env_overrides: dict[str, str],   # task 级 inline
) -> dict[str, str]:
    result = {}

    # 1. system 级（Server 进程 env）
    for k, v in os.environ.items():
        if secret_keys is None or k in secret_keys:
            result[k] = v

    # 2. tenant 级（PG 解密）
    tenant_secrets = metadata.list_secrets(tenant_id)
    for s in tenant_secrets:
        if secret_keys is None or s.key_name in secret_keys:
            result[s.key_name] = crypto.decrypt(tenant_id, s.key_name, ...)

    # 3. task 级 inline
    result.update(env_overrides)

    return result
```

---

## 10. 安全分析

| 威胁 | 防护 |
|------|------|
| 密钥泄露到 Git | 密钥存 PG，业务代码只有 `os.environ["KEY"]`，无硬编码 |
| 跨租户密钥访问 | PG 查询按 tenant_id 过滤 + AES-GCM AAD 绑定 tenant_id |
| 密钥出现在 MCP 返回值 | `list_secrets` 不返回值；`ray_submit_job` 不返回 env_vars |
| 密钥出现在 Ray 日志 | Server 捕获 worker 输出后 redaction |
| 密钥出现在 Server 日志 | 只记 key_name + tenant_id，不记 value |
| 主密钥泄露 | `LAKEMIND_MASTER_KEY` 存容器环境变量 / docker secret，不进 Git |
| 密钥未加密存储 | AES-256-GCM 加密，PG 中只有密文 |
| 读取无审计 | `secret_access_log` 记录每次密钥读取 |

---

## 11. 实时音频流适配

实时流场景无需改变密钥设计 — **流启动时检索一次密钥，缓存在会话上下文中**，后续分片复用：

```
stream_start(task_id)
  → secrets = resolve_env_vars(tenant_id, env_overrides)
  → 缓存到 stream session
  → 后续分片直接用缓存密钥调 ASR
stream_end
  → 清理 session 密钥缓存
```

不需要每个分片都查密钥。实时流的 Ray job 提交与批量相同，只是 entrypoint 不同（streaming vs batch）。

---

## 12. 工作量估算

| 模块 | 工作量 |
|------|--------|
| PG 表 + migration | 0.5d |
| 加密模块 `crypto.py` | 0.5d |
| 日志脱敏 `log_redact.py` | 0.5d |
| ray.yaml 解析 `ray_yaml.py` | 0.5d |
| Server 密钥 REST API + metadata 扩展 | 1d |
| RayCompute `submit_skill_job` 改造 | 1d |
| Server jobs API 改造 | 0.5d |
| AdminMCP 4 tools + server_client | 0.5d |
| DataMCP 6 tools + server_client | 0.5d |
| AssetMCP Skill 工具扩展（zip 格式） | 0.5d |
| Docker / config | 0.5d |
| 测试 + 验证脚本 | 1.5d |
| **合计** | **~8.5d** |

---

## 13. 不做（Out of Scope）

1. **不引入外部密钥管理器**（HashiCorp Vault / Infisical）— 复用 PG 统一元数据底座
2. **不做 envelope encryption 二层密钥** — MVP 单层 KEK 足够
3. **不做密钥自动轮换** — 手动 `update_secret` 即可
4. **不做 task 级密钥 PG 存储** — task 级走 inline `env_overrides`
5. **不新建 RayJob 资产类型** — 复用 Skill 资产 + `jobs/` 目录扩展
6. **不代理外部服务调用** — Server 只注入密钥，业务代码自行调 ASR
7. **不做 Ray worker 隔离强化** — 依赖 Ray 原生进程隔离，生产阶段加 namespace + resource quota
8. **不做 Skill 包签名验证** — MVP 信任租户管理员上传的包，生产阶段加签名 + 扫描

---

## 14. 后续扩展

1. **密钥轮换 API** — `rotate_secret(key_name)` 生成新值，旧值留 history
2. **密钥模板** — 租户创建时自动继承一组默认密钥
3. **Ray job 依赖链** — 同一 Skill 内 job A 完成后自动触发 job B（asr → summarize → extract pipeline）
4. **流式 Ray job** — 支持实时音频流接入，stream_start → 分片提交 → stream_end
5. **Ray worker 资源隔离** — 按租户 namespace + resource quota
6. **密钥版本管理** — 密钥历史版本 + 回滚
7. **Monitor UI 密钥管理页面** — 人类可操作的密钥 CRUD 界面
8. **Skill 包签名验证** — 上传时验签，防篡改
9. **Skill 包内 job 依赖声明** — ray.yaml 中声明 `depends_on: ["asr"]`，Server 自动编排 pipeline
