# AGENTS.md

本仓库为多包（monorepo）结构。平台基础设施已可运行（见 `LakeMindServer`），其余包待实现。

## 唯一权威文档

**`LakeMind整体技术方案.md`** 是项目的唯一权威技术方案，整合了产品设计、架构决策、开发规范与当前状态。任何架构、组件选型、数据域映射、开发规范的讨论都必须先读它，不要凭名字猜测。

其他文档为素材：
- `多模智能数据湖方案.md`：原始设计文档
- `LakeMind简介.md`：产品概要
- `LakeMind多模智能数据湖规划方案.md`：规划方案

文档名为非 ASCII 中文，在 Windows PowerShell 下读写需注意 UTF-8 编码（`[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`），否则会乱码。

## 仓库包结构（五件套）

| 目录 | 平面 | 职责 | 状态 |
|------|------|------|------|
| `LakeMindServer/` | 数据平面 | 存储与计算底座（3 容器 + 验证脚本） | ✅ 已完成 |
| `LakeMindMCP/` | 运行平面 | Agent 唯一入口，资产编排，全量引擎适配 | 🔨 待开发（P0） |
| `LakeMindSteward/` | 运行平面 | 管理运维 Agent，对话式管理 + 自主巡检 | 🔨 待开发（P1） |
| `LakeMindMonitor/` | 运行平面 | 人类只读仪表板 + Steward 对话窗 | 🔨 待开发（P1） |
| `LakeMindStudio/` | 开发平面 | 资产设计、MCP 调试、Skill 脚手架、CI/CD | 🔨 待开发（P2） |

## 访问拓扑（关键决策）

- **MCP 是 Agent 唯一入口**，全量嵌入式引擎装在 MCP 中。
- **Steward** 正常走 MCP admin 域，MCP 不可用时降级直连 Server（保留 pyiceberg + duckdb 应急能力）。
- **Monitor** 全走 MCP（只读），自身极轻，仅装 MCP 客户端 SDK。
- **Studio** 走 MCP + Git，装 MCP 客户端 + CLI 工具链。

## 约定

- `docker-compose` 必须在 `LakeMindServer/` 内运行（`.env`、`config/` 为相对路径）。
- 平台验证脚本统一放 `LakeMindServer/scripts/`：
  - `python LakeMindServer/scripts/verify_services.py`（基础集成，依赖 `boto3 redis`）
  - `python LakeMindServer/scripts/verify_scenario.py`（端到端场景，依赖全量引擎）
- 跨包依赖只通过 MCP 协议（运行平面）或 S3/Gravitino/Dragonfly 接口（数据平面），不要跨包直连内部存储。
- 共享 Lance 数据目录 `LakeMindServer/data/lance/`（bind mount）。

## 技术栈是固定的，不要擅自替换

方案已锁定全开源组件（Apache 2.0 / MIT / BSD）。除非用户明确要求，不要引入替代品或闭源依赖：

- 存储底座：**SeaweedFS**（S3 兼容）
- 表格式：**Apache Iceberg**（结构化），**PyLance**（多模态/向量，PyPI 包名是 `pylance` 不是 `lance`）
- 元数据：**Apache Gravitino**（Iceberg 表 + Fileset 统一编目）
- 缓存/短期记忆：**Dragonfly**（TTL KV）
- 计算：**Daft**（嵌入式 DataFrame）；**Ray** 仅生产阶段引入
- 向量检索：**LanceDB**；即席分析：**DuckDB**
- 权限审计：**Apache Ranger**，仅生产阶段引入

## MVP 范围约束

- 部署形态：**单机 `docker-compose`**，所有组件容器化。
- **MVP 不引入**：Ray、Apache Ranger、Trino。遇到"加分布式/权限"类需求时，先确认是否已进入生产阶段。
- 嵌入式引擎（PyIceberg / PyLance / LanceDB / DuckDB / Daft）在 MCP 进程内运行，不需要独立容器。
- 长期记忆采用 Lance 向量 + Iceberg 小表双表设计，两表通过 `lance_uri` 字段关联——这是方案明确约定的模式，实现时不要合并成单表。

## 数据域 → 引擎映射（来自方案，勿偏离）

| 数据域 | 引擎 | MCP 资产 |
|--------|------|---------|
| 结构化数据 | Iceberg + Gravitino | `lake://data` |
| 知识 / 多模态 RAG | Lance + LanceDB，Gravitino Fileset | `lake://knowledge` |
| 短期/工作记忆 | Dragonfly（TTL KV） | `lake://memory` |
| 长期/语义记忆 | Lance 向量 + Iceberg 元信息小表（`lance_uri` 关联） | `lake://memory` |
| Skills | 文件存 SeaweedFS，元信息存 Iceberg，语义检索走 LanceDB | `lake://skills` |
| Experience | Iceberg 事件表 | `lake://experience` |

## 设计原则（不可偏离）

1. 统一存储底座
2. 统一元数据
3. 计算与引擎分离
4. Agent 直连引擎（经 MCP 代理）

新增组件或 API 层时应对照这四条判断是否偏离设计。

## 语言与文档约定

- 设计文档为中文。新增的设计说明、架构注释倾向用中文以保持一致；代码标识符用英文。
- 代码不加注释，除非逻辑非显而易见。
