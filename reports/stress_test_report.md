# LakeMind 性能优化报告 v3

> 生成时间: 2026-07-21
> 环境: Ray 5 CPU, Docker Desktop, Windows, uvicorn workers=1
> 优化: P0 asyncio.to_thread + P1 uvicorn workers + P2 Arrow IPC + LanceDB Lock

## 1. 优化效果总览

| 轮次 | PASS | FAIL | 关键改善 |
|------|------|------|----------|
| v1 (12 CPU, 原始) | 3 | 6 | 基线 |
| v2 (5 CPU, 修正脚本) | 4 | 5 | 修正计算 |
| **v3 (5 CPU, 优化后)** | **5** | **4** | **并发修复 + Arrow IPC** |

## 2. 三层优化结果

### P0: asyncio.to_thread — 同步 I/O 包线程化

**根因**: async 端点直接调用同步阻塞 I/O（boto3、LanceDB、Valkey），冻结事件循环。

**改动**: 9 个 API 文件的全部引擎调用包进 `await asyncio.to_thread(...)`:
- `api/objects.py` — S3 上传/下载
- `api/vectors.py` — 向量 CRUD
- `api/kv.py` — KV 读写
- `api/memory.py` — 记忆 8 方法
- `api/tables.py` — Iceberg 表操作
- `api/graph.py` — 图操作
- `api/search.py` — 全局搜索
- `api/memories.py` — v2 记忆 API
- `api/knowledge.py` — 知识 API

**效果**:

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| TC-1 文件上传 | 0% success (1000 errors) | **100% success, 27 MB/s** |
| TC-10 conc_10 | 53% error | **0% error** |
| TC-10 conc_20 | 100% error | **0% error** |
| TC-10 conc_30 | 100% error | **0.67% error** |

### P1: uvicorn 多 worker

**改动**: `__main__.py` 加 `workers` 参数, `docker-compose.yml` 加 `UVICORN_WORKERS` 环境变量。

**结果**: workers=2 在 Docker Desktop 下端口转发异常（IPv6 绑定问题），回退为 workers=1。P0 的 `to_thread` 已足够解决并发问题。

### P2: Arrow IPC 二进制向量入库

**改动**: `api/vectors.py` 新增 `POST /{db}/{name}/add_arrow` 端点，接受 Arrow IPC stream 二进制 body，跳过 Pydantic JSON 解析。

**效果**:

| 路径 | 10K vecs | 50K vecs | 加速比 |
|------|----------|----------|--------|
| JSON (原) | 715 vec/s | 670 vec/s | 1x |
| **Arrow IPC (新)** | **11988 vec/s** | **14630 vec/s** | **~20x** |

### 附加: LanceDB 线程锁

**问题**: P0 后并发向量搜索触发 LanceDB Rust panic (`pyo3_async_runtimes.RustPanic: rust future panicked`)。

**修复**: `lancedb.py` 加 `threading.Lock`，`basic.py` 用装饰器模式锁全部 8 个公开方法。

**效果**: 消除 500 错误，TC-8 并发 50/50 ok (之前 66% error)。

## 3. 压测结果明细

| TC | 名称 | 判定 | 关键指标 | 说明 |
|----|------|------|----------|------|
| TC-1 | 文件批量上传 | ❌ FAIL | 100% success, 27 MB/s | 阈值 30 MB/s, 差 3 MB/s |
| TC-2 | 大文件读写 | ✅ PASS | put p99=3.3s, get p99=2.1s | — |
| TC-3 | 批量嵌入 | ✅ PASS | 43 texts/s, speedup=4.78x | — |
| TC-4 | 批量向量入库 | ❌ FAIL | JSON 670-715 vec/s, **Arrow 12K-15K vec/s** | JSON 路径瓶颈, Arrow 达标 |
| TC-5 | 向量检索 | ❌ FAIL | p99=2.0s, conc5 0% err, conc10 62% err | 锁序列化, 高并发超时 |
| TC-8 | 记忆读写 | ❌ FAIL | search p99=0.13s, conc10 50/50 ok | add p99=11s (LLM 抽取) |
| TC-10 | 阶梯并发 | ✅ **PASS** | conc30 0.67% err, 8.2 QPS | **从 100% err → 0.67%** |
| TC-11 | 冷启动 | ✅ PASS | health=7.2s, cold embed=11.6s | — |
| TC-12 | MCP vs REST | ✅ PASS | MCP 16ms vs REST 53ms | MCP 更快 |

## 4. 剩余瓶颈与建议

### TC-1: 上传吞吐 27 MB/s (差 3 MB/s)
- **现状**: 20 并发 × 50 文件 × 1MB, 37s 完成
- **建议**: 调整阈值至 25 MB/s, 或增大并发至 50

### TC-4: JSON 向量入库 670-715 vec/s
- **现状**: REST JSON 序列化 768 维向量是瓶颈
- **解决**: **已提供 Arrow IPC 端点 (12K-15K vec/s)**, 客户端改用 Arrow 路径即可
- **建议**: 压测脚本改用 Arrow 路径作为主路径

### TC-5: 向量检索并发
- **现状**: LanceDB 锁序列化搜索, 单次 ~1.4s, QPS ~0.7
- **根因**: 60K+ 向量无 IVF 索引, 暴力扫描
- **建议**: 创建 LanceDB IVF 索引加速单次搜索, 或接受当前 QPS (适合低并发场景)

### TC-8: 记忆 add p99=11s
- **现状**: 单次 add 12ms, 但 p99=11s (LLM 事实抽取偶发慢)
- **建议**: add 操作 infer=false 跳过 LLM, 或异步化 LLM 抽取

## 5. 改动文件清单

| 文件 | 改动 |
|------|------|
| `__main__.py` | 加 workers 参数 |
| `api/objects.py` | to_thread × 5 |
| `api/vectors.py` | to_thread × 6 + add_arrow 端点 |
| `api/kv.py` | to_thread × 4 |
| `api/memory.py` | to_thread × 8 |
| `api/tables.py` | to_thread × 7 |
| `api/graph.py` | to_thread × 5 |
| `api/search.py` | to_thread × 1 |
| `api/memories.py` | to_thread × 8 |
| `api/knowledge.py` | to_thread × 5 |
| `plugins/storage/vector/lancedb.py` | threading.Lock |
| `plugins/cognitive/memory/basic.py` | threading.Lock 装饰器 |
| `docker-compose.yml` | UVICORN_WORKERS 环境变量 |
