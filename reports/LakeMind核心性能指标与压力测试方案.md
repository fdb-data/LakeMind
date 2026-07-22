# LakeMind 核心性能指标与压力测试方案

> **版本**: v0.2.0  
> **日期**: 2026-07-21（含实测基线）  
> **定位**: 本文定义 LakeMind 作为多模态智能数据湖的核心性能指标体系，并给出可执行的压力测试方案。  
> **环境基线**: 5 CPU Ray 集群（head=1, worker=2×2），PG 16，SeaweedFS S3，LanceDB 768 维，fastembed jina-v2-base-zh
> **实测数据**: 4 轮压测 (v1→v4)，最终 7/9 PASS，详见 `reports/2026.0721.性能优化全轮次总结报告.md`

---

## 1. 指标体系总览

LakeMind 的性能指标按**数据域 × 处理模式**划分为四大块：

```
                    批量处理 (Batch)              实时处理 (Real-time)
                 ┌──────────────────────┐    ┌──────────────────────┐
多模态文件管理    │ §2  批量上传/入库/迁移 │    │ §2  单文件读写延迟    │
                 ├──────────────────────┤    ├──────────────────────┤
向量处理          │ §3  批量嵌入+批量入库  │    │ §4  实时嵌入+ANN检索  │
                 ├──────────────────────┤    ├──────────────────────┤
认知资产          │ §5  批量知识摄入/重建  │    │ §5  实时记忆/知识检索 │
                 ├──────────────────────┤    ├──────────────────────┤
计算与调度        │ §6  Ray 批作业吞吐    │    │ §6  作业提交/即席查询 │
                 └──────────────────────┘    └──────────────────────┘

平台级横切: §7  API 吞吐 / 并发承载 / 冷启动 / 协议开销
压力测试方案: §8
```

每个指标给出：**定义、测量方法、基线值/目标值、SLA**。

---

## 2. 多模态文件管理与存储性能

### 2.1 对象存储（S3 / SeaweedFS）

LakeMind 通过 SeaweedFS 承载全部多模态数据文件（音频、图片、文档、Skill zip、Iceberg 数据文件）。所有操作经 REST API `/api/v1/storage/objects/{bucket}/{key}` 透传。

#### 2.1.1 单文件写入延迟

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `obj.put.latency_1kb` | 1 KB 文件 PUT 端到端延迟 | — | p50 < 20ms, p99 < 100ms |
| `obj.put.latency_1mb` | 1 MB 文件 PUT 端到端延迟 | — | p50 < 100ms, p99 < 500ms |
| `obj.put.latency_10mb` | 10 MB 文件 PUT 端到端延迟 | — | p50 < 500ms, p99 < 2s |
| `obj.put.latency_100mb` | 100 MB 文件 PUT 端到端延迟 | — | p50 < 3s, p99 < 10s |

> **注意**: 当前实现为单次 `put_object`（无 multipart），大文件写入受限于单次 HTTP body 全量加载到内存。100 MB+ 文件建议未来启用 multipart upload。

#### 2.1.2 单文件读取延迟

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `obj.get.latency_1kb` | 1 KB 文件 GET 端到端延迟 | — | p50 < 15ms, p99 < 80ms |
| `obj.get.latency_1mb` | 1 MB 文件 GET 端到端延迟 | — | p50 < 50ms, p99 < 300ms |
| `obj.get.latency_10mb` | 10 MB 文件 GET 端到端延迟 | — | p50 < 200ms, p99 < 1s |
| `obj.get.latency_100mb` | 100 MB 文件 GET 端到端延迟 | — | p50 < 1.5s, p99 < 5s |

#### 2.1.3 批量上传吞吐

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `obj.batch_upload.throughput` | N 个文件并发 PUT 的聚合吞吐 (MB/s) | 23.3 | 50 文件×1 MB 并发 20: > 50 MB/s |
| `obj.batch_upload.success_rate` | 批量上传成功率 | 100% | > 99.9% |
| `obj.batch_upload.concurrency_50` | 50 并发 PUT 无错误 | 0% err | err_rate < 0.1% |

