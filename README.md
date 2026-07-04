# LakeMind — 多模智能数据湖

> Agent 原生的多模态智能数据底座。统一存储、统一元数据、计算与引擎分离，Agent 通过 MCP 直连引擎。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            开发平面                                      │
│                     LakeMindStudio (Tauri 桌面)                          │
│              资产设计器 · MCP调试台 · Skill脚手架 · CI/CD                  │
└─────────────────────────────────────────────────────────────────────────┘
                                     │ MCP Client
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          运行平面 · Agent 侧                             │
│                                                                         │
│  ┌──────────────┐     ┌──────────────────────────────────────────────┐  │
│  │  200 Agents   │     │            LakeMindSteward                    │  │
│  │  (业务 Agent)  │     │     LangGraph 巡检 + 对话管理 Agent           │  │
│  └──────┬───────┘     │     连 3 个 MCP (asset+data+admin)            │  │
│         │ asset                    │                   │ admin           │
│         ▼                          ▼                   ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │ AssetMCP    │    │  DataMCP    │    │  AdminMCP   │                  │
│  │  :8401      │    │  :8402      │    │  :8403      │                  │
│  │ 资产面      │    │  数据面     │    │  管理面     │                  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                  │
└─────────┼──────────────────┼──────────────────┼─────────────────────────┘
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            数据平面                                      │
│                        LakeMindServer                                    │
│  ┌─────────────┐  ┌──────────────────────┐  ┌─────────────┐            │
│  │  SeaweedFS   │  │    PostgreSQL 16     │  │  Dragonfly  │            │
│  │  S3 :8333    │  │    Metadata Hub      │  │  KV :6379   │            │
│  └─────────────┘  └──────────────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘

          ┌─────────────────────────────────────────────┐
          │              LakeMindMonitor (:3000)          │
          │   Express · 三面监控 · Chat(→Steward) · 极轻   │
          └─────────────────────────────────────────────┘
```

### 两层智能数据体系（数据+认知资产） ， 三面MCP for Agent 原生接口（资产面+数据面+管理面） 、 五件套核心技术系统（LakeMindServer+3*LakeMindMCP+LakeMindSteward+LakeMindMonitor+LakeMindStudio）

**两层**：
- **Data 层** — 多模态数据底座。透传，不做语义解释。数据是什么、存哪、怎么读写。
- **Asset 层** — 面向 Agent 认知模型的语义封装。声明式 YAML 定义，预置 4 类，可删可扩。

**三 MCP**（独立服务，各自可水平扩展）：

| MCP | 端口 | Scope | 面向 | 职责 |
|-----|------|-------|------|------|
| AssetMCP | 8401 | `asset` | 业务 Agent | 4 类默认资产 + 声明式自定义资产 |
| DataMCP | 8402 | `data` | Steward / 高级 Agent | Data 层全量透传 |
| AdminMCP | 8403 | `admin` | Steward | 用户/租户/Token/资产类型/健康 |

**五件套**：

| 包 | 平面 | 职责 | 状态 |
|----|------|------|------|
| `LakeMindServer/` | 数据平面 | 存储与计算底座（3 容器 + Ray 可选） | ✅ 已完成 |
| `LakeMindAssetMCP/` | 运行平面 | 资产面 MCP | ✅ 已完成 |
| `LakeMindDataMCP/` | 运行平面 | 数据面 MCP | ✅ 已完成 |
| `LakeMindAdminMCP/` | 运行平面 | 管理面 MCP | ✅ 已完成 |
| `LakeMindSteward/` | 运行平面 | 管理运维 Agent（LangGraph） | ✅ 已完成 |
| `LakeMindMonitor/` | 运行平面 | 人类仪表板 + Steward 对话窗 | 🔨 待完成 |
| `LakeMindStudio/` | 开发平面 | Tauri 桌面客户端 | ❌ 未开始 |

---

## 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 对象存储 | **SeaweedFS** | S3 兼容，存 Iceberg 数据文件 / Lance 向量 / Skill 代码 |
| 统一数据库 | **PostgreSQL 16** | Iceberg catalog + 图存储 + 用户/租户/Token + 资产定义 |
| 表格式 | **Apache Iceberg** | PyIceberg 嵌入式，PG SQL catalog |
| 向量 / 多模态 | **PyLance + LanceDB** | 共享 Lance 目录，向量检索 |
| 图 / 本体 | **PG 原生表** | graph_nodes / graph_edges + JSONB（AGE 扩展编译超时，暂用原生表） |
| 缓存 / 短期记忆 | **Dragonfly** | Redis 兼容 TTL KV |
| 即席计算 | **DuckDB** | 进程内轻量 SQL |
| Embedding | **fastembed** | ONNX + BAAI/bge-small-en-v1.5，dim=384 |
| 记忆引擎 | **mem0**（延迟） | 事实抽取 + 合并去重 + 实体图谱，需 LLM |
| 分布式计算 | **Ray**（延迟） | 批量 embedding / 重计算，镜像过大暂跳过 |
| MCP SDK | **FastMCP** | streamable_http 传输 |
| Agent 框架 | **LangGraph** | Steward 巡检工作流 |
| Monitor | **Express + 静态 HTML** | 轻量代理层，无自有 DB |

> 技术栈已锁定全开源组件（Apache 2.0 / MIT / BSD）。除非明确要求，不引入替代品。

---

## 快速开始

### 前置要求

- Docker + Docker Compose
- Python 3.12+（运行验证脚本）
- 可用内存 ≥ 4GB

### 1. 启动数据平面

```bash
cd LakeMindServer
docker compose --env-file .env up -d
```

启动 3 个容器：

| 容器 | 端口 | 用途 |
|------|------|------|
| lakemind-seaweedfs | 8333 (S3) | 对象存储 |
| lakemind-postgres | 5432 | 统一 Metadata Hub |
| lakemind-dragonfly | 6379 | TTL KV 缓存 |

> Ray 集群（ray-head + 2 worker）通过 `--profile ray` 启动，MVP 默认不启动。

### 2. 启动三个 MCP

```bash
cd LakeMindAssetMCP && docker compose up -d --build
cd LakeMindDataMCP  && docker compose up -d --build
cd LakeMindAdminMCP && docker compose up -d --build
```

| 容器 | 端口 | 工具数 |
|------|------|--------|
| lakemind-asset-mcp | 8401 | 11 tools, 7 resources |
| lakemind-data-mcp | 8402 | 13 tools |
| lakemind-admin-mcp | 8403 | 15 tools |

### 3. 启动 Steward

```bash
cd LakeMindSteward && docker compose up -d --build
```

| 容器 | 端口 | 用途 |
|------|------|------|
| lakemind-steward | 8500 | LangGraph 巡检 + 对话管理 |

### 4. 启动 Monitor（待完成）

```bash
cd LakeMindMonitor && docker compose up -d --build
```

### 5. 验证

```bash
# 基础集成验证
python LakeMindServer/scripts/verify_pg_catalog.py     # PyIceberg + PG catalog (8/8)

