# 开发指南

本指南面向在 LakeMind 平台上开发业务应用的开发者：如何编写业务代码、打包 Skill、管理密钥、提交 Ray 作业、构建完整的数据处理流水线。

---

## 1. 概述

LakeMind 是认知资产存取平台。作为业务开发者，你通过 MCP 工具存取知识/记忆/技能，通过 Ray 执行分布式计算。你的业务代码运行在 Ray worker 中，通过 `os.environ` 读取平台注入的密钥，调用外部服务，结果写回 LakeMind。

**核心流程**：

```
开发业务代码 → 打包 Skill → 存入 LakeMind → Agent 调 ray_submit_job → Ray 执行 → 结果回写
```

---

## 2. 编写 Skill 包

### 2.1 Skill 包结构

一个 Skill 是一个 zip 包，包含以下结构：

```
my-skill/
├── SKILL.md              ← 人类可读描述（给 Agent 理解用）
├── scripts/              ← 辅助脚本（给 Agent 检索执行用，可选）
│   └── helper.py
└── jobs/                 ← Ray 可执行作业（给 Ray 执行用，可选）
    ├── asr/              ← job_name = "asr"
    │   ├── ray.yaml      ← 执行清单（必须）
    │   ├── asr_batch.py  ← 业务代码
    │   ├── utils.py
    │   └── requirements.txt
    └── summarize/        ← job_name = "summarize"
        ├── ray.yaml
        ├── summarize.py
        └── requirements.txt
```

- `SKILL.md`：自然语言描述，Agent 通过语义搜索找到这个 Skill 并理解其用途
- `scripts/`：给 Agent 直接执行的辅助脚本（平台不执行）
- `jobs/`：给 Ray 执行的作业，每个子目录是一个 job，用 `job_name` 区分
- 一个 Skill 可以包含**多个 job**（如 asr → summarize → extract pipeline）

### 2.2 ray.yaml 执行清单

每个 `jobs/{job_name}/` 下必须有一个 `ray.yaml`，告诉 Ray 如何执行：

```yaml
entrypoint: "python -m asr_batch"       # Ray worker 执行命令
dependencies:                            # pip 依赖文件列表（可选）
  - requirements.txt
resources:                               # Ray 资源配额（可选）
  num_cpus: 4
  num_gpus: 0
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `entrypoint` | string | 是 | Ray worker 执行的命令，如 `python -m asr_batch` 或 `python asr_batch.py` |
| `dependencies` | list[string] | 否 | pip 依赖文件列表（requirements.txt 路径，相对 job 目录） |
| `resources` | dict | 否 | Ray 资源配额，支持 `num_cpus` / `num_gpus` / `memory` |

### 2.3 业务代码规范

业务代码运行在 Ray worker 中，通过环境变量读取密钥，**禁止硬编码任何凭证**：

```python
# jobs/asr/asr_batch.py
import os
import httpx

def main():
    # 从环境变量读取密钥（由 LakeMind Server 注入）
    api_key = os.environ["ASR_API_KEY"]
    endpoint = os.environ["ASR_ENDPOINT"]

    # 调用外部 ASR 服务
    client = httpx.Client(timeout=30.0)
    resp = client.post(endpoint, headers={"Authorization": f"Bearer {api_key}"}, json={...})
    result = resp.json()

    # 结果写回 LakeMind（通过 REST API）
    server_url = os.environ.get("SERVER_API_URL", "http://lakemind-server-api:10823")
    server_key = os.environ.get("SERVER_API_KEY", "lakemind-internal-api-key")
    client.post(
        f"{server_url}/api/v1/storage/objects/lakemind-filesets/results/transcript.json",
        headers={"Authorization": f"Bearer {server_key}"},
        content=...,
    )

if __name__ == "__main__":
    main()
```

**规范**：
- 密钥只通过 `os.environ` 读取，不写死在代码里
- 禁止 `log.info(os.environ)` 或 `log.info(f"key={api_key}")` — 不要在日志中输出密钥
- 结果通过 REST API 写回 LakeMind，不直接操作底层存储
- 依赖在 `requirements.txt` 中声明

### 2.4 requirements.txt

```
httpx>=0.27
pydub>=0.25
```

Ray worker 在执行 job 前会自动安装这些依赖。

### 2.5 SKILL.md

```markdown
# 会议录音 ASR 批量解析

将会议录音文件批量提交到外部 ASR 服务，返回转写文本。

## Jobs

- **asr**: 批量 ASR 转写，输入 audio_uris，输出 transcript
- **summarize**: 基于转写文本生成会议纪要

## 依赖