#### 2.1.4 列表操作

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `obj.list.latency_100` | 列出 100 个对象的延迟 | — | p50 < 50ms, p99 < 200ms |
| `obj.list.latency_1000` | 列出 1000 个对象的延迟（MaxKeys 上限） | — | p50 < 200ms, p99 < 1s |
| `obj.list.pageseek` | 翻页连续列表 10000 对象的总耗时 | — | < 5s |

> **当前限制**: `list_objects_v2` MaxKeys=1000，无分页 token 传递。超过 1000 对象需多次请求。

### 2.2 结构化表（Iceberg）

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `table.create.latency` | 创建 Iceberg 表（含 schema）延迟 | — | < 500ms |
| `table.append.throughput_1k` | 追加 1000 行（10 列）吞吐 | — | > 5000 rows/s |
| `table.append.throughput_10k` | 追加 10000 行（10 列）吞吐 | — | > 8000 rows/s |
| `table.scan.latency_1k` | 扫描 1000 行延迟 | — | p50 < 100ms |
| `table.scan.latency_100k` | 扫描 100000 行延迟（带 limit pushdown） | — | p50 < 500ms |

### 2.3 多模态文件全链路

从 Agent 视角，一个多模态文件（如音频）的完整生命周期：上传 → Ray Job 处理 → 结果写回 → 向量入库 → 检索。

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `mm.upload_to_process` | 上传 10 MB 音频到 Ray Job 开始执行的时间 | — | < 3s |
| `mm.process_to_result` | Ray Job ASR 处理 10 MB 音频到结果写回 S3 | — | < 60s（取决于模型） |
| `mm.result_to_vector` | 结果文本 → 嵌入 → 向量入库端到端 | — | < 2s |
| `mm.full_chain` | 上传到可检索的全链路 | — | < 70s |

---

## 3. 向量批量处理性能

### 3.1 批量嵌入生成

嵌入模型 `jinaai/jina-embeddings-v2-base-zh`（768 维），通过 ModelServing `/v1/embeddings` 调用 fastembed (ONNX CPU)。

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `embed.batch_100.latency` | 100 条中英混合文本批量嵌入延迟 | 2.4s (mean) | p50 < 3s, p99 < 8s |
| `embed.batch_500.latency` | 500 条批量嵌入延迟 | — | p50 < 12s, p99 < 25s |
| `embed.batch_1000.latency` | 1000 条批量嵌入延迟 | — | p50 < 25s, p99 < 50s |
| `embed.throughput` | 嵌入吞吐 (texts/s) | 40.9 | > 40 texts/s (CPU) |
| `embed.dim` | 向量维度 | 768 | 768 |
| `embed.batch_speedup` | 批量 vs 逐条加速比 | 4.73× | batch_100 / (100 × single) > 5× |

> **关键**: 当前 `ingest_knowledge` 逐条调用 embed（N concepts = N embed 调用）。批量嵌入应改为一次 `embed([all_texts])` 调用，预期 5-10× 加速。

### 3.2 批量向量入库

通过 LanceDB `/api/v1/storage/vectors/{db}/{table}/add` 批量写入。

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `vector.add.throughput_1k` | 批量写入 1000 条 768 维向量吞吐 | 727 (JSON) / 8081 (Arrow) | > 10000 vec/s |
| `vector.add.throughput_10k` | 批量写入 10000 条向量吞吐 | 8081 (Arrow) | > 15000 vec/s |
| `vector.add.throughput_100k` | 批量写入 100000 条向量吞吐 | 8081 (Arrow) | > 20000 vec/s |
| `vector.add.latency_100` | 写入 100 条向量延迟 | — | p50 < 50ms |
| `vector.add.latency_1000` | 写入 1000 条向量延迟 | — | p50 < 200ms |
| `vector.add.latency_10000` | 写入 10000 条向量延迟 | — | p50 < 1s |
| `vector.add.memory_per_vec` | 每条向量入库内存开销 | — | < 4 KB（768 × 4B + metadata） |

