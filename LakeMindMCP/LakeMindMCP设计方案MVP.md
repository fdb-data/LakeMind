# LakeMindMCP (MCP Server) MVP 设计稿

## 1. 产品定位

**LakeMindMCP** 是 **LakeMind 认知基础设施**的唯一切面，通过标准 MCP 协议将底层多模存储抽象为**认知资产**，为 AI Agent 提供发现、读写、检索、记忆与技能调用的统一能力。

**核心原则：**
- **Agent-First**：接口面向 Agent 认知模型，而非存储引擎
- **资产抽象**：以可扩展的 Asset 为中心，隔离底层引擎变化
- **先发现后操作**：Resource 用于探索，Tool 用于执行
- **唯一入口**：网络层面封禁直连存储，MCP Server 是唯一可信通道

---

## 2. 架构分层

```
┌─────────────────────────────────┐
│           接入层                 │  MCP 协议端点 (Streamable HTTP)
├─────────────────────────────────┤
│           安全层                 │  Token 认证、租户注入、权限校验、审计
├─────────────────────────────────┤
│         资产编排层               │  资产路由、资源映射、工具分发、流式处理
├─────────────────────────────────┤
│         引擎适配层               │  封装各引擎客户端，按资产类型适配
└─────────────────────────────────┘
```

> 核心约束：资产编排层只与 Asset 抽象交互，引擎适配层负责翻译为具体引擎调用。上层代码不出现 `LanceDB`、`Redis` 等具体实现名称。

---

## 3. 认知资产模型

### 3.1 资产类型注册表

每种资产类型定义为：

| 字段 | 说明 |
|------|------|
| `type` | 唯一标识（`data`, `knowledge`, `memory`, `skill`, `experience`） |
| `description` | 人类可读描述 |
| `schema` | 该资产的元数据结构定义 |
| `resource_root` | MCP 资源 URI 前缀 |
| `capabilities` | 该资产支持的操作列表 |
| `lifecycle` | 预留字段，可选（`draft`, `published`, `archived`），MVP 不强制 |

新增资产类型只需向注册表添加条目并实现适配器，核心代码零改动。

### 3.2 内置资产与 Schema

**Data**
- 资源根路径：`lake://data`
- Schema：`name, columns, partition, location, row_count, created_at`
- Capabilities：`query, insert, merge`

**Knowledge**
- 资源根路径：`lake://knowledge`
- Schema：`name, description, language, tags, embedding_model, document_count, created_at`
- Capabilities：`search`

**Memory**
- 资源根路径：`lake://memory`
- Schema：`session_id, content, context, created_at, ttl`
- Capabilities：`remember, recall, forget`

**Skill**
- 资源根路径：`lake://skills`
- Schema：`name, version, description, inputs, outputs, tags, status`
- Capabilities：`search, execute`

**Experience**
- 资源根路径：`lake://experience`
- Schema：`type(success/failure/reflection), workflow, content, tags, score, created_at`
- Capabilities：`record`

> **预留资产类型**：`Ontology`（`lake://ontology`），MVP 阶段已注册但返回“暂未启用”，Agent 可提前感知能力边界。

### 3.3 资产代码组织

```
assets/
├── native/          # 内置资产，MVP 全部在此
│   ├── data.py
│   ├── knowledge.py
│   ├── memory.py
│   ├── skill.py
│   └── experience.py
└── extension/       # 未来第三方资产插件目录，MVP 为空
    └── .gitkeep
```

---

## 4. 资源与工具设计

### 4.1 系统级资源

| 资源 URI | 说明 |
|----------|------|
| `lake://capabilities` | 返回资产类型 → 支持操作列表的映射图，Agent 首次连接必读 |
| `lake://workspace` | 当前租户上下文：Catalog、策略、推荐资产、命名规范、当前会话 |

### 4.2 Data 资产

**资源：**
- `lake://data` → 数据集列表
- `lake://data/{name}` → 表结构、分区、行数

**工具：**
- `query_table(table, columns?, filter?, limit?)` — 高层查询，推荐优先使用
- `write_table(table, rows, mode="append")` — 写入
- `execute_sql(sql)` — 高级模式，复杂查询保留

### 4.3 Knowledge 资产

