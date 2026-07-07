# 模型网关设计与改造方案

**日期**: 2026-07-05  
**状态**: 待批准

---

## 1. 背景与动机

### 1.1 现状

| 能力 | 现状 | 问题 |
|------|------|------|
| Embedding | fastembed 本地 ONNX（jinaai/jina-embeddings-v2-base-zh, dim=768） | 中英混合，无法用外部模型 |
| LLM 对话 | Steward `provider: "simple"` 关键词匹配 | 无真实 LLM 推理能力 |
| mem0 记忆 | 延迟 | 依赖 LLM 做事实抽取 |
| MCP 工具 | 39 个工具无 LLM 调用 | 无法做智能分析、生成 |
| 外部模型 | 无接入点 | 无法用 OpenAI/Claude/DeepSeek/Ollama |

### 1.2 目标

在 LakeMindServer 中新增**模型网关**（Model Gateway），作为统一的 LLM/Embedding 推理入口：

- 支持多 provider（OpenAI 兼容、Anthropic、Ollama 本地）
- 支持聊天补全（chat completion）和文本嵌入（text embedding）
- 支持模型路由：按 tenant/scope/task 类型自动选择模型
- 支持降级 fallback：主模型不可用时自动切换备用
- 复用现有插件架构（Protocol + Registry + engines.yaml）
- Steward / MCP / Ray 均通过 REST API 调用

---

## 2. 架构设计

### 2.1 在引擎体系中的位置

```
cognitive:
  embedding:          # 已有：向量嵌入
    plugin: fastembed
  memory:             # 已有：记忆引擎
    plugin: basic
  llm:                # 新增：LLM 推理网关
    plugin: gateway   # 网关路由器
    config:
      providers: ...
      routing: ...
```

新增引擎类别 `cognitive.llm`，遵循现有 `build_engine()` 机制。

### 2.2 插件层次

```
LLMPlugin (Protocol)
├── GatewayLLM           # 网关路由器（默认入口）
│   ├── 路由逻辑：按 model/tenant/task 选 provider
│   ├── Fallback：主 → 备 → 降级
│   └── 转发到具体 provider
├── OpenAICompatProvider  # OpenAI 兼容（OpenAI/DeepSeek/vLLM/Ollama OpenAI 模式）
├── AnthropicProvider     # Claude 系列
└── OllamaProvider        # Ollama 原生 API
```

`GatewayLLM` 是对外的插件，内部持有多个 provider 实例，按路由规则分发。

### 2.3 调用拓扑

```
Steward (chat/inspect)
    ↓ REST
LakeMindServer /api/v1/cognitive/llm/chat
    ↓
GatewayLLM.chat(messages, model=auto)
    ↓ 路由
OpenAICompatProvider / AnthropicProvider / OllamaProvider
    ↓ HTTP
外部 LLM API (OpenAI / DeepSeek / Ollama / Claude)
```

MCP 工具也可调用 `/api/v1/cognitive/llm/chat` 做智能分析（如 DataMCP 的 SQL 生成、AssetMCP 的知识摘要）。

---

## 3. 接口设计

### 3.1 LLMPlugin Protocol

```python
class LLMPlugin(Protocol):
    def chat(self, messages: list[dict], model: str = "",
             temperature: float = 0.7, max_tokens: int = 0,
             stream: bool = False, **kwargs) -> dict: ...
    def embed(self, texts: list[str], model: str = "") -> list[list[float]]: ...
    def list_models(self) -> list[dict]: ...
    def health(self) -> bool: ...
```

- `chat()`: 聊天补全，输入 messages 列表，返回 `{role, content, model, usage}`
- `embed()`: 文本嵌入（可选，部分 LLM provider 也提供 embedding）
- `list_models()`: 列出可用模型
- `health()`: 健康检查

### 3.2 REST API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/cognitive/llm/chat` | 聊天补全 |
| POST | `/api/v1/cognitive/llm/embed` | LLM embedding（区别于 fastembed） |
| GET | `/api/v1/cognitive/llm/models` | 列出可用模型 |
| GET | `/api/v1/cognitive/llm/health` | 网关健康（含各 provider 状态） |

