# STATE.md — LakeMind 项目开发进展状态

> 最后更新：2026-07-04
> 权威方案：`LakeMind MVP阶段技术改造方案.md`（v3，已批准）
> 实施顺序：方案 §8，共 14 步

---

## 1. 总体进度

```
数据平面  ████████████████████  100%
运行平面  ████████████████████  100%  (3 MCP + Steward + Monitor 全完成)
开发平面  ░░░░░░░░░░░░░░░░░░░░    0%  (Studio 未开始)
验证      ██████████████████░░   90%  (单元+联合+Monitor PASS，端到端压测未做)
文档      ████████████████░░░░   80%  (总 README + .agent/ 完成，各包 README 部分)

总体      ██████████████████░░   ~85%
```

---

## 2. 步骤明细

| 步 | 内容 | 涉及包 | 状态 | 验证 | 日期 |
|----|------|--------|------|------|------|
| 1 | Server 改造：移除 Gravitino，加 PostgreSQL 16 | Server | ✅ 完成 | 3 容器 Up | — |
| 2 | PyIceberg + PG catalog 连通 | Server | ✅ 完成 | 8/8 PASS | — |
| 3 | 图存储（PG 原生表 graph_nodes/edges） | Server | ✅ 完成 | CRUD 验证 | — |
| 4 | Ray 集群 | Server | ⏭️ 跳过 | 镜像过大，嵌入式引擎足够 | — |
| 5 | AssetMCP：4 默认资产 + fastembed | AssetMCP | ✅ 完成 | 8/8 PASS | — |
| 6 | mem0 记忆引擎 | AssetMCP | ⏭️ 延迟 | 基础 remember/recall/forget 可用，mem0 需 LLM | — |
| 7 | DataMCP：13 透传工具 | DataMCP | ✅ 完成 | 联合验证 | — |
| 8 | AdminMCP：15 管理工具 | AdminMCP | ✅ 完成 | 联合验证 | — |
| 9 | 三 MCP 联合验证 | 3 MCP | ✅ 完成 | 22/22 PASS | — |
| 10 | Steward：LangGraph 巡检 + 对话 | Steward | ✅ 完成 | 巡检 + 对话验证 | — |
| 11 | Monitor：Express 仪表板 + Chat | Monitor | ✅ 完成 | 18/18 PASS | 2026-07-04 |
| 12 | Studio：Tauri 桌面客户端 | Studio | ❌ 未开始 | — | — |
| 13 | 端到端 200 Agent 并发压测 | 全部 | ❌ 未开始 | — | — |
| 14 | 更新各包 README + AGENTS.md | 全部 | 🔨 部分 | 总 README + .agent/ 完成 | 2026-07-04 |

---

## 3. 容器运行状态

> 检查时间：2026-07-04 12:10

| 容器 | 端口 | 状态 | 用途 |
|------|------|------|------|
| lakemind-postgres | 5432 | ✅ Up | Metadata Hub（Iceberg catalog + 图 + 用户/租户/Token） |
| lakemind-seaweedfs | 8333 | ✅ Up | S3 对象存储 |
| lakemind-dragonfly | 6379 | ✅ Up (healthy) | TTL KV 缓存 |
| lakemind-asset-mcp | 8401 | ✅ Up | 资产面 MCP（11 tools, 7 resources） |
| lakemind-data-mcp | 8402 | ✅ Up | 数据面 MCP（13 tools） |
| lakemind-admin-mcp | 8403 | ✅ Up | 管理面 MCP（15 tools） |
| lakemind-steward | 8500 | ✅ Up | 运维 Agent（LangGraph） |
| lakemind-monitor | 3000 | ✅ Up | 人类仪表板（Express） |

**全部 8 容器运行正常。**

---

## 4. 验证结果汇总

| 验证 | 脚本 | 结果 | 说明 |
|------|------|------|------|
| PG catalog | `LakeMindServer/scripts/verify_pg_catalog.py` | ✅ 8/8 PASS | load_catalog, create_namespace, create_table, append, scan, list_tables, concurrent_append, cleanup |
| AssetMCP | `LakeMindAssetMCP/scripts/verify_asset_mcp.py` | ✅ 8/8 PASS | tools/list(11), resources/list(7), capabilities, workspace, ontology CRUD, memory |
| 三 MCP 联合 | `scripts/verify_three_mcp.py` | ✅ 22/22 PASS | 全部 health, tool lists, AdminMCP CRUD, DataMCP ops, scope 隔离, 跨 MCP ontology |
| Monitor | `LakeMindMonitor/scripts/verify_monitor.py` | ✅ 18/18 PASS | 14 API 路由 + 4 health 子项 |
| Steward 巡检 | 手动 | ✅ 通过 | 正确识别 dragonfly health issue |
| 端到端 200 Agent | 待编写 | ❌ 未开始 | — |

