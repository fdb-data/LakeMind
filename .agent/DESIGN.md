# DESIGN.md — LakeMind 设计规范

> 本文件是 LakeMind 项目的架构设计规范，描述系统分层、组件职责、数据流与关键设计决策。
> 权威来源：`LakeMind MVP阶段技术改造方案.md`（v3，已批准）。

---

## 1. 总体架构

### 1.1 三平面 + 三 MCP

```
┌─────────────────────────────────────────────────────────┐
│                    开发平面                               │
│               LakeMindStudio (Tauri)                      │
└──────────────────────┬──────────────────────────────────┘
                       │ MCP Client
┌──────────────────────▼──────────────────────────────────┐
│                   运行平面                                │
│                                                          │
│  200 Agents ──→ AssetMCP (:8401)  ← 资产面              │
│  Steward ─────→ DataMCP  (:8402)  ← 数据面              │
│  Steward ─────→ AdminMCP (:8403)  ← 管理面              │
│  Steward (LangGraph, :8500)         ← 运维 Agent         │
│  Monitor (Express, :3000)           ← 人类仪表板         │
└──────────────────────┬──────────────────────────────────┘
                       │ S3 / PG / Dragonfly
┌──────────────────────▼──────────────────────────────────┐
│                    数据平面                               │
│               LakeMindServer                              │
│  SeaweedFS (:8333) + PostgreSQL (:5432) + Dragonfly (:6379) │
└─────────────────────────────────────────────────────────┘
```

### 1.2 两层模型

| 层 | 职责 | 面向 |
|----|------|------|
| **Data 层** | 多模态数据底座。透传，不做语义解释。数据是什么、存哪、怎么读写。 | Steward / 高级 Agent |
| **Asset 层** | 面向 Agent 认知模型的语义封装。声明式 YAML 定义，预置 4 类，可删可扩。 | 业务 Agent |

### 1.3 三 MCP 职责划分

| MCP | 端口 | Scope | 面向 | 职责 | 工具数 |
|-----|------|-------|------|------|--------|
| AssetMCP | 8401 | `asset` | 业务 Agent | 4 类默认资产 + 声明式自定义资产 | 11 |
| DataMCP | 8402 | `data` | Steward / 高级 Agent | Data 层全量透传 | 13 |
| AdminMCP | 8403 | `admin` | Steward | 用户/租户/Token/资产类型/健康 | 15 |

> 拆分为 3 个独立 MCP 的理由：独立部署、独立扩缩容、避免单点故障、职责清晰。

---

## 2. 数据平面设计

### 2.1 统一 Metadata Hub：PostgreSQL 16

**一个数据库技术栈，一个 PostgreSQL 实例**，承载全部结构化元数据：

| 用途 | 机制 | 表 |
|------|------|-----|
| Iceberg Catalog | PyIceberg SQL catalog | `iceberg_tables`, `iceberg_namespace_properties`（自动创建） |
| 图存储 | PG 原生表 + JSONB | `graph_nodes`, `graph_edges` |
| 用户/租户 | 普通 PG 表 | `tenants`, `users` |
| Token 管理 | PG 表 | `tokens` |
| 资产定义 | PG 表 | `asset_types` |

> **设计决策**：移除 Gravitino（JVM，H2），用 PostgreSQL 直接作为 PyIceberg SQL catalog。
> 少一个 JVM 服务，启动更快，资源更省，技术栈更简。
> AGE 图扩展因编译超时暂用 PG 原生表替代，功能等价。

### 2.2 引擎与存储映射

| 数据形态 | 引擎 | 物理存储 | 用途 |
|----------|------|----------|------|
| 结构化表 | Apache Iceberg | S3 数据文件 + PG catalog | 数据集、元信息小表 |
| 向量/多模态 | PyLance + LanceDB | S3 + 共享 Lance 目录 | 知识库向量、语义检索 |
| 图/本体 | PG graph_nodes/edges | PostgreSQL | 概念体系、实体关系 |
| 文件 | S3 原生 | SeaweedFS | Skill 代码、文档原文 |
| 短期 KV | Dragonfly | 内存 (TTL) | 工作记忆、会话缓存 |
| 即席计算 | DuckDB | 进程内 | 跨表 SQL、Parquet 直读 |

### 2.3 容器清单

| 容器 | 镜像 | 端口 | 状态 |
|------|------|------|------|
| seaweedfs | chrislusf/seaweedfs:latest | 8333 (S3) | ✅ 运行 |
| postgres | lakemind/postgres-age:16 | 5432 | ✅ 运行 |
| dragonfly | dragonflydb/dragonfly:latest | 6379 | ✅ 运行 |
| ray-head | rayproject/ray:2.41.0-py3.12 | 8265 | ⏭️ profile=ray，默认不启动 |
| ray-worker | rayproject/ray:2.41.0-py3.12 | — | ⏭️ ×2，默认不启动 |

