# MCP 工具参考

LakeMind 通过 3 个 MCP 服务提供 **58 个工具**、**23 个资源**、**10 个 prompts**，Agent 通过 MCP 协议直连。

---

## LakeMindAssetMCP — 认知资产面

- **端口**: 8401
- **Scope**: `asset`
- **面向**: 业务 Agent
- **工具数**: 23
- **资源数**: 11
- **Prompts**: 6

### 工具

#### Knowledge（知识库，7 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `register_knowledge` | name, description? | 创建知识库 |
| `ingest_knowledge` | kb_name, concepts[] | 摄入 OKF 概念（YAML frontmatter + markdown body） |
| `search_knowledge` | query, kb_name, top_k=5 | 向量 top-k 语义检索 |
| `get_knowledge` | kb_name, concept_id | 获取单条概念全文 |
| `list_knowledge` | — | 列出全部知识库 |
| `list_concepts` | kb_name | 列出知识库内概念 |
| `delete_knowledge` | kb_name | 删除知识库 |

#### Memory（记忆，8 tools，mem0 风格）

| 工具 | 参数 | 说明 |
|------|------|------|
| `add_memory` | messages[], infer=False | LLM 事实抽取 → 哈希去重 → Lance 向量 + PG 元信息 |
| `search_memory` | query, top_k=5 | 混合检索：Lance 语义 + Valkey 关键词 |
| `get_memory` | memory_id | 取单条记忆 |
| `list_memory` | page=1, page_size=20 | 列表（支持过滤） |
| `update_memory` | memory_id, content | 更新内容 + 记录变更历史 |
| `delete_memory` | memory_id | 删除记忆 |
| `clear_memory` | — | 清空当前 Agent/Tenant 全部记忆 |
| `memory_history` | memory_id | 查看变更历史（PG memory_history 表） |

#### Skills（技能，5 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `register_skill` | name, code, description | 注册技能（存 S3 + PG + LanceDB 向量） |
| `search_skill` | query, top_k=5 | 语义检索技能 |
| `get_skill` | name | 获取技能代码 |
| `list_skills` | — | 列出全部技能 |
| `delete_skill` | name | 删除技能 |

> `execute_skill` 已移除 — 平台只存取不执行，Agent 自行检索技能代码并在自身运行时执行。

#### Ontology（本体，3 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `query_ontology` | concept | 查询概念/关系 |
| `update_ontology` | concept, relation, target | 增补三元组 |
| `delete_ontology` | concept | 删除概念 |

### 资源（11 resources）

| URI | 说明 |
|-----|------|
| `lake://capabilities` | 资产能力图 |
| `lake://workspace` | 工作区信息 |
| `lake://knowledge` | 知识库列表 |
| `lake://knowledge/{kb}/{concept_id}` | 知识库概念详情 |
| `lake://skills` | 技能列表 |
| `lake://skills/{name}` | 技能详情 |
| `lake://memory` | 记忆概况 |
| `lake://memory/{memory_id}` | 记忆详情 |
| `lake://ontology` | 本体列表 |
| `lake://ontology/{concept}` | 本体概念详情 |

> AssetMCP **不含** `lake://system/health` — 健康属于管理/数据面。

### Prompts（6 prompts）

| Prompt | 参数 | 说明 |
|--------|------|------|
| `search_knowledge_guide` | query, kb_name | 知识检索使用指南 |
| `okf_concept_guide` | type, title | OKF 概念编写指南 |
| `register_skill_guide` | name, description, code | 技能注册指南 |
| `add_memory_guide` | messages | 记忆写入指南 |
| `search_memory_guide` | query | 记忆检索指南 |
| `query_ontology_guide` | concept | 本体查询指南 |

---

## LakeMindDataMCP — 数据面

- **端口**: 8402
- **Scope**: `data`
- **面向**: Steward / 高级 Agent
- **工具数**: 18
- **资源数**: 6
- **Prompts**: 2

### 工具

#### Iceberg（结构化表，7 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `create_table` | name, schema | 建表 |
| `write_table` | table, rows | 写数据 |
| `query_table` | table, limit=100 | 扫描表 |
| `list_tables` | — | 列表 |
| `describe_table` | table | schema + 行数 |
| `drop_table` | table | 删表 |
| `sql_query` | sql | 即席 SQL（DuckDB） |

#### LanceDB（向量检索，1 tool）

| 工具 | 参数 | 说明 |
|------|------|------|
| `vector_search` | table, query, top_k=5 | 向量语义检索 |

