# LakeMindMCP 开发方案（MVP）

> 本文件为开发执行方案，依据《LakeMindMCP设计方案MVP.md》《LakeMind简介.md》及 LakeMindServer 现状制定。
> 4 项关键决策（已确认）：
> 1. 实现语言：**Python**（与嵌入式引擎同语言，进程内直连）
> 2. Embedding：**统一接外部 embedding 服务**（HTTP），不引入本地模型/不打包 torch。定义 `EmbeddingProvider` 接口，默认 `OpenAICompatibleProvider`（OpenAI 兼容协议，可指向 OpenAI 官方或任意自托管 embedding 服务），由配置指定 endpoint/model/api_key/dim
> 3. 元数据：**PyIceberg 直连 S3 读写 + Gravitino REST 8090 资源发现/admin 注册**（与 verify_scenario.py 基线一致，REST 9001 仅探活）
> 4. 方案落盘：本文件

---

## 1. 技术选型与依赖

### 1.1 运行时
| 项 | 选型 | 说明 |
|----|------|------|
| 语言 | Python 3.11+ | 与 LakeMindServer 嵌入式引擎一致（验证基线 3.14.4） |
| MCP SDK | `mcp` 官方 Python SDK | Streamable HTTP transport |
| ASGI | `uvicorn` | 承载 MCP HTTP 端点 |
| 配置 | `pydantic-settings` + YAML | Token 映射、引擎地址、租户规则、embedding |
| 日志/审计 | `structlog` | JSON 结构化输出 |

### 1.2 引擎客户端（引擎适配层，对应 LakeMindServer）
| 引擎 | 库 | 用途 |
|------|----|------|
| SeaweedFS | `boto3` | S3 兼容 IO（Iceberg/Lance/Skill 文件） |
| Iceberg | `pyiceberg[pyarrow]` | 结构化表 + 元信息小表，SQL catalog 直连 S3 |
| Gravitino | `httpx` | REST 8090：Metalake/Catalog/Fileset 发现与 admin 注册 |
| LanceDB | `lancedb` + `lance` | 向量检索（Knowledge/Memory/Skill 语义） |
| Dragonfly | `redis` | 短期记忆 TTL KV（Redis 兼容） |
| 即席计算 | `duckdb` | `execute_sql` 工具走 DuckDB 读 Arrow |
| Arrow | `pyarrow` | 引擎互操作内存格式 |
| Embedding | `httpx` | 外部 embedding 服务（OpenAI 兼容协议），不打包本地模型 |

> 依赖与 `LakeMindServer/config/versions.yaml` 配套表保持一致，升级前先对照该表。

### 1.3 与 LakeMindServer 的关系
- MCP 容器加入 LakeMindServer 的 `lakemind` 外部网络，通过容器名访问 `lakemind-seaweedfs:8333` / `lakemind-gravitino:8090` / `lakemind-dragonfly:6379`。
- Lance 共享卷：挂载 `LakeMindServer/data/lance` 到 MCP 容器同一路径（多 Agent 共享同一 Lance 目录，与方案约定一致）。
- 嵌入式引擎（PyIceberg/LanceDB/DuckDB）在 MCP 进程内运行，不起独立容器。

---

## 2. 目录结构

