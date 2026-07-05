# AGENTS.md — LakeMind AI Agent 协作约定

> 本文件是**总文件**，定义项目结构、技术栈、设计原则与协作约定。
> 详细设计见 `.agent/DESIGN.md`，开发规范见 `.agent/SPEC.md`，当前状态见 `.agent/STATE.md`。

---

## 1. 项目定位

LakeMind 是**认知资产存取平台**（store/retrieve），不是 Agent 执行平台。
Agent 通过 MCP 检索和存取知识、记忆、技能等认知资产，在自身运行时执行。

## 2. 仓库包结构

| 目录 | 平面 | 职责 | 状态 |
|------|------|------|------|
| `LakeMindServer/` | 数据平面 | 存储与计算底座（REST API + 11 引擎 + 12 容器） | ✅ 已完成 |
| `LakeMindAssetMCP/` | 运行平面 | 资产面 MCP（知识/记忆/技能/本体），23 tools | ✅ 已完成 |
| `LakeMindDataMCP/` | 运行平面 | 数据面 MCP（全量透传），18 tools | ✅ 已完成 |
| `LakeMindAdminMCP/` | 运行平面 | 管理面 MCP（用户/租户/Token/健康），17 tools | ✅ 已完成 |
| `LakeMindMCP/` | 运行平面 | 3 MCP 的 docker-compose 编排 | ✅ 已完成 |
| `LakeMindSteward/` | 运行平面 | 管理运维 Agent（LangGraph 巡检 + 对话） | ✅ 已完成 |
| `LakeMindMonitor/` | 运行平面 | 人类只读仪表板 + Steward 对话窗（Express） | ✅ 已完成 |
| `LakeMindStudio/` | 开发平面 | 资产设计、MCP 调试、Skill 脚手架（Tauri） | ❌ 未开始（P2） |

## 3. 访问拓扑

```
Agent ──→ AssetMCP (:8401)  ← 资产面（知识/记忆/技能/本体）
Steward ─→ DataMCP  (:8402)  ← 数据面（透传）
Steward ─→ AdminMCP (:8403)  ← 管理面（用户/租户/健康）
Monitor ─→ 3 MCP（只读）+ Steward（chat/inspect）
Studio  ─→ 3 MCP + Git
         │
         ▼
LakeMindServer (:10823)  ← REST API，11 引擎
  SeaweedFS · PostgreSQL · Dragonfly · Ray · fastembed · LLM Gateway
```

- **MCP 是 Agent 唯一入口**，嵌入式引擎在 Server 进程中运行，MCP 通过 REST API 调用。
- **MCP 三要素**：Tools（操作）+ Resources（只读浏览）+ Prompts（使用指南），每个 MCP 都有全部三要素。
- **Steward** 走 MCP admin 域，MCP 不可用时降级直连 Server。
- **Monitor** 全走 MCP（只读），自身极轻。

## 4. 技术栈（锁定，不擅自替换）

全开源组件（Apache 2.0 / MIT / BSD）：

| 组件 | 选型 | 用途 |
|------|------|------|
| 对象存储 | **SeaweedFS** | S3 兼容，承载全部数据文件 |
| 统一元数据 | **PostgreSQL 16** | Iceberg SQL catalog + 图 + 用户/租户/Token（替代 Gravitino） |
| 表格式 | **Apache Iceberg** | 结构化数据 |
| 向量/多模态 | **PyLance + LanceDB** | 知识库向量、语义检索（PyPI 包名 `pylance`） |
| 缓存 | **Dragonfly** | TTL KV（Redis 兼容协议） |
| 即席计算 | **DuckDB** | 跨表 SQL、Parquet 直读 |
| 分布式计算 | **Ray 2.41.0** | 3 节点 12 CPU（已实现） |
| Embedding | **fastembed** | BAAI/bge-small-en-v1.5, dim=384 |
| LLM 网关 | **GatewayLLM** | 内部能力，路由多 provider（不通过 MCP 暴露） |
| MCP SDK | **FastMCP** | tools + resources + prompts 三要素 |
| Agent 框架 | **LangGraph** | Steward 巡检工作流 |

> **不引入**：Apache Gravitino（已用 PG 替代）、Apache Ranger（生产阶段）、Trino、Daft。

## 5. 数据域 → 引擎映射

| 数据域 | 引擎 | MCP 资产 |
|--------|------|---------|
| 结构化数据 | Iceberg + PG catalog | DataMCP 透传 |
| 知识 / 多模态 RAG | Lance + LanceDB（OKF 格式） | `lake://knowledge` |
| 短期/工作记忆 | Dragonfly（TTL KV） | `lake://memory` |
| 长期/语义记忆 | Lance 向量 + PG 元信息（mem0 风格） | `lake://memory` |
| Skills | S3 + PG + LanceDB（不执行） | `lake://skills` |
| 本体/图 | PG graph_nodes/edges | `lake://ontology` |

## 6. 设计原则（不可偏离）

1. **统一存储底座** — SeaweedFS 一个对象存储
2. **统一元数据** — PostgreSQL 一个数据库
3. **计算与引擎分离** — 引擎可替换，计算可走嵌入式或 Ray
4. **Agent 直连引擎** — 经 MCP 代理，无额外 API 层

## 7. 关键设计决策

- **`execute_skill` 已移除** — 平台只存取不执行，Agent 自行检索技能代码并在自身运行时执行。
- **Memory 采用 mem0 风格** — 8 方法（add/search/get/list/update/delete/clear/history），LLM 事实抽取 + 哈希去重。
- **Knowledge 采用 OKF 格式** — YAML frontmatter + markdown body，交叉链接存 PG 图。
- **长期记忆双表设计** — Lance 向量表 + PG 元信息小表，通过 `lance_uri` 关联，不合并成单表。
- **LLM 网关是内部能力** — 不通过 MCP 暴露，Agent 使用自己的 LLM。

## 8. 约定

- `docker-compose` 在各包目录内运行（`.env`、`config/` 为相对路径）。
- 3 compose 组：`LakeMindServer/`（含 `--profile ray`）、`LakeMindMCP/`（`--profile all`）、`LakeMindMonitor/`。
- BuildKit 禁用：`$env:DOCKER_BUILDKIT=0`。
- 跨包依赖只通过 MCP 协议（运行平面）或 REST API / S3 / PG / Dragonfly 接口（数据平面）。
- 验证脚本放 `scripts/`，主验证脚本 `scripts/verify_three_mcp_v2.py`。
- 代码不加注释，除非逻辑非显而易见。
- 设计文档用中文，代码标识符用英文。
- PowerShell 下读写中文文件名需设置 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`。

## 9. 详细文档索引

| 文件 | 内容 |
|------|------|
| `.agent/DESIGN.md` | 架构设计规范（三平面、MCP 职责、数据流、设计决策） |
| `.agent/SPEC.md` | 开发规范（包结构、代码约定、Docker、验证） |
| `.agent/STATE.md` | 当前状态（进度、容器、验证结果、已知问题） |
| `docs/` | 发布文档（architecture, api-reference, mcp-tools, etc.） |
| `reports/` | 验证报告与设计文档 |
