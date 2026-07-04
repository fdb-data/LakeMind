# LakeMindServer REST API 层设计方案

> 编号 `LM-SERVER-API-1`。待批准后开发。
>
> 核心变更：LakeMindServer 从纯基础设施（docker-compose）升级为 **REST API 网关**，
> 3 个 MCP 不再直连引擎，而是通过 REST API 访问全部数据能力。
> 引擎可插拔，支持底座切换（SeaweedFS → AWS S3 / 阿里云 OSS / 华为云 OBS 等）。

---

## 1. 改造目标与动机

### 1.1 现状问题

| 问题 | 说明 |
|------|------|
| 引擎逻辑分散 | PyIceberg / LanceDB / DuckDB / S3 / Dragonfly / Graph 适配层在 AssetMCP 和 DataMCP 中各有一份，代码重复 |
| 引擎不可替换 | S3 客户端硬编码 boto3 + SeaweedFS endpoint，无法切换到 AWS / 阿里云 / 华为云 |
| MCP 职责不清 | MCP 既做协议适配（MCP JSON-RPC），又做引擎适配，又做业务逻辑 |
| 连接管理分散 | 每个 MCP 各自管理 PG / S3 / Dragonfly 连接，无统一连接池 |
| 引擎接口不一致 | DataMCP 的 `data_sql` / `kv_get` 与引擎层签名不匹配（见调研报告） |

### 1.2 改造目标

1. **LakeMindServer 成为唯一引擎网关** — 所有数据操作经 REST API，MCP 不直连引擎
2. **引擎可插拔** — 通过配置切换引擎实现，不改代码
3. **引擎分三类** — 数据存储引擎 / 数据计算引擎 / 认知计算引擎
4. **统一连接管理** — 连接池、健康检查、指标采集集中在 Server
5. **MCP 瘦身** — MCP 只做 MCP 协议适配 + 认证 + 转发，成为薄客户端

---

## 2. 总体架构

### 2.1 改造前

```
Agent → AssetMCP ──→ PyIceberg / LanceDB / fastembed / S3 / Dragonfly / PG
Agent → DataMCP  ──→ PyIceberg / LanceDB / DuckDB / S3 / Dragonfly / PG
Steward → AdminMCP ──→ PG (psycopg2)
```

每个 MCP 内嵌全套引擎，直连存储。

### 2.2 改造后

```
Agent → AssetMCP ──→ ┐
Agent → DataMCP  ──→ ┤── LakeMindServer REST API (:10823)
Steward → AdminMCP ──→ ┘          │
                                   ├── Storage Engines (可插拔)
                                   │   ├── ObjectStorage Plugin (SeaweedFS / AWS / OSS / OBS)
                                   │   ├── TabularStorage Plugin (Iceberg)
                                   │   ├── VectorStorage Plugin (Lance/LanceDB)
                                   │   ├── KVStorage Plugin (Dragonfly / Redis)
                                   │   ├── GraphStorage Plugin (Postgres / AGE)
                                   │   └── MetadataStore Plugin (Postgres)
                                   │
                                   ├── Compute Engines (可插拔)
                                   │   ├── SQLCompute Plugin (DuckDB / Daft)
                                   │   └── DistributedCompute Plugin (Embedded / Ray)
                                   │
                                   └── Cognitive Engines (可插拔)
                                       ├── Embedding Plugin (fastembed / External)
                                       └── Memory Plugin (Basic / mem0)
```

### 2.3 分层职责

| 层 | 职责 | 不做什么 |
|----|------|---------|
| **MCP 层** | MCP 协议适配（JSON-RPC）、Token 认证、Scope 校验、请求转发到 REST API | 不直连引擎、不持有引擎客户端、不做数据操作 |
| **REST API 层** | 引擎路由、连接池管理、租户隔离、健康检查、指标采集、审计日志 | 不做 MCP 协议、不做资产语义（Asset 层在 MCP） |
| **引擎插件层** | 具体引擎操作（S3 put/get、Iceberg scan/append、LanceDB search 等） | 不做认证、不做租户隔离（由上层注入） |

---

## 3. 引擎分类与插件接口

### 3.1 三类引擎

```
引擎分类
├── 数据存储引擎 (Storage Engines)
│   ├── ObjectStorage     — 对象存储（S3 兼容）
│   ├── TabularStorage    — 结构化表（Iceberg）
│   ├── VectorStorage     — 向量存储（Lance/LanceDB）
│   ├── KVStorage         — 键值存储（Dragonfly/Redis）
│   ├── GraphStorage      — 图存储（Postgres/AGE）
│   └── MetadataStore     — 元数据存储（Postgres）
│
├── 数据计算引擎 (Compute Engines)
│   ├── SQLCompute        — 即席 SQL（DuckDB）
│   └── DistributedCompute — 分布式计算（Embedded/Ray）
│
└── 认知计算引擎 (Cognitive Engines)
    ├── Embedding         — 向量嵌入（fastembed/External）
    └── Memory            — 记忆引擎（Basic/mem0）
```

### 3.2 插件接口定义（Protocol）

#### 3.2.1 ObjectStorage — 对象存储