需要配置以下租户密钥：
- ASR_API_KEY: ASR 服务 API Key
- ASR_ENDPOINT: ASR 服务地址
```

---

## 3. 打包与注册 Skill

### 3.1 打包

```bash
# 目录结构
meeting-processing/
├── SKILL.md
├── jobs/
│   ├── asr/
│   │   ├── ray.yaml
│   │   ├── asr_batch.py
│   │   └── requirements.txt
│   └── summarize/
│       ├── ray.yaml
│       └── summarize.py

# 打成 zip
zip -r meeting-processing.zip meeting-processing/
```

### 3.2 注册到 LakeMind

通过 AssetMCP 的 `register_skill` 工具：

```python
# Agent / 脚本调用
import base64

with open("meeting-processing.zip", "rb") as f:
    code_b64 = base64.b64encode(f.read()).decode()

register_skill(
    name="meeting-processing",
    description="会议录音 ASR 解析 + 纪要生成",
    code=code_b64,           # zip 包 base64 编码
    format="zip",            # 指定 zip 格式
    version="1.0.0",
)
```

注册后，Skill 存储在 SeaweedFS（`{tenant}/skills/meeting-processing.zip`），元信息写入 Iceberg + LanceDB 向量索引。

### 3.3 查看可用 jobs

```python
list_skill_jobs(skill_uri="lake://skills/meeting-processing@v1")
# → {"jobs": ["asr", "summarize"]}
```

### 3.4 单文件 Skill（无 jobs/）

简单 Skill 不需要 zip 包，直接传 Python 代码：

```python
register_skill(
    name="hello",
    description="A simple hello skill",
    code="print('hello world')",
    format="py",             # 默认值，单文件
)
```

---

## 4. 租户密钥管理

### 4.1 配置密钥

租户管理员通过 AdminMCP 配置密钥，加密存储在 PostgreSQL 中：

```python
# 通过 AdminMCP
create_secret(key_name="ASR_API_KEY", value="sk-xxxxxxxx", description="阿里云 ASR API Key")
create_secret(key_name="ASR_ENDPOINT", value="https://asr.aliyuncs.com/v1", description="ASR 服务地址")
```

配置一次后，该租户的所有 Ray job 自动注入这些密钥。

### 4.2 密钥作用域

| 作用域 | 存储位置 | 生命周期 | 说明 |
|--------|---------|----------|------|
| `system` | Server 进程环境变量 | 永久 | 全局默认值，所有租户共享 |
| `tenant` | PostgreSQL（加密） | 持久 | 租户级，配一次所有 job 复用（**最常用**） |
| `task` | `ray_submit_job` 的 `env_overrides` 参数 | 单次 job | 临时覆盖，job 结束即消失 |

**解析优先级**：task > tenant > system（高优先级覆盖低优先级）

### 4.3 临时覆盖（task 级）

某次任务需要临时使用不同的 ASR Key：

```python
ray_submit_job(
    skill_uri="lake://skills/meeting-processing@v1",
    job_name="asr",
    params={"file_uris": [...]},
    task_id="meeting-001",
    env_overrides={"ASR_API_KEY": "sk-different-for-this-task"},  # 仅本次有效
)
```

### 4.4 密钥安全

- 密钥使用 AES-256-GCM 加密存储，绑定租户 ID 防跨租户篡改
- `list_secrets` 只返回密钥名和描述，**不返回密钥值**
- Ray worker 日志经 Server 自动脱敏（密钥值替换为 `***REDACTED***`）
- 每次密钥读取记入审计日志（`secret_access_log` 表）

### 4.5 管理密钥

```python
# 列出当前租户的密钥（不返回值）
list_secrets()
# → {"secrets": [{"key_name": "ASR_API_KEY", "description": "阿里云 ASR API Key", ...}]}

# 更新密钥
update_secret(key_name="ASR_API_KEY", value="sk-new-key")

# 删除密钥
delete_secret(key_name="ASR_API_KEY")
```

---

## 5. 提交 Ray 作业

### 5.1 基本提交

```python
# 通过 DataMCP
result = ray_submit_job(
    skill_uri="lake://skills/meeting-processing@v1",
    job_name="asr",                                    # 必填，指定 jobs/ 下的哪个 job
    params={"file_uris": ["s3://lakemind-filesets/tenant-a/meetings/m001.wav"]},
    task_id="meeting-001",
)
# → {"job_id": "job_a1b2c3d4", "status": "submitted", "ray_job_id": "ray_job_xxx"}
```

Server 内部执行：
1. 从 SeaweedFS 拉取 Skill zip 包
2. 解压 → 读 `jobs/asr/ray.yaml` → 获取 entrypoint / dependencies / resources
3. 解析密钥：system env → tenant secrets → env_overrides
4. 提交 Ray job，注入 env_vars
5. 写入 `ray_jobs` 记录
6. 返回 job_id

### 5.2 查询状态与结果

```python
# 查询状态
ray_job_status(job_id="job_a1b2c3d4")
# → {"job_id": "job_a1b2c3d4", "status": "running", ...}