```
LakeMindMCP/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml          # 仅 MCP 服务，external network: lakemind
├── config/
│   └── config.example.yaml     # Token 映射 / 引擎地址 / 租户规则 / embedding
├── src/lakemindmcp/
│   ├── __main__.py             # 入口：uvicorn -> MCP server
│   ├── server.py               # 组装：注册 resources + tools，挂载安全层
│   ├── config.py               # Pydantic Settings + YAML 加载
│   ├── context.py              # TenantContext（agent_id/tenant_id/scopes），请求级
│   ├── security/
│   │   ├── auth.py             # Bearer Token -> Identity
│   │   ├── tenant.py           # 租户路径/key 注入（S3 前缀、Catalog、LanceDB db、Dragonfly db）
│   │   └── audit.py            # 工具调用审计（脱敏 JSON）
│   ├── assets/
│   │   ├── registry.py         # AssetType 注册表 + 能力图
│   │   ├── base.py             # Asset 抽象基类
│   │   └── native/
│   │       ├── data.py
│   │       ├── knowledge.py
│   │       ├── memory.py
│   │       ├── skill.py
│   │       ├── experience.py
│   │       └── ontology.py     # 已注册，返回"暂未启用"
│   ├── engines/                # 引擎适配层：上层不出现具体引擎名
│   │   ├── s3.py
│   │   ├── iceberg.py
│   │   ├── gravitino.py
│   │   ├── lancedb.py
│   │   ├── dragonfly.py
│   │   └── embedding.py        # EmbeddingProvider 接口 + SentenceTransformer/OpenAI 实现
│   ├── resources/
│   │   ├── router.py           # lake:// URI 路由
│   │   └── system.py           # lake://capabilities, lake://workspace
│   ├── tools/
│   │   ├── router.py           # 工具名路由 + scope 校验
│   │   ├── data.py
│   │   ├── knowledge.py
│   │   ├── memory.py
│   │   ├── skill.py
│   │   ├── experience.py
│   │   └── admin.py            # admin 域，仅 Steward scope
│   └── transports/
│       └── http.py             # Streamable HTTP
├── tests/
│   ├── unit/
│   └── integration/            # 需 LakeMindServer 在跑
├── scripts/
│   └── verify_mcp.py           # MCP 端到端验证（首 Agent 读写数据湖）
└── docs/
    ├── api.md                  # MCP 工具与资源 API 文档
    ├── agent_quickstart.md     # 示例 Agent 接入教程
    └── admin.md                # 管理员手册
```

> 核心约束（设计稿§2）：`assets/` 与 `tools/`、`resources/` 只与 Asset 抽象交互，`engines/` 负责翻译为具体引擎调用。上层代码不出现 `LanceDB`、`Redis`、`PyIceberg` 等具体实现名。

---

## 3. 核心抽象

### 3.1 AssetType 注册表（设计稿§3.1）
```python
@dataclass
class AssetType:
    type: str                       # data | knowledge | memory | skill | experience | ontology
    description: str
    schema: dict                    # 元数据结构
    resource_root: str              # lake://data ...
    capabilities: list[str]         # query, insert, merge, search, remember ...
    lifecycle: list[str] | None     # draft/published/archived（MVP 不强制）
```
`registry.py` 启动时注册 6 种内置类型，`lake://capabilities` 直接序列化该注册表。

### 3.2 Asset 抽象基类
```python
class Asset(ABC):
    type: AssetType
    async def list(self, ctx) -> list[AssetMeta]: ...
    async def describe(self, name_or_id, ctx) -> AssetMeta: ...
    # 具体能力方法由子类按 capabilities 实现
```
每个 `native/*.py` 持有对应引擎适配器引用，但通过依赖注入，不硬编码引擎类名。

### 3.3 EmbeddingProvider 接口
```python
class EmbeddingProvider(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```
- 唯一内置实现 `OpenAICompatibleProvider`：走 OpenAI 兼容 `/v1/embeddings` 协议，可指向：
  - OpenAI 官方（`https://api.openai.com/v1`，model=`text-embedding-3-small`，dim=1536）
  - 任意自托管服务（vLLM / TEI / Infinity / Infinity-Parquet 等，配置 base_url 即可）
- 由配置 `embedding.{base_url, model, api_key, dim}` 指定，向量列 dim 跟随配置。
- 不引入 `sentence-transformers`/`torch`，镜像保持轻量。

### 3.4 TenantContext（设计稿§5.2）
请求进入安全层后注入，全链路自动隔离：
| 层 | 隔离 |
|----|------|
| S3 | key 前缀 `{tenant_id}/` |
| Iceberg catalog | namespace 前缀 `{tenant_id}_` |
| LanceDB | database 名 `tenant_{tenant_id}` |
| Dragonfly | DB 编号 `hash(tenant_id) % 16` |

---

## 4. 资源与工具清单（对齐设计稿§4）

### 4.1 系统资源
| URI | 说明 |
|-----|------|
| `lake://capabilities` | 资产类型 → capabilities 映射 |
| `lake://workspace` | 租户上下文：Catalog、推荐资产、命名规范、当前会话 |

### 4.2 各资产资源/工具
| 资产 | 资源 | 工具 | Scope |
|------|------|------|-------|
| Data | `lake://data`、`lake://data/{name}` | `query_table`、`write_table`、`execute_sql` | data |
| Knowledge | `lake://knowledge`、`lake://knowledge/{id}` | `search_knowledge` | data |
| Memory | `lake://memory` | `remember`、`recall`、`forget` | data |
| Skill | `lake://skills`、`lake://skills/{id}` | `search_skill` | data |
| Experience | `lake://experience`、`lake://experience/{id}` | `record_experience` | data |
| Ontology | `lake://ontology` | （无） | — 返回"暂未启用" |

