# LakeMind 全量验证报告

**日期**: 2026-07-05  
**环境**: Windows + Docker (单机 docker-compose)  
**测试人**: opencode (glm-5.2)

---

## 1. 总览

| 测试套件 | 测试数 | 通过 | 失败 | 结果 |
|----------|--------|------|------|------|
| verify_api.py (REST API) | 103 | 103 | 0 | ✅ ALL PASS |
| verify_three_mcp.py (三 MCP 联合) | 22 | 22 | 0 | ✅ ALL PASS |
| test_full_suite.py (全量功能) | 69 | 69 | 0 | ✅ ALL PASS |
| verify_monitor.py (Monitor) | 18 | 18 | 0 | ✅ ALL PASS |
| verify_ray.py (Ray 分布式) | 12 | 12 | 0 | ✅ ALL PASS |
| **合计** | **224** | **224** | **0** | **✅ ALL PASS** |

---

## 2. 容器状态

12 个容器全部运行：

| 容器 | 状态 | 端口 | CPU | 内存 |
|------|------|------|-----|------|
| lakemind-server-api | Up | 10823 | 1.10% | 443 MB |
| lakemind-postgres | Up | 5432 | 0.00% | 35 MB |
| lakemind-seaweedfs | Up | 8333/8888/9333 | 0.41% | 90 MB |
| lakemind-valkey | Up (healthy) | 6379 | 2.52% | 23 MB |
| lakemind-ray-head | Up | 8265 | 12.15% | 871 MB |
| lakemind-ray-worker-1 | Up | - | 3.82% | 334 MB |
| lakemind-ray-worker-2 | Up | - | 7.40% | 420 MB |
| lakemind-asset-mcp | Up | 8401 | 0.20% | 47 MB |
| lakemind-data-mcp | Up | 8402 | 0.19% | 47 MB |
| lakemind-admin-mcp | Up | 8403 | 0.17% | 44 MB |
| lakemind-steward | Up | 8500 | 0.16% | 62 MB |
| lakemind-monitor | Up | 3000 | 0.00% | 21 MB |

---

## 3. 引擎健康状态

10 个引擎全部健康：

```
object_storage:  true   (SeaweedFS)
tabular:         true   (Iceberg + Gravitino)
vector:          true   (LanceDB)
kv:              true   (Valkey)
graph:           true   (PostgreSQL)
metadata:        true   (PostgreSQL)
sql:             true   (DuckDB)
distributed:     true   (Ray 2.41.0, 3 nodes, 12 CPU)
embedding:       true   (fastembed BAAI/bge-small-en-v1.5, dim=384)
memory:          true   (BasicMemory)
```

---

## 4. Ray 分布式计算引擎

### 4.1 集群配置

| 组件 | 镜像 | CPU | 内存 |
|------|------|-----|------|
| ray-head | lakemind/ray:2.41.0-py3.12 | 4 | 871 MB |
| ray-worker-1 | lakemind/ray:2.41.0-py3.12 | 4 | 334 MB |
| ray-worker-2 | lakemind/ray:2.41.0-py3.12 | 4 | 420 MB |
| **合计** | | **12 CPU** | **15.02 GB memory** |

- Ray 版本: 2.41.0
- Python: 3.12
- 连接方式: `ray://lakemind-ray-head:10001` (Ray Client)
- Dashboard: http://localhost:8265

### 4.2 功能测试 (7/7 PASS)

| 测试 | 说明 | 结果 |
|------|------|------|
| health check | distributed=true | PASS |
| submit/status/result | sum([1..5])=15 | PASS |
| sleep_test | 异步任务 2s | PASS |
| map | 5 项并行 remote tasks | PASS |
| parallel_map | 100 项 4 workers 批量 | PASS |
| not_found | 无效 job_id | PASS |
| generic | 未知 func 降级 | PASS |

### 4.3 能力测试 (5/5 PASS)

| 测试 | 说明 | 结果 |
|------|------|------|
| Monte Carlo π | 4M 样本 4 workers, π≈3.141602 | PASS |
| Matrix multiply | 200×200, sum(A@B)≈1.99M | PASS |
| Large parallel_map | 1000 项 8 workers | PASS |
| 10 concurrent jobs | 全部正确返回 4950 | PASS |
| Ray cluster 3 nodes | head + 2 workers | PASS |

