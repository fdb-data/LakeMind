---
name: lakemind-connector
version: 0.1.0
type: agent-skill
description: "LakeMind MCP 连接器 — 让 AI Agent 通过 MCP 存取认知资产（知识、记忆）"
tags: [mcp, connector, cognition, lakemind]
---

# lakemind-connector

## 用途

让 AI Agent（如 opencode）通过 LakeMind 的 MCP 协议接入平台，存取自身的认知资产：
- **知识** → 向量化 → LanceDB 向量入库 → 语义检索
- **记忆** → AssetMCP add_memory / search_memory / list_memory

## 架构

```
Agent (opencode)
  │
  │  1. search_skill("lakemind connector")  ← 从 LakeMind 检索本 Skill
  │  2. get_skill("lakemind-connector")     ← 下载 Skill 代码
  │  3. 在自身运行时执行 Skill 代码          ← LakeMind 不执行，Agent 自己执行
  │
  ▼
Skill 代码运行:
  ├─ AssetMCP (:8401) → 记忆存取 (MCP tools)
  ├─ AdminMCP (:8403) → 租户/Token 管理 (MCP tools)
  ├─ ModelServing (:10824) → Embedding / LLM (REST API)
  └─ Server (:10823) → 向量存储 (REST API)
```

## 文件

| 文件 | 职责 |
|------|------|
| `connector.py` | LakeMindConnector — MCP + REST 统一封装 |
| `cognition.py` | 知识概念 + 记忆消息定义 |
| `cli.py` | CLI 入口 (ingest/search/memories/verify/...) |

## 使用

```python
from connector import LakeMindConnector
from cognition import KNOWLEDGE_BASE, KNOWLEDGE_CONCEPTS, MEMORY_MESSAGES

conn = LakeMindConnector()

# 存入知识
await conn.store_knowledge("my-kb", concepts)

# 语义检索
hits = await conn.search_knowledge("query", "my-kb")

# 存入记忆
await conn.add_memory([{"role": "user", "content": "今天做了什么"}])
```

## 依赖

- `httpx` — REST API 调用
- `mcp` — MCP 协议客户端

## 环境变量

| 变量 | 说明 |
|------|------|
| `ASSET_MCP_URL` | AssetMCP 端点 (default: http://localhost:8401/mcp) |
| `ADMIN_MCP_URL` | AdminMCP 端点 (default: http://localhost:8403/mcp) |
| `SERVER_API_URL` | Server REST API (default: http://localhost:10823) |
| `MODEL_SERVING_URL` | ModelServing (default: http://localhost:10824) |
| `OPENCODE_TOKEN` | opencode 租户 Token |
| `TENANT_ID` | 租户 ID (default: opencode) |