### 4.3 Admin 工具（仅 Steward，scope=admin）
`register_knowledge`、`create_dataset`、`register_skill`、`optimize_asset`、`get_system_health`

### 4.4 工具签名（关键几个）
```python
query_table(table: str, columns: list[str]|None, filter: str|None, limit: int=100) -> list[dict]
write_table(table: str, rows: list[dict], mode: str="append") -> WriteResult
execute_sql(sql: str) -> list[dict]                      # DuckDB 即席
search_knowledge(fileset: str, query: str, top_k: int=5, filter: dict|None) -> list[Hit]
remember(content: str, context: dict|None, ttl: int|None) -> MemId           # 短期走 Dragonfly，长期走 Lance+Iceberg
recall(query: str, limit: int=5) -> list[Memory]
forget(query: str|None) -> int                            # 返回删除条数
search_skill(query: str) -> list[SkillSummary]
record_experience(type: str, content: str, tags: list[str]|None) -> ExpId   # type ∈ success/failure/reflection
```

> Memory 的 `remember/recall/forget` 在适配层协同 Dragonfly（短期、带 TTL）与 Lance+Iceberg（长期、双表 lance_uri 关联），Agent 无感知（设计稿§4.4）。长期记忆严格采用 Lance 向量 + Iceberg 小表双表设计，`lance_uri` 关联，不合并单表（AGENTS.md）。

---

## 5. 安全与多租户

- **Token 认证**（设计稿§5.1）：静态 Token 配置在 `config.yaml`，映射 `{token -> agent_id, tenant_id, scopes}`。MVP 两 Token：业务 Agent（scope=data）+ Steward（scope=admin）。
- **Authorization: Bearer `<token>`** 在 HTTP 层校验，失败 401。
- **Scope 校验**：`tools/router.py` 在分发前校验 `tool.scope ⊆ ctx.scopes`，admin 工具仅 Steward 可调。
- **租户注入**：安全层构造 `TenantContext`，引擎适配层据此拼路径/库名，Agent 无感知。
- **审计**（设计稿§5.3）：每次工具调用记录 `timestamp, agent_id, tenant_id, tool, arguments(脱敏)`，structlog JSON 输出。

---

## 6. 性能与可靠性（设计稿§6）
- 无状态：可水平扩展（MVP 单实例）
- 引擎连接池：boto3/httpx/redis 连接复用
- 元数据缓存：资产列表缓存 30s（TTL，按租户）
- 熔断：后端不可用快速失败，返回 MCP 错误而非挂起
- 流式：大结果集走 MCP 流式 Resource（Phase 2 增强，MVP 先非流式跑通）

---

## 7. 部署与配置

### 7.1 docker-compose.yml（MCP 服务）
```yaml
services:
  lakemind-mcp:
    build: .
    container_name: lakemind-mcp
    environment:
      LAKE_CONFIG: /etc/lakemind/config.yaml
    ports: ["${MCP_PORT:-8400}:8400"]
    volumes:
      - ./config/config.yaml:/etc/lakemind/config.yaml:ro
      - ../LakeMindServer/data/lance:/data/lance        # 共享 Lance 卷
    networks: [lakemind]
    restart: unless-stopped
networks:
  lakemind:
    external: true
    name: lakemind        # 复用 LakeMindServer 创建的网络
```

### 7.2 config.example.yaml（关键字段）
```yaml
server:
  host: 0.0.0.0
  port: 8400
engines:
  s3:    {endpoint: "http://lakemind-seaweedfs:8333", access_key: admin, secret_key: admin123456, region: us-east-1}
  gravitino: {uri: "http://lakemind-gravitino:8090", metalake: lakemind_metalake}
  dragonfly: {host: lakemind-dragonfly, port: 6379, password: ""}
  lance:  {uri: "/data/lance"}
  iceberg:
    catalog: lakemind
    warehouse: "s3://lakemind-iceberg/warehouse"
embedding:
  provider: openai_compatible
  base_url: https://api.openai.com/v1     # 或自托管: http://embedding-svc:8080/v1
  model: text-embedding-3-small
  api_key: ${EMBEDDING_API_KEY}
  dim: 1536
tokens:
  - token: "<business-agent-token>"
    agent_id: agent-business-01
    tenant_id: retail
    scopes: [data]
  - token: "<steward-token>"
    agent_id: steward
    tenant_id: platform
    scopes: [admin, data]
```

