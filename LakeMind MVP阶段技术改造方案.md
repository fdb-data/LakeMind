# LakeMind MVP 阶段技术改造方案（v3）

> 编号 `LM-REFORM-3`。整合用户全部改造意见（含 mem0 集成）。批准后开发。

---

## 1. 总体架构

### 1.1 总体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            开发平面                                      │
│                     LakeMindStudio (Tauri 桌面)                          │
│              资产设计器 · MCP调试台 · Skill脚手架 · CI/CD                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │ MCP Client (直连3个MCP)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          运行平面 · Agent 侧                             │
│                                                                         │
│  ┌──────────────┐     ┌──────────────────────────────────────────────┐  │
│  │  200 Agents   │     │            LakeMindSteward                    │  │
│  │  (业务 Agent)  │     │     LangGraph 巡检 + 对话管理 Agent           │  │
│  └──────┬───────┘     │     连 3 个 MCP (asset+data+admin)            │  │
│         │              └──────────┬───────────────────┬──────────────┘  │
│         │ asset                    │                   │ admin           │
│         ▼                          ▼                   ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │ AssetMCP    │    │  DataMCP    │    │  AdminMCP   │                  │
│  │  :8401 ×N   │    │  :8402 ×N   │    │  :8403      │                  │
│  │ 资产面      │    │  数据面     │    │  管理面     │                  │
│  │ knowledge   │    │  Iceberg    │    │  用户/租户  │                  │
│  │ skills      │    │  Lance      │    │  Token     │                  │
│  │ memory(mem0)│    │  S3         │    │  资产类型   │                  │
│  │ ontology    │    │  AGE        │    │  健康/配置  │                  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                  │
│         │                  │                  │                         │
└─────────┼──────────────────┼──────────────────┼─────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            数据平面                                      │
│                        LakeMindServer                                    │
│                                                                         │
│  ┌─────────────┐  ┌──────────────────────────┐  ┌─────────────┐        │
│  │  SeaweedFS   │  │    PostgreSQL 16 + AGE    │  │  Dragonfly  │        │
│  │  S3 对象存储  │  │    Metadata Hub           │  │  TTL KV     │        │
│  │  :8333       │  │  · Iceberg Catalog        │  │  :6379      │        │
│  │              │  │  · AGE 图 (本体/graphRAG) │  │             │        │
│  │  Iceberg     │  │  · 用户/租户/Token        │  │  短期记忆    │        │
│  │  数据文件     │  │  · 资产定义/元信息        │  │             │        │
│  │  Lance 向量  │  │  · mem0 记忆元信息        │  │             │        │
│  │  Skill 代码  │  │  · Fileset 元数据         │  │             │        │
│  └─────────────┘  └──────────────────────────┘  └─────────────┘        │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │                    Ray 集群                               │          │
│  │  ray-head:8265  +  ray-worker ×2                         │          │
│  │  批量Embedding · 分布式向量检索 · 重型SQL · mem0事实抽取    │          │
│  └──────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘

          ┌─────────────────────────────────────────────┐
          │              LakeMindMonitor                 │
          │  Nuxt 3 (Node) · 三面监控 · Chat(→Steward)    │
          │  无自有DB · 无自有用户系统 · 极轻               │
          └─────────────────────────────────────────────┘
```

### 1.2 两层 + 三 MCP + 五件套

**两层**：
- **Data 层**：多模态智能数据底座。把数据是什么、存在哪、怎么读写定义清楚。透传，不做语义解释。
- **Asset 层**：面向 Agent 认知模型的语义封装。声明式 YAML 定义，预置 4 类，用户可删可扩可自定义。

**三 MCP**（独立服务，各自可水平扩展多节点，避免单点故障）：
- **LakeMindAssetMCP**：资产面。4 类默认资产操作 + 声明式自定义资产。业务 Agent 接此面。
- **LakeMindDataMCP**：数据面。Data 层全量透传。Steward / 高级 Agent 接此面。
- **LakeMindAdminMCP**：管理面。平台管控（用户、租户、Token、健康、资产类型注册）。Steward 接此面。

### 1.3 五件套

| 包 | 平面 | 职责 | MVP 状态 |
|----|------|------|----------|
| LakeMindServer | 数据平面 | 存储与计算底座（5 容器） | 改造 |
| LakeMindAssetMCP | 运行平面 | 资产面 MCP | 改造（从原 MCP 拆分） |
| LakeMindDataMCP | 运行平面 | 数据面 MCP | 新建 |
| LakeMindAdminMCP | 运行平面 | 管理面 MCP | 新建 |
| LakeMindSteward | 运行平面 | 管理运维 Agent | 新建 |
| LakeMindMonitor | 运行平面 | 人类仪表板（三面监控） | 改造 |
| LakeMindStudio | 开发平面 | 桌面客户端 | 新建 |

> 原 `LakeMindMCP` 拆分为 3 个独立 MCP 包，各自独立部署。

---

## 2. Data 层设计

### 2.1 统一数据库：PostgreSQL 16 + Apache AGE

**一个数据库技术栈，一个 PostgreSQL 实例**，承载全部结构化元数据：

| 用途 | 机制 | 说明 |
|------|------|------|
| Iceberg Catalog | PyIceberg SQL catalog（`postgresql+psycopg://`） | 替代 SQLite，解决并发写入 |
| 图存储 | Apache AGE（PostgreSQL 图扩展，openCypher） | 本体、graphRAG 实体关系图、mem0 实体图谱 |
| 用户 / 租户 | 普通 PG 表 | 平台自身用户管理，不另建库 |
| Token 管理 | PG 表 | Token 签发 / 吊销记录 |
| 资产定义 | PG 表 | 声明式资产 YAML 持久化 |
| 资产元信息 | PG 表 | 各资产实例的元数据小表 |
| Fileset 元数据 | PG 表 | S3 路径约定 + 元信息（替代 Gravitino Fileset catalog） |
| mem0 记忆元信息 | PG 表 | memory_id / agent_id / facts / timestamps |

```yaml
# LakeMindServer/docker-compose.yml
  postgres:
    image: postgres:16
    container_name: lakemind-postgres
    environment:
      POSTGRES_DB: lakemind
      POSTGRES_USER: lakemind
      POSTGRES_PASSWORD: ${PG_PASSWORD:-lakemind_pass}
    command: >
      postgres
      -c shared_preload_libraries=age
    ports:
      - "${PG_PORT:-5432}:5432"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    networks: [lakemind]
    restart: unless-stopped
```

