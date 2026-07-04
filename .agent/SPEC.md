# SPEC.md — LakeMind 开发规范

> 本文件是 LakeMind 项目的工程开发规范，所有贡献者必须遵守。

---

## 1. 仓库结构规范

### 1.1 Monorepo 布局

```
LakeMind/
├── .agent/                      # 开发规范与状态文档（本目录）
│   ├── SPEC.md                  # 开发规范（本文件）
│   ├── DESIGN.md                # 设计规范
│   └── STATE.md                 # 项目开发进展状态
├── LakeMindServer/              # 数据平面（存储底座）
├── LakeMindAssetMCP/            # 运行平面 - 资产面 MCP
├── LakeMindDataMCP/             # 运行平面 - 数据面 MCP
├── LakeMindAdminMCP/            # 运行平面 - 管理面 MCP
├── LakeMindSteward/             # 运行平面 - 运维 Agent
├── LakeMindMonitor/             # 运行平面 - 只读仪表板
├── LakeMindStudio/              # 开发平面 - 桌面客户端
├── scripts/                     # 跨包验证脚本
├── AGENTS.md                    # AI Agent 协作约定
└── README.md                    # 项目总览
```

### 1.2 包命名规则

- 目录名：`LakeMind{Plane}`，PascalCase
- Python 包名：`lakemind_{plane}_mcp`（下划线，小写）
- Docker 容器名：`lakemind-{plane}-mcp`（连字符，小写）
- Docker 镜像名：`lakemind/{plane}-mcp:latest`

### 1.3 跨包依赖规则

| 规则 | 说明 |
|------|------|
| 运行平面 → 数据平面 | 只通过 S3 / PostgreSQL / Dragonfly 接口，不直连内部文件 |
| 运行平面 → 运行平面 | 只通过 MCP 协议（JSON-RPC over HTTP） |
| Monitor → MCP | 只读代理，不引入额外业务逻辑 |
| Steward → MCP | 通过 MCP 客户端 SDK，持多面 Token |
| **禁止** | 跨包直连内部存储（绕过 MCP 协议） |

---

## 2. Python 开发规范

### 2.1 版本与风格

- Python **3.12**（容器）/ ≥3.11（本地开发兼容）
- 类型标注：全部函数签名必须标注返回类型
- 数据模型：使用 Pydantic v2
- 配置：YAML + Pydantic Settings，支持 `${ENV_VAR}` 插值
- 异步：MCP 工具用 `async def`，引擎适配层用同步（嵌入式引擎均为同步）

### 2.2 包结构（以 AssetMCP 为例）

```
src/lakemind_asset_mcp/
├── __init__.py
├── __main__.py             # 入口：uvicorn 启动
├── server.py               # FastMCP 组装 + 中间件
├── config.py               # Pydantic 配置模型
├── context.py              # contextvars（Identity / TenantContext）
├── health.py               # 健康探活
├── engines/                # 引擎适配层（一个引擎一个文件）
├── security/               # 认证 + 审计
├── tools/                  # MCP 工具（写操作）
│   └── _helpers.py         # @audited / require_scope 装饰器
├── resources/              # MCP 资源（只读）
└── assets/                 # 资产定义（仅 AssetMCP）
    ├── registry.py
    ├── native/*.yaml       # 声明式资产定义
    └── engine_patterns/    # 预置引擎模式
```

### 2.3 pyproject.toml 规范

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "lakemind-asset-mcp"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.28,<2",
    "pydantic>=2.7",
    # ... 引擎依赖
]

[project.scripts]
lakemind-asset-mcp = "lakemind_asset_mcp.__main__:main"
```

### 2.4 代码约定

- **不加注释**，除非逻辑非显而易见
- 标识符用英文，设计文档 / 架构注释用中文
- 不引入未在 pyproject.toml 声明的依赖
- 不引入闭源依赖（技术栈锁定全开源 Apache 2.0 / MIT / BSD）
- 日志用 structlog，敏感字段脱敏（token / password / secret / api_key / content）

### 2.5 引擎适配层规范

每个引擎一个文件，暴露最小接口：

```python
class S3Client:
    def __init__(self, endpoint, access_key, secret_key, region): ...
    async def get(self, uri: str) -> bytes: ...
    async def put(self, uri: str, body: bytes) -> str: ...