```python
class ObjectStoragePlugin(Protocol):
    def put(self, bucket: str, key: str, body: bytes) -> None: ...
    def get(self, bucket: str, key: str) -> bytes: ...
    def delete(self, bucket: str, key: str) -> None: ...
    def exists(self, bucket: str, key: str) -> bool: ...
    def list(self, bucket: str, prefix: str = "", limit: int = 1000) -> list[str]: ...
    def ensure_bucket(self, bucket: str) -> None: ...
    def health(self) -> bool: ...
```

**基线实现**：`SeaweedFSStorage`（boto3 + path-style）
**可插拔实现**：`AWSS3Storage`、`AliyunOSSStorage`、`HuaweiOBSStorage`（均 boto3 + 不同 endpoint/signature）

#### 3.2.2 TabularStorage — 结构化表（Iceberg）

```python
class TabularStoragePlugin(Protocol):
    def create_table(self, namespace: str, table: str, schema: pa.Schema, location: str | None = None) -> str: ...
    def table_exists(self, namespace: str, table: str) -> bool: ...
    def list_tables(self, namespace: str) -> list[str]: ...
    def list_namespaces(self) -> list[str]: ...
    def ensure_namespace(self, namespace: str) -> None: ...
    def append(self, namespace: str, table: str, data: pa.Table) -> int: ...
    def overwrite(self, namespace: str, table: str, data: pa.Table) -> int: ...
    def scan(self, namespace: str, table: str, columns: list[str] | None = None,
             filter: str | None = None, limit: int | None = None) -> pa.Table: ...
    def describe(self, namespace: str, table: str) -> dict: ...
    def drop_table(self, namespace: str, table: str) -> None: ...
    def health(self) -> bool: ...
```

**基线实现**：`IcebergTabularStorage`（PyIceberg + PG SQL catalog + S3 warehouse）
**可插拔实现**：未来可支持 `GlueTabularStorage`（AWS Glue catalog）

#### 3.2.3 VectorStorage — 向量存储

```python
class VectorStoragePlugin(Protocol):
    def create_table(self, db: str, name: str, data: pa.Table, mode: str = "overwrite") -> None: ...
    def table_exists(self, db: str, name: str) -> bool: ...
    def list_tables(self, db: str) -> list[str]: ...
    def add(self, db: str, name: str, data: pa.Table) -> int: ...
    def search(self, db: str, name: str, query_vec: list[float],
               top_k: int = 5, filter: str | None = None) -> list[dict]: ...
    def count_rows(self, db: str, name: str) -> int: ...
    def describe(self, db: str, name: str) -> dict: ...
    def health(self) -> bool: ...
```

**基线实现**：`LanceVectorStorage`（LanceDB + 共享 Lance 目录）
**可插拔实现**：`MilvusVectorStorage`、`QdrantVectorStorage`（未来）

#### 3.2.4 KVStorage — 键值存储

```python
class KVStoragePlugin(Protocol):
    def get(self, db: int, key: str) -> bytes | str | None: ...
    def set(self, db: int, key: str, value: bytes | str, ttl: int | None = None) -> None: ...
    def delete(self, db: int, key: str) -> bool: ...
    def scan(self, db: int, pattern: str = "*", limit: int = 1000) -> list[str]: ...
    def health(self) -> bool: ...
```

**基线实现**：`DragonflyKVStorage`（redis 客户端 + Dragonfly）
**可插拔实现**：`RedisKVStorage`、`ValkeyKVStorage`

#### 3.2.5 GraphStorage — 图存储

```python
class GraphStoragePlugin(Protocol):
    def add_node(self, graph: str, node_id: str, label: str, properties: dict, tenant_id: str) -> None: ...
    def add_edge(self, graph: str, edge_id: str, src: str, dst: str,
                 rel: str, properties: dict, tenant_id: str) -> None: ...
    def query_nodes(self, graph: str, tenant_id: str, label: str | None = None) -> list[dict]: ...
    def query_edges(self, graph: str, src: str, tenant_id: str) -> list[dict]: ...
    def delete_node(self, graph: str, node_id: str, tenant_id: str) -> None: ...
    def health(self) -> bool: ...
```

**基线实现**：`PostgresGraphStorage`（PG 原生表 graph_nodes/graph_edges）
**可插拔实现**：`AgeGraphStorage`（Apache AGE + openCypher）、`Neo4jGraphStorage`（未来）

#### 3.2.6 MetadataStore — 元数据存储

```python
class MetadataStorePlugin(Protocol):
    # Tenant
    def create_tenant(self, tenant_id: str, name: str) -> dict: ...
    def update_tenant(self, tenant_id: str, name: str | None, status: str | None) -> dict: ...
    def delete_tenant(self, tenant_id: str) -> dict: ...
    def list_tenants(self) -> dict: ...
    # User
    def create_user(self, username: str, tenant_id: str, role: str) -> dict: ...
    def update_user(self, user_id: str, **fields) -> dict: ...
    def delete_user(self, user_id: str) -> dict: ...
    def list_users(self, tenant_id: str | None) -> dict: ...
    # Token
    def issue_token(self, agent_id: str, tenant_id: str, scopes: list[str]) -> dict: ...
    def revoke_token(self, token: str) -> dict: ...
    def list_tokens(self, tenant_id: str | None, agent_id: str | None) -> dict: ...
    def validate_token(self, token: str) -> dict | None: ...
    # AssetType
    def register_asset_type(self, type: str, yaml_def: str) -> dict: ...
    def unregister_asset_type(self, type: str) -> dict: ...
    def list_asset_types(self) -> dict: ...
    def health(self) -> bool: ...
```

