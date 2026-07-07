# 变更日志

所有 notable 变更记录在此。日期格式 YYYY-MM-DD。

## [v0.1.0] — 2026-07-06

### 新增

#### 核心服务 LakeMindServer
- REST API 网关（40+ OpenAPI 路径，11 功能域）
- 11 个 Protocol 接口定义（Plugin 架构）
- 11 个引擎插件实现：
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

12 个容器：server-api / postgres / seaweedfs / valkey / ray-head / ray-worker-1 / ray-worker-2 / asset-mcp / data-mcp / admin-mcp / steward / monitor

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
| LLM 网关 | GatewayLLM (自建) | — |
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