#### S3（对象存储，4 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `s3_put` | uri, body | 上传文件 |
| `s3_get` | uri | 下载文件 |
| `s3_list` | uri, limit=100 | 列出文件 |
| `s3_delete` | uri | 删除文件 |

#### Valkey（KV 缓存，4 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `kv_set` | key, value | 设置 KV |
| `kv_get` | key | 获取 KV |
| `kv_delete` | key | 删除 KV |
| `kv_scan` | pattern, limit=100 | 扫描 KV |

#### Graph（图存储，2 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `graph_query` | concept | 查询节点/边 |
| `graph_update` | concept, relation, target | 添加节点/边 |

### 资源（6 resources）

| URI | 说明 |
|-----|------|
| `lake://system/health` | 系统健康状态 |
| `lake://tables` | 表列表 |
| `lake://tables/{ns}/{table}` | 表详情 |
| `lake://vectors` | 向量表列表 |
| `lake://vectors/{table}` | 向量表详情 |
| `lake://graph` | 图状态 |

### Prompts（2 prompts）

| Prompt | 参数 | 说明 |
|--------|------|------|
| `sql_query_guide` | intent | SQL 查询指南 |
| `data_exploration_guide` | table | 数据探索指南 |

---

## LakeMindAdminMCP — 管理面

- **端口**: 8403
- **Scope**: `admin`
- **面向**: Steward
- **工具数**: 17
- **资源数**: 6
- **Prompts**: 2

### 工具

#### 用户管理（5 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `create_user` | username, tenant_id, role="user" | 创建用户 |
| `get_user` | user_id | 获取用户 |
| `list_users` | tenant_id? | 列出用户 |
| `update_user` | user_id, role?, status? | 更新用户 |
| `delete_user` | user_id | 删除用户 |

#### 租户管理（4 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `create_tenant` | tenant_id, name | 创建租户 |
| `list_tenants` | — | 列出租户 |
| `update_tenant` | tenant_id, name? | 更新租户 |
| `delete_tenant` | tenant_id | 删除租户 |

#### Token 管理（3 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `issue_token` | agent_id, tenant_id, scopes | 签发 Token |
| `revoke_token` | token | 吊销 Token |
| `list_tokens` | tenant_id?, agent_id? | 列出 Token |

#### 资产类型管理（3 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `register_asset_type` | yaml_def | 注册资产类型 |
| `unregister_asset_type` | type | 注销资产类型 |
| `list_asset_types` | — | 列出资产类型 |

#### 平台管理（3 tools）

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_platform_health` | — | 11 引擎健康状态 |
| `get_node_status` | — | 平台节点状态 |
| `get_metrics` | — | 平台指标 |

### 资源（6 resources）

| URI | 说明 |
|-----|------|
| `lake://admin/health` | 管理面健康 |
| `lake://admin/tenants` | 租户列表 |
| `lake://admin/users` | 用户列表 |
| `lake://admin/tokens` | Token 列表 |
| `lake://admin/asset-types` | 资产类型列表 |
| `lake://admin/nodes` | 节点列表 |

### Prompts（2 prompts）

| Prompt | 参数 | 说明 |
|--------|------|------|
| `inspect_platform_guide` | focus_area | 平台巡检指南 |
| `manage_user_guide` | action | 用户管理指南 |

---

## Scope 隔离

| Token | 可访问 MCP | 被拒绝 MCP |
|-------|-----------|-----------|
| business (scope=asset) | AssetMCP | DataMCP, AdminMCP |
| steward (scope=asset,data,admin) | 全部 | — |
| monitor (scope=asset) | AssetMCP (只读) | DataMCP, AdminMCP |

## MCP 调用示例

```python
import httpx

# 调用 AssetMCP search_knowledge
r = httpx.post("http://localhost:8401/mcp", json={
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "search_knowledge",
        "arguments": {"kb_name": "docs", "query": "部署", "top_k": 3}
    },
    "id": 1
}, headers={"Authorization": "Bearer test-business-token"})

# 调用 DataMCP sql_query
r = httpx.post("http://localhost:8402/mcp", json={
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "sql_query",
        "arguments": {"sql": "SELECT COUNT(*) FROM my_table"}
    },
    "id": 1
}, headers={"Authorization": "Bearer test-steward-token"})

# 调用 AdminMCP list_tenants
r = httpx.post("http://localhost:8403/mcp", json={
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {"name": "list_tenants", "arguments": {}},
    "id": 1
}, headers={"Authorization": "Bearer test-steward-token"})
```
