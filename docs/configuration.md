# 配置参考

LakeMind 通过 `engines.yaml` 统一配置所有引擎，支持运行时切换插件实现，不改代码。

## 配置文件位置

- 容器内：`/etc/lakemind/engines.yaml`（bind mount from `config/engines.yaml`）
- 环境变量：`LAKE_CONFIG` 可覆盖路径

## 环境变量解析

配置中 `${VAR}` 语法自动解析为环境变量：

```yaml
api_key: "${MAAS_API_KEY}"    # → os.environ["MAAS_API_KEY"]
```

支持嵌套 list/dict 递归解析。

## 完整配置结构

```yaml
server:
  host: "0.0.0.0"
  port: 10823
  api_key: "lakemind-internal-api-key"

storage:
  object:       # 对象存储
  tabular:      # 结构化表
  vector:       # 向量存储
  kv:           # KV 缓存
  graph:        # 图存储
  metadata:     # 元数据

compute:
  sql:          # 即席 SQL
  distributed:  # 分布式计算

cognitive:
  embedding:    # Embedding
  memory:       # 记忆引擎
  llm:          # LLM 推理网关
```

## 1. 对象存储

```yaml
storage:
  object:
    plugin: seaweedfs
    config:
      endpoint: "http://lakemind-seaweedfs:8333"
      access_key: "admin"
      secret_key: "admin123456"
      region: "us-east-1"
      path_style: true
```

切换到 AWS S3：

```yaml
    plugin: aws_s3
    config:
      endpoint: "https://s3.amazonaws.com"
      access_key: "${AWS_ACCESS_KEY_ID}"
      secret_key: "${AWS_SECRET_ACCESS_KEY}"
      region: "us-east-1"
      path_style: false
```

## 2. 结构化表

```yaml
storage:
  tabular:
    plugin: iceberg
    config:
      catalog_name: "lakemind"
      warehouse: "s3://lakemind-iceberg/warehouse"
      sql_uri: "postgresql+psycopg2://lakemind:lakemind_pass@lakemind-postgres:5432/lakemind"
```

## 3. 向量存储

```yaml
storage:
  vector:
    plugin: lancedb
    config:
      uri: "/data/lance"
```

## 4. KV 缓存

```yaml
storage:
  kv:
    plugin: valkey
    config:
      host: "lakemind-valkey"
      port: 6379
      password: ""
```

切换到 Redis：

```yaml
    plugin: redis
    config:
      host: "my-redis"
      port: 6379
```

## 5. 图存储

```yaml
storage:
  graph:
    plugin: postgres_graph
    config:
      host: "lakemind-postgres"
      port: 5432
      db: "lakemind"
      user: "lakemind"
      password: "lakemind_pass"
```

## 6. 元数据

```yaml
storage:
  metadata:
    plugin: postgres
    config:
      host: "lakemind-postgres"
      port: 5432
      db: "lakemind"
      user: "lakemind"
      password: "lakemind_pass"
      pool_size: 20
```

## 7. 即席 SQL

```yaml
compute:
  sql:
    plugin: duckdb
    config:
      memory_limit: "2GB"
```

## 8. 分布式计算

```yaml
compute:
  distributed:
    plugin: ray
    config:
      address: "ray://lakemind-ray-head:10001"
```

切换回嵌入式（无 Ray）：

```yaml
    plugin: embedded
    config: {}
```

## 9. Embedding

```yaml
cognitive:
  embedding:
    plugin: fastembed
    config:
      model: "jinaai/jina-embeddings-v2-base-zh"
      dim: 768
```

切换到外部 API：

```yaml
    plugin: external
    config:
      base_url: "https://api.openai.com/v1"
      model: "text-embedding-3-small"
      dim: 1536
      api_key: "${EMBEDDING_API_KEY}"
```

## 10. 记忆引擎

```yaml
cognitive:
  memory:
    plugin: basic
    config:
      host: "lakemind-postgres"
      port: 5432
      db: "lakemind"
      user: "lakemind"
      password: "lakemind_pass"
      kv_host: "lakemind-valkey"
      embedding_model: "jinaai/jina-embeddings-v2-base-zh"
      kv_port: 6379
      lance_uri: "/data/lance"
      embedding_dim: 768
```

## 11. LLM 推理网关

```yaml
cognitive:
  llm:
    plugin: gateway
    config:
      default_chat_model: "auto"
      default_embed_model: "auto"
      providers:
        # OpenAI 兼容（DeepSeek / ModelArts / vLLM）
        - name: "modelarts"
          type: "openai_compat"
          base_url: "https://api.modelarts-maas.com/openai/v1"
          api_key: "${MAAS_API_KEY}"
          models:
            - id: "deepseek-v4-flash"
              context: 64000
              tags: [chat, general]
          priority: 1

        # OpenAI
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

        # Anthropic
        - name: "anthropic"
          type: "anthropic"
          api_key: "${ANTHROPIC_API_KEY}"
          models:
            - id: "claude-3-haiku-20240307"
              context: 200000
              tags: [chat, general]
          priority: 3

        # Ollama 本地
        - name: "ollama"
          type: "ollama"
          base_url: "http://host.docker.internal:11434"
          models:
            - id: "qwen2.5:7b"
              context: 32768
              tags: [chat, general]
          priority: 4

      # Fallback 链
      fallback:
        chat: ["deepseek-v4-flash", "gpt-4o-mini", "claude-3-haiku-20240307"]
        embed: ["text-embedding-3-small"]
```

### Provider 类型

| type | 覆盖 | 认证方式 |
|------|------|----------|
| `openai_compat` | OpenAI / DeepSeek / vLLM / Ollama OpenAI 模式 / ModelArts | Bearer Token |
| `anthropic` | Claude 系列 | x-api-key + anthropic-version |
| `ollama` | Ollama 原生 API | 无需认证 |

### 路由逻辑

- `model: "auto"` → 按 priority 选第一个可用的模型
- `model: "deepseek-v4-flash"` → 指定模型
- 主模型失败 → 按 fallback 链依次尝试
- 未设置 API key 的 provider 自动跳过（health=false）

## .env 环境变量

```env
# SeaweedFS
SEAWEEDFS_IMAGE=chrislusf/seaweedfs:latest
S3_ACCESS_KEY=admin
S3_SECRET_KEY=admin123456

# PostgreSQL
PG_DB=lakemind
PG_USER=lakemind
PG_PASSWORD=lakemind_pass

# Valkey
VALKEY_IMAGE=valkey/valkey:8.0

# Ray
RAY_IMAGE=lakemind/ray:2.41.0-py3.12
RAY_HEAD_CPUS=4
RAY_WORKER_CPUS=4

# LLM 网关
MAAS_API_KEY=your-key-here
# OPENAI_API_KEY=your-openai-key
# ANTHROPIC_API_KEY=your-anthropic-key
```