### 3.3 批量知识摄入

`ingest_knowledge` 是最重的批量操作：N 个概念 → N 次 embed + N 次 S3 put + N 次图写入 + 1 次批量 vector_add。

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `kb.ingest.latency_10` | 摄入 10 个概念端到端延迟 | — | < 5s |
| `kb.ingest.latency_100` | 摄入 100 个概念端到端延迟 | — | < 30s |
| `kb.ingest.latency_500` | 摄入 500 个概念端到端延迟 | — | < 120s |
| `kb.ingest.throughput` | 知识摄入吞吐 (concepts/s) | — | > 5 concepts/s |
| `kb.ingest.embed_batch_ratio` | embed 批量调用占比 | 0%（逐条） | 100%（全批量） |
| `kb.ingest.s3_batch_ratio` | S3 put 批量调用占比 | 0%（逐条） | 目标 50%+（可并行） |

### 3.4 向量索引构建

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `vector.index.create_100k` | 100K 向量构建索引延迟 | 98.2s (IVF_PQ) | < 30s |
| `vector.index.create_1m` | 1M 向量构建索引延迟 | — | < 300s |
| `vector.index.recall_100k` | 100K 向量 ANN 检索 recall@10 | 1.0000 | > 0.95 |
| `vector.index.recall_1m` | 1M 向量 ANN 检索 recall@10 | — | > 0.90 |

> **已实现**: IVF_PQ 索引 (num_partitions=128, num_sub_vectors=16, metric=L2)，121K 向量 14.2ms/search，Recall@10=1.0。批量 add 后需 `create_index(replace=True)` 刷新。

---

## 4. 向量实时处理与查询性能

### 4.1 单条实时嵌入

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `embed.single.latency` | 单条文本嵌入延迟 | — | p50 < 30ms, p99 < 100ms |
| `embed.single.cold` | 冷启动后首条嵌入延迟（模型加载） | — | < 5s |
| `embed.single.warm` | 热态单条嵌入延迟 | — | p50 < 30ms |

### 4.2 向量检索（ANN）

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `vector.search.latency_top10` | top-10 检索延迟（10K 向量表） | 14.2ms (L0) | p50 < 50ms, p99 < 200ms |
| `vector.search.latency_top10_100k` | top-10 检索延迟（100K 向量表） | p50=60ms, p99=193ms | p50 < 100ms, p99 < 500ms |
| `vector.search.latency_top10_1m` | top-10 检索延迟（1M 向量表） | — | p50 < 200ms, p99 < 1s |
| `vector.search.latency_top100` | top-100 检索延迟（100K 表） | — | p50 < 150ms, p99 < 800ms |
| `vector.search.with_filter` | 带 SQL filter 的检索延迟 | — | p50 < 100ms, p99 < 500ms |
| `vector.search.recall_vs_brute` | ANN vs 暴力检索 recall@10 | — | > 0.95 |

### 4.3 多表 fan-out 检索

`search_knowledge` 遍历租户下所有知识库表，每表一次向量检索，客户端合并。

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `kb.search.fanout_5` | 5 个知识库表 fan-out 检索延迟 | — | p50 < 300ms, p99 < 1s |
| `kb.search.fanout_20` | 20 个知识库表 fan-out 检索延迟 | — | p50 < 1s, p99 < 3s |
| `kb.search.fanout_50` | 50 个知识库表 fan-out 检索延迟 | — | p50 < 2.5s, p99 < 6s |
| `kb.search.parallel_speedup` | 并行 fan-out vs 串行加速比 | 1×（串行） | > 3×（并行） |

> **优化方向**: 当前 fan-out 串行执行。改为 `asyncio.gather` 并行可显著降低多表延迟。

