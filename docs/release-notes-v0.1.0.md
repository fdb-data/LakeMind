# LakeMind v0.1.0 发布说明

**发布日期**: 2026-07-05  
**代号**: Agent-Native Data Foundation MVP

---

## 发布摘要

LakeMind v0.1.0 是首个可用版本，实现了 Agent 原生的多模态智能数据底座的完整 MVP 功能。

**235 项测试全部通过，12 个容器全部运行，11 个引擎全部健康。**

---

## 核心能力

### 1. 统一数据底座

Agent 不再需要对接五种存储、六种 SDK。LakeMind 通过统一 REST API 网关提供全部数据能力：

- **对象存储** (SeaweedFS)：S3 兼容，存数据文件 / 向量 / Skill 代码
- **结构化表** (Apache Iceberg)：PG SQL catalog，支持 append / overwrite / scan
- **向量检索** (LanceDB)：语义搜索，共享 Lance 目录
- **KV 缓存** (Dragonfly)：Redis 兼容 TTL KV，短期记忆
- **图存储** (PostgreSQL)：本体 / 实体关系，JSONB 属性
- **元数据** (PostgreSQL)：用户 / 租户 / Token / 资产定义

### 2. 分布式计算

Ray 2.41 集群（3 节点 12 CPU），支持 7 种分布式任务：
- 并行 map / 批量 parallel_map
- Monte Carlo π 估计（4M 样本 4 workers）
- 矩阵乘法
- 批量 embedding
- 10 并发作业

### 3. LLM 推理网关

自建 GatewayLLM，支持多 provider 路由 + fallback 降级：
- OpenAI 兼容（OpenAI / DeepSeek / vLLM / ModelArts / Ollama OpenAI 模式）
- Anthropic（Claude 系列）
- Ollama 本地
- 零新依赖（httpx 直连，240 行代码）

### 4. Agent MCP 接口

39 个 MCP 工具，3 个独立 MCP 服务：
- **AssetMCP** (11 tools, 7 resources)：知识 / 技能 / 记忆 / 本体
- **DataMCP** (13 tools)：Iceberg / DuckDB / LanceDB / S3 / Dragonfly / Graph
- **AdminMCP** (15 tools)：用户 / 租户 / Token / 资产类型 / 平台健康

### 5. 运维工具

- **Steward**：LangGraph 巡检工作流 + 对话管理
- **Monitor**：人类仪表板 + Steward 对话窗

---

## 快速开始

```bash
# 1. 数据平面
cd LakeMindServer && docker compose --env-file .env --profile ray up -d

# 2. 三个 MCP
cd LakeMindMCP && docker compose --profile all up -d --build

# 3. Steward + Monitor
cd LakeMindMonitor && docker compose up -d --build

# 4. 验证
python scripts/verify_api.py    # 104/104 PASS
```

详见 [快速入门](quickstart.md)。

---

## 引擎可插拔

所有引擎通过 `engines.yaml` 配置切换，不改代码：

| 引擎 | 当前 | 可切换到 |
|------|------|----------|
| 对象存储 | SeaweedFS | AWS S3 / 阿里云 OSS / 华为云 OBS |
| 向量存储 | LanceDB | Milvus / Qdrant |
| KV 缓存 | Dragonfly | Redis / Valkey |
| 分布式计算 | Ray | Embedded（降级） |
| Embedding | fastembed | 外部 API / TEI |
| LLM 网关 | GatewayLLM | — |
| 记忆引擎 | BasicMemory | mem0（规划中） |

---

## 验证结果

| 套件 | 测试数 | 结果 |
|------|--------|------|
| REST API | 104 | ✅ ALL PASS |
| 三 MCP 联合 | 22 | ✅ ALL PASS |
| 全量功能 | 69 | ✅ ALL PASS |
| Monitor | 18 | ✅ ALL PASS |
| Ray 分布式 | 12 | ✅ ALL PASS |
| LLM 网关 | 10 | ✅ ALL PASS |
| **合计** | **235** | **✅ ALL PASS** |

---

## 已知限制

| 限制 | 影响 | 计划 |
|------|------|------|
| 动态 Token 不跨 MCP | MVP 使用静态 Token | v0.2 |
| Steward 未接 LLM | 关键词匹配 | v0.2 |
| LakeMindStudio 未开发 | 无桌面客户端 | v0.3 |
| 流式响应未支持 | LLM chat 同步 | v0.2 |
| per-tenant 模型配置 | 全局模型 | v0.2 |

---

## 文档

| 文档 | 说明 |
|------|------|
| [快速入门](quickstart.md) | 从零启动 LakeMind |
| [架构设计](architecture.md) | 两层模型、三 MCP、三大引擎 |
| [API 参考](api-reference.md) | REST API 40+ 端点 |
| [MCP 工具](mcp-tools.md) | 39 个工具详细说明 |
| [配置参考](configuration.md) | engines.yaml 引擎切换 |
| [部署运维](deployment.md) | 容器管理、故障排查 |
| [变更日志](changelog.md) | 版本变更记录 |

---

## 技术栈

全开源组件（Apache 2.0 / MIT / BSD / PostgreSQL License / BSL 1.1），不引入闭源依赖。

---

## License

全开源组件（Apache 2.0 / MIT / BSD）。
