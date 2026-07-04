# LakeMindMCP API 文档

LakeMindMCP 通过 MCP 协议暴露**认知资产**。端点：`POST /mcp`（Streamable HTTP），需 `Authorization: Bearer <token>`。

## 系统资源

| URI | 说明 |
|-----|------|
| `lake://capabilities` | 资产类型 → 能力映射，首次连接必读 |
| `lake://workspace` | 当前租户上下文（agent_id/tenant_id/scopes） |
| `lake://ontology` | 本体资产占位，返回 `{"status":"disabled"}` |

## Data 资产（结构化数据）

**资源**
- `lake://data` — 数据集列表
- `lake://data/{name}` — 表结构、行数

**工具**
- `query_table(table, columns?, filter?, limit=100)` → `{rows, count}`；`filter` 为 SQL WHERE 表达式
- `write_table(table, rows, mode="append")` → `{table, rows_written, mode}`；表不存在自动建
- `execute_sql(sql)` → `{rows, count}`；在当前租户全部 data 表上执行

## Knowledge 资产（知识/RAG）

**资源**
- `lake://knowledge` — 知识库列表
- `lake://knowledge/{id}` — 知识库描述、文档数

**工具**
- `search_knowledge(fileset, query, top_k=5, filter?)` → `{fileset, query, hits, count}`

## Memory 资产（记忆）

**资源**
- `lake://memory` — 当前 Agent 记忆概况（长期计数 + 短期键）

**工具**
- `remember(content, context?, ttl?)` → `{memory_id, short_term_key, lance_uri}`；短期走 Dragonfly，长期走 Lance+Iceberg 双表
- `recall(query, limit=5)` → `{query, memories, count}`
- `forget(query?)` → `{deleted, scope}`

## Skill 资产（技能）

**资源**
- `lake://skills` — Skill 摘要列表
- `lake://skills/{id}` — Skill 元信息 + 文件内容（`code`）

**工具**
- `search_skill(query, top_k=5)` → `{query, skills, count}`

## Experience 资产（经验）

**资源**
- `lake://experience` — 经验记录列表
- `lake://experience/{id}` — 经验详情

**工具**
- `record_experience(type, content, tags?, score?)` → `{exp_id, type}`；`type ∈ {success, failure, reflection}`

## Admin 工具（仅 Steward，scope=admin）

- `register_knowledge(name, location, description?)` — 建空知识库向量表
- `create_dataset(name, schema, partition?)` — 建 Iceberg 空表；`schema` 为 `{列名: 类型}`，类型：string/int64/int32/float64/float32/bool/timestamp
- `register_skill(name, location, metadata?)` — 上传代码到 S3 + 写元信息 + 建向量索引；`metadata` 可含 `description/version/code`
- `optimize_asset(asset_type, asset_name)` — MVP 占位
- `get_system_health()` — 组件健康（s3/dragonfly/gravitino/embedding）

## 返回值约定

工具返回 `dict`（FastMCP 序列化为单个 TextContent JSON）。列表型结果包裹在 `{"rows": [...]}` / `{"hits": [...]}` 等字段中。

## 错误

- 401 — 缺失/无效 Token
- 工具内 scope 不足 → `isError=true`，content 为错误说明
- 工具内业务异常 → `isError=true`，content 为 `Error executing tool <name>: <msg>`