**基线实现**：`PostgresMetadataStore`（psycopg2 + 连接池）
**可插拔实现**：未来可支持 `MySQLMetadataStore` 等

#### 3.2.7 SQLCompute — 即席 SQL

```python
class SQLComputePlugin(Protocol):
    def execute(self, sql: str, tables: dict[str, pa.Table] | None = None) -> list[dict]: ...
    def health(self) -> bool: ...
```

**基线实现**：`DuckDBSQLCompute`（进程内 DuckDB）
**可插拔实现**：`DaftSQLCompute`（Daft DataFrame SQL）

#### 3.2.8 DistributedCompute — 分布式计算

```python
class DistributedComputePlugin(Protocol):
    def submit(self, func: str, args: dict) -> str: ...
    def status(self, job_id: str) -> dict: ...
    def result(self, job_id: str) -> Any: ...
    def health(self) -> bool: ...
```

**基线实现**：`EmbeddedCompute`（同步执行，无分布式）
**可插拔实现**：`RayCompute`（Ray actor/task）

#### 3.2.9 Embedding — 向量嵌入

```python
class EmbeddingPlugin(Protocol):
    @property
    def dim(self) -> int: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def health(self) -> bool: ...
```

**基线实现**：`FastEmbedPlugin`（ONNX + BAAI/bge-small-en-v1.5）
**可插拔实现**：`ExternalEmbeddingPlugin`（OpenAI 兼容 API）、`TEIEmbeddingPlugin`（HuggingFace TEI）

#### 3.2.10 Memory — 记忆引擎

```python
class MemoryPlugin(Protocol):
    def remember(self, agent_id: str, tenant_id: str, content: str,
                 context: str | None = None, ttl: int | None = None,
                 kind: str = "general") -> dict: ...
    def recall(self, agent_id: str, tenant_id: str, query: str,
               limit: int = 5, kind: str | None = None) -> list[dict]: ...
    def forget(self, agent_id: str, tenant_id: str, query: str | None = None) -> dict: ...
    def health(self) -> bool: ...
```

**基线实现**：`BasicMemory`（Dragonfly 短期 + Lance 长期 + Iceberg 元信息）
**可插拔实现**：`Mem0Memory`（事实抽取 + 合并去重 + 实体图谱）

---

## 4. REST API 设计

### 4.1 API 分域

```
/api/v1/
├── storage/
│   ├── objects/          — 对象存储（S3）
│   ├── tables/           — 结构化表（Iceberg）
│   ├── vectors/          — 向量存储（LanceDB）
│   ├── kv/               — 键值存储（Dragonfly）
│   └── graph/            — 图存储（PG）
├── compute/
│   ├── sql/              — 即席 SQL（DuckDB）
│   └── jobs/             — 分布式计算（Ray）
├── cognitive/
│   ├── embedding/        — 向量嵌入
│   └── memory/           — 记忆引擎
├── metadata/
│   ├── tenants/          — 租户管理
│   ├── users/            — 用户管理
│   ├── tokens/           — Token 管理
│   └── asset-types/      — 资产类型管理
└── system/
    ├── health            — 全平台健康
    ├── nodes             — 节点状态
    └── metrics           — Prometheus 指标
```

### 4.2 认证

```
Authorization: Bearer <internal-api-key>
```

- REST API 使用内部 API Key 认证（非 MCP Token）
- MCP 持有内部 API Key，在转发请求时附带
- 内部 API Key 通过环境变量配置，不对外暴露
- 租户信息通过 HTTP Header 传递：`X-Tenant-Id`、`X-Agent-Id`、`X-Scopes`

### 4.3 详细端点

#### 4.3.1 对象存储 `/api/v1/storage/objects`

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/{bucket}/{key}` | 上传对象（body: binary） |
| GET | `/{bucket}/{key}` | 下载对象（返回 binary） |
| HEAD | `/{bucket}/{key}` | 检查存在 |
| DELETE | `/{bucket}/{key}` | 删除对象 |
| GET | `/{bucket}?prefix=&limit=` | 列举对象 |

#### 4.3.2 结构化表 `/api/v1/storage/tables`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/` | 建表（body: {namespace, table, schema}） |
| GET | `/{namespace}` | 列表 |
| GET | `/{namespace}/{table}` | describe |
| DELETE | `/{namespace}/{table}` | 删表 |
| POST | `/{namespace}/{table}/append` | 追加数据（body: rows JSON） |
| POST | `/{namespace}/{table}/overwrite` | 覆写数据 |
| GET | `/{namespace}/{table}/scan?columns=&filter=&limit=` | 扫描 |

#### 4.3.3 向量存储 `/api/v1/storage/vectors`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/{db}` | 建表（body: {name, schema, data}） |
| GET | `/{db}` | 列表 |
| POST | `/{db}/{name}/add` | 添加向量 |
| POST | `/{db}/{name}/search` | 检索（body: {query_vec, top_k, filter}） |
| GET | `/{db}/{name}` | describe |