### 4.4 支持的分布式任务类型

| func | 说明 | 参数 |
|------|------|------|
| `map` | 并行 map（每项一个 Ray task） | fn, items |
| `parallel_map` | 批量 map（连续分块） | fn, items, num_workers |
| `sum` | 分布式求和 | data |
| `sleep_test` | 异步延迟测试 | n |
| `embed_batch` | 批量 embedding | texts |
| `pi_monte_carlo` | Monte Carlo π 估计 | n_samples, num_workers |
| `matrix_multiply` | 矩阵乘法 | size |
| (其他) | generic 降级 | args |

---

## 5. REST API 详细结果 (103/103 PASS)

### 5.1 认证 (3/3)
- 无 auth → 401 ✅
- 错误 key → 401 ✅
- health 免 auth → 200 ✅

### 5.2 System (14/14)
- 10 引擎健康检查全 true ✅
- nodes/metrics 端点 ✅

### 5.3 Objects - SeaweedFS (9/9)
- put/get/exists/list/delete ✅
- 批量 5 keys ✅

### 5.4 Tables - Iceberg (13/13)
- create/list/describe/append/scan/overwrite/drop ✅
- scan limit + select columns ✅

### 5.5 Vectors - LanceDB (8/8)
- create/list/describe/add/search ✅
- 10 向量 + 3 追加 + top-5 搜索 ✅

### 5.6 KV - Valkey (9/9)
- set/get/delete + TTL 过期 ✅
- 批量 scan 5 ✅

### 5.7 Graph - PostgreSQL (9/9)
- add node/edge + query + delete ✅

### 5.8 SQL - DuckDB (5/5)
- select/count/filter+order ✅

### 5.9 Jobs - Ray (5/5)
- submit/status/result ✅

### 5.10 Embedding - fastembed (5/5)
- 2 文本 → 2 向量 × 384 维 ✅

### 5.11 Memory - BasicMemory (7/7)
- remember(长期/短期) + recall + forget ✅

### 5.12 Metadata - PostgreSQL (16/16)
- tenant/user/token/asset_type CRUD ✅

---

## 6. 三 MCP 联合验证 (22/22 PASS)

### 6.1 各 MCP 工具数

| MCP | 端口 | scope | 工具数 | 资源数 |
|-----|------|-------|--------|--------|
| AssetMCP | 8401 | asset | 11 | 7 |
| DataMCP | 8402 | data | 13 | - |
| AdminMCP | 8403 | admin | 15 | - |

### 6.2 跨 MCP 集成

- AdminMCP 创建 tenant/user/token → AssetMCP/DataMCP 使用 ✅
- AssetMCP ontology 跨 MCP 查询 ✅
- scope 隔离: business token 被 DataMCP 拒绝 ✅
- Steward chat → MCP 路由 ✅
- Steward inspect workflow ✅

---

## 7. 全量功能测试 (69/69 PASS)

### 7.1 AssetMCP (34 tests)
- Knowledge CRUD + 批量 50 docs + 50 并发搜索 ✅
- Skill CRUD ✅
- Memory CRUD + 30 并发 remember/recall ✅
- Ontology CRUD + relation ✅
- 7 resources 全可读 ✅

### 7.2 DataMCP (12 tests)
- Iceberg create/write/query/list/describe ✅
- DuckDB SQL ✅
- LanceDB vector query ✅
- S3 put/get ✅
- Valkey kv set/get ✅
- Graph query/update ✅
- 50 并发 kv set+get ✅

### 7.3 AdminMCP (12 tests)
- Tenant/User/Token/AssetType CRUD ✅
- Platform health/status ✅

### 7.4 Scope Isolation (4 tests)
- business token 被 DataMCP/AdminMCP 拒绝 ✅
- monitor token 被 DataMCP 拒绝 ✅
- steward token 在 AssetMCP 允许 ✅

### 7.5 Cross-MCP (3 tests)
- AdminMCP-issued token → AssetMCP ✅
- Steward chat → MCP routing ✅
- Steward inspect ✅

### 7.6 Monitor (4 tests)
- Steward health ✅
- Monitor health ✅

