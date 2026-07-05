# LLM 模型网关实现报告

**日期**: 2026-07-05  
**状态**: 完成，全部测试通过

---

## 1. 总览

模型网关已实现在 LakeMindServer 中，作为 `cognitive.llm` 引擎，遵循现有插件架构（Protocol + Registry + engines.yaml）。

### 测试结果

| 测试套件 | 测试数 | 通过 | 失败 |
|----------|--------|------|------|
| verify_llm.py (LLM 网关) | 10 | 10 | 0 |
| verify_api.py (REST API) | 104 | 104 | 0 |
| verify_three_mcp.py (三 MCP) | 22 | 22 | 0 |
| test_full_suite.py (全量功能) | 69 | 69 | 0 |
| verify_monitor.py (Monitor) | 18 | 18 | 0 |
| verify_ray.py (Ray 分布式) | 12 | 12 | 0 |
| **合计** | **235** | **235** | **0** |

---

## 2. 架构

```
Steward / MCP → REST /api/v1/cognitive/llm/chat
                     ↓
                GatewayLLM (路由器)
                     ↓
           OpenAICompatProvider (httpx)
                     ↓
           外部 LLM API (ModelArts/DeepSeek)
```

### 引擎体系位置

```
cognitive:
  embedding: fastembed     # 已有：向量嵌入
  memory: basic            # 已有：记忆引擎
  llm: gateway             # 新增：LLM 推理网关
```

---

## 3. 新增文件

| 文件 | 说明 | 行数 |
|------|------|------|
| `plugins/cognitive/llm/__init__.py` | 包初始化 | 0 |
| `plugins/cognitive/llm/openai_compat.py` | OpenAI 兼容 provider | 72 |
| `plugins/cognitive/llm/anthropic.py` | Anthropic provider | 80 |
| `plugins/cognitive/llm/ollama.py` | Ollama provider | 72 |
| `plugins/cognitive/llm/gateway.py` | GatewayLLM 路由器 | 130 |
| `api/llm.py` | REST API 路由 (4 端点) | 62 |
| `scripts/verify_llm.py` | 测试脚本 | 120 |

## 4. 修改文件

| 文件 | 改动 |
|------|------|
| `plugins/protocols.py` | +LLMPlugin Protocol (chat/embed/list_models/health) |
| `plugins/registry.py` | +cognitive.llm: {gateway} |
| `engines.py` | +self.llm + all_health()["llm"] |
| `config.py` | +llm 字段 + 递归 env 解析 |
| `config/engines.yaml` | +cognitive.llm 段 (modelarts/deepseek-v4-flash) |
| `app.py` | +llm 路由注册 |
| `docker-compose.yml` | +MAAS_API_KEY 环境变量 |
| `.env` | +MAAS_API_KEY |

---

## 5. REST API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/cognitive/llm/chat` | 聊天补全 |
| POST | `/api/v1/cognitive/llm/embed` | LLM embedding |
| GET | `/api/v1/cognitive/llm/models` | 列出可用模型 |
| GET | `/api/v1/cognitive/llm/health` | 网关健康 |

OpenAPI 路径总数：36 → **40**

---

## 6. LLMPlugin Protocol

```python
class LLMPlugin(Protocol):
    def chat(self, messages: list[dict], model: str = "",
             temperature: float = 0.7, max_tokens: int = 0,
             **kwargs) -> dict: ...
    def embed(self, texts: list[str], model: str = "") -> list[list[float]]: ...
    def list_models(self) -> list[dict]: ...
    def health(self) -> bool: ...
```

---

## 7. Provider 实现

### 7.1 OpenAICompatProvider
- 覆盖：OpenAI / DeepSeek / vLLM / Ollama OpenAI 模式 / ModelArts
- 端点：`/chat/completions` + `/embeddings`
- 认证：`Authorization: Bearer {api_key}`
- 72 行，纯 httpx

### 7.2 AnthropicProvider
- 覆盖：Claude 系列
- 端点：`/v1/messages`
- 认证：`x-api-key` + `anthropic-version`
- system prompt 单独传，消息格式适配
- 80 行

### 7.3 OllamaProvider
- 覆盖：Ollama 本地模型
- 端点：`/api/chat` + `/api/embeddings`
- 无需认证
- 72 行

### 7.4 GatewayLLM (路由器)
- 多 provider 路由：按 priority 排序
- `model=auto`：自动选优先级最高的可用模型
- Fallback 链：主模型失败 → 依次尝试备用
- 模型注册表：model_id → provider 映射
- 130 行

---

## 8. 配置

```yaml
cognitive:
  llm:
    plugin: gateway
    config:
      default_chat_model: "auto"
      providers:
        - name: "modelarts"
          type: "openai_compat"
          base_url: "https://api.modelarts-maas.com/openai/v1"
          api_key: "${MAAS_API_KEY}"
          models:
            - id: "deepseek-v4-flash"
              context: 64000
              tags: [chat, general]
          priority: 1
      fallback:
        chat: ["deepseek-v4-flash"]
```

环境变量 `${MAAS_API_KEY}` 递归解析，支持嵌套 list/dict 结构。

---

## 9. 测试详情 (10/10 PASS)

### 基础测试 (3/3)
| 测试 | 说明 |
|------|------|
| health check | llm=true |
| system health | all_health 包含 llm |
| list models | deepseek-v4-flash / modelarts |

### Chat 功能测试 (5/5)
| 测试 | 说明 | 响应 |
|------|------|------|
| basic chat | 1 条消息 | "Hello" |
| system prompt | 中文回复 | "2+3=5" |
| auto model | model=auto 路由 | DeepSeek-V4-Flash |
| multi-turn | 3 轮对话记忆 | "Your name is Alice" |
| usage tokens | token 计数 | prompt + completion |

### 能力测试 (2/2)
| 测试 | 说明 | 结果 |
|------|------|------|
| long response | 500 token 限制 | 1734 chars |
| concurrent | 3 并发请求 | 全部成功 |

---

## 10. 引擎健康状态 (11 引擎)

```
object_storage:  true
tabular:         true
vector:          true
kv:              true
graph:           true
metadata:        true
sql:             true
distributed:     true   (Ray 3 nodes, 12 CPU)
embedding:       true   (fastembed)
memory:          true   (BasicMemory)
llm:             true   (GatewayLLM → deepseek-v4-flash)  ← 新增
```

---

## 11. 设计原则对照

| 原则 | 对照 |
|------|------|
| 薄 wrapper 包裹开源库 | httpx 直连外部 API，72-130 行/provider |
| 零新依赖 | httpx 已有，不引入 litellm/openai SDK |
| 插件可替换 | plugin: gateway 可换 plugin: openai_compat 直连 |
| 配置驱动 | engines.yaml 声明 providers + routing + fallback |
| HTTP 统一 | 全项目用 httpx，LLM 调用也用 httpx |
| 计算与引擎分离 | LLM 作为 cognitive 引擎，与存储/计算分离 |

---

## 12. 后续扩展

1. **Steward 接入**: 改 agent.py 用 `/api/v1/cognitive/llm/chat` 替代关键词匹配
2. **MCP 工具增强**: DataMCP 加 nl2sql，AssetMCP 加 summarize
3. **mem0 记忆**: 用 LLM 做事实抽取
4. **更多 Provider**: 取消 engines.yaml 中 OpenAI/Anthropic/Ollama 的注释，填入 API key 即可
5. **流式响应**: SSE stream 支持
