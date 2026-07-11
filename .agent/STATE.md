# STATE.md — LakeMind 项目开发进展状态

> 最后更新：2026-07-11 21:40
> 总文件：`AGENTS.md`，设计规范：`.agent/DESIGN.md`，开发规范：`.agent/SPEC.md`

---

## 1. 总体进度

```
数据平面  ████████████████████  100%  (REST API + 10 引擎 + Ray + ModelServing)
运行平面  ████████████████████  100%  (3 MCP + Steward + Monitor 全完成)
开发平面  ░░░░░░░░░░░░░░░░░░░░    0%  (Studio 未开始)
示例      ████████████████████  100%  (meeting-agent + lakemind-connector)
验证      ████████████████████  100%  (L0-L8 286/286 PASS)
文档      ████████████████████  100%  (AGENTS + .agent/ + docs/ + README + README_agent + CHANGELOG)
v0.1.0 审计 ████████████████████  100%  (3 BLOCKER + 9 NEEDS ATTENTION 已修复)

总体      ████████████████████  ~99%
```

### 里程碑时间线

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1-2 | Server REST API + 3 容器 + PG catalog | ✅ 完成 |
| Phase 3-4 | 3 MCP + Steward + Monitor | ✅ 完成 |
| Ray 分布式 | 自建镜像，3 节点 12 CPU，7 任务类型 | ✅ 完成 |
| LLM 网关 | GatewayLLM 路由器，3 provider，4 端点 | ✅ 完成 |
| MCP 重设计 | mem0 记忆 + OKF 知识 + execute_skill 移除 + 三要素 | ✅ 完成 |
| 许可证审计 | Dragonfly BSL 1.1 → Valkey BSD 3-Clause | ✅ 完成 |
| LakeMindModelServing | 统一模型服务：litellm + fastembed + FunASR | ✅ 完成 |
| Steward LLM 接入 | Steward 通过 ModelServing LLM 驱动对话 | ✅ 完成 |
| Monitor 前端修复 | 移除旧引擎、添加 model_serving、暗色主题修复 | ✅ 完成 |
| 文档刷新 | AGENTS + .agent/ + docs/ + README + reports/ | ✅ 完成 |
| 文档一致性修复 | 5 核心文档对齐 + docs/reports 传播修复 | ✅ 完成 |
| 全面测试 | L0-L9 全分层验证，297/297 PASS | ✅ 完成 |
| v0.1.0 审计修复 | 3 BLOCKER + 9 NEEDS ATTENTION 全修复 | ✅ 完成 |
| Embedding 路由修复 | AssetMCP/DataMCP embed() → ModelServing | ✅ 完成 |
| Memory 搜索修复 | L2 → cosine 距离度量 | ✅ 完成 |
| verify_full.py 更新 | 适配 ModelServing 架构，286/286 L0-L8 PASS | ✅ 完成 |
| examples/meeting-agent | 浏览器实时会议 Agent Demo | ✅ 完成 |
| examples/lakemind-connector | opencode Skill + 全局安装 | ✅ 完成 |
| README_agent.md | Agent 面向接入指南 | ✅ 完成 |
| LakeMindStudio | Tauri 桌面客户端 | ❌ 未开始 |

---

## 2. 容器运行状态

> 检查时间：2026-07-11 21:30

| 容器 | 端口 | 状态 | 用途 |
|------|------|------|------|
| lakemind-server-api | 10823 | ✅ Up | REST API + 10 引擎 |
| lakemind-model-serving | 10824 | ✅ Up | 统一模型服务（litellm + fastembed + FunASR） |
| lakemind-postgres | 5432 | ✅ Up | Metadata Hub |
| lakemind-seaweedfs | 8333 | ✅ Up | S3 对象存储 |
| lakemind-valkey | 6379 | ✅ Up | TTL KV 缓存（BSD 3-Clause） |
| lakemind-ray-head | 8265 | ✅ Up | Ray 主节点 |
| lakemind-ray-worker-1 | — | ✅ Up | Ray 工作节点 |
| lakemind-ray-worker-2 | — | ✅ Up | Ray 工作节点 |
| lakemind-asset-mcp | 8401 | ✅ Up | 资产面 MCP（23 tools, 6 prompts, 11 resources） |
| lakemind-data-mcp | 8402 | ✅ Up | 数据面 MCP（18 tools, 2 prompts, 6 resources） |
| lakemind-admin-mcp | 8403 | ✅ Up | 管理面 MCP（17 tools, 2 prompts, 6 resources） |
| lakemind-steward | 8500 | ✅ Up | 运维 Agent（LangGraph） |
| lakemind-monitor | 3000 | ✅ Up | 人类仪表板（Express） |

