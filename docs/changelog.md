# 变更日志

所有 notable 变更记录在此。日期格式 YYYY-MM-DD。

## [v0.1.2] — 2026-07-11

### 修复

#### AssetMCP/DataMCP embedding 路由
- `server_client.py` 的 `embed()` 方法从 Server `/api/v1/cognitive/embedding/embed`（404 未 mount）改为直接调用 ModelServing `/v1/embeddings`
- 影响：`ingest_knowledge`、`search_knowledge`、`register_skill`、`search_skill`、`vector_search` 全部恢复正常
- AssetMCP 和 DataMCP 的 `server_client.py` 均已修复

#### Memory 搜索距离度量
- `basic.py` 的 `search()` 从默认 L2 距离改为 `.metric("cosine")`
- 根因：L2 距离 >1.0 时 `score = 1.0 - dist = 0`，低于 threshold 0.1，导致所有结果被过滤
- 修复后：4 query × top-3 均返回相关结果（score 0.12~0.67）

#### verify_full.py 适配 ModelServing 架构
- L0：修正 ray-worker 容器名（`lakemind-server-ray-worker-*`），新增 `lakemind-model-serving`
- L1：移除 `embedding`/`llm` 引擎检查（已移至 ModelServing）
- L2：`_l2_embedding()` 和 `_l2_llm()` 改为检查 ModelServing `:10824` 端点
- 验证结果：L0-L8 共 286/286 PASS

### 新增

#### examples/meeting-agent/
- 浏览器实时会议知识化 Agent Demo
- 流水线：录音 → ASR → 摘要 → 知识萃取 → 入库 → 检索
- MediaRecorder per-chunk restart + host ffmpeg WebM→WAV + FunASR 标签清理
- E2E 验证通过：12 chunk ASR, 3 摘要, 1 萃取, 检索自检

#### examples/lakemind-connector/
- opencode AI Agent 通过 Skill 接入 LakeMind 的示例
- `LakeMindConnector`：MCP + REST 统一封装
- 9 知识概念 + 5 记忆入库，全量检索验证通过
- 全局 opencode Skill 安装（`~/.config/opencode/skills/lakemind-connector/`）

#### README_agent.md
- Agent 面向的接入指南，位于项目根目录
- 包含连接信息、copy-paste 代码、MCP 工具表、REST API 速查、踩坑清单

## [v0.1.1] — 2026-07-10

### 新增

#### LakeMindModelServing（统一模型服务）
- litellm Router 替代手写 GatewayLLM，多 provider 路由 + fallback
- fastembed 本地嵌入（jinaai/jina-embeddings-v2-base-zh, dim=768）从 Server 移入
- FunASR 本地 ASR（SenseVoice-Small，CPU）
- OpenAI 兼容 API（/v1/chat/completions, /v1/embeddings, /v1/audio/transcriptions）
- 模型注册表（PG model_registry 表，运行时热加载）
- 端口 :10824，容器 lakemind-model-serving

#### Steward LLM 对话
- Steward 通过 ModelServing LLM 驱动对话（model=deepseek-v4-flash）
- 意图识别 → MCP 工具调用 → LLM 格式化输出
- 10 个意图关键词 + 自然对话 fallback

### 变更

- Server 引擎从 11 → 10（移除 embedding + llm，新增 model_serving 健康检查）
- Server `all_health()` 用 `model_serving` 替代 `embedding` + `llm`
- Server memory 引擎通过 HTTP 调用 ModelServing 获取 embedding 和 LLM
- 容器从 12 → 13（新增 lakemind-model-serving）
- 3 compose 组：lakemind-server（7 容器）/ lakemind-mcp（3 容器）/ lakemind-runtime（3 容器）
- Monitor 前端：移除 embedding/llm 引擎显示，添加 model_serving，暗色主题修复
- Asset MCP：修复 skills/knowledge/memory 资源在表不存在时的 error 泄漏

### 已知限制（更新）

- ~~Steward LLM provider=simple~~ → 已接入 ModelServing LLM
- ~~funasr 仍在后台安装~~ → 已完成安装，ASR health=true
- 动态 Token 不跨 MCP 共享（MVP 使用静态 config.yaml Token）
- LakeMindStudio 未开发（Tauri 桌面客户端）
- 3 份 server_client.py 重复（待提取共享包）

## [v0.1.0] — 2026-07-06

### 新增

