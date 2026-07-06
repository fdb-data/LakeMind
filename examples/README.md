# LakeMind 业务 Agent 接入示例

本目录包含业务 Agent 通过 LakeMind MCP 接入认知资产的示例。

## 示例

| 目录 | 说明 |
|------|------|
| `retail-agent/` | 零售业务 Agent：知识摄入/检索 + 记忆管理 + 技能注册 |

## 前置

LakeMind 已启动（参见 [快速入门](../docs/quickstart.md)）：

```bash
cd LakeMindServer && docker compose --env-file .env --profile ray up -d
cd LakeMindMCP && docker compose --profile all up -d --build
```

## 接入步骤

1. **获取 MCP 端点和 Token** — AssetMCP 在 `localhost:8401/mcp`，Token 在 `LakeMindMCP/LakeMindAssetMCP/config/config.yaml` 中定义
2. **引入 MCP 客户端** — 复制 `retail-agent/lakemind_client.py` 或自行实现 MCP JSON-RPC 调用
3. **调用 Tools** — `ingest_knowledge` / `search_knowledge` / `add_memory` / `search_memory` / `register_skill` / `search_skill`
4. **浏览 Resources** — `lake://knowledge` / `lake://memory` / `lake://skills` / `lake://ontology`
5. **使用 Prompts** — `search_knowledge_guide` / `add_memory_guide` 等（引导 Agent 高效使用）
