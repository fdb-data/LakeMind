# 快速入门

本文帮助你从零启动 LakeMind v0.1.0，完成全部验证。

## 前置要求

- Docker + Docker Compose
- Python 3.12+（运行验证脚本）
- 可用内存 ≥ 8GB（含 Ray 集群）
- 磁盘空间 ≥ 20GB（镜像 + 数据）

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
| lakemind-dragonfly | 6379 | TTL KV 缓存 |
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
| lakemind-asset-mcp | 8401 | 11 tools, 7 resources |
| lakemind-data-mcp | 8402 | 13 tools |
| lakemind-admin-mcp | 8403 | 15 tools |

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
python scripts/verify_api.py          # 104 REST API 测试
python scripts/verify_three_mcp.py    # 22 三 MCP 联合
python scripts/test_full_suite.py     # 69 全量功能
python scripts/verify_llm.py          # 10 LLM 网关
python LakeMindServer/scripts/verify_ray.py       # 12 Ray 分布式
python LakeMindMonitor/scripts/verify_monitor.py  # 18 Monitor
```

期望结果：**235/235 PASS**

## 5. 第一个 Agent 调用

通过 AssetMCP 摄入知识并检索：

```python
import httpx

# 摄入知识
r = httpx.post("http://localhost:8401/mcp/tools/call", json={
    "method": "tools/call",
    "params": {
        "name": "ingest_knowledge",
        "arguments": {
            "kb": "my_kb",
            "documents": [
                {"content": "LakeMind 是 Agent 原生的多模态智能数据底座"},
                {"content": "LakeMind 使用 MCP 协议作为 Agent 入口"},
            ]
        }
    },
    "headers": {"Authorization": "Bearer test-business-token"}
})

# 语义检索
r = httpx.post("http://localhost:8401/mcp/tools/call", json={
    "method": "tools/call",
    "params": {
        "name": "search_knowledge",
        "arguments": {"kb": "my_kb", "query": "什么是 LakeMind", "top_k": 3}
    },
    "headers": {"Authorization": "Bearer test-business-token"}
})
print(r.json())
```

## 6. LLM 对话

通过 REST API 调用 LLM 网关：

```bash
curl -X POST http://localhost:10823/api/v1/cognitive/llm/chat \
  -H "Authorization: Bearer lakemind-internal-api-key" \
  -H "X-Tenant-Id: default" \
  -H "X-Agent-Id: test" \
  -H "X-Scopes: all" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好，LakeMind 是什么？"}],
    "model": "auto",
    "max_tokens": 100
  }'
```

## 下一步

- [架构设计](architecture.md) — 理解两层模型、三 MCP、三大引擎
- [API 参考](api-reference.md) — REST API 40+ 端点完整文档
- [MCP 工具](mcp-tools.md) — 39 个 MCP 工具详细说明
- [配置参考](configuration.md) — engines.yaml 引擎切换指南
- [部署运维](deployment.md) — 容器管理、引擎切换、故障排查
