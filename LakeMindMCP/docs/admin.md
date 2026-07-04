# 管理员手册

## 1. 部署

### 1.1 配置

复制 `config/config.example.yaml` 为 `config/config.yaml`，按需修改：

- `server.host/port` — 监听地址
- `engines.*` — 各引擎地址（容器内用容器名，如 `lakemind-seaweedfs:8333`）
- `engines.lance.uri` — Lance 共享目录（与 LakeMindServer/data/lance 挂载同路径）
- `engines.iceberg.sql_uri` — PyIceberg SQL catalog 本地元数据库
- `embedding.*` — 外部 embedding 服务（OpenAI 兼容），`base_url/model/api_key/dim`
- `tokens` — 静态 Token 映射，每条含 `token/agent_id/tenant_id/scopes`

### 1.2 Token 规划

MVP 两 Token：

| 用途 | agent_id | tenant_id | scopes |
|------|----------|-----------|--------|
| 业务 Agent | agent-business-01 | retail | `[data]` |
| Steward | steward | platform | `[admin, data]` |

新增业务组：在 `tokens` 增加条目，分配独立 `tenant_id` 与 `data` scope。

### 1.3 启动

```bash
cd LakeMindServer && docker compose --env-file .env up -d   # 数据平面
cd LakeMindMCP   && docker compose up -d --build            # MCP
```

健康检查：`GET http://localhost:8400/health` → `{"status":"ok"}`

## 2. Embedding 服务

MCP 不内置 embedding 模型，统一接外部服务（OpenAI 兼容 `/v1/embeddings`）。

- OpenAI 官方：`base_url: https://api.openai.com/v1`，`model: text-embedding-3-small`，`dim: 1536`
- 自托管（vLLM/TEI/Infinity 等）：填 `base_url` 即可
- 可选 `fallback_base_url` 作降级

健康：Steward 调 `get_system_health` 查看 `embedding` 状态。

## 3. 资产管理（Steward 通过 admin 工具）

- `register_knowledge(name, location)` — 建知识库（空向量表），后续由数据导入流程灌文档
- `create_dataset(name, schema)` — 建空数据集
- `register_skill(name, location, metadata)` — 注册技能（上传代码 + 元信息 + 向量索引）
- `get_system_health()` — 组件健康

## 4. 租户隔离

全链路按 `tenant_id` 隔离：

| 层 | 隔离方式 |
|----|----------|
| S3 | 对象键 `{tenant_id}/` 前缀 |
| Iceberg | namespace `{tenant_id}_{domain}` |
| LanceDB | 数据库 `tenant_{tenant_id}` |
| Dragonfly | DB 编号 `hash(tenant_id) % 16` |

## 5. 审计

每次工具调用输出 JSON 审计日志：`timestamp, agent_id, tenant_id, tool, arguments(脱敏)`。脱敏键由 `audit.redact_keys` 配置。

## 6. 故障排查

| 现象 | 排查 |
|------|------|
| 启动时 `engines unavailable` | S3/Gravitino/Dragonfly 未就绪；先起 LakeMindServer |
| `embedding: fail` | 外部 embedding 服务不可达；检查 `base_url/api_key` |
| 工具返回 `Table ... already exists` | 同名表已存在；用 `overwrite` 模式或换名 |
| 401 | Token 缺失/无效 |
| 工具 `isError` 且 `missing required scope` | Token scope 不足 |

## 7. 验证

```bash
python scripts/verify_mcp.py   # 端到端 24/24
```