### 4.4 并发检索

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `vector.search.qps_10` | 10 并发检索 QPS | 19.0 | > 100 QPS |
| `vector.search.qps_50` | 50 并发检索 QPS | — | > 200 QPS |
| `vector.search.qps_100` | 100 并发检索 QPS | — | > 300 QPS |
| `vector.search.err_rate_100` | 100 并发检索错误率 | 0% (10并发) | < 0.1% |

---

## 5. 认知资产实时与批量性能

### 5.1 知识摄入（批量）

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `kb.ingest.10_concepts` | 10 概念摄入（含 embed + S3 + 向量 + 图） | — | < 5s |
| `kb.ingest.100_concepts` | 100 概念摄入 | — | < 30s |
| `kb.ingest.500_concepts` | 500 概念摄入 | — | < 120s |
| `kb.ingest.parallel_100` | 100 概念并行摄入（embed 批量 + S3 并行） | — | < 15s |
| `kb.reindex.1k` | 1000 概念重建索引延迟 | — | < 60s |

### 5.2 知识检索（实时）

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `kb.search.single` | 单知识库检索延迟（1 embed + 1 vector search） | — | p50 < 100ms, p99 < 500ms |
| `kb.search.multi_5` | 5 知识库 fan-out 检索 | — | p50 < 300ms, p99 < 1s |
| `kb.search.with_graph` | 检索 + 图扩展（1 跳邻居） | — | p50 < 200ms, p99 < 800ms |
| `kb.search.qps_50` | 50 并发知识检索 QPS | — | > 50 QPS |

### 5.3 记忆读写（实时）

记忆服务（mem0 风格）：LLM 事实抽取 + 哈希去重 + Lance 向量 + PG 元信息。

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `mem.add.latency` | 添加记忆（含 LLM 抽取 + embed + 去重 + 入库） | p50=25ms, p99=33ms | p50 < 2s, p99 < 5s |
| `mem.add.no_llm` | 添加记忆（跳过 LLM 抽取，直接 embed + 入库） | — | p50 < 100ms, p99 < 300ms |
| `mem.search.latency` | 记忆检索（1 embed + cosine search, top-10） | p50=76ms | p50 < 100ms, p99 < 500ms |
| `mem.search.threshold` | 带阈值过滤的检索延迟（threshold=0.1） | — | p50 < 100ms |
| `mem.list.latency` | 列出记忆（PG 分页） | p50=21ms | p50 < 50ms, p99 < 200ms |
| `mem.get.latency` | 单条记忆获取 | — | p50 < 30ms, p99 < 100ms |
| `mem.update.latency` | 更新记忆（含 re-embed） | — | p50 < 200ms |
| `mem.delete.latency` | 删除记忆 | — | p50 < 50ms |
| `mem.search.qps_50` | 50 并发记忆检索 QPS | 17.8 (10并发) | > 80 QPS |

### 5.4 技能注册与检索

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `skill.register.latency` | 注册技能（embed description + S3 put + Iceberg append） | — | p50 < 500ms, p99 < 2s |
| `skill.search.latency` | 技能检索（1 embed + 1 vector search） | — | p50 < 100ms, p99 < 500ms |
| `skill.search.qps_50` | 50 并发技能检索 QPS | — | > 80 QPS |

### 5.5 本体图查询

PG graph_nodes / graph_edges 图存储。

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `ontology.query.1hop` | 1 跳邻居查询延迟 | — | p50 < 30ms, p99 < 100ms |
| `ontology.query.2hop` | 2 跳邻居查询延迟 | — | p50 < 100ms, p99 < 500ms |
| `ontology.update.latency` | 插入节点 + 边延迟 | — | p50 < 50ms |
| `ontology.query.complex` | 复杂图模式查询（5 节点 + 10 边模式匹配） | — | p50 < 200ms, p99 < 1s |

### 5.6 认知资产综合并发

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `cognitive.mix.qps_50` | 50 并发混合认知操作 QPS | qps > 10 | > 30 QPS |
| `cognitive.mix.err_rate_50` | 50 并发混合操作错误率 | < 1% | < 0.5% |
| `cognitive.mix.sustained_10s` | 50 并发持续 10s | err < 1%, qps > 10 | err < 0.5%, qps > 30 |