> AGE 扩展需在镜像中预装（自定义 Dockerfile 基于 postgres:16 加 AGE）。MVP 阶段可先用纯 PG，AGE 作为 init 脚本按需 `CREATE EXTENSION age`。

### 2.2 移除 Gravitino

**现状**：Gravitino（JVM，H2）提供 Iceberg + Fileset 统一编目 REST API。

**改造**：移除 Gravitino。理由：
- PostgreSQL 直接作为 PyIceberg SQL catalog，REST 编目不再需要。
- Fileset 管理用 S3 路径约定 + PG 元信息表替代。
- 少一个 JVM 服务，启动更快，资源更省，技术栈更简。
- 生产阶段如需统一 Fileset 治理可重新引入。

### 2.3 引擎与存储映射

| 数据形态 | 引擎 | 物理存储 | 用途 |
|----------|------|----------|------|
| 结构化表 | Apache Iceberg | S3 数据文件 + PG catalog | 数据集、元信息小表 |
| 向量 / 多模态 | PyLance + LanceDB | S3 数据文件 + 共享 Lance 目录 | 知识库向量、语义检索 |
| 图 / 本体 | Apache AGE | PostgreSQL | 概念体系、实体关系、graphRAG |
| 文件 | S3 原生 | SeaweedFS | Skill 代码、文档原文、任意二进制 |
| 短期 KV | Dragonfly | 内存 (TTL) | 工作记忆、会话缓存 |
| 分布式计算 | Ray | ray-head + ray-worker | 批量 embedding、重计算、并行扫描 |
| 即席计算 | DuckDB | 进程内 | 跨表 SQL、Parquet 直读（轻量查询走嵌入式，重量级走 Ray） |

### 2.4 Ray 纳入（MVP 即引入）

```yaml
  ray-head:
    image: rayproject/ray:latest
    container_name: lakemind-ray-head
    command: ray start --head --port=6379 --dashboard-port=8265
    ports:
      - "8265:8265"   # Ray Dashboard
      - "6379:6379"   # Ray GCS
    volumes:
      - ./data/lance:/data/lance    # 共享 Lance 目录
    networks: [lakemind]
    restart: unless-stopped

  ray-worker:
    image: rayproject/ray:latest
    command: ray start --address=lakemind-ray-head:6379
    volumes:
      - ./data/lance:/data/lance
    networks: [lakemind]
    deploy:
      replicas: 2
    restart: unless-stopped
```

**Ray 用途**：
- 批量 Embedding（200 Agent 并发时，embedding 是 CPU 密集，走 Ray actor 批处理）
- 大规模向量检索（LanceDB 分布式查询）
- 重型 Iceberg 扫描 / DuckDB 跨表 JOIN
- mem0 事实抽取 LLM 批处理（smart 模式 remember 时调 LLM）
- MCP 进程内嵌入式引擎处理轻量请求，重请求提交 Ray

### 2.5 LakeMindServer 容器清单（改造后）

| 容器 | 镜像 | 端口 | 状态 |
|------|------|------|------|
| seaweedfs | chrislusf/seaweedfs | 8333(S3) | 保留 |
| **postgres** | **postgres:16 + AGE** | **5432** | **新增（替代 SQLite + Gravitino H2）** |
| dragonfly | dragonflydb/dragonfly | 6379 | 保留 |
| **ray-head** | **rayproject/ray** | **8265** | **新增** |
| **ray-worker** | **rayproject/ray** | — | **新增（×2）** |
| ~~gravitino~~ | — | — | **移除** |

### 2.6 Data 层透传接口（DataMCP）

| 工具 | 引擎 | 说明 |
|------|------|------|
| `data_query(table, columns?, filter?, limit?)` | Iceberg | 扫描表 |
| `data_write(table, rows, mode)` | Iceberg | 追加 / 覆写 |
| `data_sql(sql)` | DuckDB / Ray | 即席 SQL（轻量走 DuckDB，重量级走 Ray） |
| `data_list_tables(namespace?)` | Iceberg | 列表 |
| `data_describe(table)` | Iceberg | schema + 行数 + location |
| `data_create_table(name, schema, partition?)` | Iceberg | 建表 |
| `lance_query(table, query, top_k, filter?)` | LanceDB / Ray | 向量检索 |
| `lance_write(table, rows)` | LanceDB | 写向量表 |
| `s3_get(uri)` / `s3_put(uri, body)` | S3 | 文件读写 |
| `kv_get(key)` / `kv_set(key, value, ttl?)` / `kv_del(key)` | Dragonfly | KV 透传 |
| `graph_query(cypher)` | AGE | openCypher 图查询 |
| `graph_update(cypher)` | AGE | 图更新 |

### 2.7 租户隔离

| 层 | 隔离方式 |
|----|----------|
| S3 | key 前缀 `{tenant_id}/` |
| Iceberg | namespace `{tenant_id}_{domain}` |
| LanceDB | 每租户独立 database |
| Dragonfly | key 前缀 `{tenant_id}:` |
| PostgreSQL | 行级 `tenant_id` 列 + RLS（MVP 用应用层过滤） |
| AGE 图 | 每租户独立 graph name |

---

## 3. Asset 层设计

### 3.1 声明式资产定义（非代码继承）

自定义资产**不写代码**，用 YAML 声明：schema 是什么、什么格式存、什么引擎算。

```yaml
# 资产定义示例：自定义 RAG 资产
type: my_rag
description: "产品文档 RAG 知识库"
resource_root: "lake://my_rag"
capabilities: [search, ingest]

storage:
  vector:
    engine: lancedb
    schema:
      doc_id: string
      title: string
      content: string
      vector: float32[512]
  metadata:
    engine: iceberg
    schema:
      kb_id: string
      name: string
      doc_count: int64
      created_at: timestamp

operations:
  search:
    engine: vector_topk        # 预置引擎模式：向量 top-k 检索
    params: [query, top_k=5, filter?]
  ingest:
    engine: embed_and_write    # 预置引擎模式：embedding + 写向量表
    params: [documents]

embedding: default             # 用平台默认 embedding
```

**预置引擎模式**（MVP 内置，覆盖常见场景）：