### 3.3 请求/响应格式

**POST /chat**
```json
{
  "messages": [
    {"role": "system", "content": "你是 LakeMind 管理助手"},
    {"role": "user", "content": "列出所有租户"}
  ],
  "model": "auto",           // auto = 网关路由；或指定 "gpt-4o-mini" / "deepseek-chat" / "claude-3-haiku" 等
  "temperature": 0.7,
  "max_tokens": 0,           // 0 = 不限
  "stream": false            // MVP 先不支持 stream
}
```

响应：
```json
{
  "id": "chat_xxxx",
  "model": "deepseek-chat",
  "choices": [
    {"role": "assistant", "content": "当前系统有以下租户：..."}
  ],
  "usage": {"prompt_tokens": 50, "completion_tokens": 80, "total_tokens": 130}
}
```

**POST /embed**
```json
{
  "texts": ["hello", "world"],
  "model": "auto"            // auto = 用 cognitive.embedding 引擎；或指定 LLM embedding 模型
}
```

响应：
```json
{
  "vectors": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
  "dim": 1536,
  "model": "text-embedding-3-small"
}
```

**GET /models**
```json
{
  "models": [
    {"id": "deepseek-chat", "provider": "openai_compat", "context": 64000},
    {"id": "gpt-4o-mini", "provider": "openai_compat", "context": 128000},
    {"id": "claude-3-haiku", "provider": "anthropic", "context": 200000},
    {"id": "qwen2.5:7b", "provider": "ollama", "context": 32768}
  ]
}
```

---

## 4. 配置设计

### 4.1 engines.yaml 新增段

```yaml
cognitive:
  # ... existing embedding / memory ...

  # ── LLM 推理网关 ──
  llm:
    plugin: gateway
    config:
      # 默认路由策略
      default_chat_model: "auto"       # auto = 按优先级选第一个可用的
      default_embed_model: "auto"

      # Provider 列表
      providers:
        # ── OpenAI 兼容（DeepSeek）──
        - name: "deepseek"
          type: "openai_compat"
          base_url: "https://api.deepseek.com/v1"
          api_key: "${DEEPSEEK_API_KEY}"
          models:
            - id: "deepseek-chat"
              context: 64000
              tags: [chat, general]
            - id: "deepseek-reasoner"
              context: 64000
              tags: [chat, reasoning]
          priority: 1                   # 数字越小优先级越高

        # ── OpenAI 兼容（OpenAI）──
        - name: "openai"
          type: "openai_compat"
          base_url: "https://api.openai.com/v1"
          api_key: "${OPENAI_API_KEY}"
          models:
            - id: "gpt-4o-mini"
              context: 128000
              tags: [chat, general]
            - id: "text-embedding-3-small"
              context: 8191
              tags: [embed]
              dim: 1536
          priority: 2

        # ── Anthropic ──
        - name: "anthropic"
          type: "anthropic"
          api_key: "${ANTHROPIC_API_KEY}"
          models:
            - id: "claude-3-haiku-20240307"
              context: 200000
              tags: [chat, general]
            - id: "claude-3-sonnet-20240229"
              context: 200000
              tags: [chat, reasoning]
          priority: 3

        # ── Ollama 本地 ──
        - name: "ollama"
          type: "ollama"
          base_url: "http://host.docker.internal:11434"
          models:
            - id: "qwen2.5:7b"
              context: 32768
              tags: [chat, general]
            - id: "nomic-embed-text"
              context: 8192
              tags: [embed]
              dim: 768
          priority: 4

      # 路由规则（可选）
      routing:
        - match: {task: "reasoning"}
          model: "deepseek-reasoner"
        - match: {task: "embed"}
          model: "text-embedding-3-small"
        - match: {tenant: "premium"}
          model: "claude-3-sonnet-20240229"

      # Fallback 链
      fallback:
        chat: ["deepseek-chat", "gpt-4o-mini", "claude-3-haiku-20240307", "qwen2.5:7b"]
        embed: ["text-embedding-3-small", "nomic-embed-text"]
```