# AssetMCP 验证
python LakeMindAssetMCP/scripts/verify_asset_mcp.py     # 11 tools + 7 resources (8/8)

# 三 MCP 联合验证
python scripts/verify_three_mcp.py                      # 22/22 全通过
```

---

## 包结构详解

### LakeMindServer — 数据平面

```
LakeMindServer/
├── docker-compose.yml          # 3 服务 + Ray(profile)
├── .env                        # 环境变量
├── docker/postgres-age/
│   ├── Dockerfile              # postgres:16 基础镜像
│   └── init/
│       └── 01-age.sql          # 图表 + 平台元数据表初始化
├── config/seaweedfs/           # SeaweedFS S3 配置
├── data/                       # 持久化数据 (bind mount)
│   ├── seaweedfs/
│   ├── postgres/
│   ├── dragonfly/
│   └── lance/                  # 共享 Lance 向量目录
└── scripts/
    ├── verify_pg_catalog.py    # PyIceberg + PG 验证
    └── verify_scenario.py      # 端到端场景验证
```

**PostgreSQL 表结构**（由 `01-age.sql` 初始化）：

| 表 | 用途 |
|----|------|
| `iceberg_tables` | PyIceberg SQL catalog（自动创建） |
| `iceberg_namespace_properties` | PyIceberg 命名空间属性（自动创建） |
| `graph_nodes` | 图节点（id, label, properties JSONB） |
| `graph_edges` | 图边（src, dst, rel_type, properties JSONB） |
| `tenants` | 租户 |
| `users` | 用户 |
| `tokens` | Token 管理记录 |
| `asset_types` | 资产类型定义 |

### LakeMindAssetMCP — 资产面 MCP

```
LakeMindAssetMCP/
├── src/lakemind_asset_mcp/
│   ├── server.py               # FastMCP 服务入口
│   ├── assets/
│   │   ├── native/             # 4 个默认资产 YAML
│   │   │   ├── knowledge.yaml
│   │   │   ├── skill.yaml
│   │   │   ├── memory.yaml
│   │   │   └── ontology.yaml
│   │   └── registry.py         # 资产注册表（从 PG 热加载）
│   ├── engines/
│   │   ├── embedding.py        # fastembed 懒加载
│   │   ├── iceberg.py          # PyIceberg 适配
│   │   ├── lancedb.py          # LanceDB 向量检索
│   │   ├── graph.py            # PG 图客户端
│   │   ├── dragonfly.py        # TTL KV
│   │   ├── s3.py               # S3 读写
│   │   └── duckdb.py           # 即席 SQL
│   ├── tools/                  # 11 个工具
│   │   ├── knowledge.py        # search/ingest/register
│   │   ├── skill.py            # search/execute/register
│   │   ├── memory.py           # remember/recall/forget
│   │   └── ontology.py         # query/update
│   ├── resources/              # 7 个资源
│   └── security/               # Token 认证 + 租户隔离
└── config/config.yaml
```

**11 个工具**：

| 工具 | 资产 | 说明 |
|------|------|------|
| `search_knowledge` | Knowledge | 向量 top-k 语义检索 |
| `ingest_knowledge` | Knowledge | embedding + 写向量表 |
| `register_knowledge` | Knowledge | 创建知识库实例 |
| `search_skill` | Skills | 语义检索技能 |
| `register_skill` | Skills | 注册技能 |
| `execute_skill` | Skills | 沙箱执行技能 |
| `remember` | Memory | 写入记忆（短期/长期） |
| `recall` | Memory | 语义召回记忆 |
| `forget` | Memory | 删除记忆 |
| `query_ontology` | Ontology | 查询概念/关系 |
| `update_ontology` | Ontology | 增补三元组 |

**7 个资源**：`lake://capabilities`, `lake://workspace`, `lake://system/health`, `lake://knowledge`, `lake://skills`, `lake://memory`, `lake://ontology`

