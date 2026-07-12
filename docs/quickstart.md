# 快速入门

本文帮助你从零启动 LakeMind v0.1.0，完成全部验证。

> **预计耗时**：首次约 15-25 分钟（含镜像构建），后续启动约 2 分钟。
>
> 如果你对项目概念不熟悉，建议先阅读 [核心概念与术语表](glossary.md)（5 分钟）。

## 前置要求

| 要求 | 最低版本 | 用途 |
|------|----------|------|
| Docker + Docker Compose | Docker 24+ | 运行 13 个容器 |
| Python | 3.12+ | 运行验证脚本 |
| 可用内存 | ≥ 8GB | 含 Ray 集群 |
| 磁盘空间 | ≥ 20GB | 镜像 + 数据 |

### 验证前置条件

```bash
docker --version          # Docker version 24+
docker compose version    # Docker Compose v2+
python --version          # Python 3.12+
```

如果 Docker 未安装，参考 [Docker 官方安装指南](https://docs.docker.com/get-docker/)。

## 1. 启动数据平面

```bash
cd LakeMindServer
docker compose --env-file .env --profile ray up -d
```

启动 7 个容器：

| 容器 | 端口 | 用途 |
|------|------|------|
| lakemind-server-api | 10823 | REST API 网关 (40+ 路径) |
| lakemind-postgres | 5432 | 统一元数据 + 图存储 |
| lakemind-seaweedfs | 8333 | S3 对象存储 |
| lakemind-valkey | 6379 | TTL KV 缓存 |
| lakemind-ray-head | 8265 | Ray dashboard |
| lakemind-ray-worker-1/2 | — | Ray worker (各 4 CPU) |

验证：

```bash
curl http://localhost:10823/api/v1/system/health
# 期望：11 个引擎全部 true
```

## 2. 启动三个 MCP

```bash
cd LakeMindMCP
docker compose --profile all up -d --build
```

| 容器 | 端口 | 工具数 |
|------|------|--------|
| lakemind-asset-mcp | 8401 | 23 tools, 11 resources, 6 prompts |
| lakemind-data-mcp | 8402 | 18 tools, 6 resources, 2 prompts |
| lakemind-admin-mcp | 8403 | 17 tools, 6 resources, 2 prompts |

## 3. 启动 Steward + Monitor

```bash
cd LakeMindMonitor
docker compose up -d --build
```

| 容器 | 端口 | 用途 |
|------|------|------|
| lakemind-steward | 8500 | 管理运维 Agent |
| lakemind-monitor | 3000 | 人类仪表板 |

## 4. 验证

```bash
python scripts/verify_full.py  # L0-L9 全分层验证，297/297 PASS
```

期望结果：**297/297 PASS**

## 5. 第一个 Agent 调用

通过 AssetMCP 摄入知识并检索：

```python
import httpx

headers = {"Authorization": "Bearer test-business-token",
           "Content-Type": "application/json"}

# 摄入知识
r = httpx.post("http://localhost:8401/mcp", headers=headers, json={
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
        "name": "ingest_knowledge",
        "arguments": {
            "kb_name": "my_kb",
            "concepts": [
                {"frontmatter": {"type": "concept", "title": "LakeMind"},
                 "body": "LakeMind 是认知资产存取平台"},
            ]
        }
    }
})

# 语义检索
r = httpx.post("http://localhost:8401/mcp", headers=headers, json={
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
        "name": "search_knowledge",
        "arguments": {"kb_name": "my_kb", "query": "什么是 LakeMind", "top_k": 3}
    }
})
print(r.json())
```

## 6. LLM 对话

通过 LakeMindModelServing 调用 LLM：

```bash
curl -X POST http://localhost:10824/v1/chat/completions \
  -H "Authorization: Bearer lakemind-modelserving-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好，LakeMind 是什么？"}],
    "model": "deepseek-v4-flash",
    "max_tokens": 100
  }'
```

## 下一步

- [架构设计](architecture.md) — 理解两层模型、三 MCP、三大引擎
- [API 参考](api-reference.md) — REST API 40+ 端点完整文档
- [MCP 工具](mcp-tools.md) — 58 个 MCP 工具详细说明
- [配置参考](configuration.md) — engines.yaml 引擎切换指南
- [部署运维](deployment.md) — 容器管理、引擎切换、故障排查