---

## 8. 分阶段开发任务

| Phase | 内容 | 产出 | 验收 |
|-------|------|------|------|
| **P0 骨架** | pyproject、Dockerfile、compose、config 模型、入口、健康端点 | 容器可起，`/health` 200 | `docker compose up` 成功 |
| **P1 引擎适配层** | s3/iceberg/gravitino/lancedb/dragonfly/embedding 客户端 + 连接池 | 各 client 单测可连 LakeMindServer | 复用 verify_scenario 基线 |
| **P2 安全层** | Bearer 认证、TenantContext、scope 校验、审计 | 401/403 路径正确 | 单测覆盖 |
| **P3 资产注册表 + 系统资源** | registry、capabilities/workspace 资源 | `lake://capabilities` 返回能力图 | 资源读测 |
| **P4 Data 资产** | 资源 `lake://data[/name]` + 工具 query_table/write_table/execute_sql | Agent 可查/写/SQL | 集成测：建表→写→查 |
| **P5 Knowledge 资产** | 资源 + search_knowledge（LanceDB 向量 + S3 取原文） | RAG 检索→原文 | 集成测 |
| **P6 Memory 资产** | remember/recall/forget（Dragonfly 短期 + Lance/Iceberg 长期双表） | 记忆写入/召回/遗忘 | 集成测：双表 lance_uri 关联 |
| **P7 Skill 资产** | 资源（含 read 文件内容）+ search_skill | 语义检索 + 加载代码 | 集成测 |
| **P8 Experience 资产** | record_experience（success/failure/reflection） | 经验记录可回查 | 集成测 |
| **P9 Admin 工具域** | register_knowledge/create_dataset/register_skill/optimize_asset/get_system_health | Steward 可注册资产 | scope=admin 测 |
| **P10 Ontology 占位** | 注册类型，资源返回"暂未启用" | 能力图含 ontology | 资源读测 |
| **P11 集成验证 + 文档** | verify_mcp.py、api.md、agent_quickstart.md、admin.md | **首 Agent 经 MCP 读写数据湖成功** | verify_mcp PASS |

### 里程碑
- **M1（P0–P4）**：首个业务 Agent 通过 MCP 成功读写结构化数据 —— 对齐简介"首要任务"
- **M2（P5–P8）**：5 个数据域工具全可用
- **M3（P9–P11）**：admin 域 + 验证脚本 + 文档，MVP 交付

---

## 9. 验收标准

1. `docker compose up`（LakeMindServer + LakeMindMCP）全部健康。
2. `python scripts/verify_mcp.py` 全 PASS，覆盖：
   - Token 认证失败返回 401；跨 scope 调 admin 返回 403
   - 业务 Agent 经 MCP：建数据集 → 写数据 → query_table → execute_sql
   - search_knowledge → 返回原文
   - remember → recall → forget
   - search_skill → 加载代码
   - record_experience
   - 租户隔离：A 租户不可见 B 租户数据
3. `lake://capabilities` 返回 6 种资产类型，ontology 标注"暂未启用"。
4. 审计日志 JSON 格式、含脱敏 arguments。

---

## 10. 交付清单（对齐设计稿§8）
- [ ] 源代码（Apache 2.0，pyproject 声明 license）
- [ ] Docker 镜像 + docker-compose 模板
- [ ] MCP 工具与资源 API 文档（docs/api.md）
- [ ] 示例 Agent 接入教程（docs/agent_quickstart.md）
- [ ] 管理员手册（docs/admin.md）
- [ ] verify_mcp.py 集成验证脚本

---

## 11. 风险与演进预留

| 风险 | 应对 |
|------|------|
| 外部 embedding 服务不可用导致检索全降级 | 适配层熔断 + 健康检查暴露 embedding 状态；可选配置 fallback base_url |
| Gravitino REST 9001 建表需 JDBC 后端 | MVP 不依赖 9001 建表，PyIceberg 直连 S3；admin 注册走 8090 Fileset API |
| Lance 共享卷单机局限 | MVP 单机约定；生产阶段引 Ray 时再分布式化 |

演进预留（设计稿§9 已全部落地于本方案）：资产 Schema、native/extension 分区、lifecycle 字段、能力图、Ontology 占位、Experience type 字段。

---

**请审批。批准后按 P0→P11 顺序展开开发，每个 Phase 完成后提交可运行的增量。**