#### 4.3.4 键值存储 `/api/v1/storage/kv`

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/{key}` | 设置（body: {value, ttl?}） |
| GET | `/{key}` | 获取 |
| DELETE | `/{key}` | 删除 |
| GET | `?pattern=&limit=` | 扫描 |

#### 4.3.5 图存储 `/api/v1/storage/graph`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/{graph}/nodes` | 添加节点 |
| POST | `/{graph}/edges` | 添加边 |
| GET | `/{graph}/nodes?label=&tenant_id=` | 查询节点 |
| GET | `/{graph}/edges?src=&tenant_id=` | 查询边 |
| DELETE | `/{graph}/nodes/{node_id}` | 删除节点 |

#### 4.3.6 即席 SQL `/api/v1/compute/sql`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/` | 执行 SQL（body: {sql, tables?}） |

#### 4.3.7 分布式计算 `/api/v1/compute/jobs`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/` | 提交作业 |
| GET | `/{job_id}` | 查询状态 |
| GET | `/{job_id}/result` | 获取结果 |

#### 4.3.8 向量嵌入 `/api/v1/cognitive/embedding`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/embed` | 批量嵌入（body: {texts: [...]}） |

#### 4.3.9 记忆引擎 `/api/v1/cognitive/memory`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/remember` | 记忆（body: {content, context?, ttl?, kind?}） |
| POST | `/recall` | 召回（body: {query, limit?, kind?}） |
| POST | `/forget` | 遗忘（body: {query?}） |

#### 4.3.10 元数据 `/api/v1/metadata/*`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tenants` | 创建租户 |
| GET | `/tenants` | 列出租户 |
| PUT | `/tenants/{id}` | 更新租户 |
| DELETE | `/tenants/{id}` | 删除租户 |
| POST | `/users` | 创建用户 |
| GET | `/users?tenant_id=` | 列出用户 |
| PUT | `/users/{id}` | 更新用户 |
| DELETE | `/users/{id}` | 删除用户 |
| POST | `/tokens` | 签发 Token |
| GET | `/tokens?tenant_id=&agent_id=` | 列出 Token |
| DELETE | `/tokens/{token}` | 吊销 Token |
| POST | `/asset-types` | 注册资产类型 |
| GET | `/asset-types` | 列出资产类型 |
| DELETE | `/asset-types/{type}` | 移除资产类型 |

#### 4.3.11 系统 `/api/v1/system`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 全平台健康（所有引擎插件） |
| GET | `/nodes` | 节点状态 |
| GET | `/metrics` | Prometheus 指标 |

---

## 5. 插件配置设计

### 5.1 配置文件 `LakeMindServer/config/engines.yaml`

```yaml
# ════════════════════════════════════════════════════════════
# 引擎插件配置 — 通过修改 plugin 字段切换实现，不改代码
# ════════════════════════════════════════════════════════════

storage:
  # ── 对象存储 ──
  object:
    plugin: seaweedfs          # seaweedfs | aws_s3 | aliyun_oss | huawei_obs
    config:
      endpoint: "http://lakemind-seaweedfs:8333"
      access_key: "admin"
      secret_key: "admin123456"
      region: "us-east-1"
      path_style: true         # SeaweedFS 需要 path-style
    # 切换到 AWS S3：
    # plugin: aws_s3
    # config:
    #   endpoint: "https://s3.amazonaws.com"
    #   access_key: "${AWS_ACCESS_KEY_ID}"
    #   secret_key: "${AWS_SECRET_ACCESS_KEY}"
    #   region: "us-east-1"
    #   path_style: false
    # 切换到阿里云 OSS：
    # plugin: aliyun_oss
    # config:
    #   endpoint: "https://oss-cn-hangzhou.aliyuncs.com"
    #   access_key: "${OSS_ACCESS_KEY_ID}"
    #   secret_key: "${OSS_ACCESS_KEY_SECRET}"
    #   region: "cn-hangzhou"
    # 切换到华为云 OBS：
    # plugin: huawei_obs
    # config:
    #   endpoint: "https://obs.cn-north-4.myhuaweicloud.com"
    #   access_key: "${OBS_ACCESS_KEY_ID}"
    #   secret_key: "${OBS_ACCESS_KEY_SECRET}"
    #   region: "cn-north-4"

  # ── 结构化表（Iceberg）──
  tabular:
    plugin: iceberg            # iceberg | (future: glue)
    config:
      catalog_name: "lakemind"
      warehouse: "s3://lakemind-iceberg/warehouse"
      sql_uri: "postgresql+psycopg2://lakemind:lakemind_pass@lakemind-postgres:5432/lakemind"

  # ── 向量存储 ──
  vector:
    plugin: lancedb            # lancedb | (future: milvus, qdrant)
    config:
      uri: "/data/lance"

  # ── KV 存储 ──
  kv:
    plugin: dragonfly          # dragonfly | redis | valkey
    config:
      host: "lakemind-dragonfly"
      port: 6379
      password: ""
    # 切换到 Redis：
    # plugin: redis
    # config:
    #   host: "my-redis"
    #   port: 6379

  # ── 图存储 ──
  graph:
    plugin: postgres_graph     # postgres_graph | age | (future: neo4j)
    config:
      host: "lakemind-postgres"
      port: 5432
      db: "lakemind"
      user: "lakemind"
      password: "lakemind_pass"

  # ── 元数据存储 ──
  metadata:
    plugin: postgres           # postgres | (future: mysql)
    config:
      host: "lakemind-postgres"
      port: 5432
      db: "lakemind"
      user: "lakemind"
      password: "lakemind_pass"
      pool_size: 20

compute:
  # ── 即席 SQL ──
  sql:
    plugin: duckdb             # duckdb | daft
    config:
      memory_limit: "2GB"

  # ── 分布式计算 ──
  distributed:
    plugin: embedded           # embedded | ray
    config: {}
    # 切换到 Ray：
    # plugin: ray
    # config:
    #   address: "ray://lakemind-ray-head:10001"

cognitive:
  # ── Embedding ──
  embedding:
    plugin: fastembed          # fastembed | external | tei
    config:
      model: "BAAI/bge-small-en-v1.5"
      dim: 384
    # 切换到外部 API：
    # plugin: external
    # config:
    #   base_url: "https://api.openai.com/v1"
    #   model: "text-embedding-3-small"
    #   dim: 1536
    #   api_key: "${EMBEDDING_API_KEY}"

  # ── 记忆引擎 ──
  memory:
    plugin: basic              # basic | mem0
    config:
      short_term_engine: kv    # 复用 storage.kv
      long_term_engine: vector # 复用 storage.vector
      metadata_engine: tabular # 复用 storage.tabular
    # 切换到 mem0：
    # plugin: mem0
    # config:
    #   fact_extraction: true
    #   consolidation: true
    #   entity_graph: true
    #   llm:
    #     provider: ray_batch
    #     model: "qwen2.5-7b"
```

