# 变更日志

所有 notable 变更记录在此。日期格式 YYYY-MM-DD。

## [v0.1.0] — 2026-07-12

### 核心

#### LakeMindServer
- REST API 网关（40+ OpenAPI 路径，11 功能域）
- 11 个 Protocol 接口定义（Plugin 架构）
- 10 个 Server 引擎插件 + ModelServing
- 引擎可插拔配置（engines.yaml）
- Bearer Token 认证 + 租户/Agent/Scope 三级上下文
- httpx 连接池（max 50 连接，10 keepalive）

#### LakeMindModelServing（统一模型服务）
- litellm Router 替代手写 GatewayLLM，多 provider 路由 + fallback
- fastembed 本地嵌入（jinaai/jina-embeddings-v2-base-zh, dim=768）
- FunASR 本地 ASR（SenseVoice-Small，CPU）
- OpenAI 兼容 API（/v1/chat/completions, /v1/embeddings, /v1/audio/transcriptions）
- 模型注册表（PG model_registry 表，运行时热加载）
- 端口 :10824，容器 lakemind-model-serving

#### Ray 分布式计算
- 自建 Ray 镜像（python:3.12-slim + ray 2.41.0 + numpy）
- RayCompute 插件：7 种分布式任务
- 3 节点集群（head + 2 workers，12 CPU）
- `--profile ray` 开关，支持 embedded ↔ ray 切换

#### 三个 MCP 服务
- LakeMindAssetMCP（:8401）：23 tools, 11 resources, 6 prompts
- LakeMindDataMCP（:8402）：18 tools, 6 resources, 2 prompts
- LakeMindAdminMCP（:8403）：17 tools, 6 resources, 2 prompts
- 合计：58 tools, 23 resources, 10 prompts
- `execute_skill` 已移除（平台只存取不执行）

#### 认知资产
- mem0 风格记忆引擎：8 方法，LLM 事实抽取 + 哈希去重
- OKF 知识格式：YAML frontmatter + markdown body + PG 图交叉链接
- Embedding：fastembed + jinaai/jina-embeddings-v2-base-zh（dim=768）

#### 运行平面
- LakeMindSteward（:8500）：LangGraph 巡检工作流 + ModelServing LLM 对话
- LakeMindMonitor（:3000）：Express + 静态 HTML，14 API 路由

### 修复 — Ray jobs（一等公民）

#### Ray dashboard 跨容器不可達
- 根因：Ray dashboard 默认绑定 `127.0.0.1`，`JobSubmissionClient` 从 server-api 容器无法访问 `lakemind-ray-head:8265`
- 修复：docker-compose.yml 添加 `--dashboard-host=0.0.0.0`
- 修复：`ray_compute.py` 使用 dashboard 地址 `http://lakemind-ray-head:8265` 而非 Ray client 地址 `ray://lakemind-ray-head:10001`

#### JobSubmissionClient 导入
- `ray.job_submission` 属性不可用，改为 `from ray.job_submission import JobSubmissionClient` 显式导入

#### runtime_env py_modules → working_dir
- Ray 不接受 `.zip` 作为 `py_modules`，改用 `working_dir`

#### Skill job 状态轮询
- 新增 `RayCompute.get_job_status(ray_job_id)` 方法
- `jobs.py` 的 `job_status`/`job_result` 端点支持 skill job：查 PG 获取 `ray_job_id`，轮询 Ray 获取实时状态
- `DistributedComputePlugin` 协议新增 `get_job_status` 方法

#### Skill URI 解析
- `lake://skills/test-skill` 被误当 `s3://` 格式解析，`lake:` 成 bucket 名
- 修复：先判断 URI 前缀，`s3://` 走 S3 路径，`lake://` 走 tenant 路径

#### 清理
- 移除死代码 `_remote_eval`（module-level `@staticmethod`）
- temp file 在 `finally` block 中清理