> 混合负载分布：40% memory/list, 20% memory/search, 15% s3 list, 10% kv scan, 10% tables list, 5% health。

---

## 6. 计算与作业调度性能

### 6.1 Ray 作业提交与执行

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `ray.submit.latency` | 作业提交到 Ray 开始执行延迟 | — | p50 < 500ms, p99 < 2s |
| `ray.submit.skill_zip_10mb` | 含 10 MB Skill zip 的提交延迟 | — | p50 < 2s |
| `ray.job.short` | 短作业（sleep 1s）端到端 | — | < 3s |
| `ray.job.embed_batch_100` | 100 条批量嵌入作业端到端 | — | < 8s |
| `ray.job.throughput` | 12 CPU 集群并发作业吞吐 | — | > 10 jobs/s（短作业） |
| `ray.job.queue_depth` | 排队深度 10 时的作业启动延迟 | — | p50 < 2s |
| `ray.job.cancel.latency` | 取消运行中作业延迟 | — | < 1s |

### 6.2 DuckDB 即席查询

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `sql.query.simple` | 简单 SELECT 1000 行延迟 | — | p50 < 50ms, p99 < 200ms |
| `sql.query.join_2` | 2 表 JOIN 10000 行延迟 | — | p50 < 200ms, p99 < 1s |
| `sql.query.aggregation` | 聚合查询 100000 行延迟 | — | p50 < 500ms, p99 < 2s |
| `sql.query.cross_table` | 跨 Iceberg 表 + Parquet 直读查询 | — | p50 < 1s, p99 < 3s |
| `sql.memory_limit` | DuckDB 内存限制 | 2 GB | 2 GB |

### 6.3 Valkey KV 操作

| 指标 | 定义 | 基线 | 目标 |
|------|------|------|------|
| `kv.set.latency` | KV 写入延迟 | — | p50 < 5ms, p99 < 20ms |
| `kv.get.latency` | KV 读取延迟 | — | p50 < 3ms, p99 < 10ms |
| `kv.scan.latency_100` | 扫描 100 个 key 延迟 | — | p50 < 20ms |
| `kv.scan.latency_1000` | 扫描 1000 个 key 延迟 | — | p50 < 100ms |
| `kv.qps_100` | 100 并发 KV 读写 QPS | — | > 5000 QPS |

---

## 7. 平台级性能指标

### 7.1 REST API 吞吐与延迟

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `api.health.latency` | `/system/health` 延迟 | mean < 0.2s | p50 < 50ms, p99 < 200ms |
| `api.qps_50` | 50 并发混合 API QPS | — | > 100 QPS |
| `api.qps_100` | 100 并发混合 API QPS | — | > 150 QPS |
| `api.err_rate_100` | 100 并发错误率 | — | < 0.5% |

### 7.2 并发承载（阶梯压测）

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `conc.10.err_rate` | 10 并发错误率 | 0% | < 0.1% |
| `conc.30.err_rate` | 30 并发错误率 | 0% | < 0.5% |
| `conc.50.err_rate` | 50 并发错误率 | 0% | < 1% |
| `conc.100.err_rate` | 100 并发错误率 | < 5% | < 5% |
| `conc.breaking_point` | 错误率突破 10% 的并发数 | — | > 150 |

### 7.3 冷启动

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `cold.mcp_first_call` | MCP 重启后首次工具调用延迟 | 10ms (warm) | < 5s |
| `cold.embed_model_load` | 嵌入模型冷加载延迟 | 6.7s | < 10s |
| `cold.asr_model_load` | ASR 模型冷加载延迟 | — | < 30s |
| `cold.server_health` | Server 重启到 healthy 延迟 | 7.2s | < 15s |

### 7.4 MCP vs REST 协议开销