### 2.4 数据域 → 引擎映射

| 数据域 | 引擎 | 资源 URI | MCP |
|--------|------|----------|-----|
| 结构化数据 | Iceberg + PG catalog | DataMCP 透传 | DataMCP |
| 知识/多模态 RAG | Lance + LanceDB | `lake://knowledge` | AssetMCP |
| 短期/工作记忆 | Dragonfly (TTL KV) | `lake://memory` | AssetMCP |
| 长期/语义记忆 | Lance 向量 + Iceberg 小表 | `lake://memory` | AssetMCP |
| Skills | S3 + Iceberg + LanceDB | `lake://skills` | AssetMCP |
| 本体/图 | PG graph_nodes/edges | `lake://ontology` | AssetMCP |

> **长期记忆双表设计**：Lance 向量表 + Iceberg 元信息小表，通过 `lance_uri` 字段关联。
> 这是方案明确约定的模式，**不要合并成单表**。

---

## 3. 资产层设计

### 3.1 声明式资产定义

自定义资产**不写代码**，用 YAML 声明：schema 是什么、什么格式存、什么引擎算。

```yaml
type: my_rag
description: "产品文档 RAG"
resource_root: "lake://my_rag"
capabilities: [search, ingest]

storage:
  vector:
    engine: lancedb
    schema: { doc_id: string, content: string, vector: float32[384] }
  metadata:
    engine: iceberg
    schema: { kb_id: string, name: string, created_at: timestamp }

operations:
  search:
    engine: vector_topk        # 预置引擎模式
    params: [query, top_k=5]
  ingest:
    engine: embed_and_write
    params: [documents]

embedding: default
```

### 3.2 默认 4 类资产

| 资产 | 能力 | 存储 | 工具 |
|------|------|------|------|
| **Knowledge** | search, ingest | LanceDB 向量 + Iceberg 元信息 | `search_knowledge`, `ingest_knowledge`, `register_knowledge` |
| **Skills** | search, execute | S3 代码 + Iceberg 元信息 + LanceDB 向量 | `search_skill`, `register_skill`, `execute_skill` |
| **Memory** | remember, recall, forget | Dragonfly 短期 + Lance 长期 + Iceberg 元信息 | `remember`, `recall`, `forget` |
| **Ontology** | query, update | PG graph_nodes/edges | `query_ontology`, `update_ontology` |

### 3.3 资产扩展机制

```
assets/
├── native/              # 4 个默认资产（内置）
│   ├── knowledge.yaml
│   ├── skill.yaml
│   ├── memory.yaml
│   └── ontology.yaml
├── extension/           # 用户自定义（自动扫描）
└── engine_patterns/     # 预置引擎模式实现
```

- **添加**：写 YAML → 放 `extension/` 或 AdminMCP `register_asset_type(yaml)` → AssetMCP 热加载
- **删除**：AdminMCP `unregister_asset_type(type)` → 仅删定义，不删底层数据
- **自定义引擎**：`engine: custom` + `handler: module.path`（逃生通道，MVP 不强制）

---

## 4. 运行平面设计

### 4.1 LakeMindAssetMCP（资产面）

```
AssetMCP (:8401)
├── 认证：Bearer Token, scope=asset
├── 资产注册表（从 PG + YAML 加载）
├── 嵌入式引擎（PyIceberg / LanceDB / fastembed / Dragonfly / PG graph）
├── 11 tools: search/ingest/register_knowledge, search/register/execute_skill,
│              remember/recall/forget, query/update_ontology
└── 7 resources: capabilities, workspace, system/health, knowledge, skills, memory, ontology
```

- fastembed 懒加载（模型在首次 embed() 时下载，不阻塞启动）
- 无状态，可多副本

### 4.2 LakeMindDataMCP（数据面）

```
DataMCP (:8402)
├── 认证：Bearer Token, scope=data
├── 全量透传，不做语义包装
├── 13 tools: data_query/write/sql/list_tables/describe/create_table,
│              lance_query, s3_get/put, kv_get/set, graph_query/update
└── 不关心上层，拿到表名/路径就读写
```

### 4.3 LakeMindAdminMCP（管理面）

```
AdminMCP (:8403)
├── 认证：Bearer Token, scope=admin
├── 直连 PostgreSQL（psycopg2，无引擎栈）
├── 15 tools: user CRUD, tenant CRUD, token issue/revoke/list,
│              register/unregister_asset_type, get_platform_health, get_node_status
└── 单副本即可（管理操作低频）
```

### 4.4 LakeMindSteward（运维 Agent）

```
Steward (:8500)
├── LangGraph 状态图
│   ├── 巡检工作流：check_health → analyze → report
│   └── 对话管理：意图识别 → 路由到 3 MCP
├── MCP Client（asset + data + admin 三面）
├── 端点：POST /chat, POST /inspect, GET /health
└── 不做降级直连（MCP 自身高可用）
```