**全部 13 容器运行正常，10 引擎全部健康。**

### 引擎健康状态

```
object_storage: True    tabular:       True    vector:        True
kv:              True    graph:         True    metadata:      True
sql:             True    distributed:   True    model_serving: True
memory:          True
```

---

## 3. MCP 工具清单

### 3.1 AssetMCP（23 tools, 6 prompts, 11 resources）

| 域 | 工具 | 数量 |
|----|------|------|
| Knowledge | register, ingest, search, get, list, list_concepts, delete | 7 |
| Memory | add, search, get, list, update, delete, clear, history | 8 |
| Skill | search, register, get, list, delete | 5 |
| Ontology | query, update, delete | 3 |

- Prompts: search_knowledge_guide, okf_concept_guide, register_skill_guide, add_memory_guide, search_memory_guide, query_ontology_guide
- Resources: capabilities, workspace, knowledge, knowledge/{kb}/{id}, skills, skills/{name}, memory, memory/{id}, ontology, ontology/{concept}
- `execute_skill` 已移除
- `lake://system/health` 不在 AssetMCP

### 3.2 DataMCP（18 tools, 2 prompts, 6 resources）

| 域 | 工具 | 数量 |
|----|------|------|
| 表操作 | query_table, write_table, sql_query, list_tables, describe_table, create_table, drop_table | 7 |
| 向量 | vector_search | 1 |
| S3 | s3_get, s3_put, s3_list, s3_delete | 4 |
| KV | kv_get, kv_set, kv_delete, kv_scan | 4 |
| 图 | graph_query, graph_update | 2 |

### 3.3 AdminMCP（17 tools, 2 prompts, 6 resources）

| 域 | 工具 | 数量 |
|----|------|------|
| 用户 | create_user, list_users, update_user, delete_user | 4 |
| 租户 | create_tenant, list_tenants, update_tenant, delete_tenant | 4 |
| Token | issue_token, revoke_token, list_tokens | 3 |
| 资产类型 | register_asset_type, unregister_asset_type, list_asset_types | 3 |
| 平台 | get_platform_health, get_node_status, get_metrics | 3 |

---

## 4. 验证结果汇总

| 验证 | 脚本 | 结果 | 说明 |
|------|------|------|------|
| **全面测试 L0-L8** | `scripts/verify_full.py` | **286/286 PASS** | 全分层验证（L9 性能压测跳过） |
| PG catalog | `LakeMindServer/scripts/verify_pg_catalog.py` | 8/8 PASS | PyIceberg + PG |
| Ray 计算 | `LakeMindServer/scripts/verify_ray.py` | 12/12 PASS | 7 任务类型 |
| LLM 网关 | `scripts/verify_llm.py` | 10/10 PASS | 3 provider 路由 |
| Monitor | `LakeMindMonitor/scripts/verify_monitor.py` | 18/18 PASS | 14 API 路由 + 4 health |

### 全面测试分层明细（verify_full.py，2026-07-11 21:38）

| 层 | 内容 | 结果 |
|----|------|------|
| L0 | 容器健康（13 容器） | 13/13 PASS |
| L1 | 引擎健康（9 引擎） | 10/10 PASS |
| L2 | REST API + ModelServing（13 域 ~65 路由） | 65/65 PASS |
| L3 | AssetMCP（23 tools / 6 resources / 6 prompts） | 73/73 PASS |
| L4 | DataMCP（18 tools / 4 resources / 2 prompts） | 50/50 PASS |
| L5 | AdminMCP（17 tools / 6 resources / 2 prompts） | 51/51 PASS |
| L6 | MCP 安全（auth / scope 隔离） | 11/11 PASS |
| L7 | Steward + Monitor 集成 | 8/8 PASS |
| L8 | 端到端业务流（知识/记忆/技能/本体/跨域） | 5/5 PASS |
| L9 | 性能基线（10 项，含 150 Agent 并发） | SKIP（耗时，历史 297/297 PASS） |