| 指标 | 定义 | 基线（L9） | 目标 |
|------|------|-----------|------|
| `proto.mcp_vs_rest` | MCP 工具调用 vs 等价 REST API 的额外开销 | 10ms vs 21ms | < 0.5s |
| `proto.mcp.streaming_http` | Streamable HTTP 传输开销 | — | < 100ms/call |

---

## 8. 压力测试方案

### 8.1 测试环境

```
OS:         Windows 11 + WSL2 (Docker Desktop)
CPU:        12 逻辑核 (分配给 Docker)
RAM:        32 GB (Docker 限制 16 GB)
Disk:       NVMe SSD

容器拓扑:
  lakemind-postgres       PG 16
  lakemind-seaweedfs      S3 对象存储
  lakemind-valkey         KV 缓存
  lakemind-ray-head       1 CPU
  lakemind-ray-worker ×2  2 CPU each
  lakemind-server-api     REST API :10823
  lakemind-model-serving  嵌入/LLM/ASR :10824
  lakemind-asset-mcp      :8401
  lakemind-data-mcp       :8402
  lakemind-admin-mcp      :8403
  lakemind-control-center :3000
```

### 8.2 测试工具

| 工具 | 用途 |
|------|------|
| `scripts/verify_full.py` L9 | 已有性能压测框架（trimmed mean, p50/p95/p99） |
| `httpx` + `asyncio` | 自定义并发压测脚本 |
| `locust`（可选） | 图形化阶梯压测 |
| `pg_stat_statements` | PG 查询性能 |
| `docker stats` | 容器资源监控 |
| `ray status` | Ray 集群资源利用 |

### 8.3 测试数据集

| 数据集 | 规模 | 用途 |
|--------|------|------|
| `texts_small` | 100 条中英混合文本 | 嵌入基准 |
| `texts_medium` | 1000 条 | 批量嵌入 |
| `texts_large` | 10000 条 | 大批量嵌入 |
| `vectors_10k` | 10000 条 768 维随机向量 | 向量入库/检索基准 |
| `vectors_100k` | 100000 条 | 大表检索 |
| `vectors_1m` | 1000000 条 | ANN recall 基准 |
| `concepts_100` | 100 个 OKF 格式知识概念 | 知识摄入 |
| `concepts_500` | 500 个 | 批量知识摄入 |
| `audio_10mb` | 10 MB WAV 音频 | 多模态全链路 |
| `files_mixed_50` | 50 个混合文件（1 MB-50 MB） | S3 批量上传 |

### 8.4 测试用例集

#### TC-1: 多模态文件批量上传

```
前置: SeaweedFS 运行, S3 bucket 已创建
步骤:
  1. 并发 20 线程, 每线程上传 50 个文件 (1 MB each)
  2. 记录每个 PUT 的延迟
  3. 统计吞吐 (MB/s) 和错误率
验证:
  - obj.batch_upload.throughput > 50 MB/s
  - obj.batch_upload.success_rate > 99.9%
  - 无 OOM, 容器内存增长 < 2 GB
```

#### TC-2: 大文件读写

```
步骤:
  1. 上传 100 MB 文件, 记录延迟
  2. 下载同一文件, 记录延迟
  3. 重复 10 次, 统计 p50/p99
验证:
  - obj.put.latency_100mb p99 < 10s
  - obj.get.latency_100mb p99 < 5s
```

#### TC-3: 批量嵌入基准

```
前置: ModelServing 运行, jina-v2-base-zh 已加载
步骤:
  1. 对 texts_small (100), texts_medium (1000), texts_large (10000) 分别批量嵌入
  2. 记录每轮延迟, 计算 throughput
  3. 对比逐条嵌入 vs 批量嵌入的加速比
验证:
  - embed.batch_100.latency p50 < 3s
  - embed.batch_1000.latency p50 < 25s
  - embed.throughput > 40 texts/s
  - embed.batch_speedup > 5×
```

#### TC-4: 批量向量入库