**声明式资产定义示例**：

```yaml
type: knowledge
description: "知识库，向量检索与多模态 RAG"
resource_root: "lake://knowledge"
capabilities: [search, ingest]
storage:
  vector:
    engine: lancedb
    schema:
      doc_uri: string
      title: string
      content: string
      vector: float32[384]
operations:
  search:
    engine: vector_topk
    params: [kb, query, top_k=5, filter?]
  ingest:
    engine: embed_and_write
    params: [kb, documents]
```

### LakeMindDataMCP — 数据面 MCP

13 个透明透传工具：

| 工具 | 引擎 | 说明 |
|------|------|------|
| `data_query` | Iceberg | 扫描表 |
| `data_write` | Iceberg | 追加/覆写 |
| `data_sql` | DuckDB | 即席 SQL |
| `data_list_tables` | Iceberg | 表列表 |
| `data_describe` | Iceberg | schema + 行数 |
| `data_create_table` | Iceberg | 建表 |
| `lance_query` | LanceDB | 向量检索 |
| `s3_get` / `s3_put` | S3 | 文件读写 |
| `kv_get` / `kv_set` | Dragonfly | KV 读写 |
| `graph_query` / `graph_update` | PG Graph | 图查询/更新 |

### LakeMindAdminMCP — 管理面 MCP

15 个平台管理工具：

| 类别 | 工具 |
|------|------|
| 用户 | `create_user`, `update_user`, `delete_user`, `list_users` |
| 租户 | `create_tenant`, `update_tenant`, `delete_tenant`, `list_tenants` |
| Token | `issue_token`, `revoke_token`, `list_tokens` |
| 资产类型 | `register_asset_type`, `unregister_asset_type` |
| 平台 | `get_platform_health`, `get_node_status` |

### LakeMindSteward — 管理运维 Agent

```
LakeMindSteward/
├── src/lakemind_steward/
│   ├── agent.py                # LangGraph 状态图
│   │                           # 巡检: check_health → analyze → report
│   │                           # 对话: 意图识别 → 路由到 3 MCP
│   └── server.py               # FastAPI (chat + inspect 端点)
└── config/config.yaml          # 连接 3 个 MCP 的 steward token
```

- **巡检工作流**：LangGraph 状态图，`check_health → analyze → report`
- **对话管理**：自然语言 → 意图识别 → 路由到 AssetMCP / DataMCP / AdminMCP
- 端点：`POST /chat`（对话）、`POST /inspect`（巡检）、`GET /health`

### LakeMindMonitor — 人类仪表板（待完成）