### 5.2 插件注册机制

```python
# LakeMindServer/src/lakemind_server/plugins/registry.py

PLUGIN_REGISTRY = {
    "storage.object": {
        "seaweedfs": SeaweedFSStorage,
        "aws_s3": AWSS3Storage,
        "aliyun_oss": AliyunOSSStorage,
        "huawei_obs": HuaweiOBSStorage,
    },
    "storage.tabular": {
        "iceberg": IcebergTabularStorage,
    },
    "storage.vector": {
        "lancedb": LanceVectorStorage,
    },
    "storage.kv": {
        "dragonfly": DragonflyKVStorage,
        "redis": RedisKVStorage,
    },
    "storage.graph": {
        "postgres_graph": PostgresGraphStorage,
        "age": AgeGraphStorage,
    },
    "storage.metadata": {
        "postgres": PostgresMetadataStore,
    },
    "compute.sql": {
        "duckdb": DuckDBSQLCompute,
        "daft": DaftSQLCompute,
    },
    "compute.distributed": {
        "embedded": EmbeddedCompute,
        "ray": RayCompute,
    },
    "cognitive.embedding": {
        "fastembed": FastEmbedPlugin,
        "external": ExternalEmbeddingPlugin,
    },
    "cognitive.memory": {
        "basic": BasicMemory,
        "mem0": Mem0Memory,
    },
}

def build_engine(category: str, plugin_name: str, config: dict) -> Plugin:
    cls = PLUGIN_REGISTRY[category][plugin_name]
    return cls(**config)
```

### 5.3 插件实现规范

每个插件实现需遵守：

1. **构造函数接收 config dict** — `__init__(self, **config)`
2. **实现全部 Protocol 方法** — 类型检查确保接口完整
3. **惰性初始化** — 连接在首次调用时建立，不阻塞启动
4. **提供 `health()` 方法** — 返回 bool，供健康检查
5. **线程安全** — 支持并发调用（内部用连接池或锁）
6. **无状态或可重连** — 连接断开后自动重连

---

## 6. 基线架构与基线性能

### 6.1 基线架构（MVP 默认配置）

```
LakeMindServer REST API (:10823)
├── storage.object    → SeaweedFS (:8333, S3 兼容, path-style)
├── storage.tabular   → PyIceberg + PG SQL catalog (:5432) + S3 warehouse
├── storage.vector    → LanceDB + 共享目录 /data/lance
├── storage.kv        → Dragonfly (:6379, Redis 兼容)
├── storage.graph     → PG 原生表 graph_nodes/graph_edges
├── storage.metadata  → PG 表 tenants/users/tokens/asset_types
├── compute.sql       → DuckDB (进程内)
├── compute.dist      → Embedded (同步)
├── cognitive.embed   → fastembed (BAAI/bge-small-en-v1.5, dim=384)
└── cognitive.memory  → Basic (Dragonfly + Lance + Iceberg)
```

### 6.2 基线性能指标