**资源：**
- `lake://knowledge` → 知识库列表
- `lake://knowledge/{id}` → 知识库描述、文档数、索引状态

**工具：**
- `search_knowledge(fileset, query, top_k=5, filter?)` → 向量/全文检索

### 4.4 Memory 资产

> 接口脱离 Redis KV 思维，采用认知化语义。

**资源：**
- `lake://memory` → 当前 Agent 记忆概况

**工具：**
- `remember(content, context?, ttl?)` — 记住一件事
- `recall(query, limit=5)` — 语义/关键词召回
- `forget(query?)` — 遗忘匹配的记忆

底层由短期记忆适配器（MVP 使用 Dragonfly）与长期记忆适配器（MVP 使用 Lance）协同实现，Agent 无感知。

### 4.5 Skill 资产

> Skill 首先是 Resource，其次才是 Tool。

**资源：**
- `lake://skills` → 可用 Skill 摘要列表
- `lake://skills/{id}` → Skill 完整元信息，`resources/read` 直接获取文件内容

**工具：**
- `search_skill(query)` → 语义搜索匹配的 Skill

> 已移除 `load_skill` 工具，Agent 通过资源读取即可加载 Skill 本体。

### 4.6 Experience 资产

**资源：**
- `lake://experience` → 经验记录摘要列表
- `lake://experience/{id}` → 某条经验详情

**工具：**
- `record_experience(type, content, tags?)` — 记录成功/失败/反思

> `type` 可选值：`success`, `failure`, `reflection`，为未来向 Learning 演进预留。

### 4.7 管理工具（admin 域，仅 Steward 可用）

- `register_knowledge(name, location, description?)`
- `create_dataset(name, schema, partition?)`
- `register_skill(name, location, metadata?)`
- `optimize_asset(asset_type, asset_name)`
- `get_system_health()`

> 管理工具语义面向资产，如 `register_knowledge` 而非 `register_fileset`。

---

## 5. 多租户与安全

### 5.1 Token 认证
- 静态 Token → 配置文件映射 `{agent_id, tenant_id, scopes}`
- Agent 通过 `Authorization: Bearer <token>` 携带
- MVP 建议两 Token：业务 Agent 组（`data` 域）+ Steward（`admin` 域）

### 5.2 租户隔离
全链路通过注入的 `tenant_id` 自动完成：

| 层次 | 隔离方式 |
|------|----------|
| 存储 (S3) | 对象键自动加 `{tenant_id}/` 前缀 |
| 元数据 (Gravitino) | 每租户独立 Catalog |
| 向量 (LanceDB) | 每租户独立数据库 |
| 缓存 (Dragonfly) | 不同 DB 编号 |

Agent 无感知，所有路径拼接由安全层自动完成。

### 5.3 审计
每次工具调用记录 `timestamp, agent_id, tenant_id, tool, arguments`（脱敏），JSON 格式输出。

---

## 6. 性能与可靠性

- **无状态**：可水平扩展
- **连接池**：与后端引擎保持长连接
- **流式传输**：大数据集使用 MCP 流式 Resource
- **元数据缓存**：资产列表缓存 30s
- **熔断**：后端不可用时快速失败

---

## 7. 部署与配置

- **形式**：单容器，docker-compose 编排
- **配置**：YAML 文件（Token 映射、引擎地址、租户规则）

---

## 8. 交付清单

- [ ] 源代码仓库（Apache 2.0）
- [ ] Docker 镜像 + docker-compose 模板
- [ ] MCP 工具与资源 API 文档
- [ ] 示例 Agent 接入教程
- [ ] 管理员手册

---

## 9. 演进预留

| 预留项 | MVP 动作 |
|--------|----------|
| 资产 Schema | ✅ 已内置 |
| Native/Extension 目录 | ✅ 已分区 |
| 生命周期字段 | ✅ Schema 中已预留 |
| Capability 能力图 | ✅ 已实现 |
| Ontology 资产类型 | ✅ 已注册，返回“暂未启用” |
| Experience 的 type 字段 | ✅ 已支持 `success/failure/reflection` |

---

此版本为 **MVP-Ready 最终稿**，所有设计决策均已考虑未来平台化演进，同时严格控制 MVP 开发范围，不引入任何过度设计。可进入开发阶段。