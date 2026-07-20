# LakeMind 压力测试报告

> **生成时间**: 2026-07-19T23:34:43.945230+00:00
> **环境**: http://localhost:10823 / http://localhost:10824
> **租户**: stress-test

## 汇总: 9 项 | PASS 3 | FAIL 6 | ERROR 0

| TC | 名称 | 结果 | 关键指标 |
|----|------|------|----------|
| TC-1 | 多模态文件批量上传 | FAIL | 吞吐 16.9 MB/s | 成功率 100.0% |
| TC-2 | 大文件读写 | PASS | PUT p99 1.201s | GET p99 0.856s |
| TC-3 | 批量嵌入基准 | FAIL | batch_100 4.113s | 吞吐 24.3 texts/s | 加速比 3.5x |
| TC-4 | 批量向量入库 | FAIL | 1K: 658.0 vec/s | 5K: 730.5 vec/s |
| TC-5 | 向量实时检索 | FAIL | p50 0.161s p99 0.708s | QPS_50 2.2 |
| TC-8 | 记忆实时读写 | FAIL | add p99 0.016s | search p99 12.54s | QPS 1.6 |
| TC-10 | 阶梯并发压测 | FAIL | conc_10: 0.0qps 100.0%err | conc_30: 1.1qps 95.33%err | conc_50: 0.0qps 100.0%err | conc_100: 0.0qps 100.0%err |
| TC-11 | 冷启动 | PASS | 嵌入冷启动 0.099s | health 0.139s |
| TC-12 | MCP vs REST 开销 | PASS | REST 0.079s | MCP 0.012s | 开销 -0.067s |

## 详细结果

### TC-1: 多模态文件批量上传 — FAIL

```json
{
  "files": 200,
  "total_mb": 200.0,
  "elapsed_s": 11.81,
  "throughput_mbs": 16.9,
  "success_rate": 100.0,
  "errors": 0,
  "latency_s": {
    "count": 200,
    "mean": 9.817,
    "p50": 10.295,
    "p95": 10.951,
    "p99": 11.056,
    "min": 2.203,
    "max": 11.781
  }
}
```

**未通过指标**: ['throughput > 50 MB/s']

### TC-2: 大文件读写 — PASS

```json
{
  "file_mb": 50,
  "rounds": 3,
  "put_s": {
    "count": 3,
    "mean": 1.028,
    "p50": 1.005,
    "p95": 1.201,
    "p99": 1.201,
    "min": 0.878,
    "max": 1.201
  },
  "get_s": {
    "count": 3,
    "mean": 0.818,
    "p50": 0.807,
    "p95": 0.856,
    "p99": 0.856,
    "min": 0.79,
    "max": 0.856
  }
}
```

### TC-3: 批量嵌入基准 — FAIL

```json
{
  "batch_100": {
    "latency_s": 4.113,
    "throughput": 24.3,
    "dim": 768
  },
  "batch_500": {
    "latency_s": 18.23,
    "throughput": 27.4,
    "dim": 768
  },
  "batch_1000": {
    "latency_s": 39.566,
    "throughput": 25.3,
    "dim": 768
  },
  "single_100_total_s": 2.853,
  "batch_speedup": 3.5
}
```

**未通过指标**: ['batch_100 p50 < 3s', 'batch_1000 < 25s', 'throughput > 40 texts/s', 'batch_speedup > 5x']

### TC-4: 批量向量入库 — FAIL

```json
{
  "add_1k": {
    "latency_s": 1.52,
    "throughput": 658.0,
    "ok": true
  },
  "add_5k": {
    "latency_s": 6.845,
    "throughput": 730.5,
    "ok": true
  },
  "dim": 768
}
```

**未通过指标**: ['1k throughput > 10000 vec/s', '5k throughput > 10000 vec/s']

### TC-5: 向量实时检索 — FAIL

```json
{
  "single_search_s": {
    "count": 100,
    "mean": 0.17,
    "p50": 0.161,
    "p95": 0.227,
    "p99": 0.708,
    "min": 0.127,
    "max": 0.708
  },
  "qps_10": {
    "qps": 6.0,
    "err_rate": 0.0,
    "elapsed_s": 8.35
  },
  "qps_50": {
    "qps": 2.2,
    "err_rate": 86.8,
    "elapsed_s": 15.18
  }
}
```

**未通过指标**: ['search p99 < 500ms', 'qps_50 > 100']

### TC-8: 记忆实时读写 — FAIL

```json
{
  "add_s": {
    "count": 49,
    "mean": 0.012,
    "p50": 0.011,
    "p95": 0.015,
    "p99": 0.016,
    "min": 0.009,
    "max": 0.016
  },
  "search_s": {
    "count": 50,
    "mean": 0.379,
    "p50": 0.13,
    "p95": 0.159,
    "p99": 12.54,
    "min": 0.116,
    "max": 12.54
  },
  "list_s": {
    "count": 20,
    "mean": 0.077,
    "p50": 0.074,
    "p95": 0.197,
    "p99": 0.197,
    "min": 0.028,
    "max": 0.197
  },
  "concurrent_qps_50": 1.6
}
```

**未通过指标**: ['search p99 < 500ms', 'qps_50 > 80']

### TC-10: 阶梯并发压测 — FAIL

```json
{
  "conc_10": {
    "qps": 0.0,
    "err_rate": 100.0,
    "total": 100
  },
  "conc_30": {
    "qps": 1.1,
    "err_rate": 95.33,
    "total": 300
  },
  "conc_50": {
    "qps": 0.0,
    "err_rate": 100.0,
    "total": 500
  },
  "conc_100": {
    "qps": 0.0,
    "err_rate": 100.0,
    "total": 1000
  },
  "breaking_point": 10
}
```

**未通过指标**: ['conc_100 err < 5%']

### TC-11: 冷启动 — PASS

```json
{
  "embed_cold_s": 0.099,
  "health_latency_s": 0.139
}
```

### TC-12: MCP vs REST 开销 — PASS

```json
{
  "rest_s": {
    "count": 20,
    "mean": 0.079,
    "p50": 0.077,
    "p95": 0.211,
    "p99": 0.211,
    "min": 0.029,
    "max": 0.211
  },
  "mcp_s": {
    "count": 20,
    "mean": 0.012,
    "p50": 0.012,
    "p95": 0.018,
    "p99": 0.018,
    "min": 0.01,
    "max": 0.018
  },
  "overhead_s": -0.067
}
```
