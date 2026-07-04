# Phase 2 — REST API 验证报告

## 概要

| 项目 | 结果 |
|------|------|
| 功能测试 (verify_api.py) | **103/103 PASS** |
| 性能基准 (单线程) | **12 组全部 0 error** |
| 并发压测 (20 workers × 50 ops) | **8 组 × 1000 ops，全部 0 error** |
| 高并发压测 (50 workers × 100 ops) | **2 组 × 5000 ops，全部 0 error** |
| 可插拔性验证 | **5/5 PASS** |
| OpenAPI 路径数 | **36** |

## 功能测试详情 (103/103 PASS)

### Auth (3/3)
- 无 auth → 401 ✓
- 错误 key → 401 ✓
- health 无需 auth → 200 ✓

### 1. System (14/14)
- 全部 10 引擎健康
- nodes / metrics 端点正常

### 2. Objects — SeaweedFS (9/9)
- PUT / GET / HEAD / DELETE / LIST 全通过
- 批量写入 5 keys 验证

### 3. Tables — Iceberg (13/13)
- create / list / describe / append / scan / overwrite / drop 全通过
- scan 支持 limit + column select

### 4. Vectors — LanceDB (8/8)
- create / list / describe / add / search 全通过
- 向量搜索 top_k=5 返回正确

### 5. KV — Dragonfly (9/9)
- set / get / delete / scan 全通过
- TTL 过期验证通过

### 6. Graph — PostgreSQL (9/9)
- add_node / add_edge / query_nodes / query_edges / delete_node 全通过
- label 过滤 + tenant 隔离

### 7. SQL — DuckDB (5/5)
- SELECT 1 / count / filter+order 全通过
- 支持传入内存表

### 8. Jobs — Embedded (5/5)
- submit / status / result 全通过

### 9. Embedding — fastembed (5/5)
- 2 texts → 2 vectors, dim=384
- 空列表处理

### 10. Memory — BasicMemory (7/7)
- 长期记忆 (Lance 向量) ✓
- 短期记忆 (Dragonfly TTL) ✓
- recall / forget ✓

### 11. Metadata — PostgreSQL (16/16)
- tenant CRUD + user CRUD + token issue/revoke + asset_type register/unregister

## 性能基准 (单线程, 100 ops)

| 端点 | avg (ms) | p50 (ms) | p95 (ms) | RPS |
|------|----------|----------|----------|-----|
| system/health | 175.38 | 165.64 | 247.76 | 5.7 |
| kv/set | 12.78 | 11.42 | 26.15 | 78.2 |
| kv/get | 11.73 | 10.80 | 20.92 | 85.2 |
| object/put (20B) | 40.68 | 28.05 | 62.83 | 24.6 |
| object/get (20B) | 16.35 | 15.29 | 23.53 | 61.2 |
| sql/select 1 | 51.17 | 47.48 | 74.25 | 19.5 |
| sql/with_table(3 rows) | 55.21 | 51.00 | 81.80 | 18.1 |
| graph/add_node | 75.05 | 70.91 | 103.93 | 13.3 |
| graph/query_nodes | 77.02 | 72.61 | 107.31 | 13.0 |
| metadata/list_tenants | 11.66 | 10.78 | 21.54 | 85.8 |
| job/submit | 11.22 | 10.48 | 15.06 | 89.1 |
| embedding/embed(1 text) | 30.97 | 29.15 | 44.20 | 32.3 |

## 并发压测 (20 workers × 50 ops = 1000 ops)

| 端点 | ok | err | 吞吐 (ops/s) | p95 (ms) |
|------|-----|-----|-------------|----------|
| kv/set | 1000 | 0 | 133.4 | 198.17 |
| kv/get | 1000 | 0 | 139.4 | 199.32 |
| object/put | 1000 | 0 | 46.3 | 561.09 |
| object/get | 1000 | 0 | 90.1 | 264.81 |
| sql/select | 1000 | 0 | 23.7 | 997.09 |
| graph/query | 1000 | 0 | 14.4 | 1663.84 |
| metadata/list_tenants | 1000 | 0 | 152.7 | 167.29 |
| job/submit | 1000 | 0 | 174.5 | 149.64 |

## 高并发压测 (50 workers × 100 ops = 5000 ops)

| 端点 | ok | err | 吞吐 (ops/s) | p95 (ms) |
|------|-----|-----|-------------|----------|
| kv/get | 5000 | 0 | 167.2 | 517.42 |
| sql/select | 5000 | 0 | 23.2 | 2462.91 |

## 可插拔性验证 (5/5 PASS)

- ✓ 全部 10 引擎健康
- ✓ 引擎名称匹配 Protocol 定义
- ✓ health 无需 auth 可访问
- ✓ OpenAPI docs 可访问
- ✓ OpenAPI spec 36 路径

## 修复的 Bug (Phase 1 遗留)

1. **SeaweedFS**: `addressing_style` 不是 `BotoConfig` 直接参数 → 改用 `s3={"addressing_style": "path"}`
2. **Auth middleware**: raise HTTPException → 返回 JSONResponse
3. **Graph JSONB**: psycopg2 返回 dict 而非 str → 添加 isinstance 检查
4. **Token scopes**: `json.dumps(scopes)` → 直接传 list 给 PG `TEXT[]`
5. **Asset types**: `updated_at` 列不存在 → 移除
6. **Tenant/User upsert**: ON CONFLICT DO NOTHING → DO UPDATE 恢复 status='active'
7. **FastEmbed numpy**: `list(v)` 保留 numpy.float32 → `[float(x) for x in v]`
8. **Memory generator**: `embed([text])[0]` 不可下标 → `next(embed([text]))`

## 结论

Phase 2 全部通过。REST API 网关功能完整、性能合理、并发稳定、插件可插拔性验证通过。
可进入 Phase 3 — MCP 重构为 REST 客户端。