---

## 5. 各包完成度

### 5.1 LakeMindServer — 100%

- ✅ docker-compose.yml（3 服务 + Ray profile）
- ✅ PostgreSQL 16 容器（含 init/01-age.sql 建表）
- ✅ SeaweedFS + Dragonfly 容器
- ✅ PyIceberg PG catalog 验证通过
- ✅ 图存储（PG 原生表）
- ⏭️ Ray 集群（profile=ray，默认不启动）

### 5.2 LakeMindAssetMCP — 100%

- ✅ FastMCP 服务（:8401）
- ✅ 4 个声明式资产 YAML（knowledge, skill, memory, ontology）
- ✅ 11 个工具（search/ingest/register_knowledge, search/register/execute_skill, remember/recall/forget, query/update_ontology）
- ✅ 7 个资源（capabilities, workspace, system/health, knowledge, skills, memory, ontology）
- ✅ 引擎适配层（s3, iceberg, lancedb, duckdb, dragonfly, graph, embedding）
- ✅ fastembed（BAAI/bge-small-en-v1.5, dim=384，懒加载）
- ✅ 认证中间件（Bearer Token + scope）
- ✅ 租户隔离（contextvars）
- ⏭️ mem0 引擎（延迟，需 LLM）

### 5.3 LakeMindDataMCP — 100%

- ✅ FastMCP 服务（:8402）
- ✅ 13 个透传工具（data_query/write/sql/list_tables/describe/create_table, lance_query, s3_get/put, kv_get/set, graph_query/update）
- ✅ 引擎适配层（与 AssetMCP 同构）
- ✅ 认证中间件（scope=data）
- ⚠️ `data_sql` 已知问题：`engines.duckdb` 签名是 `query_arrow(tables, sql, params)` 不是 `(sql)`，需修复

### 5.4 LakeMindAdminMCP — 100%

- ✅ FastMCP 服务（:8403）
- ✅ 15 个管理工具（user CRUD, tenant CRUD, token issue/revoke/list, register/unregister_asset_type, get_platform_health, get_node_status）
- ✅ 直连 PostgreSQL（psycopg2）
- ✅ 认证中间件（scope=admin）

### 5.5 LakeMindSteward — 100%

- ✅ FastAPI 服务（:8500）
- ✅ LangGraph 巡检工作流（check_health → analyze → report）
- ✅ 对话管理（意图识别 → 路由到 3 MCP）
- ✅ MCP 客户端（asset + data + admin 三面）
- ✅ 端点：POST /chat, POST /inspect, GET /health
- ⚠️ LLM provider=simple（未接真实 LLM，关键词匹配）

### 5.6 LakeMindMonitor — 100%

- ✅ Express 服务（:3000）
- ✅ 14 API 路由（health, asset×5, data, admin×4, chat, inspect）
- ✅ 静态页面（Dashboard / Asset / Data / Admin / Chat + Inspection）
- ✅ 无自有 DB，无自有用户系统
- ⚠️ 存在历史遗留代码（frontend/, backend/, pages/, nuxt.config.ts），Docker 实际走 Express

### 5.7 LakeMindStudio — 0%

- ❌ 空目录，未开始
- 规划：Tauri 2.0 + Vue 3 + Vite
- 功能：资产设计器, MCP 调试台, Skill 脚手架, CI/CD
- 优先级：P2

---

## 6. 已知问题与技术债

| # | 问题 | 影响 | 优先级 | 状态 |
|---|------|------|--------|------|
| 1 | DataMCP `data_sql` 签名不匹配 | `data_sql` 工具调用会失败 | P0 | 待修复 |
| 2 | Monitor 历史遗留代码 | frontend/backend/pages/nuxt.config.ts 混乱 | P2 | 待清理 |
| 3 | Monitor config.yaml 指向旧 8400 | 配置不一致（Docker 走 env var，不影响运行） | P2 | 待清理 |
| 4 | Steward LLM provider=simple | 未接真实 LLM，关键词匹配 | P1 | 待接入 |
| 5 | fastembed 仅英文模型 | 中文语义检索效果差 | P1 | 可换 bge-small-zh |
| 6 | 旧 LakeMindMCP 目录残留 | 已拆分为 3 MCP，旧代码可清理 | P2 | 待删除 |