class IcebergClient:
    def __init__(self, catalog_name, warehouse, sql_uri): ...
    def load_catalog(self): ...
    def create_table(self, name, schema): ...
    def append(self, table, rows): ...
    def scan(self, table, columns, filter, limit): ...
```

- 引擎在 MCP 进程内运行（嵌入式），不需要独立容器
- 重计算提交 Ray（生产阶段），MVP 走嵌入式
- `build_engines(config)` 聚合为 `Engines` dataclass，在 server.py 中注入

---

## 3. MCP 服务规范

### 3.1 FastMCP 组装模式

```python
mcp = FastMCP("LakeMindAssetMCP", stateless=True)

# 认证中间件
mcp.custom_middleware = AuthMiddleware(tokens, required_scope="asset")

# 注册工具
@mcp.tool()
async def search_knowledge(kb: str, query: str, top_k: int = 5): ...

# 注册资源
@mcp.resource("lake://knowledge")
async def knowledge_list(): ...
```

### 3.2 工具命名

- `search_*` — 语义检索
- `ingest_*` — 批量写入
- `register_*` — 创建实例
- `data_*` — 数据面透传
- `create_*` / `update_*` / `delete_*` / `list_*` — 管理面 CRUD
- `get_*` — 只读查询

### 3.3 资源 URI 约定

| URI | 说明 |
|-----|------|
| `lake://capabilities` | 资产能力图（所有注册的资产类型 + 操作） |
| `lake://workspace` | 工作区信息 |
| `lake://system/health` | 系统健康 |
| `lake://knowledge` | 知识库列表 |
| `lake://knowledge/{id}` | 知识库详情 |
| `lake://skills` | 技能列表 |
| `lake://memory` | 记忆概况 |
| `lake://ontology` | 本体列表 |

### 3.4 认证与 Scope

- Bearer Token 认证，Token 携 `tenant_id` + `scopes`
- 每个 MCP 只接受对应 scope 的 Token：

| MCP | Required Scope |
|-----|---------------|
| AssetMCP | `asset` |
| DataMCP | `data` |
| AdminMCP | `admin` |

- Token 由 AdminMCP 签发，存 PostgreSQL
- MVP 兼容配置文件静态 Token

### 3.5 租户隔离

| 层 | 隔离方式 |
|----|----------|
| S3 | key 前缀 `{tenant_id}/` |
| Iceberg | namespace `{tenant_id}_{domain}` |
| LanceDB | 每租户独立 database |
| Dragonfly | key 前缀 `{tenant_id}:` |
| PostgreSQL | 行级 `tenant_id` 列（应用层过滤） |

---

## 4. 声明式资产规范

### 4.1 YAML 结构

```yaml
type: knowledge                    # 资产类型标识（唯一）
description: "知识库"               # 人类可读描述
resource_root: "lake://knowledge"  # MCP 资源根 URI
capabilities: [search, ingest]     # 能力声明

storage:                           # 存储映射
  vector:                          # 向量存储
    engine: lancedb
    schema: { ... }
  metadata:                        # 元信息存储
    engine: iceberg
    schema: { ... }

operations:                        # 操作定义
  search:
    engine: vector_topk            # 预置引擎模式
    params: [kb, query, top_k=5, filter?]
  ingest:
    engine: embed_and_write
    params: [kb, documents]

embedding: default                 # embedding 配置
```

### 4.2 预置引擎模式

| 模式 | 说明 |
|------|------|
| `vector_topk` | 向量 top-k 检索（LanceDB） |
| `embed_and_write` | embedding + 写向量表 |
| `keyword_search` | 关键词全文检索 |
| `graph_query` | 图查询（PG graph） |
| `graph_update` | 图更新 |
| `kv_ttl` | TTL KV 读写（Dragonfly） |
| `table_query` | Iceberg 表查询 |
| `table_append` | Iceberg 表追加 |
| `mem0` | 记忆智能引擎（延迟实现） |

### 4.3 资产扩展

- 新增资产类型：写 YAML → 放 `extension/` 或通过 AdminMCP `register_asset_type` 注册
- 不需要写代码（除非用 `engine: custom` + `handler`）
- AssetMCP 热加载：从 PG 重新加载全部定义

