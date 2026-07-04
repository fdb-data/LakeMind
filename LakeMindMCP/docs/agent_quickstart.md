# 示例 Agent 接入教程

本教程演示一个业务 Agent 通过 MCP 读写 LakeMind 数据湖的完整流程。

## 1. 前置条件

- LakeMindServer 已启动（`cd LakeMindServer && docker compose --env-file .env up -d`）
- LakeMindMCP 已启动（`cd LakeMindMCP && docker compose up -d --build`）
- 已获得业务 Agent Token（由管理员在 `config.yaml` 的 `tokens` 中配置，scope 含 `data`）
- 外部 embedding 服务可达（OpenAI 兼容 `/v1/embeddings`）

## 2. 连接

MCP 端点：`http://<mcp-host>:8400/mcp`，认证头 `Authorization: Bearer <token>`。

Python 客户端示例：

```python
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TOKEN = "<business-agent-token>"
URL = "http://localhost:8400/mcp"

async with streamablehttp_client(URL, headers={"Authorization": f"Bearer {TOKEN}"}) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()

        # 首读能力图
        caps = await session.read_resource("lake://capabilities")
        print(caps.contents[0].text)

        # 写数据
        await session.call_tool("write_table", {
            "table": "events",
            "rows": [{"event_id": "e1", "kind": "click", "ts": "2026-07-01T10:00:00Z"}],
        })

        # 查数据
        res = await session.call_tool("query_table", {"table": "events", "limit": 10})
        print(res.content[0].text)

        # 记忆
        await session.call_tool("remember", {"content": "用户偏好深色主题", "ttl": 3600})
        mem = await session.call_tool("recall", {"query": "用户偏好"})
        print(mem.content[0].text)
```

## 3. 典型工作流

1. **启动时**：读 `lake://capabilities` 与 `lake://workspace`，感知可用资产与租户上下文。
2. **结构化数据**：`write_table` → `query_table`（推荐）→ `execute_sql`（复杂分析）。
3. **知识检索**：`search_knowledge(fileset, query)` 获取 RAG 命中，`doc_uri` 指向原文。
4. **记忆**：`remember` 记事实，`recall` 语义召回，`forget` 清理。
5. **技能发现**：`search_skill(query)` 找技能，读 `lake://skills/{id}` 获取代码。
6. **经验沉淀**：`record_experience(type, content)` 记录成功/失败/反思。

## 4. 租户隔离

Token 编码 `tenant_id`，所有读写自动隔离到该租户的命名空间（S3 前缀、Iceberg namespace、LanceDB 库、Dragonfly DB）。Agent 无需也无法跨租户访问。

## 5. 验证

运行集成验证（需 LakeMindServer 在跑）：

```bash
python scripts/verify_mcp.py   # 预期 24/24 PASS
```