---

## 7. 延迟项

| 项 | 原因 | 替代方案 | 恢复条件 |
|----|------|---------|---------|
| Ray 集群 | 镜像过大（~2GB），拉取超时 | 嵌入式引擎足够 MVP 单机 | 生产阶段或网络改善 |
| AGE 图扩展 | 编译超时（>20min） | PG 原生表 graph_nodes/edges | 预编译镜像或 Alpine 包 |
| mem0 记忆引擎 | 需 LLM 做事实抽取 | 基础 remember/recall/forget | 接入 LLM 后 |
| Apache Ranger | 生产阶段 | 应用层过滤 | 生产阶段 |
| Trino | 明确不引入 | DuckDB + Ray | — |

---

## 8. 关键配置

### 8.1 PostgreSQL

```
host: lakemind-postgres:5432
db: lakemind
user: lakemind / password: lakemind_pass
```

### 8.2 S3 (SeaweedFS)

```
endpoint: http://lakemind-seaweedfs:8333
access_key: admin / secret_key: admin123456
region: us-east-1
buckets: lakemind-iceberg, lakemind-filesets
```

### 8.3 Token

```
test-business-token  → tenant=retail,  scopes=[asset]
test-steward-token   → tenant=platform, scopes=[asset,data,admin]
test-monitor-token   → tenant=platform, scopes=[asset]
```

### 8.4 Embedding

```
provider: fastembed
model: BAAI/bge-small-en-v1.5
dim: 384
```

---

## 9. 下一步计划

| 优先级 | 任务 | 预估工作量 |
|--------|------|-----------|
| P0 | 修复 DataMCP `data_sql` 签名不匹配 | 30min |
| P1 | 端到端 200 Agent 并发压测 | 2h |
| P1 | 接入真实 LLM 到 Steward | 1h |
| P2 | 清理 Monitor 历史遗留代码 | 1h |
| P2 | 清理旧 LakeMindMCP 目录 | 30min |
| P2 | 更新各包 README | 2h |
| P2 | LakeMindStudio（Tauri 桌面客户端） | 2-3d |
| P3 | 换中文 embedding 模型 | 1h |
| P3 | AGE 预编译镜像 | 2h |
| P3 | mem0 集成 | 4h |

---

## 10. 文件索引

### 权威文档

| 文件 | 说明 |
|------|------|
| `LakeMind MVP阶段技术改造方案.md` | v3 改造方案（唯一权威） |
| `AGENTS.md` | AI Agent 协作约定 |
| `README.md` | 项目总览 |
| `.agent/SPEC.md` | 开发规范 |
| `.agent/DESIGN.md` | 设计规范 |
| `.agent/STATE.md` | 本文件 |

### 关键源码

| 文件 | 说明 |
|------|------|
| `LakeMindServer/docker-compose.yml` | 数据平面编排 |
| `LakeMindServer/docker/postgres-age/init/01-age.sql` | PG 建表脚本 |
| `LakeMindAssetMCP/src/lakemind_asset_mcp/server.py` | AssetMCP 入口 |
| `LakeMindAssetMCP/src/lakemind_asset_mcp/assets/native/*.yaml` | 4 个资产定义 |
| `LakeMindAssetMCP/src/lakemind_asset_mcp/engines/embedding.py` | fastembed 懒加载 |
| `LakeMindDataMCP/src/lakemind_data_mcp/tools/data.py` | 13 个透传工具 |
| `LakeMindAdminMCP/src/lakemind_admin_mcp/tools/admin.py` | 15 个管理工具 |
| `LakeMindSteward/src/lakemind_steward/agent.py` | LangGraph 巡检 + 对话 |
| `LakeMindMonitor/server.js` | Express 代理层 |
| `LakeMindMonitor/public/index.html` | 仪表板页面 |

### 验证脚本

| 脚本 | 结果 |
|------|------|
| `LakeMindServer/scripts/verify_pg_catalog.py` | 8/8 PASS |
| `LakeMindAssetMCP/scripts/verify_asset_mcp.py` | 8/8 PASS |
| `scripts/verify_three_mcp.py` | 22/22 PASS |
| `LakeMindMonitor/scripts/verify_monitor.py` | 18/18 PASS |
