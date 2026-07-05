# REST API 参考

LakeMindServer 提供 40+ OpenAPI 路径，覆盖 11 个功能域。

## 认证

所有 `/api/v1/` 路径需要 Bearer Token 认证（`/api/v1/system/health` 除外）：

```
Authorization: Bearer lakemind-internal-api-key
X-Tenant-Id: default
X-Agent-Id: test
X-Scopes: all
```

## 1. System

### GET /api/v1/system/health

返回 11 引擎健康状态。

```json
{
  "object_storage": true,
  "tabular": true,
  "vector": true,
  "kv": true,
  "graph": true,
  "metadata": true,
  "sql": true,
  "distributed": true,
  "embedding": true,
  "memory": true,
  "llm": true
}
```

### GET /api/v1/system/nodes

返回平台节点状态。

### GET /api/v1/system/metrics

指标端点（占位）。

## 2. Objects (SeaweedFS)

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | /api/v1/storage/objects/{bucket}/{key} | 上传对象 |
| GET | /api/v1/storage/objects/{bucket}/{key} | 下载对象 |
| HEAD | /api/v1/storage/objects/{bucket}/{key} | 检查存在 |
| DELETE | /api/v1/storage/objects/{bucket}/{key} | 删除对象 |
| GET | /api/v1/storage/objects/{bucket} | 列对象 |

## 3. Tables (Iceberg)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/storage/tables/ | 建表 |
| GET | /api/v1/storage/tables/{namespace} | 列表 |
| GET | /api/v1/storage/tables/{namespace}/{table} | 描述表 |
| DELETE | /api/v1/storage/tables/{namespace}/{table} | 删表 |
| POST | /api/v1/storage/tables/{namespace}/{table}/append | 追加数据 |
| POST | /api/v1/storage/tables/{namespace}/{table}/overwrite | 覆写数据 |
| GET | /api/v1/storage/tables/{namespace}/{table}/scan | 扫描表 |

### 建表示例

```bash
POST /api/v1/storage/tables/
{
  "namespace": "default",
  "table": "my_table",
  "schema": {
    "fields": [
      {"name": "id", "type": "int64"},
      {"name": "name", "type": "string"}
    ]
  }
}
```

### 扫描示例

```bash
GET /api/v1/storage/tables/default/my_table/scan?limit=10
```

## 4. Vectors (LanceDB)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/storage/vectors/{db} | 创建向量表 |
| GET | /api/v1/storage/vectors/{db} | 列向量表 |
| GET | /api/v1/storage/vectors/{db}/{name} | 描述表 |
| POST | /api/v1/storage/vectors/{db}/{name}/add | 添加向量 |
| POST | /api/v1/storage/vectors/{db}/{name}/search | 向量检索 |

### 向量检索示例

```bash
POST /api/v1/storage/vectors/mydb/mytable/search
{
  "query_vec": [0.1, 0.2, ...],
  "top_k": 5
}
```

## 5. KV (Dragonfly)

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | /api/v1/storage/kv/{key} | 设置 KV |
| GET | /api/v1/storage/kv/{key} | 获取 KV |
| DELETE | /api/v1/storage/kv/{key} | 删除 KV |
| GET | /api/v1/storage/kv/ | 扫描 KV |

## 6. Graph (PostgreSQL)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/storage/graph/{graph}/nodes | 添加节点 |
| POST | /api/v1/storage/graph/{graph}/edges | 添加边 |
| GET | /api/v1/storage/graph/{graph}/nodes | 查询节点 |
| GET | /api/v1/storage/graph/{graph}/edges | 查询边 |
| DELETE | /api/v1/storage/graph/{graph}/nodes/{node_id} | 删除节点 |

## 7. SQL (DuckDB)

### POST /api/v1/storage/sql/

```bash
{
  "sql": "SELECT 1"
}
```

## 8. Jobs (Ray 分布式计算)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/compute/jobs/ | 提交作业 |
| GET | /api/v1/compute/jobs/{job_id} | 查询状态 |
| GET | /api/v1/compute/jobs/{job_id}/result | 获取结果 |

### 提交作业示例

```bash
POST /api/v1/compute/jobs/
{
  "func": "map",
  "args": {
    "fn": "lambda x: x * x",
    "items": [1, 2, 3, 4, 5]
  }
}
```

支持的 func：`map`, `parallel_map`, `sum`, `sleep_test`, `embed_batch`, `pi_monte_carlo`, `matrix_multiply`

## 9. Embedding (fastembed)

### POST /api/v1/cognitive/embedding/embed

```bash
{
  "texts": ["hello", "world"]
}
```

响应：

```json
{
  "vectors": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
  "dim": 384,
  "count": 2
}
```

## 10. LLM 网关 (GatewayLLM)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/cognitive/llm/chat | 聊天补全 |
| POST | /api/v1/cognitive/llm/embed | LLM embedding |
| GET | /api/v1/cognitive/llm/models | 列出可用模型 |
| GET | /api/v1/cognitive/llm/health | 网关健康 |

### 聊天示例

```bash
POST /api/v1/cognitive/llm/chat
{
  "messages": [
    {"role": "system", "content": "你是助手"},
    {"role": "user", "content": "你好"}
  ],
  "model": "auto",
  "temperature": 0.7,
  "max_tokens": 100
}
```

响应：

```json
{
  "id": "chat_xxxx",
  "model": "deepseek-v4-flash",
  "choices": [
    {"message": {"role": "assistant", "content": "你好！有什么可以帮你的？"}}
  ],
  "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35}
}
```

## 11. Memory (BasicMemory)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/cognitive/memory/remember | 写入记忆 |
| POST | /api/v1/cognitive/memory/recall | 召回记忆 |
| POST | /api/v1/cognitive/memory/forget | 删除记忆 |

### 记忆示例

```bash
# 写入长期记忆
POST /api/v1/cognitive/memory/remember
{
  "content": "用户偏好深色主题",
  "kind": "general"
}

# 写入短期记忆（60秒过期）
POST /api/v1/cognitive/memory/remember
{
  "content": "当前会话上下文",
  "ttl": 60,
  "kind": "general"
}

# 语义召回
POST /api/v1/cognitive/memory/recall
{
  "query": "用户喜欢什么主题",
  "limit": 5
}
```

## 12. Metadata (PostgreSQL)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/metadata/tenants | 创建租户 |
| GET | /api/v1/metadata/tenants | 列出租户 |
| PUT | /api/v1/metadata/tenants/{tenant_id} | 更新租户 |
| DELETE | /api/v1/metadata/tenants/{tenant_id} | 删除租户 |
| POST | /api/v1/metadata/users | 创建用户 |
| GET | /api/v1/metadata/users | 列出用户 |
| PUT | /api/v1/metadata/users/{user_id} | 更新用户 |
| DELETE | /api/v1/metadata/users/{user_id} | 删除用户 |
| POST | /api/v1/metadata/tokens | 签发 Token |
| GET | /api/v1/metadata/tokens | 列出 Token |
| DELETE | /api/v1/metadata/tokens/{token} | 吊销 Token |
| POST | /api/v1/metadata/asset-types | 注册资产类型 |
| GET | /api/v1/metadata/asset-types | 列出资产类型 |
| DELETE | /api/v1/metadata/asset-types/{type} | 注销资产类型 |