| 模式 | 说明 |
|------|------|
| `vector_topk` | 向量 top-k 检索（LanceDB） |
| `embed_and_write` | embedding + 写向量表 |
| `keyword_search` | 关键词全文检索 |
| `graph_query` | 图查询（AGE openCypher） |
| `graph_update` | 图更新（AGE openCypher） |
| `kv_ttl` | TTL KV 读写（Dragonfly） |
| `table_query` | Iceberg 表查询 |
| `table_append` | Iceberg 表追加 |
| `mem0` | 记忆智能引擎（事实抽取 + 合并去重 + 实体图谱，复用 LanceDB/AGE/PG） |

用户只需选预置模式 + 填 schema，MCP 自动生成资源 + 工具。无需预置模式时，可指定 `engine: custom` + `handler: module.path` 走自定义代码（高级逃生通道，MVP 不强制）。

### 3.2 默认 4 类资产

#### Knowledge（知识 / 多模态 RAG）

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
  metadata:
    engine: iceberg
    schema:
      kb_id: string
      name: string
      description: string
      doc_count: int64
      created_at: timestamp
operations:
  search:
    engine: vector_topk
    params: [kb, query, top_k=5, filter?]
  ingest:
    engine: embed_and_write
    params: [kb, documents]
```

- 资源：`lake://knowledge` → 列表；`lake://knowledge/{id}` → 详情
- 工具：`search_knowledge(kb, query, top_k=5, filter?)`
- 工具：`ingest_knowledge(kb, documents)`

#### Skills（技能）

```yaml
type: skill
description: "可语义检索、可执行的技能库"
resource_root: "lake://skills"
capabilities: [search, execute]
storage:
  code:
    engine: s3
  metadata:
    engine: iceberg
    schema:
      skill_id: string
      name: string
      description: string
      version: string
      owner: string
      s3_uri: string
  vector:
    engine: lancedb
    schema:
      skill_id: string
      name: string
      description: string
      vector: float32[384]
operations:
  search:
    engine: vector_topk
    params: [query]
  execute:
    engine: custom
    handler: native.skill.execute
    params: [name, inputs]
```

- 资源：`lake://skills` → 列表；`lake://skills/{id}` → 元信息 + 代码
- 工具：`search_skill(query)`
- 工具：`execute_skill(name, inputs)` — 沙箱 subprocess 执行

#### Memory（记忆 · mem0 引擎）

> **mem0 是记忆智能层，不是存储层。** 它复用 LakeMind 已有的 LanceDB（向量）+ AGE（图）+ Dragonfly（短期）+ PG（元信息），在其上加事实抽取、合并去重、实体图谱。不引入任何新存储。

```yaml
type: memory
description: "Agent 记忆：短期工作记忆 + 长期语义记忆 + 实体图谱"
resource_root: "lake://memory"
capabilities: [remember, recall, forget]
storage:
  short_term:
    engine: dragonfly          # TTL KV，工作记忆
  long_term:
    engine: lancedb            # 向量长期记忆
    schema:
      content: string
      context: string
      kind: string             # general | experience | reflection
      vector: float32[384]
      created_at: timestamp
  entity_graph:
    engine: age                # mem0 实体图谱（graphRAG for memory）
  metadata:
    engine: postgresql         # mem0 记忆元信息存 PG
    schema:
      mem_id: string
      agent_id: string
      kind: string
      facts: json              # mem0 抽取的结构化事实
      lance_uri: string
      created_at: timestamp
operations:
  remember:
    engine: mem0               # ← 声明式，一行指定 mem0 引擎
    params: [content, context?, ttl?, kind?, mode?]
  recall:
    engine: mem0
    params: [query, limit=5, kind?]
  forget:
    engine: mem0
    params: [query?]

mem0:
  fact_extraction: true        # 事实抽取（LLM 提取结构化事实，非存原文）
  consolidation: true         # 合并去重（向量相似度判断，自动更新/合并/去重）
  entity_graph: true           # 实体图谱（抽取实体关系存 AGE，支持 graphRAG 召回）
  llm:                         # 事实抽取 LLM
    provider: ray_batch        # 走 Ray 批处理（同 embedding 模式）
    model: "qwen2.5-7b"        # 可配本地 vLLM 或外部 API
  mode: auto                   # auto: 有ttl→simple(不调LLM), 无ttl→smart(调LLM)
```

**mem0 三种模式**：

| 模式 | LLM 调用 | 延迟 | 适用 |
|------|---------|------|------|
| `simple` | 不调 LLM，直接存原文+向量 | ~5ms | 高频工作记忆 |
| `smart` | 调 LLM 抽事实 + 合并去重 + 实体图谱 | +200ms（走 Ray 批处理） | 重要长期记忆 |
| `auto`（默认） | 有 ttl → simple，无 ttl → smart | 自适应 | 推荐 |

- 资源：`lake://memory` → 当前 Agent 记忆概况
- 工具：`remember(content, context?, ttl?, kind?, mode?)` — `kind` 支持 `general`/`experience`/`reflection`（原 experience 资产积淀于此）
- 工具：`recall(query, limit=5, kind?)` — 语义召回 + 实体图谱遍历，可按 kind 过滤
- 工具：`forget(query?)`

**mem0 集成适配**：

| 适配项 | 工作量 | 说明 |
|--------|--------|------|
| LanceDB 适配器 | ~100 行 | mem0 `VectorStoreBase` 子类 |
| AGE 适配器 | ~100 行 | mem0 `GraphStoreBase` 子类（mem0 原生支持 Neo4j，AGE 需适配） |
| PG 元信息 | ~50 行 | mem0 记忆元信息存 PG Metadata Hub |
| remember/recall/forget 映射 | ~30 行 | mem0.add / mem0.search / mem0.delete |
| Ray LLM 批处理 | 复用 | 与 embedding 共用 Ray actor 模式 |

#### Ontology（本体 / 领域模型）

```yaml
type: ontology
description: "领域本体，概念体系与关系（图存储）"
resource_root: "lake://ontology"
capabilities: [query, update]
storage:
  graph:
    engine: age              # Apache AGE
    schema:
      concepts: [id, name, description, attributes]
      relations: [src_id, rel_type, dst_id, properties]
operations:
  query:
    engine: graph_query
    params: [concept, relation?]
  update:
    engine: graph_update
    params: [concept, relation, target]
```

