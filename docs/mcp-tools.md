# MCP 工具参考

LakeMind 通过 3 个 MCP 服务提供 39 个工具和 7 个资源，Agent 通过 MCP 协议直连。

## LakeMindAssetMCP — 认知资产面

- **端口**: 8401
- **Scope**: `asset`
- **面向**: 业务 Agent
- **工具数**: 11
- **资源数**: 7

### 工具

#### Knowledge（知识库）

| 工具 | 参数 | 说明 |
|------|------|------|
| `search_knowledge` | kb, query, top_k=5 | 向量 top-k 语义检索 |
| `ingest_knowledge` | kb, documents | embedding + 写向量表 |
| `register_knowledge` | kb, description?, schema? | 创建知识库实例 |

```json
// search_knowledge 示例
{
  "kb": "product_docs",
  "query": "如何部署 LakeMind",
  "top_k": 5
}
```

#### Skills（技能）

| 工具 | 参数 | 说明 |
|------|------|------|
| `search_skill` | query, top_k=5 | 语义检索技能 |
| `register_skill` | name, code, description | 注册技能 |
| `execute_skill` | name, args | 执行技能（MVP 占位） |

#### Memory（记忆）

| 工具 | 参数 | 说明 |
|------|------|------|
| `remember` | content, kind="general", ttl?, context? | 写入记忆（短期/长期） |
| `recall` | query, limit=5, kind? | 语义召回记忆 |
| `forget` | query? | 删除记忆 |

记忆策略：
- `ttl` 有值 → 短期记忆写 Valkey（TTL 过期自动清除）
- `ttl` 为空 → 长期记忆用 fastembed 生成向量写 LanceDB

#### Ontology（本体）

| 工具 | 参数 | 说明 |
|------|------|------|
| `query_ontology` | label?, relation? | 查询概念/关系 |
| `update_ontology` | subject, relation, object | 增补三元组 |

### 资源

| URI | 说明 |
|-----|------|
| `lake://capabilities` | MCP 能力声明 |
| `lake://workspace` | 工作空间信息 |
| `lake://system/health` | 系统健康状态 |
| `lake://knowledge` | 知识库列表 |
| `lake://skills` | 技能列表 |
| `lake://memory` | 记忆引擎状态 |
| `lake://ontology` | 本体图状态 |

---

## LakeMindDataMCP — 数据面

- **端口**: 8402
- **Scope**: `data`
- **面向**: Steward / 高级 Agent
- **工具数**: 13

### 工具

#### Iceberg（结构化表）

| 工具 | 参数 | 说明 |
|------|------|------|
| `data_create_table` | namespace, table, schema | 建表 |
| `data_write` | namespace, table, data, mode="append" | 写数据 |
| `data_query` | namespace, table, columns?, filter?, limit? | 扫描表 |
| `data_list_tables` | namespace | 列表 |
| `data_describe` | namespace, table | schema + 行数 |

#### DuckDB（即席 SQL）

| 工具 | 参数 | 说明 |
|------|------|------|
| `data_sql` | sql | 即席 SQL 查询 |

#### LanceDB（向量检索）

| 工具 | 参数 | 说明 |
|------|------|------|
| `lance_query` | db, table, query, top_k=5 | 向量语义检索 |

#### S3（对象存储）

| 工具 | 参数 | 说明 |
|------|------|------|
| `s3_put` | bucket, key, data | 上传文件 |
| `s3_get` | bucket, key | 下载文件 |

#### Valkey（KV 缓存）

| 工具 | 参数 | 说明 |
|------|------|------|
| `kv_set` | key, value, ttl? | 设置 KV |
| `kv_get` | key | 获取 KV |

#### Graph（图存储）

| 工具 | 参数 | 说明 |
|------|------|------|
| `graph_query` | graph, label? | 查询节点/边 |
| `graph_update` | graph, action, data | 添加节点/边 |

---

## LakeMindAdminMCP — 管理面

- **端口**: 8403
- **Scope**: `admin`
- **面向**: Steward
- **工具数**: 15

### 工具

#### 用户管理

| 工具 | 参数 | 说明 |
|------|------|------|
| `create_user` | username, tenant_id, role="user" | 创建用户 |
| `update_user` | user_id, username?, role?, status? | 更新用户 |
| `delete_user` | user_id | 删除用户 |
| `list_users` | tenant_id? | 列出用户 |

#### 租户管理

| 工具 | 参数 | 说明 |
|------|------|------|
| `create_tenant` | tenant_id, name | 创建租户 |
| `update_tenant` | tenant_id, name?, status? | 更新租户 |
| `delete_tenant` | tenant_id | 删除租户 |
| `list_tenants` | — | 列出租户 |

#### Token 管理

| 工具 | 参数 | 说明 |
|------|------|------|
| `issue_token` | agent_id, tenant_id, scopes | 签发 Token |
| `revoke_token` | token | 吊销 Token |
| `list_tokens` | tenant_id?, agent_id? | 列出 Token |

#### 资产类型管理

| 工具 | 参数 | 说明 |
|------|------|------|
| `register_asset_type` | type, yaml_def | 注册资产类型 |
| `unregister_asset_type` | type | 注销资产类型 |

#### 平台管理

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_platform_health` | — | 11 引擎健康状态 |
| `get_node_status` | — | 平台节点状态 |

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
        "arguments": {"kb": "docs", "query": "部署", "top_k": 3}
    },
    "id": 1
}, headers={"Authorization": "Bearer test-business-token"})

# 调用 DataMCP data_sql
r = httpx.post("http://localhost:8402/mcp", json={
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "data_sql",
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