# 获取结果
ray_job_result(job_id="job_a1b2c3d4")
# → {"result": {...}}

# 取消
ray_job_cancel(job_id="job_a1b2c3d4")
# → {"job_id": "job_a1b2c3d4", "status": "cancelled"}

# 列出当前租户的 jobs
ray_job_list(status="running")
# → {"jobs": [...], "count": 3}
```

### 5.3 覆盖资源配额

`ray_submit_job` 的 `resources` 参数可覆盖 `ray.yaml` 中的资源配额：

```python
ray_submit_job(
    skill_uri="lake://skills/meeting-processing@v1",
    job_name="asr",
    params={...},
    resources={"num_cpus": 8},     # 覆盖 ray.yaml 中的 num_cpus=4
)
```

---

## 6. 完整示例：会议录音处理流水线

### 6.1 一次性配置

```python
# 1. 配置租户密钥（AdminMCP）
create_secret(key_name="ASR_API_KEY", value="sk-xxx", description="阿里云 ASR")
create_secret(key_name="ASR_ENDPOINT", value="https://asr.aliyuncs.com/v1")
create_secret(key_name="LLM_API_KEY", value="sk-yyy", description="纪要生成 LLM")

# 2. 注册 Skill（AssetMCP）
register_skill(
    name="meeting-processing",
    description="会议录音 ASR + 纪要 + 知识萃取",
    code=meeting_zip_b64,
    format="zip",
    version="1.0.0",
)
```

### 6.2 每次会议

```python
# 1. 上传录音文件（DataMCP）
s3_put(uri="s3://lakemind-filesets/tenant-a/meetings/m001.wav", data=audio_bytes)

# 2. 提交 ASR job
asr_job = ray_submit_job(
    skill_uri="lake://skills/meeting-processing@v1",
    job_name="asr",
    params={"file_uris": ["s3://lakemind-filesets/tenant-a/meetings/m001.wav"]},
    task_id="meeting-001",
)

# 3. 等待完成
while True:
    status = ray_job_status(asr_job["job_id"])
    if status["status"] in ("completed", "failed"):
        break
    time.sleep(5)

# 4. 提交纪要生成 job
summarize_job = ray_submit_job(
    skill_uri="lake://skills/meeting-processing@v1",
    job_name="summarize",
    params={"transcript_uri": status.get("result_uri")},
    task_id="meeting-001",
)

# 5. 纪要结果存入知识库（AssetMCP）
result = ray_job_result(summarize_job["job_id"])
ingest_knowledge(kb_name="meetings", concepts=[{
    "id": "meeting-001",
    "title": "2026-07-07 项目评审会",
    "content": result["summary"],
}])
```

---

## 7. Skill 包内多个 Job 的协作

一个 Skill 包内的多个 job 共享上下文，适合构建处理流水线：

```
meeting-processing/
└── jobs/
    ├── asr/          ← 第一步：录音 → 文本
    ├── summarize/    ← 第二步：文本 → 纪要
    └── extract/      ← 第三步：纪要 → 知识点
```

Agent 按顺序提交：

```python
# 流水线
job1 = ray_submit_job(skill_uri=uri, job_name="asr",       params={...}, task_id="m001")
# ... 等待 job1 完成 ...
job2 = ray_submit_job(skill_uri=uri, job_name="summarize",  params={"transcript_uri": ...}, task_id="m001")
# ... 等待 job2 完成 ...
job3 = ray_submit_job(skill_uri=uri, job_name="extract",    params={"summary_uri": ...}, task_id="m001")
```

> **后续扩展**：ray.yaml 中将支持 `depends_on` 声明，Server 自动编排 pipeline。

---

## 8. 实时音频流适配

实时流的密钥处理与批量相同 — 流启动时注入一次密钥，后续分片复用：

```python
# 流式 job（entrypoint 指向流式处理脚本）
stream_job = ray_submit_job(
    skill_uri="lake://skills/meeting-processing@v1",
    job_name="asr-stream",
    params={"stream_url": "rtmp://..."},
    task_id="meeting-live-001",
)
```

业务代码内部处理流分片，密钥在 `os.environ` 中全程可用。

---

## 9. REST API 参考

### 9.1 密钥管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/metadata/secrets` | 创建密钥 |
| PUT | `/api/v1/metadata/secrets/{key_name}` | 更新密钥 |
| DELETE | `/api/v1/metadata/secrets/{key_name}` | 删除密钥 |
| GET | `/api/v1/metadata/secrets` | 列出密钥（不返回值） |