- 资源：`lake://ontology` → 本体列表；`lake://ontology/{id}` → 概念树
- 工具：`query_ontology(concept, relation?)` — 查概念 / 关系
- 工具：`update_ontology(concept, relation, target)` — 增补三元组

> Ontology 从原"预留占位"升级为**实装默认资产**，底层用 AGE 图存储，为 graphRAG 预留。

### 3.3 资产扩展机制

```
assets/
├── native/              # 4 个默认资产实现（内置引擎模式）
│   ├── knowledge.yaml
│   ├── skill.yaml
│   ├── memory.yaml
│   └── ontology.yaml
├── extension/           # 用户自定义资产 YAML（自动扫描）
│   └── .gitkeep
└── engine_patterns/     # 预置引擎模式实现
    ├── vector_topk.py
    ├── embed_and_write.py
    ├── graph_query.py
    ├── graph_update.py
    ├── mem0.py            # 记忆智能引擎
    └── ...
```

- **添加资产类型**：AdminMCP `register_asset_type(yaml)` → 存 PG → AssetMCP 热加载
- **删除资产类型**：AdminMCP `unregister_asset_type(type)` → 从 PG 移除 → AssetMCP 下线对应资源/工具。仅删定义，不删底层数据。
- **自定义资产**：写 YAML，指定 schema + storage + operations（选预置引擎模式），丢 `extension/` 或通过 AdminMCP 注册。无需写代码。

### 3.4 资产注册表

```python
@dataclass
class Registry:
    types: dict[str, AssetDefinition]   # AssetDefinition = YAML 解析结果

    def register(self, defn: AssetDefinition) -> None: ...
    def unregister(self, type: str) -> None: ...
    def capability_graph(self) -> dict: ...
    def reload(self) -> None:             # 从 PG 重新加载全部定义
        ...
```

`lake://capabilities` 资源实时反映注册表。

---

## 4. 三 MCP 接口设计

### 4.1 LakeMindAssetMCP（资产面 · :8401）

面向业务 Agent，操作资产语义。资产实例的创建也在此面（register_knowledge 等）。

| 类别 | 资源 | 工具 |
|------|------|------|
| Knowledge | `lake://knowledge`, `lake://knowledge/{id}` | `search_knowledge`, `ingest_knowledge`, `register_knowledge` |
| Skills | `lake://skills`, `lake://skills/{id}` | `search_skill`, `execute_skill`, `register_skill` |
| Memory | `lake://memory` | `remember`, `recall`, `forget` |
| Ontology | `lake://ontology`, `lake://ontology/{id}` | `query_ontology`, `update_ontology` |
| 系统只读 | `lake://capabilities`, `lake://workspace` | — |

- 认证：Bearer Token，Token 携 `tenant_id` + `asset` scope。
- 租户隔离自动生效。
- 轻量请求走进程内嵌入式引擎，重请求提交 Ray。

### 4.2 LakeMindDataMCP（数据面 · :8402）

全量透传，面向 Steward / 高级 Agent。见 §2.6 全部工具。

- 认证：Bearer Token，`data` scope。
- 不做资产语义，不关心上层。拿到表名 / 路径就读写。

### 4.3 LakeMindAdminMCP（管理面 · :8403）

**平台管控**，不是资产 / 数据操作。面向 Steward。

| 工具 | 说明 |
|------|------|
| `create_user(username, tenant_id, role)` | 创建用户 |
| `update_user(user_id, username?, role?, status?)` | 更新用户（改名/改角色/启用禁用） |
| `delete_user(user_id)` | 删除用户（软删除，保留审计记录） |
| `list_users(tenant_id?)` | 用户列表 |
| `create_tenant(tenant_id, name)` | 创建租户 |
| `update_tenant(tenant_id, name?, status?)` | 更新租户 |
| `delete_tenant(tenant_id)` | 删除租户（软删除，关联用户一并禁用） |
| `list_tenants()` | 租户列表 |
| `issue_token(agent_id, tenant_id, scopes)` | 签发 Token |
| `revoke_token(token)` | 吊销 Token |
| `list_tokens(tenant_id?, agent_id?)` | Token 列表 |
| `register_asset_type(yaml)` | 注册新资产类型（声明式 YAML） |
| `unregister_asset_type(type)` | 移除资产类型 |
| `get_platform_health()` | 全平台健康（5 容器 + 3 MCP + Ray） |
| `get_node_status()` | 各服务节点状态 |
| `get_config()` / `update_config(key, value)` | 平台配置管理 |

- 认证：Bearer Token，`admin` scope。
- 用户 / 租户 / Token 存 PostgreSQL，平台自身管理，不另建库。
- 资产实例操作（register_knowledge 等）在 AssetMCP，资产类型注册在 AdminMCP。

### 4.4 Token 体系

Token 由 AdminMCP 签发，存 PostgreSQL。MVP 阶段也支持配置文件静态 Token。

```yaml
# 典型 Token 分配
tokens:
  - token: "test-business-token"
    agent_id: "agent-business-01"
    tenant_id: "retail"
    scopes: ["asset"]           # 只接 AssetMCP
    mcp_endpoints: ["asset"]
  - token: "test-steward-token"
    agent_id: "steward"
    tenant_id: "platform"
    scopes: ["asset", "data", "admin"]
    mcp_endpoints: ["asset", "data", "admin"]
  - token: "test-monitor-token"
    agent_id: "monitor"
    tenant_id: "platform"
    scopes: ["asset"]           # 只读资产面
    mcp_endpoints: ["asset"]
```

---

## 5. 并发与性能（200 Agent 场景）

### 5.1 问题分析

200 个 Agent 并发 → 200 条 MCP 连接。嵌入式引擎在 MCP 进程内运行，瓶颈点：

| 瓶颈 | 原因 | 解决 |
|------|------|------|
| Iceberg 元数据并发写 | SQLite 文件锁 | → PostgreSQL（已改） |
| Embedding CPU 密集 | 200 并发 embedding 请求 | → Ray actor 批处理 |
| 大向量检索 | LanceDB 单进程扫描 | → Ray 分布式查询 |
| MCP 单进程 | 单实例吞吐上限 | → 每类 MCP 多副本 + 负载均衡 |
| Lance 并发写 | 多进程写同一 Lance 目录 | → 写操作走 Ray actor 串行化 |