> **选 LangGraph 理由**：巡检是典型多步图工作流，状态图 + 条件边天然契合。
> 内置 state persistence（检查点），巡检中断可恢复。human-in-the-loop 支持。

### 4.5 LakeMindMonitor（人类仪表板）

```
Monitor (:3000)
├── Express + 静态 HTML（极轻）
├── API 代理层 → 3 MCP（只读）+ Steward（chat/inspect）
├── 5 页面：Dashboard / Asset / Data / Admin / Chat
├── 无自有 DB · 无自有用户系统
└── 认证：用平台 Token（配置文件静态）
```

> **设计决策**：原方案 Nuxt 3，但 npm install 超时。改用 Express + 静态 HTML，
> 功能等价，Docker 构建秒级完成。

### 4.6 LakeMindStudio（开发平面 · 待开发）

```
Studio (Tauri 2.0)
├── Vue 3 + Vite + TypeScript（前端）
├── Tauri Rust Core（本地文件系统 / Git / 进程管理）
├── MCP Client（直连 3 MCP）
├── 资产设计器：YAML 编辑 + 实时预览 + 一键注册
├── MCP 调试台：在线调用工具/资源
├── Skill 脚手架：模板生成 + 本地沙箱
└── CI/CD：触发 webhook + 查看状态
```

---

## 5. Token 体系

### 5.1 Token 分配

| Token | Agent | Tenant | Scopes | 接入 |
|-------|-------|--------|--------|------|
| `test-business-token` | agent-business-01 | retail | `asset` | AssetMCP |
| `test-steward-token` | steward | platform | `asset, data, admin` | 3 MCP |
| `test-monitor-token` | monitor | platform | `asset` | AssetMCP (只读) |

### 5.2 Token 生命周期

- 签发：AdminMCP `issue_token(agent_id, tenant_id, scopes)` → 存 PG
- 校验：各 MCP AuthMiddleware 校验 Bearer Token + scope
- 吊销：AdminMCP `revoke_token(token)` → PG 标记 inactive
- MVP 兼容配置文件静态 Token

---

## 6. 并发与性能设计

### 6.1 200 Agent 场景瓶颈分析

| 瓶颈 | 原因 | 解决方案 |
|------|------|---------|
| Iceberg 元数据并发写 | SQLite 文件锁 | → PostgreSQL（已改） |
| Embedding CPU 密集 | 200 并发 embedding | → Ray actor 批处理（生产阶段） |
| 大向量检索 | LanceDB 单进程扫描 | → Ray 分布式查询（生产阶段） |
| MCP 单进程 | 单实例吞吐上限 | → 每类 MCP 多副本 + 负载均衡 |
| Lance 并发写 | 多进程写同一目录 | → 写操作走 Ray actor 串行化 |

### 6.2 MVP 策略

- 嵌入式引擎在 MCP 进程内运行，单机 CPU 够用
- fastembed ONNX CPU ~2ms/text
- PostgreSQL 连接池（每 MCP 实例 10 连接）
- 生产阶段引入 Ray + MCP 多副本 + Nginx 负载均衡

---

## 7. 设计原则（不可偏离）

1. **统一存储底座** — SeaweedFS 一个对象存储承载全部数据文件
2. **统一元数据** — PostgreSQL 一个数据库承载全部结构化元数据
3. **计算与引擎分离** — 引擎适配层可替换，计算可走嵌入式或 Ray
4. **Agent 直连引擎** — 经 MCP 代理，无额外 API 层

> 新增组件或 API 层时应对照这四条判断是否偏离设计。

---

## 8. 关键设计决策记录

| 决策 | 理由 | 日期 |
|------|------|------|
| PostgreSQL 替代 Gravitino + SQLite | 少一个 JVM 服务，并发安全，技术栈更简 | v3 |
| 3 MCP 拆分替代单体 | 独立部署、独立扩缩容、避免单点故障 | v3 |
| 声明式 YAML 替代代码继承 | 用户无需写代码即可扩展资产 | v3 |
| fastembed 替代 SHA256 | 真实语义检索，ONNX CPU ~2ms | v3 |
| Express 替代 Nuxt 3 | npm install 超时，Express 构建秒级 | 实施中 |
| PG 原生表替代 AGE | AGE 编译超时（>20min），原生表功能等价 | 实施中 |
| mem0 延迟 | 需 LLM 做事实抽取，基础记忆已可用 | v3 |
| Ray 延迟 | 镜像过大（~2GB），嵌入式引擎足够 MVP | 实施中 |
| experience 积淀进 memory.kind | 减少资产类型，kind 区分 general/experience/reflection | v3 |
| Steward 不降级直连 | MCP 自身高可用，各司其职 | v3 |
| Monitor 无自有 DB | 纯代理层，状态全靠 AdminMCP | v3 |