| 操作 | 基线性能 | 说明 |
|------|---------|------|
| S3 put (1KB) | < 5ms | 本地 SeaweedFS |
| S3 get (1KB) | < 3ms | 本地 SeaweedFS |
| Iceberg append (100 rows) | < 50ms | PG catalog + S3 |
| Iceberg scan (1000 rows) | < 30ms | PyIceberg 嵌入式 |
| LanceDB search (top-5) | < 10ms | 本地 Lance 目录 |
| KV set (with TTL) | < 2ms | 本地 Dragonfly |
| KV get | < 1ms | 本地 Dragonfly |
| Graph add_node | < 5ms | PG INSERT |
| Graph query_nodes (100 nodes) | < 10ms | PG SELECT |
| DuckDB SQL (simple) | < 5ms | 进程内 |
| Embedding (1 text) | ~2ms | fastembed ONNX CPU |
| Embedding (batch 100) | ~50ms | fastembed ONNX CPU |
| Memory remember (short) | < 3ms | Dragonfly SET |
| Memory remember (long) | < 20ms | Lance add + Iceberg append |
| Memory recall | < 15ms | LanceDB search |

### 6.3 REST API 开销

| 环节 | 额外延迟 | 说明 |
|------|---------|------|
| MCP → REST API (HTTP) | +1-2ms | 本机 HTTP 调用 |
| REST API → 引擎 | 0 | 同进程调用 |
| **总额外延迟** | **+1-2ms** | 可接受，换取架构清晰度 |

### 6.4 连接池配置

| 引擎 | 池大小 | 说明 |
|------|--------|------|
| PostgreSQL | 20 | catalog + metadata + graph 共享 |
| S3 (boto3) | 连接池自动管理 | |
| Dragonfly | 10 | Redis 客户端连接池 |
| LanceDB | 每租户一个连接 | 惰性创建 |

---

## 7. MCP 改造

### 7.1 MCP 瘦身后的职责

| 职责 | 保留 | 移除 |
|------|------|------|
| MCP 协议适配（JSON-RPC） | ✅ | — |
| Token 认证 + Scope 校验 | ✅ | — |
| 资产语义封装（Asset 层） | ✅ AssetMCP | — |
| 请求转发到 REST API | ✅ | — |
| 引擎客户端 | — | ❌ 移到 Server |
| 引擎连接管理 | — | ❌ 移到 Server |
| 引擎适配层代码 | — | ❌ 移到 Server |

### 7.2 MCP REST 客户端

```python
# 各 MCP 共用的 REST API 客户端
class ServerClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    async def request(self, method: str, path: str, *,
                      tenant_id: str, agent_id: str, scopes: list[str],
                      body: dict | bytes | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Tenant-Id": tenant_id,
            "X-Agent-Id": agent_id,
            "X-Scopes": ",".join(scopes),
        }
        # httpx 调用 REST API
        ...
```

### 7.3 AssetMCP 改造示例

```python
# 改造前：直连引擎
async def search_knowledge(kb, query, top_k=5):
    ctx = get_tenant()
    qvec = engines.embedding.embed([query])[0]
    results = engines.lancedb.search(ctx, kb, qvec, top_k)
    return {"results": results}

# 改造后：调 REST API
async def search_knowledge(kb, query, top_k=5):
    ctx = get_tenant()
    # 1. embed via REST API
    resp = await server.post("/api/v1/cognitive/embedding/embed",
                             tenant_id=ctx.tenant_id, body={"texts": [query]})
    qvec = resp["vectors"][0]
    # 2. search via REST API
    resp = await server.post(f"/api/v1/storage/vectors/{ctx.lancedb_name()}/{kb}/search",
                             tenant_id=ctx.tenant_id,
                             body={"query_vec": qvec, "top_k": top_k})
    return {"results": resp["results"]}
```

### 7.4 AdminMCP 改造

AdminMCP 不再直连 PG，全部走 REST API：

```python
# 改造前：直连 PG
async def list_tenants():
    conn = _conn(config)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM tenants WHERE status='active'")
        ...

# 改造后：调 REST API
async def list_tenants():
    resp = await server.get("/api/v1/metadata/tenants")
    return resp
```

---

## 8. LakeMindServer 包结构

### 8.1 目录结构