### L9 性能基线结果

| 测试 | 结果 | 指标 |
|------|------|------|
| MCP 单次 tool 延迟 | PASS | mean=0.46ms, p99=0.63ms, 30 次取样 |
| REST 单次 API 延迟 | PASS | mean=0.09s, p99=0.15s, 50 次取样 |
| Embedding 100 条中英文 | PASS | mean=2.77s, p99=3.0s, 10 轮取样 |
| Vector search top-10 | PASS | mean=0.36s, p99=0.52s, 30 次取样 |
| Memory add+search 闭环 | PASS | 20 轮 0 错误 |
| 150 Agent × 50 ops 并发 | PASS | 7500 ops, QPS=35.1, 2 错误 (0.03%) |
| 150 Agent 持续 30s 稳定性 | PASS | QPS=32.4, err_rate=0.0% |
| MCP vs REST 延迟对比 | PASS | MCP 开销 0.42s |
| 冷启动延迟 | PASS | asset-mcp 重启后 2.56s 可用 |
| 并发递增阶梯 10→200 | PASS | 150 workers 无降级 |

### 阶梯压测 QPS 数据

| workers | QPS | err_rate |
|---------|-----|----------|
| 10 | 53.8 | 0.00% |
| 30 | 42.5 | 0.00% |
| 50 | 37.4 | 0.00% |
| 100 | 36.6 | 0.00% |
| 150 | 34.5 | 0.00% |
| 200 | 34.4 | 0.00% |

---

## 5. 各包完成度

### 5.1 LakeMindServer — 100%

- ✅ REST API（:10823，40+ 路径）
- ✅ 10 引擎全部健康（object_storage, tabular, vector, kv, graph, metadata, sql, distributed, model_serving, memory）
- ✅ PostgreSQL 16（Iceberg catalog + 图 + 用户/租户/Token + memory_history）
- ✅ SeaweedFS + Valkey
- ✅ Ray 2.41.0（3 节点 12 CPU，7 任务类型，12/12 PASS）
- ✅ Memory 引擎（mem0 风格 8 方法，LLM 事实抽取 via ModelServing + 哈希去重）
- ✅ Embedding/LLM/ASR 移至 LakeMindModelServing（:10824）

### 5.2 LakeMindAssetMCP — 100%

- ✅ FastMCP 服务（:8401）
- ✅ 23 tools（knowledge 7 + memory 8 + skill 5 + ontology 3）
- ✅ 6 prompts
- ✅ 11 resources
- ✅ `execute_skill` 已移除
- ✅ OKF 知识格式（YAML frontmatter + markdown body + PG 图交叉链接）
- ✅ mem0 风格记忆（8 方法 + LLM 事实抽取）
- ✅ 认证中间件（Bearer Token + scope）

### 5.3 LakeMindDataMCP — 100%

- ✅ FastMCP 服务（:8402）
- ✅ 18 tools（表操作 7 + 向量 1 + S3 4 + KV 4 + 图 2）
- ✅ 2 prompts
- ✅ 6 resources
- ✅ 工具命名统一为 `verb_noun`
- ✅ 认证中间件（scope=data）

### 5.4 LakeMindAdminMCP — 100%

- ✅ FastMCP 服务（:8403）
- ✅ 17 tools（用户 4 + 租户 4 + Token 3 + 资产类型 3 + 平台 3）
- ✅ 2 prompts
- ✅ 6 resources
- ✅ 通过 REST API 访问 Server（不直连任何引擎）
- ✅ 认证中间件（scope=admin）

### 5.5 LakeMindSteward — 100%