#### 核心服务 LakeMindServer
- REST API 网关（40+ OpenAPI 路径，11 功能域）
- 11 个 Protocol 接口定义（Plugin 架构）
- 9 个 Server 引擎插件 + ModelServing：
  - 数据存储：SeaweedFS / Iceberg / LanceDB / Valkey / PostgreSQL Graph / PostgreSQL Metadata
  - 数据计算：DuckDB / Ray / Embedded
  - 认知计算：fastembed / BasicMemory / GatewayLLM
- 引擎可插拔配置（engines.yaml）
- Bearer Token 认证 + 租户/Agent/Scope 三级上下文
- httpx 连接池（max 50 连接，10 keepalive）

#### Ray 分布式计算
- 自建 Ray 镜像（python:3.12-slim + ray 2.41.0 + numpy）
- RayCompute 插件：7 种分布式任务（map / parallel_map / sum / sleep_test / embed_batch / pi_monte_carlo / matrix_multiply）
- 3 节点集群（head + 2 workers，12 CPU）
- `--profile ray` 开关，支持 embedded ↔ ray 切换

#### LLM 模型网关
- GatewayLLM 路由器：多 provider 路由 + fallback 降级
- 3 种 Provider：OpenAICompat / Anthropic / Ollama
- 4 个 REST 端点：/chat /embed /models /health
- 配置驱动：engines.yaml 声明 providers + routing + fallback
- 零新依赖（httpx 直连，不引入 LiteLLM/openai SDK）

#### 三个 MCP 服务
- LakeMindAssetMCP（:8401）：23 tools, 11 resources, 6 prompts，认知资产面
- LakeMindDataMCP（:8402）：18 tools, 6 resources, 2 prompts，数据面通过 REST API 透传
- LakeMindAdminMCP（:8403）：17 tools, 6 resources, 2 prompts，管理面
- 合计：58 tools, 23 resources, 10 prompts
- MCP 瘦客户端：仅 mcp + pydantic + pyyaml + structlog + httpx
- ServerClient：httpx.AsyncClient + 连接池，通过 REST API 访问 Server
- scope 隔离：business / steward / monitor 三级 Token
- `execute_skill` 已移除（平台只存取不执行）

#### 认知资产
- mem0 风格记忆引擎：8 方法（add/search/get/list/update/delete/clear/history），LLM 事实抽取 + 哈希去重
- OKF 知识格式：YAML frontmatter + markdown body + PG 图交叉链接
- Embedding：fastembed + jinaai/jina-embeddings-v2-base-zh（dim=768，中英混合，Apache 2.0）

#### 运行平面
- LakeMindSteward（:8500）：LangGraph 巡检工作流 + 对话管理
- LakeMindMonitor（:3000）：Express + 静态 HTML，14 API 路由

#### 验证脚本
- verify_full.py：L0-L9 全分层验证，297/297 PASS（含 150 Agent 并发压测）
- verify_monitor.py：18 Monitor 测试
- verify_ray.py：12 Ray 分布式测试
- verify_llm.py：10 LLM 网关测试

### 变更

- PostgreSQL 16 替代 Gravitino + SQLite 作为统一元数据
- PG 原生表替代 AGE 图扩展（编译超时）
- Express 替代 Nuxt 3（构建秒级完成）
- MCP 从直连引擎改为 REST API 瘦客户端（MCP 不直连任何引擎）
- Valkey 替代 Dragonfly（BSD 3-Clause 替代 BSL 1.1）
- Embedding 从 BAAI/bge-small-en-v1.5 (384d) 换为 jinaai/jina-embeddings-v2-base-zh (768d)
- 3 个 MCP 目录移入 LakeMindMCP/ 统一编排
- 3 compose 组：LakeMindServer / LakeMindMCP / LakeMindMonitor

### 验证结果

| 套件 | 结果 |
|------|------|
| verify_full.py L0-L9 | 297/297 PASS |
| verify_monitor.py | 18/18 PASS |
| verify_ray.py | 12/12 PASS |
| verify_llm.py | 10/10 PASS |
| **合计** | **297/297 PASS** |

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
- Steward LLM provider=simple（关键词匹配，未接 LLM 网关）
- Steward inspect() 无 MCP 降级处理（MCP 不可用时无 fallback 直连 REST API）
- LakeMindStudio 未开发（Tauri 桌面客户端）
- 流式响应未支持（LLM chat 为同步）
- per-tenant 模型配置未实现
- 3 份 server_client.py 重复（待提取共享包）