```
LakeMindServer/
├── docker-compose.yml          # 基础设施编排（保留）
├── .env
├── pyproject.toml              # 新增：REST API 服务依赖
├── Dockerfile                  # 新增：REST API 服务镜像
├── config/
│   ├── engines.yaml            # 引擎插件配置
│   ├── seaweedfs/s3.json
│   └── versions.yaml
├── docker/
│   └── postgres-age/           # PG 镜像（保留）
├── src/lakemind_server/
│   ├── __init__.py
│   ├── __main__.py             # uvicorn 入口
│   ├── app.py                  # FastAPI 应用
│   ├── config.py               # 配置加载
│   ├── auth.py                 # 内部 API Key 认证
│   ├── tenant.py               # 租户上下文（从 Header 提取）
│   ├── health.py               # 全引擎健康聚合
│   ├── plugins/
│   │   ├── registry.py         # 插件注册表
│   │   ├── protocols.py        # 10 个 Protocol 定义
│   │   ├── storage/
│   │   │   ├── object/
│   │   │   │   ├── seaweedfs.py
│   │   │   │   ├── aws_s3.py
│   │   │   │   ├── aliyun_oss.py
│   │   │   │   └── huawei_obs.py
│   │   │   ├── tabular/
│   │   │   │   └── iceberg.py
│   │   │   ├── vector/
│   │   │   │   └── lancedb.py
│   │   │   ├── kv/
│   │   │   │   ├── dragonfly.py
│   │   │   │   └── redis.py
│   │   │   ├── graph/
│   │   │   │   ├── postgres_graph.py
│   │   │   │   └── age.py
│   │   │   └── metadata/
│   │   │       └── postgres.py
│   │   ├── compute/
│   │   │   ├── sql/
│   │   │   │   ├── duckdb.py
│   │   │   │   └── daft.py
│   │   │   └── distributed/
│   │   │       ├── embedded.py
│   │   │       └── ray.py
│   │   └── cognitive/
│   │       ├── embedding/
│   │       │   ├── fastembed.py
│   │       │   └── external.py
│   │       └── memory/
│   │           ├── basic.py
│   │           └── mem0.py
│   └── api/
│       ├── objects.py          # /storage/objects 路由
│       ├── tables.py           # /storage/tables 路由
│       ├── vectors.py          # /storage/vectors 路由
│       ├── kv.py               # /storage/kv 路由
│       ├── graph.py            # /storage/graph 路由
│       ├── sql.py              # /compute/sql 路由
│       ├── jobs.py             # /compute/jobs 路由
│       ├── embedding.py        # /cognitive/embedding 路由
│       ├── memory.py           # /cognitive/memory 路由
│       ├── metadata.py         # /metadata/* 路由
│       └── system.py           # /system/* 路由
├── scripts/
│   └── verify_api.py           # REST API 验证脚本
└── data/                       # 持久化（保留）
```

### 8.2 依赖

```toml
[project]
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "httpx>=0.27",
    # 引擎依赖（全部移到 Server）
    "boto3>=1.34",
    "redis>=5.0",
    "psycopg2-binary>=2.9",
    "pyarrow>=15.0",
    "pyiceberg[pyarrow,sql-postgres]>=0.11",
    "lancedb>=0.33",
    "pylance>=1.2",
    "duckdb>=1.0",
    "fastembed>=0.4",
]
```

---

## 9. docker-compose 改造

```yaml
services:
  # ... seaweedfs / postgres / dragonfly 保留 ...

  # 新增：REST API 服务
  server-api:
    build: .
    container_name: lakemind-server-api
    environment:
      LAKE_CONFIG: /etc/lakemind/engines.yaml
      API_KEY: "${SERVER_API_KEY:-lakemind-internal-api-key}"
    ports:
      - "10823:10823"
    volumes:
      - ./config/engines.yaml:/etc/lakemind/engines.yaml:ro
      - ./data/lance:/data/lance        # Lance 共享目录
    networks: [lakemind]
    restart: unless-stopped
    depends_on:
      - postgres
      - seaweedfs
      - dragonfly
```

3 个 MCP 的 docker-compose 各加环境变量：

```yaml
environment:
  SERVER_API_URL: "http://lakemind-server-api:10823"
  SERVER_API_KEY: "${SERVER_API_KEY:-lakemind-internal-api-key}"
```

---

## 10. 实施计划

> 总原则：**先完成 API 开发 → 再对 API 全面验证测试（功能 + 性能）→ 再改造 MCP → 再完整验证测试**
>
> 四阶段串行，每阶段全部通过才进入下一阶段。

### 10.1 阶段一：API 开发

| 步 | 内容 | 产出 |
|----|------|------|
| 1 | 创建 LakeMindServer REST API 骨架：FastAPI 应用 + 配置加载 + 内部 API Key 认证 + 租户上下文 | 服务可启动 :10823 |
| 2 | 定义 10 个引擎插件 Protocol（`plugins/protocols.py`） | Protocol 接口定义 |
| 3 | 实现插件注册表（`plugins/registry.py`）+ `build_engine()` 工厂 | 注册表 + 配置驱动加载 |
| 4 | 实现 5 个存储引擎基线插件：ObjectStorage(SeaweedFS)、TabularStorage(Iceberg)、VectorStorage(LanceDB)、KVStorage(Dragonfly)、GraphStorage(PG) | 从 MCP 现有 engines/ 迁移代码 |
| 5 | 实现 MetadataStore 插件（PG，含连接池） | 从 AdminMCP admin.py 迁移 |
| 6 | 实现 2 个计算引擎基线插件：SQLCompute(DuckDB)、DistributedCompute(Embedded) | DuckDB 修复签名问题 |
| 7 | 实现 2 个认知引擎基线插件：Embedding(fastembed)、Memory(Basic) | 从 AssetMCP 迁移 |
| 8 | 实现 11 个 API 域全部路由：storage/{objects,tables,vectors,kv,graph} + compute/{sql,jobs} + cognitive/{embedding,memory} + metadata + system | 全端点可调用 |
| 9 | 编写 `config/engines.yaml` 基线配置 + 全部切换示例注释 | 配置文件 |
| 10 | 编写 Dockerfile + docker-compose 加 server-api 服务 | 容器可构建启动 |

**阶段一完成标志**：`lakemind-server-api` 容器在 :10823 运行，`/api/v1/system/health` 返回全部引擎 health=true。

### 10.2 阶段二：API 全面验证测试