---

## 8. Monitor 验证 (18/18 PASS)

| 路由 | 测试 | 结果 |
|------|------|------|
| GET / | 静态页面 | PASS |
| GET /api/health | 4 服务健康 | PASS |
| GET /api/asset/* | 5 资产路由 | PASS |
| GET /api/data/tables | 数据路由 | PASS |
| GET /api/admin/* | 4 管理路由 | PASS |
| POST /api/chat | 对话 | PASS |
| POST /api/inspect | 巡检 | PASS |

---

## 9. 引擎切换验证

### Ray → embedded 降级
```
engines.yaml: plugin: embedded → distributed: true (EmbeddedCompute)
engines.yaml: plugin: ray     → distributed: true (RayCompute, 3 nodes)
```
两种模式均正常工作，切换无需改代码，只改配置文件。

---

## 10. 镜像清单

| 镜像 | 大小 | 说明 |
|------|------|------|
| lakemind/server-api:latest | 2.06 GB | REST API + 10 引擎 + Ray Client |
| lakemind/ray:2.41.0-py3.12 | 914 MB | Ray head + worker（自建） |
| lakemind/asset-mcp:latest | 478 MB | AssetMCP 瘦客户端 |
| lakemind/data-mcp:latest | 478 MB | DataMCP 瘦客户端 |
| lakemind/admin-mcp:latest | 478 MB | AdminMCP 瘦客户端 |
| lakemind/steward:latest | 196 MB | Steward Agent |
| lakemind-monitor:latest | 143 MB | Monitor 仪表板 |
| postgres:16 | 451 MB | 元数据 + 图存储 |
| chrislusf/seaweedfs:latest | 255 MB | 对象存储 |
| valkey/valkey:8.0 | 131 MB | KV 缓存 |

---

## 11. 架构拓扑

```
                    ┌─────────────────────────────────────────┐
                    │           LakeMindServer (数据平面)       │
                    │                                         │
                    │  server-api (:10823)                    │
                    │    ├── SeaweedFS (:8333)   [对象存储]    │
                    │    ├── PostgreSQL (:5432)  [元数据+图]   │
                    │    ├── Valkey (:6379)   [KV缓存]     │
                    │    ├── Iceberg/LanceDB/DuckDB [嵌入式]  │
                    │    ├── fastembed [embedding]            │
                    │    └── Ray Client → Ray Cluster         │
                    │                                         │
                    │  Ray Cluster (--profile ray)            │
                    │    ├── ray-head (:8265)    [4 CPU]      │
                    │    ├── ray-worker-1        [4 CPU]      │
                    │    └── ray-worker-2        [4 CPU]      │
                    └─────────────────────────────────────────┘
                                    ↑ REST API
                    ┌───────────────┼───────────────┐
                    │               │               │
              AssetMCP         DataMCP         AdminMCP
              (:8401)          (:8402)         (:8403)
              11 tools         13 tools        15 tools
                    │
              Steward (:8500) → Monitor (:3000)
```

---

## 12. 启动命令

```bash
# 1. 数据平面 + Ray 集群
cd LakeMindServer
docker compose --env-file .env --profile ray up -d

# 2. 三 MCP
cd LakeMindMCP
docker compose --profile all up -d

# 3. Steward + Monitor
cd LakeMindMonitor
docker compose up -d
```

---

## 13. 验证命令

```bash
python scripts/verify_api.py          # 103 REST API 测试
python scripts/verify_three_mcp.py    # 22 三 MCP 联合
python scripts/test_full_suite.py     # 69 全量功能
python LakeMindMonitor/scripts/verify_monitor.py  # 18 Monitor
python LakeMindServer/scripts/verify_ray.py       # 12 Ray 分布式
```

---

## 14. 结论

**224/224 全部通过，零失败。**

- LakeMindServer REST API 36 个 OpenAPI 路径，10 引擎全部健康
- Ray 分布式计算引擎完整实现：3 节点 12 CPU，7 种任务类型，功能+能力测试全通过
- 3 MCP 瘦客户端（39 工具）全部通过 REST API 连接 server-api
- Steward + Monitor 运行平面正常
- 引擎可插拔切换验证通过（embedded ↔ ray）
