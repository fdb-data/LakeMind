# STATE.md — LakeMind 项目开发进展状态

> 最后更新：2026-07-05
> 总文件：`AGENTS.md`，设计规范：`.agent/DESIGN.md`，开发规范：`.agent/SPEC.md`

---

## 1. 总体进度

```
数据平面  ████████████████████  100%  (REST API + 11 引擎 + Ray + LLM 网关)
运行平面  ████████████████████  100%  (3 MCP + Steward + Monitor 全完成)
开发平面  ░░░░░░░░░░░░░░░░░░░░    0%  (Studio 未开始)
验证      ██████████████████░░   90%  (128/142 PASS，端到端压测未做)
文档      ████████████████████  100%  (AGENTS + .agent/ + docs/ + README)

总体      ██████████████████░░   ~90%
```

---

## 2. 容器运行状态

> 检查时间：2026-07-05

| 容器 | 端口 | 状态 | 用途 |
|------|------|------|------|
| lakemind-server-api | 10823 | ✅ Up | REST API + 11 引擎 |
| lakemind-postgres | 5432 | ✅ Up | Metadata Hub |
| lakemind-seaweedfs | 8333 | ✅ Up | S3 对象存储 |
| lakemind-dragonfly | 6379 | ✅ Up (healthy) | TTL KV 缓存 |
| lakemind-ray-head | 8265 | ✅ Up | Ray 主节点 |
| lakemind-ray-worker-1 | — | ✅ Up | Ray 工作节点 |
| lakemind-ray-worker-2 | — | ✅ Up | Ray 工作节点 |
| lakemind-asset-mcp | 8401 | ✅ Up | 资产面 MCP（23 tools, 6 prompts, 11 resources） |
| lakemind-data-mcp | 8402 | ✅ Up | 数据面 MCP（18 tools, 2 prompts, 6 resources） |
| lakemind-admin-mcp | 8403 | ✅ Up | 管理面 MCP（17 tools, 2 prompts, 6 resources） |
| lakemind-steward | 8500 | ✅ Up | 运维 Agent（LangGraph） |
| lakemind-monitor | 3000 | ✅ Up | 人类仪表板（Express） |

**全部 12 容器运行正常，11 引擎全部健康。**

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
| 用户 | create_user, get_user, list_users, update_user, delete_user | 5 |
| 租户 | create_tenant, get_tenant, list_tenants | 3 |
| Token | issue_token, revoke_token, list_tokens | 3 |
| 资产类型 | register_asset_type, unregister_asset_type, list_asset_types | 3 |
| 平台 | get_platform_health, get_node_status, get_metrics | 3 |

---

## 4. 验证结果汇总

| 验证 | 脚本 | 结果 | 说明 |
|------|------|------|------|
| 三 MCP 联合 | `scripts/verify_three_mcp_v2.py` | 128/142 PASS | 58 tools + 10 prompts + 23 resources + 端到端 |
| PG catalog | `LakeMindServer/scripts/verify_pg_catalog.py` | 8/8 PASS | PyIceberg + PG |
| Ray 计算 | `LakeMindServer/scripts/verify_ray.py` | 12/12 PASS | 7 任务类型 |
| LLM 网关 | `LakeMindServer/scripts/verify_llm_gateway.py` | 10/10 PASS | 3 provider 路由 |
| Monitor | `LakeMindMonitor/scripts/verify_monitor.py` | 18/18 PASS | 14 API 路由 + 4 health |
| 端到端 200 Agent | 待编写 | ❌ 未开始 | — |

### 14 项失败明细（verify_three_mcp_v2.py）

| 类别 | 失败项 | 原因 | 状态 |
|------|--------|------|------|
| Prompt 参数 | 部分 prompt 调用传了多余参数 | 测试脚本传统一 args 给所有 prompt | 已修复（按 prompt 传专属参数） |
| vector_search | 不存在的表 | 预期行为，测试用例需调整 | 待修复 |
| update_user / delete_user | list_users 响应格式 | 响应结构字段名不匹配 | 已修复（兼容 users/results 字段） |

---

## 5. 各包完成度

### 5.1 LakeMindServer — 100%