### 5.2 部署拓扑

```
                     ┌─ AssetMCP #1 ─┐
200 Agents ──LB────┼─ AssetMCP #2 ─┼──→ Ray (embedding, vector, mem0 LLM)
                     └─ AssetMCP #3 ─┘
                     
Steward ──── DataMCP #1/#2 ────→ Ray (heavy SQL, scan)
Steward ──── AdminMCP ────────→ PostgreSQL
```

- 每类 MCP 2-3 副本（docker-compose `replicas`），前置 Nginx / Traefik 负载均衡。
- 轻量请求（单条 search / recall）走进程内嵌入式引擎，<10ms。
- 重请求（批量 ingest / 大扫描 / 批量 embedding）提交 Ray，异步返回。
- PostgreSQL 连接池（每 MCP 实例 10 连接）。

### 5.3 Embedding 选型

**现状**：SHA256 伪向量，无语义，仅确定性哈希。不适合真实语义检索。

**改造**：

| 方案 | 说明 | 性能 | 依赖 |
|------|------|------|------|
| **fastembed（推荐 MVP）** | ONNX Runtime + BAAI/bge-small-en-v1.5（130MB） | CPU ~2ms/text，批量 ~0.5ms/text | `fastembed`（无 torch） |
| Ray embedding actor | fastembed 部署为 Ray actor，批处理 200 并发 | 分布式，线性扩展 | Ray + fastembed |
| 外部服务 | TEI / vLLM / OpenAI 兼容 | GPU，最快 | 外部依赖 |

**MVP 方案**：AssetMCP 内置 fastembed（单机 CPU 够用）。配置 `embedding.batch_threshold=10`，超过 10 条自动提交 Ray actor 批处理。`provider` 配置可切 `external`。

```yaml
embedding:
  provider: fastembed          # fastembed | external
  model: "BAAI/bge-small-en-v1.5"
  dim: 384
  batch_threshold: 10          # 超过此数走 Ray
  # external:
  base_url: ""
  api_key: ""
```

---

## 6. 五件套技术选型与设计要点

### 6.1 LakeMindServer（数据平面）

**架构图**：

```
┌─────────────────────────────────────────────────────────────┐
│                    LakeMindServer                            │
│                                                             │
│  ┌──────────────┐   ┌────────────────────┐   ┌───────────┐ │
│  │  SeaweedFS   │   │  PostgreSQL 16     │   │ Dragonfly │ │
│  │  :8333 (S3)  │   │  + AGE   :5432     │   │  :6379    │ │
│  │              │   │                    │   │           │ │
│  │ · Iceberg    │   │ Metadata Hub:      │   │ · TTL KV  │ │
│  │   数据文件   │   │ · Iceberg Catalog  │   │ · 短期记忆 │ │
│  │ · Lance 向量 │   │ · AGE 图存储       │   │           │ │
│  │ · Skill 代码 │   │ · 用户/租户/Token  │   │           │ │
│  │ · 文档原文   │   │ · 资产定义/元信息   │   │           │ │
│  │              │   │ · Fileset 元数据   │   │           │ │
│  │              │   │ · mem0 记忆元信息   │   │           │ │
│  └──────────────┘   └────────────────────┘   └───────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                   Ray 集群                              │ │
│  │  ┌─────────────┐    ┌─────────────┐  ┌─────────────┐  │ │
│  │  │  ray-head   │    │ ray-worker  │  │ ray-worker  │  │ │
│  │  │  :8265      │    │     #1      │  │     #2      │  │ │
│  │  │  :6379(GCS) │    │             │  │             │  │ │
│  │  └─────────────┘    └─────────────┘  └─────────────┘  │ │
│  │  · 批量 Embedding (fastembed)                          │ │
│  │  · 分布式向量检索 (LanceDB)                             │ │
│  │  · 重型 SQL / 跨表 JOIN (DuckDB)                       │ │
│  │  · mem0 事实抽取 LLM 批处理                             │ │
│  │  共享 Lance 目录 (bind mount)                          │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  网络: lakemind (bridge)                                    │
│  持久化: ./data/{seaweedfs,postgres,dragonfly,lance}       │
└─────────────────────────────────────────────────────────────┘
```

| 项 | 选型 | 说明 |
|----|------|------|
| 对象存储 | SeaweedFS | S3 兼容 |
| **统一数据库** | **PostgreSQL 16 + Apache AGE** | **Iceberg catalog + 图 + 用户/租户 + 资产定义** |
| 表格式 | Apache Iceberg | PyIceberg 嵌入式，PG catalog |
| 向量 / 多模态 | PyLance + LanceDB | 共享 Lance 目录 |
| 缓存 / 短期记忆 | Dragonfly | Redis 兼容 TTL KV |
| **分布式计算** | **Ray** | **MVP 即引入，head + 2 worker** |
| 即席计算 | DuckDB | 进程内轻量 SQL |
| ~~Gravitino~~ | — | **移除，PG 替代** |
| ~~Trino~~ | — | **明确不引入** |
| Apache Ranger | — | 下一阶段引入 |

**设计要点**：
- 5 容器：seaweedfs / postgres / dragonfly / ray-head / ray-worker(×2)
- bind mount `./data/` 持久化
- AGE 预装在自定义 PG 镜像中
- Ray worker 共享 Lance 目录（bind mount）

### 6.2 三 MCP 架构图（运行平面 · Agent 唯一入口）