请求头：

```
Authorization: Bearer lakemind-internal-api-key
X-Tenant-Id: tenant-a
X-Agent-Id: agent-001
```

### 9.2 Ray Job

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/compute/jobs/submit` | 提交 Skill-based Ray job |
| GET | `/api/v1/compute/jobs/{job_id}` | 查询状态 |
| GET | `/api/v1/compute/jobs/{job_id}/result` | 获取结果 |
| POST | `/api/v1/compute/jobs/{job_id}/cancel` | 取消 job |
| GET | `/api/v1/compute/jobs` | 列出 jobs（按租户过滤） |

提交请求体：

```json
{
    "skill_uri": "lake://skills/meeting-processing@v1",
    "job_name": "asr",
    "params": {"file_uris": ["s3://..."]},
    "task_id": "meeting-001",
    "env_overrides": {},
    "resources": {}
}
```

---

## 10. MCP 工具速查

### AdminMCP（密钥管理）

| 工具 | 参数 | 说明 |
|------|------|------|
| `create_secret` | key_name, value, description="" | 创建租户密钥 |
| `update_secret` | key_name, value, description="" | 更新密钥 |
| `delete_secret` | key_name | 删除密钥 |
| `list_secrets` | — | 列出密钥名（不返回值） |

### DataMCP（Ray job）

| 工具 | 参数 | 说明 |
|------|------|------|
| `ray_submit_job` | skill_uri, job_name, params={}, task_id="", env_overrides={}, resources={} | 提交 Ray job |
| `ray_job_status` | job_id | 查询状态 |
| `ray_job_result` | job_id | 获取结果 |
| `ray_job_cancel` | job_id | 取消 job |
| `ray_job_list` | status="" | 列出 jobs |
| `list_skill_jobs` | skill_uri | 列出 Skill 包中的可用 job |

### AssetMCP（Skill 管理）

| 工具 | 参数 | 说明 |
|------|------|------|
| `register_skill` | name, code, description, format="py", version="1.0.0" | 注册 Skill（format: "py" 或 "zip"） |
| `get_skill` | name, format="py" | 获取 Skill 代码 |
| `search_skill` | query, top_k=5 | 语义搜索 Skill |
| `list_skills` | — | 列出全部 Skill |
| `delete_skill` | name, format="py" | 删除 Skill |

---

## 11. 调试技巧

### 11.1 本地测试业务代码

业务代码是普通 Python，可本地测试（手动设环境变量）：

```bash
# 设置密钥环境变量
export ASR_API_KEY="sk-test"
export ASR_ENDPOINT="https://asr.aliyuncs.com/v1"

# 运行
python -m asr_batch
```

### 11.2 检查 Skill 包结构

```python
import zipfile, io

with open("meeting-processing.zip", "rb") as f:
    with zipfile.ZipFile(io.BytesIO(f.read())) as zf:
        for name in zf.namelist():
            print(name)
        # 确认 jobs/asr/ray.yaml 存在
```

### 11.3 查看密钥是否正确注入

在业务代码中（临时调试用，生产环境删除）：

```python
import os
# 检查密钥是否存在（不打印值）
print("ASR_API_KEY set:", "ASR_API_KEY" in os.environ)
print("ASR_ENDPOINT set:", "ASR_ENDPOINT" in os.environ)
```

### 11.4 查看 Ray job 日志

```python
# Ray Dashboard
# http://localhost:8265 → Jobs → 选择 job → Logs
# 日志中的密钥值已自动替换为 ***REDACTED***
```

---

## 12. 最佳实践

1. **密钥与代码分离** — 密钥走 `create_secret`，代码里只读 `os.environ`
2. **一个 Skill 一个领域** — `meeting-processing` 包含 asr/summarize/extract，不要把不相关的 job 混在一起
3. **ray.yaml 最小化** — 只声明 entrypoint + dependencies + resources，业务逻辑在代码里
4. **结果写回 LakeMind** — 通过 REST API 写回 SeaweedFS，不要直接操作底层存储
5. **SKILL.md 写清楚** — Agent 靠语义搜索找 Skill，描述质量直接影响检索效果
6. **版本管理** — Skill 注册时指定 version，`skill_uri` 中用 `@v1` 引用特定版本
7. **资源配额合理** — ray.yaml 中声明实际需要的 CPU/GPU，避免资源浪费