```
前置: LanceDB 运行, 向量表已创建 (768 维)
步骤:
  1. 批量写入 vectors_10k, vectors_100k, vectors_1m
  2. 记录入库延迟和吞吐
  3. 监控内存使用
验证:
  - vector.add.throughput_10k > 15000 vec/s
  - vector.add.throughput_100k > 20000 vec/s
  - vector.add.memory_per_vec < 4 KB
```

#### TC-5: 向量实时检索

```
前置: 向量表已加载 100K 向量
步骤:
  1. 生成 1000 个随机查询向量
  2. 逐条检索 top-10, 记录延迟
  3. 并发 10/50/100 检索, 记录 QPS
  4. 对比 ANN vs 暴力检索的 recall@10
验证:
  - vector.search.latency_top10_100k p99 < 500ms
  - vector.search.qps_100 > 300 QPS
  - vector.search.recall_vs_brute > 0.95
```

#### TC-6: 多表 fan-out 知识检索

```
前置: 创建 5/20/50 个知识库, 每库 1000 概念
步骤:
  1. search_knowledge 跨所有库检索
  2. 记录 fan-out 延迟
  3. 对比串行 vs 并行 fan-out
验证:
  - kb.search.fanout_20 p99 < 3s
  - kb.search.parallel_speedup > 3×
```

#### TC-7: 批量知识摄入

```
前置: AssetMCP 运行, 知识库已注册
步骤:
  1. ingest_knowledge 摄入 concepts_100, concepts_500
  2. 记录端到端延迟
  3. 分析 embed 调用次数 (应为批量, 非逐条)
验证:
  - kb.ingest.latency_100 < 30s
  - kb.ingest.latency_500 < 120s
  - kb.ingest.embed_batch_ratio = 100%
```

#### TC-8: 记忆实时读写

```
前置: Memory 服务运行
步骤:
  1. 100 轮 add + search 循环
  2. 50 并发混合 add/search/list
  3. 记录各操作延迟和 QPS
验证:
  - mem.add.latency p99 < 5s
  - mem.search.latency p99 < 500ms
  - mem.search.qps_50 > 80 QPS
```

#### TC-9: 多模态全链路

```
前置: Ray 集群运行, ASR Skill 已发布
步骤:
  1. 上传 audio_10mb 到 S3
  2. 提交 Ray ASR Job
  3. 轮询 Job 完成状态
  4. 下载结果, 嵌入入库
  5. 检索验证
  6. 记录全链路各阶段耗时
验证:
  - mm.upload_to_process < 3s
  - mm.full_chain < 70s
```

#### TC-10: 阶梯并发压测

```
步骤:
  1. 10 → 30 → 50 → 100 → 150 → 200 并发
  2. 每级持续 30s 混合负载
  3. 记录 QPS, err_rate, p99 延迟
  4. 找到错误率突破 10% 的拐点
验证:
  - conc.100.err_rate < 5%
  - conc.breaking_point > 150
```

#### TC-11: 冷启动

```
步骤:
  1. 重启 asset-mcp, 首次工具调用计时
  2. 重启 model-serving, 首次嵌入调用计时
  3. 重启 server-api, health 轮询计时
验证:
  - cold.mcp_first_call < 5s
  - cold.embed_model_load < 10s
  - cold.server_health < 15s
```

#### TC-12: MCP vs REST 开销

```
步骤:
  1. 同一操作通过 MCP 工具调用和 REST API 各执行 20 次
  2. 对比延迟差异
验证:
  - proto.mcp_vs_rest < 0.5s
```

### 8.5 执行顺序

```
Phase 1 — 基础基准 (单操作延迟)
  TC-1 → TC-2 → TC-3 → TC-4 → TC-5

Phase 2 — 认知资产 (批量 + 实时)
  TC-7 → TC-8 → TC-6

Phase 3 — 全链路
  TC-9

Phase 4 — 并发与极限
  TC-10 → TC-11 → TC-12
```

### 8.6 报告格式

每个测试用例输出：

