# LakeMindMCP

多模智能数据湖服务器平台面向外部的 MCP Server。通过标准 MCP 协议（Streamable HTTP）将底层多模存储抽象为**认知资产**，为 AI Agent 提供发现、读写、检索、记忆与技能调用的统一能力。

> LakeMind 认知基础设施的唯一切面。Agent 是一等公民，所有访问经 MCP 收敛。

## 状态

MVP 已实现并通过端到端验证（24/24）。覆盖 5 个数据域 + admin 域 + 多租户隔离 + 认证审计。

## 架构

```
接入层  MCP 协议端点 (Streamable HTTP, /mcp)
安全层  Bearer Token 认证 / 租户注入 / scope 校验 / 审计
资产编排层  资产路由 / 资源映射 / 工具分发
引擎适配层  S3 / Iceberg / Gravitino / LanceDB / Dragonfly / Embedding
```

核心约束：资产编排层只与 Asset 抽象交互，引擎适配层负责翻译，上层不出现具体引擎名。

## 资产能力

| 资产 | 资源 | 工具 |
|------|------|------|
| Data | `lake://data[/{name}]` | `query_table` `write_table` `execute_sql` |
| Knowledge | `lake://knowledge[/{id}]` | `search_knowledge` |
| Memory | `lake://memory` | `remember` `recall` `forget` |
| Skill | `lake://skills[/{id}]` | `search_skill` |
| Experience | `lake://experience[/{id}]` | `record_experience` |
| Ontology | `lake://ontology` | （预留，返回"暂未启用"） |

Admin 域（仅 Steward）：`register_knowledge` `create_dataset` `register_skill` `optimize_asset` `get_system_health`

## 快速开始

```bash
# 1. 数据平面
cd ../LakeMindServer && cp .env.example .env && docker compose --env-file .env up -d

# 2. MCP
cd ../LakeMindMCP && cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml：填 embedding 凭证、Token
docker compose up -d --build

# 3. 验证
pip install -e ".[dev]"
python scripts/verify_mcp.py   # 预期 24/24 PASS
```

## 文档

| 文档 | 内容 |
|------|------|
| [开发方案](开发方案.md) | 架构、分阶段任务、验收标准 |
| [API 文档](docs/api.md) | MCP 工具与资源 API 参考 |
| [Agent 接入教程](docs/agent_quickstart.md) | 示例 Agent 接入 |
| [管理员手册](docs/admin.md) | 部署、配置、运维、排查 |

## 配置要点

- **Embedding**：统一接外部 OpenAI 兼容服务，不内置本地模型
- **元数据**：PyIceberg 直连 S3 读写 + Gravitino REST 资源发现
- **长期记忆**：Lance 向量 + Iceberg 元信息小表双表（`lance_uri` 关联）
- **多租户**：Token 编码 `tenant_id`，全链路自动隔离

## 依赖

依赖 LakeMindServer 提供的引擎（SeaweedFS / Gravitino / Dragonfly）与外部 embedding 服务。嵌入式引擎（PyIceberg / LanceDB / DuckDB）在 MCP 进程内运行。详见 [pyproject.toml](pyproject.toml) 与 [LakeMindServer/config/versions.yaml](../LakeMindServer/config/versions.yaml)。

## 许可

Apache-2.0