```
                    ┌─────────────────────────────────┐
                    │       Nginx / Traefik (LB)       │
                    └──┬──────────┬──────────┬────────┘
                       │          │          │
          ┌────────────┴──┐ ┌────┴────────┐ ┌┴────────────┐
          │  AssetMCP     │ │  DataMCP    │ │  AdminMCP   │
          │  :8401 ×N     │ │  :8402 ×N   │ │  :8403      │
          │               │ │             │ │             │
          │ ┌───────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │
          │ │Asset YAML │ │ │ │Iceberg  │ │ │ │PG CRUD  │ │
          │ │Registry   │ │ │ │LanceDB  │ │ │ │用户/租户 │ │
          │ │(from PG)  │ │ │ │S3       │ │ │ │Token    │ │
          │ └───────────┘ │ │ │Dragonfly│ │ │ │资产类型  │ │
          │ ┌───────────┐ │ │ │AGE      │ │ │ │健康/配置 │ │
          │ │嵌入式引擎  │ │ │ │DuckDB   │ │ │ └─────────┘ │
          │ │PyIceberg  │ │ │ └─────────┘ │ │             │
          │ │LanceDB    │ │ │ ┌─────────┐ │ │ ┌─────────┐ │
          │ │fastembed  │ │ │ │ Ray     │ │ │ │PostgreSQL│ │
          │ │mem0       │ │ │ │ client  │ │ │ │ (psycopg)│ │
          │ └───────────┘ │ │ └─────────┘ │ │ └─────────┘ │
          │ ┌───────────┐ │ │             │ │             │
          │ │ Ray client│ │ │ 轻量→嵌入式  │ │ 单副本      │
          │ │ (重请求)  │ │ │ 重量→Ray    │ │             │
          │ └───────────┘ │ │             │ │             │
          └───────────────┘ └─────────────┘ └─────────────┘
               ↑ asset            ↑ data          ↑ admin
          业务 Agent(200)    Steward/高级Agent    Steward
```

> 三个 MCP 共享引擎适配层代码（PyIceberg/LanceDB/S3/Dragonfly/AGE/DuckDB），
> 但各自只暴露本面工具，独立部署、独立扩缩容。

### 6.3 LakeMindAssetMCP（资产面）

| 项 | 选型 |
|----|------|
| 语言 | Python 3.12 |
| MCP SDK | FastMCP + streamable_http |
| 嵌入式引擎 | PyIceberg / PyLance / LanceDB / fastembed |
| **记忆引擎** | **mem0（事实抽取 + 合并去重 + 实体图谱）** |
| 重计算 | Ray client（提交 actor / task） |
| 配置 | YAML + Pydantic |

**设计要点**：
- 声明式资产 YAML → 自动生成资源 + 工具
- 4 默认资产 + extension/ 自动扫描 + PG 动态加载
- memory 资产用 mem0 引擎（事实抽取 + 合并去重 + 实体图谱）
- 轻量走嵌入式，重请求走 Ray
- 无状态，可多副本

### 6.4 LakeMindDataMCP（数据面）

| 项 | 选型 |
|----|------|
| 语言 | Python 3.12 |
| MCP SDK | FastMCP + streamable_http |
| 引擎 | PyIceberg / LanceDB / DuckDB / S3 / Dragonfly / AGE |
| 重计算 | Ray client |

**设计要点**：
- 全量透传，不做语义包装
- `data_sql` 轻量走 DuckDB，重量级走 Ray
- 无状态，可多副本

### 6.5 LakeMindAdminMCP（管理面）

| 项 | 选型 |
|----|------|
| 语言 | Python 3.12 |
| MCP SDK | FastMCP + streamable_http |
| 数据库 | PostgreSQL（psycopg） |

**设计要点**：
- 用户 / 租户 / Token / 资产类型定义 CRUD，存 PG
- 平台健康聚合（探活 5 容器 + 3 MCP + Ray）
- 节点状态管理
- 单副本即可（管理操作低频）

### 6.6 LakeMindSteward（运行平面 · 管理运维 Agent）

**架构图**：

```
┌─────────────────────────────────────────────────────────┐
│                   LakeMindSteward                        │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              LangGraph 状态图                       │  │
│  │                                                   │  │
│  │  对话管理              自主巡检                     │  │
│  │  ┌─────────┐         ┌──────────────────────┐     │  │
│  │  │自然语言  │         │ 定时触发              │     │  │
│  │  │  ↓      │         │   ↓                  │     │  │
│  │  │意图识别  │         │ 检查健康(AdminMCP)   │     │  │
│  │  │  ↓      │         │   ↓                  │     │  │
│  │  │路由到   │         │ 分析异常              │     │  │
│  │  │工具调用  │         │   ↓                  │     │  │
│  │  │  ↓      │         │ 决策(需确认→暂停)    │     │  │
│  │  │返回结果  │         │   ↓                  │     │  │
│  │  └─────────┘         │ 执行修复(DataMCP)    │     │  │
│  │                      │   ↓                  │     │  │
│  │  state persistence   │ 验证                 │     │  │
│  │  (检查点/可恢复)      └──────────────────────┘     │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ MCP Client  │  │ MCP Client  │  │ MCP Client  │     │
│  │ →AssetMCP   │  │ →DataMCP    │  │ →AdminMCP   │     │
│  │ scope:asset │  │ scope:data  │  │ scope:admin │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                         │
│  LLM: 可配置 (OpenAI / 本地 vLLM via Ray)               │
│  不做降级直连 · MCP高可用全挂则系统不可用                 │
└─────────────────────────────────────────────────────────┘
```

| 项 | 选型 |
|----|------|
| 语言 | Python 3.12 |
| **Agent 框架** | **LangGraph** |
| MCP 接入 | MCP 客户端 SDK，持 `asset + data + admin` Token，连 3 个 MCP |
| LLM | 可配置（OpenAI / 本地 vLLM） |

**选 LangGraph 理由**：
- 巡检是典型多步图工作流：`检查健康 → 分析异常 → 决策 → 执行修复 → 验证`，LangGraph 的状态图 + 条件边天然契合。
- 内置 state persistence（检查点），巡检中断可恢复。
- human-in-the-loop：管理操作需人类确认时暂停等待。
- 生态成熟，文档完善。
- Pydantic AI 更轻但缺状态管理和复杂工作流编排。

**设计要点**：
- 对话式管理：自然语言 → LangGraph → 调 3 个 MCP
- 自主巡检：定时触发 LangGraph 巡检工作流
- **不做 MCP 降级直连**：MCP 自身高可用（多副本），全挂了系统就不玩了，各司其职。
- 单容器

### 6.7 LakeMindMonitor（运行平面 · 人类仪表板）

**架构图**：