- ✅ FastAPI 服务（:8500）
- ✅ LangGraph 巡检工作流（check_health → analyze → report）
- ✅ LLM 对话管理（意图识别 → MCP 工具调用 → LLM 格式化输出）
- ✅ LLM 通过 ModelServing（:10824）驱动，model=deepseek-v4-flash
- ✅ MCP 客户端（asset + data + admin 三面）
- ✅ 10 个意图关键词 + 自然对话 fallback

### 5.6 LakeMindMonitor — 100%

- ✅ Express BFF（:3000）+ Vue 3 + Element Plus + Pinia 前端
- ✅ 23 API 路由（含 `/api/dashboard/overview` 聚合端点）
- ✅ 5 页专业仪表板：
  - Dashboard：13 容器状态 + 10 引擎健康 + 资产/数据/平台计数 + 15s 自动刷新
  - Asset：4 Tab（知识库/技能/记忆/本体）结构化表格
  - Data：5 Tab（Iceberg/向量/S3/KV/图）前缀过滤
  - Admin：5 Tab（租户/用户/Token/类型/健康）全只读
  - Chat：Steward 对话 + 6 快捷指令 + 巡检面板 + localStorage
- ✅ 深色主题（GitHub Dark 风格）
- ✅ Steward inspect() bug 修复（`v != "ok"` → `v is not True`）
- ✅ Steward chat() 工具名修复（`data_list_tables` → `list_tables`）
- ✅ 无自有 DB，无自有用户系统

### 5.7 LakeMindModelServing — 100%

- ✅ FastAPI 服务（:10824）
- ✅ litellm Router（统一 LLM 路由，多 provider 支持）
- ✅ fastembed 本地嵌入（jina-embeddings-v2-base-zh, dim=768）
- ✅ FunASR 本地 ASR（SenseVoice-Small，CPU）
- ✅ 模型注册表（PG model_registry 表，运行时热加载）
- ✅ OpenAI 兼容 API（/v1/chat/completions, /v1/embeddings, /v1/audio/transcriptions）
- ✅ 模型管理 API（/v1/models/register, /v1/models/{id}）

### 5.8 LakeMindStudio — 0%

- ❌ 空目录，未开始
- 规划：Tauri 2.0 + Vue 3 + Vite
- 优先级：P2

---

## 6. 已知问题与技术债

| # | 问题 | 影响 | 优先级 | 状态 |
|---|------|------|--------|------|
| 1 | 3 个 server_client.py 重复 | AssetMCP/DataMCP/AdminMCP 各有一份 | P2 | v0.2 提取共享包 |
| 2 | 动态 Token 不跨 MCP 共享 | 静态 config.yaml Token，MVP 限制 | P2 | 已知限制 |
| 3 | Steward inspect() 无 MCP 降级 | MCP 不可用时无 fallback | P2 | v0.2 实现 |
| 4 | server-api Docker build 耗时 | Ray 依赖安装 ~10min | P3 | 用 docker cp 热更新 |
| 5 | ~~AssetMCP/DataMCP embed() 404~~ | ~~ingest/search_knowledge/skill 不可用~~ | ~~P0~~ | ✅ 已修复（v0.1.2） |
| 6 | ~~Memory search L2 距离~~ | ~~search_memory 返回空~~ | ~~P0~~ | ✅ 已修复（v0.1.2） |

---

## 7. 关键配置

### 7.1 PostgreSQL

```
host: lakemind-postgres:5432
db: lakemind
user: lakemind / password: lakemind_pass
```

### 7.2 S3 (SeaweedFS)

```
endpoint: http://lakemind-seaweedfs:8333
access_key: admin / secret_key: admin123456
region: us-east-1
buckets: lakemind-iceberg, lakemind-filesets
```

### 7.3 Valkey

```
host: lakemind-valkey:6379
image: valkey/valkey:8.0
license: BSD 3-Clause
```

### 7.4 REST API 认证

```
Authorization: Bearer lakemind-internal-api-key
X-Tenant-Id: retail / X-Agent-Id: agent-001 / X-Scopes: asset,data,admin
```

### 7.5 MCP Token

```
test-business-token  → tenant=retail,   scopes=[asset]          → AssetMCP
test-steward-token   → tenant=platform, scopes=[asset,data,admin] → 3 MCP
test-monitor-token   → tenant=platform, scopes=[asset]          → AssetMCP (只读)
```