- Express + 静态 HTML，极轻
- 三面监控：Dashboard / Asset / Data / Admin
- Chat 窗对接 Steward
- 无自有 DB，无自有用户系统，纯代理层

### LakeMindStudio — 桌面客户端（未开始）

- Tauri 2.0 + Vue 3 + Vite
- 资产设计器（YAML 编辑 + 实时预览 + 一键注册）
- MCP 调试台（在线调用 3 个 MCP 工具/资源）
- Skill 脚手架（模板生成 + 本地沙箱 + 一键上传）
- CI/CD 集成（触发 webhook + 查看状态）

---

## 数据域 → 引擎映射

| 数据域 | 引擎 | MCP 资产 | 资源 URI |
|--------|------|---------|----------|
| 结构化数据 | Iceberg + PG catalog | `lake://data` | DataMCP 透传 |
| 知识 / 多模态 RAG | Lance + LanceDB | `lake://knowledge` | AssetMCP |
| 短期/工作记忆 | Dragonfly (TTL KV) | `lake://memory` | AssetMCP |
| 长期/语义记忆 | Lance 向量 + Iceberg 小表 | `lake://memory` | AssetMCP |
| Skills | S3 + Iceberg + LanceDB | `lake://skills` | AssetMCP |
| 本体 / 图 | PG graph_nodes/edges | `lake://ontology` | AssetMCP |

> 长期记忆采用 Lance 向量 + Iceberg 小表双表设计，通过 `lance_uri` 字段关联。

---

## Token 体系

Token 由 AdminMCP 签发，存 PostgreSQL。MVP 兼容配置文件静态 Token。

| Token | Agent | Tenant | Scopes | 接入 |
|-------|-------|--------|--------|------|
| `test-business-token` | agent-business-01 | retail | `asset` | AssetMCP |
| `test-steward-token` | steward | platform | `asset, data, admin` | 3 MCP |
| `test-monitor-token` | monitor | platform | `asset` | AssetMCP (只读) |

---

## 租户隔离

| 层 | 隔离方式 |
|----|----------|
| S3 | key 前缀 `{tenant_id}/` |
| Iceberg | namespace `{tenant_id}_{domain}` |
| LanceDB | 每租户独立 database |
| Dragonfly | key 前缀 `{tenant_id}:` |
| PostgreSQL | 行级 `tenant_id` 列（应用层过滤） |

---

## 设计原则

1. **统一存储底座** — SeaweedFS 一个对象存储承载全部数据文件
2. **统一元数据** — PostgreSQL 一个数据库承载全部结构化元数据
3. **计算与引擎分离** — 引擎适配层可替换，计算可走嵌入式或 Ray
4. **Agent 直连引擎** — 经 MCP 代理，无额外 API 层

---

## 验证状态

| 验证 | 脚本 | 结果 |
|------|------|------|
| PyIceberg + PG catalog | `verify_pg_catalog.py` | ✅ 8/8 PASS |
| AssetMCP | `verify_asset_mcp.py` | ✅ 8/8 PASS |
| 三 MCP 联合 | `verify_three_mcp.py` | ✅ 22/22 PASS |
| Steward 巡检 | 手动 | ✅ 正确识别异常 |
| Monitor | — | 🔨 待验证 |
| 端到端 200 Agent | — | ❌ 未开始 |

---

## 实验环境运行容器

```
lakemind-postgres      :5432   Up   Metadata Hub
lakemind-seaweedfs     :8333   Up   S3 对象存储
lakemind-dragonfly     :6379   Up   TTL KV
lakemind-asset-mcp     :8401   Up   资产面 MCP
lakemind-data-mcp      :8402   Up   数据面 MCP
lakemind-admin-mcp     :8403   Up   管理面 MCP
lakemind-steward       :8500   Up   管理运维 Agent
```

---

## 延迟项

| 项 | 原因 | 影响 |
|----|------|------|
| Ray 集群 | 镜像过大（~2GB+），拉取超时 | 嵌入式引擎足够 MVP 单机 |
| AGE 图扩展 | 编译超时（>20min） | PG 原生表替代，功能等价 |
| mem0 记忆引擎 | 需 LLM 做事实抽取 | 基础 remember/recall/forget 已可用 |
| LakeMindStudio | 未开始 | P2 优先级 |

---

## 文档

| 文档 | 说明 |
|------|------|
| `AGENTS.md` | 开发规范与包结构约定 |

---

## License

全开源组件（Apache 2.0 / MIT / BSD）。