```json
{
  "test_case": "TC-3",
  "test_name": "批量嵌入基准",
  "timestamp": "2026-07-19T10:00:00Z",
  "environment": {"ray_cpus": 12, "embed_model": "jina-v2-base-zh"},
  "results": {
    "batch_100": {"p50": 2.1, "p95": 4.3, "p99": 7.8, "mean": 2.5, "unit": "s"},
    "batch_1000": {"p50": 22.0, "p95": 35.0, "p99": 48.0, "mean": 24.0, "unit": "s"},
    "throughput": {"value": 42.0, "unit": "texts/s"},
    "batch_speedup": 6.2
  },
  "verdict": "PASS",
  "failed_metrics": []
}
```

### 8.7 已知性能瓶颈与优化方向

| 瓶颈 | 当前状态 | 影响 | 优化方向 |
|------|----------|------|----------|
| ~~async 端点同步 I/O 阻塞~~ | ✅ 已修复 (v3) | 事件循环冻结 | `asyncio.to_thread()` 包 49 个调用 |
| ~~LanceDB 多线程 Rust panic~~ | ✅ 已修复 (v3→v4) | 并发搜索崩溃 | 每表 `threading.Lock` |
| ~~121K 向量无 ANN 索引~~ | ✅ 已修复 (v4) | 搜索 1220ms 暴力扫描 | IVF_PQ 索引 14ms, Recall=1.0 |
| ~~全局锁串行化 LLM/Embedding~~ | ✅ 已修复 (v4) | Memory Add p99=11s | 精确锁只保护 LanceDB 临界区 |
| ~~REST JSON 高维向量传输~~ | ✅ 已修复 (v3) | 入库 700 vec/s | Arrow IPC 端点 8081 vec/s |
| `ingest_knowledge` 逐条 embed | 未修复 | 摄入吞吐低 | 改为一次 `embed([all_texts])` 批量调用 |
| `search_knowledge` 串行 fan-out | 未修复 | 多表延迟线性增长 | 改为 `asyncio.gather` 并行 |
| S3 无 multipart upload | 未修复 | 大文件 OOM 风险 | 启用 multipart upload for >50 MB |
| S3 list 无分页 token | 未修复 | >1000 对象无法一次列出 | 传递 continuation token |
| Arrow 未接入 Knowledge outbox | 待接入 | 真实向量写入仍走 JSON | outbox worker 改用 add_arrow |
| `vector.scan` 全量加载 | 未修复 | 大表 scan OOM | 使用 LanceDB scanner 流式读取 |
| Iceberg 无 partition pushdown | 未修复 | scan 全量后 limit | 支持 partition spec + pushdown |
| DuckDB 每查询新建连接 | 未修复 | 连接开销 | 复用 DuckDB 连接 |

---

## 9. 指标速查表

| 域 | 批量 | 实时 |
|----|------|------|
| 多模态文件 | 上传 23.3 MB/s, 100% success, 100MB PUT p99=2.8s | 1MB GET < 50ms, 全链路 < 70s |
| 向量 | 嵌入 40.9 texts/s, 入库 8081 vec/s (Arrow) | ANN top-10 p50=60ms, 10并发 19 QPS 0% err |
| 认知资产 | 知识摄入 > 5 concepts/s (待优化) | 记忆 Add p99=33ms, 检索 p50=76ms, 10并发 17.8 QPS |
| 计算调度 | Ray 吞吐 > 10 jobs/s | 作业提交 < 500ms, SQL < 200ms |
| 平台 | 30 并发 0% err, 10.8 QPS | MCP 10ms vs REST 21ms, 冷启动 7.2s |

> **实测结论**: 9 项压测 7 PASS / 2 FAIL（TC-1 环境限制, TC-4 JSON 已知瓶颈）
> **优化历程**: v1 3P/6F → v2 4P/5F → v3 5P/4F → v4 7P/2F
> **关键提升**: 向量检索 23x, Memory Add 335x, 并发错误率 100%→0%