---

## 5. Docker 规范

### 5.1 Dockerfile 约定

- Python 包：`python:3.12-slim` 基镜像
- Node 包：`node:20-alpine` 基镜像
- BuildKit 禁用：`$env:DOCKER_BUILDKIT=0`（Windows 环境兼容）
- 多阶段构建仅在有编译步骤时使用

### 5.2 docker-compose 约定

- `name: lakemind`（统一项目名）
- 外部网络：`lakemind_lakemind`（由 LakeMindServer 创建）
- 持久化：bind mount 到 `./data/`（不用 named volume）
- `restart: unless-stopped`
- Ray 服务用 `profiles: [ray]`（默认不启动）

### 5.3 启动顺序

```
1. LakeMindServer      (docker compose --env-file .env up -d)
2. LakeMindAssetMCP    (docker compose up -d --build)
3. LakeMindDataMCP     (docker compose up -d --build)
4. LakeMindAdminMCP    (docker compose up -d --build)
5. LakeMindSteward     (docker compose up -d --build)
6. LakeMindMonitor     (docker compose up -d --build)
```

---

## 6. 验证规范

### 6.1 验证脚本约定

- 脚本放各包 `scripts/` 目录或根 `scripts/`
- 输出格式：`PASS/FAIL` 逐项 + 最终 `Result: N passed, M failed`
- 退出码：0 = 全通过，1 = 有失败
- 超时：单项 30s，巡检类 60s

### 6.2 验证矩阵

| 验证 | 脚本 | 范围 | 当前结果 |
|------|------|------|---------|
| PG catalog | `LakeMindServer/scripts/verify_pg_catalog.py` | PyIceberg + PG | 8/8 PASS |
| AssetMCP | `LakeMindAssetMCP/scripts/verify_asset_mcp.py` | 11 tools + 7 resources | 8/8 PASS |
| 三 MCP 联合 | `scripts/verify_three_mcp.py` | 全部 MCP + scope 隔离 | 22/22 PASS |
| Monitor | `LakeMindMonitor/scripts/verify_monitor.py` | 14 API 路由 + 页面 | 18/18 PASS |
| 端到端 | 待编写 | 200 Agent 并发 | 未开始 |

### 6.3 验证流程

每次完成一个步骤后：
1. 运行该步骤的验证脚本
2. 全部 PASS 才能进入下一步
3. 验证结果记录到 `.agent/STATE.md`

---

## 7. 技术栈锁定

**除非用户明确要求，不引入替代品或闭源依赖。**

| 组件 | 选型 | PyPI 包名 |
|------|------|-----------|
| 对象存储 | SeaweedFS | — |
| 统一数据库 | PostgreSQL 16 | `psycopg2-binary` |
| 表格式 | Apache Iceberg | `pyiceberg[pyarrow,sql-postgres]` |
| 向量/多模态 | PyLance + LanceDB | `pylance`, `lancedb` |
| 缓存 | Dragonfly | `redis`（Redis 兼容协议） |
| 即席计算 | DuckDB | `duckdb` |
| Embedding | fastembed | `fastembed` |
| MCP SDK | FastMCP | `mcp` |
| Agent 框架 | LangGraph | `langgraph` |
| Web 框架 | FastAPI（Steward）/ Express（Monitor） | — |

### 延迟项（不阻塞 MVP）

| 项 | 原因 | 替代方案 |
|----|------|---------|
| Ray 集群 | 镜像过大 | 嵌入式引擎 |
| AGE 图扩展 | 编译超时 | PG 原生表 graph_nodes/graph_edges |
| mem0 记忆引擎 | 需 LLM | 基础 remember/recall/forget |
| Apache Ranger | 生产阶段 | 应用层过滤 |

---

## 8. 文档规范

- 设计文档用中文，代码标识符用英文
- 新增设计说明倾向中文以保持一致
- 文档名为非 ASCII 中文时，PowerShell 下需设置 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
- 不主动创建 README.md / 文档文件，除非明确要求
- 权威文档：`LakeMind MVP阶段技术改造方案.md`（v3，已批准）