- ✅ REST API（:10823，40+ 路径）
- ✅ 11 引擎全部健康（object_storage, tabular, vector, kv, graph, metadata, sql, distributed, embedding, memory, llm）
- ✅ PostgreSQL 16（Iceberg catalog + 图 + 用户/租户/Token + memory_history）
- ✅ SeaweedFS + Dragonfly
- ✅ Ray 2.41.0（3 节点 12 CPU，7 任务类型，12/12 PASS）
- ✅ LLM Gateway（GatewayLLM，3 provider，10/10 PASS）
- ✅ fastembed（BAAI/bge-small-en-v1.5, dim=384）
- ✅ Memory 引擎（mem0 风格 8 方法，LLM 事实抽取 + 哈希去重）

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
- ✅ 17 tools（用户 5 + 租户 3 + Token 3 + 资产类型 3 + 平台 3）
- ✅ 2 prompts
- ✅ 6 resources
- ✅ 直连 PostgreSQL（psycopg2）
- ✅ 认证中间件（scope=admin）

### 5.5 LakeMindSteward — 100%

- ✅ FastAPI 服务（:8500）
- ✅ LangGraph 巡检工作流（check_health → analyze → report）
- ✅ 对话管理（意图识别 → 路由到 3 MCP）
- ✅ MCP 客户端（asset + data + admin 三面）
- ⚠️ LLM provider=simple（未接 GatewayLLM，关键词匹配）

### 5.6 LakeMindMonitor — 100%

- ✅ Express 服务（:3000）
- ✅ 14 API 路由
- ✅ 静态页面（Dashboard / Asset / Data / Admin / Chat + Inspection）
- ✅ 无自有 DB，无自有用户系统

### 5.7 LakeMindStudio — 0%

- ❌ 空目录，未开始
- 规划：Tauri 2.0 + Vue 3 + Vite
- 优先级：P2

---

## 6. 已知问题与技术债

| # | 问题 | 影响 | 优先级 | 状态 |
|---|------|------|--------|------|
| 1 | Steward LLM provider=simple | 未接 GatewayLLM，关键词匹配 | P1 | 待接入 |
| 2 | 3 个 server_client.py 重复 | AssetMCP/DataMCP/AdminMCP 各有一份 | P2 | 待提取共享包 |
| 3 | 动态 Token 不跨 MCP 共享 | 静态 config.yaml Token，MVP 限制 | P2 | 已知限制 |
| 4 | fastembed 仅英文模型 | 中文语义检索效果差 | P3 | 可换 bge-small-zh |
| 5 | Monitor 历史遗留代码 | frontend/backend/pages/nuxt.config.ts | P3 | 待清理 |
| 6 | server-api Docker build 耗时 | Ray 依赖安装 ~10min | P3 | 用 docker cp 热更新 |

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

### 7.3 REST API 认证

```
Authorization: Bearer lakemind-internal-api-key
X-Tenant-Id: retail / X-Agent-Id: agent-001 / X-Scopes: asset,data,admin
```

### 7.4 MCP Token

```
test-business-token  → tenant=retail,   scopes=[asset]          → AssetMCP
test-steward-token   → tenant=platform, scopes=[asset,data,admin] → 3 MCP
test-monitor-token   → tenant=platform, scopes=[asset]          → AssetMCP (只读)
```

### 7.5 Embedding

```
provider: fastembed
model: BAAI/bge-small-en-v1.5
dim: 384
```

### 7.6 LLM 网关

```
provider: modelarts
endpoint: https://api.modelarts-maas.com/openai/v1
model: deepseek-v4-flash
api_key: from MAAS_API_KEY env
```

### 7.7 Ray

```
head: lakemind-ray-head:8265
workers: lakemind-ray-worker-1, lakemind-ray-worker-2
CPU: 12 (4 per node)
```

---

## 8. 下一步计划

| 优先级 | 任务 | 预估工作量 |
|--------|------|-----------|
| P0 | 修复剩余 14 项测试失败，重跑全量验证 | 1h |
| P1 | Steward 接入 GatewayLLM | 1h |
| P1 | 端到端 200 Agent 并发压测 | 2h |
| P2 | 提取共享 LakeMindMCPShared 包 | 2h |
| P2 | LakeMindStudio（Tauri 桌面客户端） | 2-3d |
| P3 | 换中文 embedding 模型 | 1h |
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
| `LakeMindServer/src/lakemind_server/engines.py` | 11 引擎聚合 |
| `LakeMindServer/src/lakemind_server/plugins/protocols.py` | 11 Protocol 定义 |
| `LakeMindServer/src/lakemind_server/plugins/cognitive/memory/basic.py` | mem0 风格记忆引擎 |
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
| `scripts/verify_three_mcp_v2.py` | 128/142 PASS |
| `LakeMindServer/scripts/verify_pg_catalog.py` | 8/8 PASS |
| `LakeMindServer/scripts/verify_ray.py` | 12/12 PASS |
| `LakeMindServer/scripts/verify_llm_gateway.py` | 10/10 PASS |
| `LakeMindMonitor/scripts/verify_monitor.py` | 18/18 PASS |