### 4.2 环境变量

```env
# .env 新增
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

未设置 API key 的 provider 自动跳过（health=false），不影响其他 provider。

---

## 5. 文件清单

### 5.1 新建文件

| 文件 | 说明 |
|------|------|
| `plugins/cognitive/llm/__init__.py` | 包初始化 |
| `plugins/cognitive/llm/protocol.py` | LLMPlugin Protocol（或加到 protocols.py） |
| `plugins/cognitive/llm/gateway.py` | GatewayLLM 路由器 |
| `plugins/cognitive/llm/openai_compat.py` | OpenAI 兼容 provider |
| `plugins/cognitive/llm/anthropic.py` | Anthropic provider |
| `plugins/cognitive/llm/ollama.py` | Ollama provider |
| `api/llm.py` | REST API 路由 |
| `scripts/verify_llm.py` | 模型网关测试脚本 |

### 5.2 修改文件

| 文件 | 改动 |
|------|------|
| `plugins/protocols.py` | 新增 `LLMPlugin` Protocol |
| `plugins/registry.py` | 注册 `cognitive.llm: {gateway}` |
| `engines.py` | 新增 `self.llm = build_engine(...)` + `all_health()` 加 `"llm"` |
| `config.py` | `EnginesConfig` 加 `llm` 字段 + `load_config` 解析 |
| `config/engines.yaml` | 新增 `cognitive.llm` 段 |
| `app.py` | 注册 `llm` 路由 |
| `pyproject.toml` | 加 `httpx`（已有，无需改） |

### 5.3 不改动的文件

- MCP 代码不改（MCP 通过 REST 调用，不直连 LLM）
- Steward 代码暂不改（Phase 2 再改 Steward 接入网关）
- 现有 embedding/memory 引擎不改

---

## 6. 实现细节

### 6.1 GatewayLLM（路由器）

```python
class GatewayLLM:
    def __init__(self, providers: list, routing: list, fallback: dict, **kwargs):
        self._providers = {}  # name -> provider_instance
        self._models = {}     # model_id -> (provider_name, model_info)
        self._routing = routing
        self._fallback = fallback
        # 按 config 初始化各 provider
        for p in providers:
            if p["type"] == "openai_compat":
                self._providers[p["name"]] = OpenAICompatProvider(**p)
            elif p["type"] == "anthropic":
                self._providers[p["name"]] = AnthropicProvider(**p)
            elif p["type"] == "ollama":
                self._providers[p["name"]] = OllamaProvider(**p)

    def chat(self, messages, model="auto", **kwargs) -> dict:
        target = self._resolve_model(model, task="chat")
        # 尝试主模型 → fallback 链
        for m in self._fallback_chain(target, "chat"):
            try:
                return self._call_chat(m, messages, **kwargs)
            except Exception:
                continue
        raise RuntimeError("all providers failed")

    def embed(self, texts, model="auto") -> list[list[float]]:
        # 如果 model=auto 且无 LLM embed 配置，降级到 cognitive.embedding 引擎
        ...

    def list_models(self) -> list[dict]:
        return [{"id": mid, "provider": pname, **info} for mid, (pname, info) in self._models.items()]

    def health(self) -> bool:
        return any(p.health() for p in self._providers.values())
```

### 6.2 OpenAICompatProvider

```python
class OpenAICompatProvider:
    def __init__(self, name, base_url, api_key, models, priority, **kwargs):
        self._base_url = base_url
        self._api_key = api_key
        self._client = httpx.AsyncClient(...)  # 复用 httpx

    async def chat(self, messages, model, **kwargs) -> dict:
        # POST {base_url}/chat/completions
        # OpenAI 标准格式
        ...

    async def embed(self, texts, model) -> list[list[float]]:
        # POST {base_url}/embeddings
        ...

    def health(self) -> bool:
        # 检查 api_key 非空 + base_url 可达
        ...