```
┌─────────────────────────────────────────────────────────┐
│              LakeMindMonitor (Nuxt 3 / Node)             │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │                  Vue 3 SSR 页面                     │  │
│  │                                                   │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │  │
│  │  │Dashboard │ │ Asset   │ │  Data   │ │  Admin  │  │  │
│  │  │全局概览  │ │ Monitor │ │ Monitor │ │ Monitor │  │  │
│  │  │平台健康  │ │ 4类资产  │ │ 表/存储  │ │用户/配置│  │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │  │
│  │  ┌─────────────────────────────────────────────┐   │  │
│  │  │              Chat (→ Steward)                │   │  │
│  │  │    未就绪就显示"未就绪" · 不降级 · 不加戏      │   │  │
│  │  └─────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │            Nitro API Routes (代理层)               │  │
│  │  /api/asset/* → AssetMCP (只读)                    │  │
│  │  /api/data/*  → DataMCP  (只读)                    │  │
│  │  /api/admin/* → AdminMCP (只读)                    │  │
│  │  /api/chat    → Steward                            │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  无自有数据库 · 无自有用户系统                             │
│  认证: 平台Token (AdminMCP签发 或 配置文件静态)           │
│  单容器 · 极轻                                          │
└─────────────────────────────────────────────────────────┘
```

| 项 | 选型 |
|----|------|
| **框架** | **Nuxt 3（Node.js，Vue 3 SSR）** |
| MCP 接入 | 3 个 MCP 客户端（asset / data / admin 只读） |
| **自有数据库** | **无** |
| **自有用户系统** | **无** |

**设计要点**：
- **纯 Node，不搞前后端分离**。Nuxt 3 一个应用：Vue 3 页面 + Nitro API routes（代理 MCP 调用）。
- **不建自己的数据库**。用户 / 租户 / 状态全靠 AdminMCP（背后 PG）。Monitor 只做展示和代理。
- **三面监控**：Asset 面视图 / Data 面视图 / Admin 面视图。
- Chat 窗对接 Steward。**Steward 未就绪就显示"未就绪"，不加戏、不降级、不额外逻辑**。
- 认证：用平台 Token（从 AdminMCP 获取或配置文件静态 Token）。
- 极轻，单容器。

**视图设计**：

| 视图 | 面 | 内容 |
|------|-----|------|
| Dashboard | 全局 | 三面概览 + 平台健康 |
| AssetMonitor | 资产面 | 4 类资产状态、能力图、资产实例列表 |
| DataMonitor | 数据面 | 表列表、存储用量、查询监控 |
| AdminMonitor | 管理面 | 用户/租户/Token 管理、节点状态、平台配置 |
| Chat | — | Steward 对话窗 |

### 6.8 LakeMindStudio（开发平面 · 桌面客户端）

**架构图**：

```
┌─────────────────────────────────────────────────────────┐
│            LakeMindStudio (Tauri 2.0 桌面客户端)          │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Vue 3 + Vite + TS (前端)               │  │
│  │                                                   │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │  │
│  │  │资产设计器 │ │MCP调试台  │ │Skill脚手架│          │  │
│  │  │YAML编辑  │ │3个MCP    │ │模板生成   │          │  │
│  │  │实时预览  │ │工具/资源  │ │本地沙箱   │          │  │
│  │  │一键注册  │ │原始返回   │ │一键上传   │          │  │
│  │  └──────────┘ └──────────┘ └──────────┘          │  │
│  │  ┌──────────────────────────────────────────┐     │  │
│  │  │         CI/CD (触发webhook · 查看状态)    │     │  │
│  │  └──────────────────────────────────────────┘     │  │
│  └───────────────────────────────────────────────────┘  │
│                          │ IPC                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │            Tauri Rust Core (本地能力)               │  │
│  │  · 本地文件系统读写 · Git 操作 · 进程管理(沙箱)     │  │
│  │  · MCP Client (HTTP 直连 3 个 MCP)                 │  │
│  │  · 自动更新 (Tauri updater)                        │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  跨平台: Windows / macOS / Linux (~10MB)                │
│  独立于服务端部署 · 开发者各自安装                         │
│  CI/CD流水线跑在服务端(GitHub Actions) · Studio触发webhook│
└─────────────────────────────────────────────────────────┘
```

| 项 | 选型 |
|----|------|
| **形态** | **Tauri 2.0 桌面客户端** |
| 前端 | Vue 3 + Vite + TypeScript |
| 后端 | Tauri Rust core（本地文件系统、Git、进程管理） |
| MCP 接入 | MCP 客户端 SDK（直连 3 个 MCP） |

**选 Tauri 桌面客户端理由**：
- Studio 是开发者工具（资产设计、MCP 调试、Skill 脚手架），开发者工作在本地。
- 桌面客户端可直接访问本地 Git、本地文件系统、本地终端，无需服务端中转。
- Tauri 比 Electron 轻 10 倍（~10MB vs ~150MB），Rust core 安全高效。
- 独立于服务端部署，开发者各自安装，互不影响。
- **缺点**：跨平台打包（Windows / macOS / Linux）、自动更新需 Tauri updater。CI/CD 流水线本身跑在服务端（GitHub Actions），Studio 触发 webhook。
- CI/CD 集成：Studio 触发发布 webhook，流水线在服务端跑，Studio 查看状态。

**功能**：
- 资产设计器：YAML 编辑器 + 实时预览 + 一键注册到 AdminMCP
- MCP 调试台：在线调用 3 个 MCP 的工具 / 读资源，查看原始返回
- Skill 脚手架：模板生成 + 本地沙箱测试 + 一键上传
- CI/CD：触发流水线、查看构建状态

---

## 7. MVP 改造清单

### 7.1 已完成 · 保留

| 项 | 说明 |
|----|------|
| SeaweedFS / Dragonfly 容器 | 不变 |
| MCP 认证中间件机制 | ContextVar 注入保留，3 个 MCP 各自一份 |
| MCP S3 / Dragonfly / LanceDB / DuckDB 引擎适配 | 保留，DataMCP 复用 |
| MCP schema_convert | 保留 |
| Monitor 前端 Vue 3 视图组件 | 部分复用，迁移到 Nuxt 3 |

### 7.2 已完成 · 需调整

