# 零售业务 Agent 示例

演示一个零售业务 Agent 如何通过 LakeMind AssetMCP 管理认知资产。

## 架构

```
retail-agent ──→ AssetMCP (:8401) ──→ LakeMindServer (:10823) ──→ 11 引擎
                   (MCP 协议)          (REST API)
```

Agent 只对接 AssetMCP，不关心底层存储引擎。

## 文件说明

| 文件 | 说明 |
|------|------|
| `lakemind_client.py` | LakeMind MCP 客户端封装（Knowledge/Memory/Skill） |
| `agent.py` | 零售 Agent 主逻辑（摄入知识 → 检索 → 记忆 → 技能） |
| `Dockerfile` | 容器化构建 |
| `pyproject.toml` | Python 项目配置 |

## 快速运行

### 前置：LakeMind 已启动

```bash
cd LakeMindServer && docker compose --env-file .env --profile ray up -d
cd LakeMindMCP && docker compose --profile all up -d --build
```

### 方式 1：本地运行

```bash
cd examples/retail-agent
pip install httpx
python agent.py
```

### 方式 2：Docker 运行

```bash
cd examples/retail-agent
docker build -t retail-agent .
docker run --network host -e ASSET_MCP_URL=http://localhost:8401/mcp retail-agent
```

## Agent 做了什么

1. **摄入商品知识** — 用 OKF 格式写入 2 个商品概念（保温杯、咖啡机）
2. **语义检索** — 查询"户外喝热饮需要什么装备"
3. **记录用户偏好** — mem0 风格记忆，LLM 自动从对话抽取事实并去重
4. **检索记忆** — 查询用户偏好辅助推荐决策
5. **注册技能** — 注册 `recommend_product` 技能代码（平台只存取不执行）
6. **检索技能** — 语义检索已注册的技能
7. **资源浏览** — 通过 `lake://` URI 浏览知识库和记忆概况

## 关键设计

- Agent 通过 **MCP 协议** 访问 LakeMind，不直连任何存储引擎
- 知识用 **OKF 格式**（YAML frontmatter + markdown body）
- 记忆用 **mem0 风格**（LLM 事实抽取 + 哈希去重）
- 技能 **只注册不执行**（`execute_skill` 已移除，Agent 自行检索并在运行时执行）