```

### 6.3 AnthropicProvider

```python
class AnthropicProvider:
    # POST https://api.anthropic.com/v1/messages
    # Header: x-api-key, anthropic-version
    # 请求/响应格式与 OpenAI 不同，需适配
    ...
```

### 6.4 OllamaProvider

```python
class OllamaProvider:
    # POST {base_url}/api/chat
    # POST {base_url}/api/embeddings
    # Ollama 原生格式
    ...
```

---

## 7. 测试方案

### 7.1 单元测试（无外部依赖）

| 测试 | 说明 |
|------|------|
| 网关初始化 | providers 解析、model 注册 |
| 路由逻辑 | model=auto 选优先级最高 |
| Fallback | 主模型失败 → 备用 |
| 健康检查 | 无 API key 的 provider health=false |
| 模型列表 | list_models 返回正确 |
| API 端点 | /chat, /embed, /models, /health 状态码 |

### 7.2 集成测试（需外部 API key）

- 配置 DeepSeek API key → 调用 `deepseek-chat` 真实推理
- 配置 Ollama 本地 → 调用 `qwen2.5:7b` 本地推理
- 无任何 API key → 网关 health=false 但不影响其他引擎

### 7.3 验证脚本

`scripts/verify_llm.py`：
- 6 项单元测试（始终运行）
- 2 项集成测试（有 API key 时运行）
- 验证 `all_health()` 中 `"llm"` 字段正确

---

## 8. 开发步骤

| 步骤 | 内容 | 预计 |
|------|------|------|
| 1 | 新增 `LLMPlugin` Protocol | 5 min |
| 2 | 实现 `OpenAICompatProvider` | 30 min |
| 3 | 实现 `AnthropicProvider` | 20 min |
| 4 | 实现 `OllamaProvider` | 20 min |
| 5 | 实现 `GatewayLLM` 路由器 | 30 min |
| 6 | 注册插件 + 配置解析 | 15 min |
| 7 | 实现 REST API 路由 | 15 min |
| 8 | 更新 engines.yaml + .env | 10 min |
| 9 | 重建 server-api 镜像 | 10 min |
| 10 | 编写 verify_llm.py 测试 | 20 min |
| 11 | 运行测试 + 修复 | 15 min |
| 12 | 运行全量回归测试 | 10 min |
| **合计** | | **~3.5h** |

---

## 9. 设计原则对照

| 原则 | 对照 |
|------|------|
| 统一认知资产管理与多模态数据管理 | LLM 网关为认知计算引擎，支撑记忆事实抽取等认知能力 |
| 统一存储底座 | 不涉及存储，纯推理网关 |
| 统一元数据 | 模型配置在 engines.yaml，不引入新元数据 |
| 计算与引擎分离 | LLM 推理作为 cognitive 引擎，与存储/计算分离 |
| MCP 通过 REST API 调用 | Steward/MCP → REST API → GatewayLLM → Provider |
| 插件可替换 | `plugin: gateway` 可换 `plugin: openai_compat` 直连单 provider |
| 不引入闭源依赖 | httpx 调用外部 API，不引入 SDK；Ollama 开源 |

---

## 10. MVP 范围约束

- **不做**: stream 流式响应、function calling、多模态（图片/音频）、token 计费、per-tenant 限流
- **不做**: 模型微调管理、模型下载（Ollama 自行管理）
- **做**: 同步 chat/embed、多 provider 路由、fallback 降级、模型列表、健康检查
- **做**: OpenAI 兼容 + Anthropic + Ollama 三种 provider

---

## 11. 后续扩展（Phase 2）

1. **Steward 接入**: 改 `agent.py` 用 LLM 做意图识别和回复生成
2. **MCP 工具增强**: DataMCP 加 `nl2sql`（自然语言转 SQL）、AssetMCP 加 `summarize`（知识摘要）
3. **mem0 记忆**: 用 LLM 做事实抽取，实现 mem0 插件
4. **Ray embed_batch**: Ray worker 调用网关做批量 embedding
5. **流式响应**: SSE stream 支持
6. **Per-tenant 配置**: 元数据存储模型偏好