| 项 | 现状 | 改造 |
|----|------|------|
| **Iceberg catalog** | SQLite | → PostgreSQL |
| **单 MCP** | LakeMindMCP | → 拆分为 AssetMCP / DataMCP / AdminMCP 3 个独立服务 |
| **Scope 体系** | `data` / `admin` | → `asset` / `data` / `admin`，每 MCP 一个面 |
| **默认资产** | 5 类 + ontology 占位 | → 4 类（knowledge / skill / memory / ontology），experience 积淀进 memory.kind |
| **资产定义** | 代码注册 | → 声明式 YAML + 预置引擎模式 |
| **Asset 基类** | ABC 空壳 | → 废弃继承模式，改声明式 YAML |
| **Embedding** | SHA256 伪向量 | → fastembed（ONNX 真实语义） |
| **Memory 引擎** | 手写 remember/recall/forget | → mem0 引擎（事实抽取 + 合并去重 + 实体图谱） |
| **Gravitino** | JVM 容器 | → 移除，PG 替代 |
| **Monitor** | FastAPI BFF + Vue SPA | → Nuxt 3 纯 Node，无自有 DB |
| **Monitor Chat** | Steward + 降级直连 | → 仅对接 Steward，不降级 |
| **Token** | 配置文件静态 | → AdminMCP 签发 + PG 存储（兼容静态配置） |

### 7.3 新增

| 项 | 说明 |
|----|------|
| PostgreSQL 16 + AGE 容器 | 统一数据库 |
| Ray head + 2 worker 容器 | 分布式计算 |
| LakeMindAssetMCP | 资产面 MCP 服务 |
| LakeMindDataMCP | 数据面 MCP 服务 |
| LakeMindAdminMCP | 管理面 MCP 服务（用户/租户/Token/资产类型/健康） |
| AGE 图存储 | 本体 + graphRAG |
| Ontology 资产实装 | native/ontology.yaml + AGE 引擎模式 |
| 声明式资产引擎模式 | vector_topk / embed_and_write / graph_query / graph_update / kv_ttl / table_query / table_append |
| extension/ 自动扫描 | YAML 自动注册 |
| fastembed | ONNX embedding |
| Ray embedding actor | 批处理 embedding |
| **mem0 记忆引擎** | **事实抽取 + 合并去重 + 实体图谱，LanceDB/AGE/PG 适配器** |
| LakeMindSteward | LangGraph Agent |
| LakeMindStudio | Tauri 桌面客户端 |
| Nginx / Traefik 负载均衡 | MCP 多副本前置 |

### 7.4 删除

| 项 | 说明 |
|----|------|
| LakeMindMCP（单体） | 拆分为 3 个 |
| Gravitino 容器 | PG 替代 |
| `experience` 独立资产 | 积淀进 memory.kind |
| `data` 作为资产类型 | 降为数据面透传 |
| SHA256 LocalEmbeddingProvider | fastembed 替代 |
| 手写 memory remember/recall/forget | mem0 引擎替代 |
| Monitor FastAPI BFF | Nuxt 3 替代 |
| Monitor 降级直连逻辑 | 不加戏 |
| Steward 直连 Server 降级 | MCP 自身高可用 |
| Asset ABC 继承模式 | 声明式 YAML 替代 |

---

## 8. 实施顺序

| 步 | 内容 | 涉及包 | 验证 |
|----|------|--------|------|
| 1 | LakeMindServer 改造：移除 Gravitino，加 PostgreSQL+AGE、Ray head+worker，docker-compose 更新 | Server | 5 容器全 Up |
| 2 | Iceberg catalog 切 PostgreSQL，PyIceberg 连通验证 | Server | 建表 + 读写 |
| 3 | AGE 扩展安装，openCypher 查询验证 | Server | 建图 + 查询 |
| 4 | Ray 集群验证，submit task 测试 | Server | Ray dashboard |
| 5 | LakeMindAssetMCP：从原 MCP 拆分，4 默认资产声明式 YAML，fastembed embedding，Ray 集成 | AssetMCP | verify_asset |
| 6 | mem0 集成：LanceDB/AGE/PG 适配器，remember/recall/forget 映射，Ray LLM 批处理 | AssetMCP | verify_mem0 |
| 7 | LakeMindDataMCP：全量透传工具集，PG/AGE/Ray 集成 | DataMCP | verify_data |
| 8 | LakeMindAdminMCP：用户/租户/Token/资产类型 CRUD，平台健康 | AdminMCP | verify_admin |
| 9 | 三 MCP 联合验证（Token 签发 → 各面调用 → 租户隔离） | 3 MCP | verify_mcp_combined |
| 10 | LakeMindSteward：LangGraph 巡检工作流 + 对话管理，连 3 MCP | Steward | verify_steward |
| 11 | LakeMindMonitor：Nuxt 3 三面监控 + Chat 对接 Steward | Monitor | verify_monitor |
| 12 | LakeMindStudio：Tauri 桌面客户端，资产设计器 + MCP 调试台 + Skill 脚手架 | Studio | 手动验证 |
| 13 | 端到端验证：200 Agent 并发压测 | 全部 | load_test |
| 14 | 更新各包 README + AGENTS.md | 全部 | — |

---

## 9. 验收标准

- [ ] LakeMindServer 5 容器全 Up（seaweedfs / postgres+AGE / dragonfly / ray-head / ray-worker×2）
- [ ] Gravitino 已移除，Iceberg catalog 走 PostgreSQL，并发写入无死锁
- [ ] AGE 图查询可用（openCypher）
- [ ] Ray 集群可用，task 提交成功
- [ ] 3 个 MCP 独立部署，各自可多副本
- [ ] AssetMCP：4 默认资产（knowledge/skill/memory/ontology）资源 + 工具全可用
- [ ] AssetMCP：声明式自定义资产 YAML 注册可用
- [ ] DataMCP：全量透传工具可用
- [ ] AdminMCP：用户/租户/Token/资产类型 CRUD 可用
- [ ] Token 三面权限隔离生效
- [ ] fastembed embedding 语义检索可用
- [ ] mem0 记忆引擎可用：事实抽取 + 合并去重 + 实体图谱（AGE）
- [ ] mem0 三种模式可用：simple（不调LLM）/ smart（调LLM）/ auto（自适应）
- [ ] experience 积淀为 memory.kind，不再独立资产
- [ ] LakeMindSteward：LangGraph 巡检 + 对话可用
- [ ] LakeMindMonitor：Nuxt 3 三面监控 + Chat 可用，无自有 DB
- [ ] LakeMindStudio：Tauri 桌面客户端可安装运行
- [ ] 200 Agent 并发压测通过（MCP 多副本 + Ray 分布式计算）
- [ ] 全部 verify 脚本 PASS

---

> 批准后按 §8 顺序实施，每步验证通过再进下一步。