### 修复 — Embedding & Memory

#### AssetMCP/DataMCP embedding 路由
- `server_client.py` 的 `embed()` 方法从 Server `/api/v1/cognitive/embedding/embed`（404 未 mount）改为直接调用 ModelServing `/v1/embeddings`
- 影响：`ingest_knowledge`、`search_knowledge`、`register_skill`、`search_skill`、`vector_search` 全部恢复正常

#### Memory 搜索距离度量
- `basic.py` 的 `search()` 从默认 L2 距离改为 `.metric("cosine")`
- 根因：L2 距离 >1.0 时 `score = 1.0 - dist = 0`，低于 threshold 0.1，导致所有结果被过滤
- 修复后：4 query × top-3 均返回相关结果（score 0.12~0.67）

### 新增 — Examples

#### examples/meeting-agent/
- 浏览器实时会议知识化 Agent Demo
- 流水线：录音 → ASR → 摘要 → 知识萃取 → 入库 → 检索
- 四层架构：Web → Agent → Skill → Job (Ray)
- 17 分钟实时测试：145 chunks, 100+ Ray jobs, 100% success
- MediaRecorder per-chunk restart + host ffmpeg WebM→WAV + FunASR 标签清理

#### examples/lakemind-connector/
- opencode AI Agent 通过 Skill 接入 LakeMind 的统一连接器
- `LakeMindConnector`：MCP + REST + Ray Jobs + ASR 统一封装（36 public methods）
- Ray job 管理：submit / poll / cancel / list / submit_and_wait
- S3 URI-based API：`s3_put_uri` / `s3_get_uri` / `s3_exists_uri`
- ASR + FunASR 标签清理、Skill 打包上传、统一健康检查
- 9 知识概念 + 5 记忆入库，全量检索验证通过
- 全局 opencode Skill 安装（`~/.config/opencode/skills/lakemind-connector/`）

#### README_agent.md
- Agent 面向的接入指南，位于项目根目录
- §4: Ray jobs 开发指南（四层架构、step-by-step、开发模式、最佳实践清单）
- §9: 踩坑清单（container DNS vs localhost、/add 不覆盖、FunASR 清理等）

### 验证结果

| 套件 | 结果 |
|------|------|
| verify_full.py L0-L8 | 286/286 PASS |
| Ray built-in func | 5/5 PASS |
| Skill-based Ray job | submit/status/result/cancel 全 PASS |
| DataMCP → Server → Ray | PASS |
| **合计** | **286/286 PASS** |

### 运行容器

13 个容器：server-api / postgres / seaweedfs / valkey / ray-head / ray-worker-1 / ray-worker-2 / asset-mcp / data-mcp / admin-mcp / steward / monitor / model-serving

### 技术栈

| 组件 | 选型 | 许可证 |
|------|------|--------|
| 对象存储 | SeaweedFS | Apache 2.0 |
| 表格式 | Apache Iceberg | Apache 2.0 |
| 向量 | PyLance + LanceDB | Apache 2.0 / MIT |
| 元数据 | PostgreSQL 16 | PostgreSQL License |
| 缓存 | Valkey | BSD 3-Clause |
| 即席计算 | DuckDB | MIT |
| 分布式计算 | Ray 2.41 | Apache 2.0 |
| Embedding | fastembed (jina-zh) | Apache 2.0 |
| LLM 网关 | litellm | MIT |
| 语音识别 | FunASR | MIT |
| MCP SDK | FastMCP | MIT |
| Agent 框架 | LangGraph | MIT |
| Monitor | Express | MIT |

### 已知限制

- 动态 Token 不跨 MCP 共享（MVP 使用静态 config.yaml Token）
- LakeMindStudio 未开发（Tauri 桌面客户端）
- 3 份 server_client.py 重复（待提取共享包）
- 流式响应未支持（LLM chat 为同步）
- per-tenant 模型配置未实现