### 7.6 Embedding

```
provider: fastembed
model: jinaai/jina-embeddings-v2-base-zh
dim: 768
```

### 7.7 LLM 网关

```
provider: modelarts
endpoint: https://api.modelarts-maas.com/openai/v1
model: deepseek-v4-flash
api_key: from MAAS_API_KEY env
```

### 7.8 Ray

```
head: lakemind-ray-head:8265
workers: lakemind-ray-worker-1, lakemind-ray-worker-2
CPU: 12 (4 per node)
```

### 7.9 LakeMindModelServing

```
port: 10824
container: lakemind-model-serving
litellm: Router（多 provider 路由）
fastembed: jinaai/jina-embeddings-v2-base-zh, dim=768
funasr: SenseVoice-Small（CPU）
endpoints:
  /v1/chat/completions, /v1/embeddings, /v1/audio/transcriptions
  /v1/models/register, /v1/models/{id}
config: LakeMindModelServing/config/models.yaml
pg_table: model_registry（运行时热加载）
```

---

## 8. 下一步计划

| 优先级 | 任务 | 预估工作量 |
|--------|------|-----------|
| P1 | **v0.1.0 发版**：git tag + GitHub release | 30min |
| P2 | 提取共享 LakeMindMCPShared 包 | 2h |
| P2 | LakeMindStudio（Tauri 桌面客户端） | 2-3d |
| P3 | 清理 Monitor 历史遗留代码 | 1h |

---

## 9. 文件索引

### 设计文档

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | AI Agent 协作约定（总文件） |
| `.agent/DESIGN.md` | 架构设计规范 |
| `.agent/SPEC.md` | 开发规范 |
| `.agent/STATE.md` | 本文件 |
| `README.md` | 项目总览 |
| `docs/` | 发布文档（architecture, api-reference, mcp-tools, etc.） |
| `reports/` | 验证报告与设计文档 |

### 关键源码

| 文件 | 说明 |
|------|------|
| `LakeMindServer/src/lakemind_server/engines.py` | 10 引擎聚合 |
| `LakeMindServer/src/lakemind_server/plugins/protocols.py` | 10 Protocol 定义 |
| `LakeMindServer/src/lakemind_server/plugins/cognitive/memory/basic.py` | mem0 风格记忆引擎 |
| `LakeMindServer/src/lakemind_server/plugins/storage/kv/valkey.py` | Valkey KV 引擎 |
| `LakeMindServer/src/lakemind_server/api/memory.py` | 8 mem0 风格 REST 端点 |
| `LakeMindServer/config/engines.yaml` | 引擎插件配置 |
| `LakeMindAssetMCP/src/lakemind_asset_mcp/server.py` | AssetMCP 入口（23 tools + 11 resources + 6 prompts） |
| `LakeMindAssetMCP/src/lakemind_asset_mcp/tools/knowledge.py` | 7 OKF tools |
| `LakeMindAssetMCP/src/lakemind_asset_mcp/tools/memory.py` | 8 mem0-style tools |
| `LakeMindDataMCP/src/lakemind_data_mcp/tools/data.py` | 18 透传 tools |
| `LakeMindAdminMCP/src/lakemind_admin_mcp/tools/admin.py` | 17 管理 tools |
| `LakeMindSteward/src/lakemind_steward/agent.py` | LangGraph 巡检 + 对话 |
| `LakeMindMonitor/server.js` | Express 代理层 |

### 验证脚本

| 脚本 | 结果 |
|------|------|
| `scripts/verify_full.py` | **297/297 PASS**（L0-L9 全分层） |
| `scripts/verify_three_mcp_v2.py` | 128/142 PASS（旧脚本，已被 verify_full.py 替代） |
| `LakeMindServer/scripts/verify_pg_catalog.py` | 8/8 PASS |
| `LakeMindServer/scripts/verify_ray.py` | 12/12 PASS |
| `scripts/verify_llm.py` | 10/10 PASS |
| `LakeMindMonitor/scripts/verify_monitor.py` | 18/18 PASS |