| 步 | 内容 | 验证脚本 |
|----|------|---------|
| 11 | 编写 REST API 功能验证脚本 `verify_api.py`：覆盖全部端点、全部引擎 | `scripts/verify_api.py` |
| 12 | 运行功能验证：11 个域 × 全部 CRUD 操作 | 全端点 PASS |
| 13 | 编写 REST API 性能基准脚本 `benchmark_api.py`：逐操作测延迟 | `scripts/benchmark_api.py` |
| 14 | 运行性能基准：对照 §6.2 基线性能指标，记录实际延迟 | 全操作达标 |
| 15 | 编写并发测试：20 线程 × 50-150 次操作 | 并发无错误 |
| 16 | 编写可插拔验证：切换 kv plugin 配置，验证不报错 | 配置切换有效 |

**阶段二完成标志**：`verify_api.py` 全 PASS + `benchmark_api.py` 全达标 + 并发测试 PASS + 可插拔验证 PASS。

### 10.3 阶段三：改造 MCP

| 步 | 内容 | 验证 |
|----|------|------|
| 17 | 实现 MCP 共用 REST 客户端 `ServerClient`（httpx + 内部 API Key + 租户 Header） | 连通 :10823 |
| 18 | 改造 AssetMCP：移除 `engines/` 目录，全部 tools/resources 改用 ServerClient | 工具接口不变 |
| 19 | 改造 DataMCP：移除 `engines/` 目录，13 个透传工具改用 ServerClient | 工具接口不变 |
| 20 | 改造 AdminMCP：移除直连 PG，15 个管理工具改用 ServerClient | 工具接口不变 |
| 21 | 更新 3 个 MCP 的 docker-compose（加 SERVER_API_URL + SERVER_API_KEY 环境变量） | 容器重建 |
| 22 | 删除 MCP 中旧引擎代码（`engines/` 目录、引擎依赖从 pyproject.toml 移除） | 代码清理 |

**阶段三完成标志**：3 个 MCP 不再直连任何引擎，全部通过 ServerClient 调 REST API，MCP pyproject.toml 不含引擎依赖。

### 10.4 阶段四：完整验证测试

| 步 | 内容 | 验证脚本 |
|----|------|---------|
| 23 | 运行全量功能测试 `test_full_suite.py`（69 项） | 69/69 PASS |
| 24 | 运行三 MCP 联合验证 `verify_three_mcp.py`（22 项） | 22/22 PASS |
| 25 | 运行 Monitor 验证 `verify_monitor.py`（18 项） | 18/18 PASS |
| 26 | 运行 Steward 巡检 + 对话验证 | 巡检 + 对话正常 |
| 27 | 端到端延迟对比：MCP → REST API → 引擎 vs 基线性能 | 延迟增量 < 2ms |
| 28 | 全容器健康检查（9 容器） | 全 Up |

**阶段四完成标志**：全部验证脚本 PASS，端到端延迟达标，9 容器全部运行。

### 10.5 实施时间线

```
阶段一（API 开发）        步 1-10   ████████░░  预计 2-3 天
阶段二（API 验证测试）    步 11-16  ███░░░░░░  预计 1 天
阶段三（改造 MCP）        步 17-22  █████░░░░  预计 1-2 天
阶段四（完整验证测试）    步 23-28  ██░░░░░░░  预计 0.5 天
```

### 10.6 兼容性

- REST API 版本前缀 `/api/v1/`，未来变更可加 `/api/v2/`
- MCP 改造后对外接口（工具名、参数、返回值）不变，Agent 无感知
- 引擎配置 `engines.yaml` 独立于 MCP 配置，MCP 只需知道 `SERVER_API_URL`

### 10.7 风险与缓解

| 风险 | 缓解 |
|------|------|
| REST API 成为单点 | 生产阶段可多副本 + Nginx 负载均衡 |
| 额外 HTTP 跳增加延迟 | 本机 HTTP ~1-2ms，可接受；未来可用 Unix socket 优化 |
| 引擎连接集中到 Server | 连接池管理更高效，总体连接数减少 |
| 迁移期间双份代码 | 阶段三完成后删除旧引擎代码；阶段一二期间 MCP 仍用旧引擎，Server API 独立验证 |

---

## 11. 验收标准

- [ ] LakeMindServer REST API 在 :10823 运行
- [ ] 10 个基线插件全部实现且 health() = true
- [ ] 全部 REST API 端点可用（`verify_api.py` PASS）
- [ ] REST API 性能基准达标（`benchmark_api.py` 对照 §6.2 基线）
- [ ] 并发测试通过（20 线程 × 50-150 次）
- [ ] 引擎可插拔验证通过（切换 kv plugin 配置不报错）
- [ ] 3 个 MCP 改造为 REST 客户端，不再直连引擎
- [ ] MCP 对外接口不变（工具名、参数、返回值）
- [ ] 全量功能测试 69/69 PASS
- [ ] 三 MCP 联合验证 22/22 PASS
- [ ] Monitor 验证 18/18 PASS
- [ ] 端到端延迟增量 < 2ms
- [ ] 9 容器全部 Up
- [ ] `engines.yaml` 包含全部切换示例注释（AWS / 阿里云 / 华为云 / Redis / Ray / mem0）

---

> 批准后按 §10.1-10.4 四阶段顺序实施，每阶段全部通过才进入下一阶段。
