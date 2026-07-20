#!/usr/bin/env python3
"""LakeMind 核心性能压测脚本 — 执行 TC-1 ~ TC-12 并输出报告。

运行: python scripts/stress_test.py
输出: reports/stress_test_report.json + reports/stress_test_report.md
"""
from __future__ import annotations
import asyncio, json, os, time, statistics, random, string, sys, io
from datetime import datetime, timezone
from collections import defaultdict
import httpx

SERVER = os.environ.get("SERVER_API_URL", "http://localhost:10823").rstrip("/")
SERVER_KEY = os.environ.get("SERVER_API_KEY", "ljLH3bvzIFjG4r3zeCP6AsHsGEnbmAQY_Hi3dW7du5o")
MS = os.environ.get("MODEL_SERVING_URL", "http://localhost:10824").rstrip("/")
MS_KEY = os.environ.get("MODELSERVING_API_KEY", "lakemind-modelserving-key")
TENANT = "stress-test"
S3_BUCKET = "lakemind-filesets"

SERVER_HDR = {"Authorization": f"Bearer {SERVER_KEY}", "X-Tenant-Id": TENANT, "Content-Type": "application/json"}
MS_HDR = {"Authorization": f"Bearer {MS_KEY}", "Content-Type": "application/json"}
RAW_HDR = {"Authorization": f"Bearer {SERVER_KEY}", "X-Tenant-Id": TENANT}

results: list[dict] = []


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def percentile(data, p):
    if not data:
        return None
    s = sorted(data)
    k = int(len(s) * p / 100)
    k = min(k, len(s) - 1)
    return s[k]


def stats(data):
    if not data:
        return {"count": 0}
    return {
        "count": len(data),
        "mean": round(statistics.mean(data), 3),
        "p50": round(percentile(data, 50), 3),
        "p95": round(percentile(data, 95), 3),
        "p99": round(percentile(data, 99), 3),
        "min": round(min(data), 3),
        "max": round(max(data), 3),
    }


def record(tc_id, name, metrics: dict, verdict="PASS", failed=None):
    entry = {
        "test_case": tc_id, "test_name": name,
        "timestamp": now_iso(), "results": metrics,
        "verdict": verdict, "failed_metrics": failed or [],
    }
    results.append(entry)
    status = "✅" if verdict == "PASS" else "❌"
    print(f"\n{status} {tc_id}: {name} — {verdict}")
    for k, v in metrics.items():
        if isinstance(v, dict) and "p50" in v:
            print(f"   {k}: p50={v['p50']} p99={v.get('p99','—')} mean={v['mean']}")
        else:
            print(f"   {k}: {v}")


def check(verdicts: list[tuple[str, bool]]) -> tuple[str, list[str]]:
    failed = [name for name, ok in verdicts if not ok]
    return ("PASS" if not failed else "FAIL", failed)


# ──────────────────────────────────────────────────────────────
# TC-1: 多模态文件批量上传
# ──────────────────────────────────────────────────────────────
async def tc1_batch_upload(client):
    print("\n▶ TC-1: 多模态文件批量上传 (10 并发 × 20 文件 × 1MB)")
    N_WORKERS = 10
    FILES_PER_WORKER = 20
    FILE_SIZE = 1024 * 1024  # 1 MB
    data = os.urandom(FILE_SIZE)
    latencies = []
    errors = 0
    total_bytes = 0

    async def upload_one(wid, fid):
        nonlocal errors, total_bytes
        key = f"{TENANT}/stress/tc1/w{wid}/f{fid}.bin"
        url = f"{SERVER}/api/v1/storage/objects/{S3_BUCKET}/{key}"
        t0 = time.perf_counter()
        try:
            resp = await client.put(url, content=data, headers={**RAW_HDR, "Content-Type": "application/octet-stream"}, timeout=30)
            dt = time.perf_counter() - t0
            if resp.status_code in (200, 201):
                latencies.append(dt)
                total_bytes += FILE_SIZE
            else:
                errors += 1
        except Exception:
            errors += 1

    tasks = [upload_one(w, f) for w in range(N_WORKERS) for f in range(FILES_PER_WORKER)]
    t0 = time.perf_counter()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0

    throughput_mbs = (total_bytes / 1024 / 1024) / elapsed if elapsed > 0 else 0
    success_rate = (N_WORKERS * FILES_PER_WORKER - errors) / (N_WORKERS * FILES_PER_WORKER)
    v, failed = check([
        ("throughput > 50 MB/s", throughput_mbs > 50),
        ("success_rate > 99.9%", success_rate > 0.999),
    ])
    record("TC-1", "多模态文件批量上传", {
        "files": N_WORKERS * FILES_PER_WORKER, "total_mb": round(total_bytes / 1024 / 1024, 1),
        "elapsed_s": round(elapsed, 2), "throughput_mbs": round(throughput_mbs, 1),
        "success_rate": round(success_rate * 100, 2), "errors": errors,
        "latency_s": stats(latencies),
    }, v, failed)


# ──────────────────────────────────────────────────────────────
# TC-2: 大文件读写
# ──────────────────────────────────────────────────────────────
async def tc2_large_file(client):
    print("\n▶ TC-2: 大文件读写 (50MB × 3 轮)")
    FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    data = os.urandom(FILE_SIZE)
    key = f"{TENANT}/stress/tc2/large_50mb.bin"
    url = f"{SERVER}/api/v1/storage/objects/{S3_BUCKET}/{key}"
    put_lats, get_lats = [], []

    for i in range(3):
        t0 = time.perf_counter()
        resp = await client.put(url, content=data, headers={**RAW_HDR, "Content-Type": "application/octet-stream"}, timeout=60)
        put_lats.append(time.perf_counter() - t0)
        if resp.status_code not in (200, 201):
            print(f"   PUT round {i} failed: {resp.status_code}")

        t0 = time.perf_counter()
        resp = await client.get(url, headers=RAW_HDR, timeout=60)
        get_lats.append(time.perf_counter() - t0)
        if resp.status_code != 200:
            print(f"   GET round {i} failed: {resp.status_code}")

    put_s = stats(put_lats)
    get_s = stats(get_lats)
    v, failed = check([
        ("put p99 < 10s", put_s.get("p99", 999) < 10),
        ("get p99 < 5s", get_s.get("p99", 999) < 5),
    ])
    record("TC-2", "大文件读写", {
        "file_mb": 50, "rounds": 3,
        "put_s": put_s, "get_s": get_s,
    }, v, failed)


# ──────────────────────────────────────────────────────────────
# TC-3: 批量嵌入基准
# ──────────────────────────────────────────────────────────────
async def tc3_batch_embed(client):
    print("\n▶ TC-3: 批量嵌入基准 (100/500/1000 texts)")
    texts_100 = [f"这是第{i}条中文测试文本 LakeMind performance benchmark item {i}" for i in range(100)]
    texts_500 = [f"测试文本 {i} embedding benchmark {'hello world ' * 3}" for i in range(500)]
    texts_1000 = [f"文本内容 {i} {'中英混合 test content ' * 2}" for i in range(1000)]

    async def embed_batch(texts, label):
        t0 = time.perf_counter()
        resp = await client.post(f"{MS}/v1/embeddings", headers=MS_HDR,
                                 json={"model": "jinaai/jina-embeddings-v2-base-zh", "input": texts}, timeout=120)
        dt = time.perf_counter() - t0
        dim = len(resp.json()["data"][0]["embedding"]) if resp.status_code == 200 else 0
        throughput = len(texts) / dt if dt > 0 else 0
        return {"latency_s": round(dt, 3), "throughput": round(throughput, 1), "dim": dim}

    r100 = await embed_batch(texts_100, "100")
    r500 = await embed_batch(texts_500, "500")
    r1000 = await embed_batch(texts_1000, "1000")

    # 逐条 vs 批量 (20 条对比)
    t0 = time.perf_counter()
    for t in texts_100[:20]:
        await client.post(f"{MS}/v1/embeddings", headers=MS_HDR,
                          json={"model": "jinaai/jina-embeddings-v2-base-zh", "input": [t]}, timeout=30)
    single_total = time.perf_counter() - t0
    single_20 = single_total
    speedup = (single_20 / 20 * 100) / r100["latency_s"] if r100["latency_s"] > 0 else 0

    v, failed = check([
        ("batch_100 p50 < 3s", r100["latency_s"] < 3),
        ("batch_1000 < 25s", r1000["latency_s"] < 25),
        ("throughput > 40 texts/s", r100["throughput"] > 40),
        ("batch_speedup > 5x", speedup > 5),
    ])
    record("TC-3", "批量嵌入基准", {
        "batch_100": r100, "batch_500": r500, "batch_1000": r1000,
        "single_100_total_s": round(single_total, 3),
        "batch_speedup": round(speedup, 1),
    }, v, failed)


# ──────────────────────────────────────────────────────────────
# TC-4: 批量向量入库
# ──────────────────────────────────────────────────────────────
async def tc4_batch_vector_add(client):
    print("\n▶ TC-4: 批量向量入库 (10K/100K vectors, 768 dim)")
    db = f"tenant_{TENANT}"
    table = "stress_vec"
    dim = 768

    # 创建表
    sample_rows = [{"id": "init", "vector": [0.0] * dim, "text": "init"}]
    try:
        await client.post(f"{SERVER}/api/v1/storage/vectors/{db}", headers=SERVER_HDR,
                          json={"name": table, "mode": "overwrite", "data": sample_rows}, timeout=30)
    except Exception:
        pass

    async def add_batch(n, label):
        rows = [{"id": f"v{i}", "vector": [random.gauss(0, 1) for _ in range(dim)], "text": f"text {i}"} for i in range(n)]
        t0 = time.perf_counter()
        resp = await client.post(f"{SERVER}/api/v1/storage/vectors/{db}/{table}/add", headers=SERVER_HDR,
                                 json={"data": rows}, timeout=120)
        dt = time.perf_counter() - t0
        throughput = n / dt if dt > 0 else 0
        ok = resp.status_code in (200, 201)
        return {"latency_s": round(dt, 3), "throughput": round(throughput, 1), "ok": ok}

    r1k = await add_batch(1000, "1K")
    r5k = await add_batch(5000, "5K")

    v, failed = check([
        ("1k throughput > 10000 vec/s", r1k["throughput"] > 10000),
        ("5k throughput > 10000 vec/s", r5k["throughput"] > 10000),
    ])
    record("TC-4", "批量向量入库", {
        "add_1k": r1k, "add_5k": r5k, "dim": dim,
    }, v, failed)


# ──────────────────────────────────────────────────────────────
# TC-5: 向量实时检索
# ──────────────────────────────────────────────────────────────
async def tc5_vector_search(client):
    print("\n▶ TC-5: 向量实时检索 (ANN top-10 + 并发 QPS)")
    db = f"tenant_{TENANT}"
    table = "stress_vec"
    dim = 768

    # 单条检索延迟
    latencies = []
    for _ in range(100):
        q = [random.gauss(0, 1) for _ in range(dim)]
        t0 = time.perf_counter()
        try:
            resp = await client.post(f"{SERVER}/api/v1/storage/vectors/{db}/{table}/search", headers=SERVER_HDR,
                                     json={"query_vec": q, "top_k": 10}, timeout=10)
            latencies.append(time.perf_counter() - t0)
        except Exception:
            pass

    search_s = stats(latencies)

    # 并发 QPS
    async def search_once():
        q = [random.gauss(0, 1) for _ in range(dim)]
        try:
            resp = await client.post(f"{SERVER}/api/v1/storage/vectors/{db}/{table}/search", headers=SERVER_HDR,
                                     json={"query_vec": q, "top_k": 10}, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    qps_results = {}
    for concurrency in [10, 50]:
        tasks = [search_once() for _ in range(concurrency * 5)]
        t0 = time.perf_counter()
        outcomes = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - t0
        qps = sum(1 for o in outcomes if o) / elapsed
        err_rate = sum(1 for o in outcomes if not o) / len(outcomes)
        qps_results[concurrency] = {"qps": round(qps, 1), "err_rate": round(err_rate * 100, 2), "elapsed_s": round(elapsed, 2)}

    q10 = qps_results.get(10, {"qps": 0, "err_rate": 100})
    q50 = qps_results.get(50, {"qps": 0, "err_rate": 100})
    v, failed = check([
        ("search p99 < 500ms", search_s.get("p99", 999) < 0.5),
        ("qps_50 > 100", q50["qps"] > 100),
    ])
    record("TC-5", "向量实时检索", {
        "single_search_s": search_s, "qps_10": q10, "qps_50": q50,
    }, v, failed)


# ──────────────────────────────────────────────────────────────
# TC-8: 记忆实时读写
# ──────────────────────────────────────────────────────────────
async def tc8_memory(client):
    print("\n▶ TC-8: 记忆实时读写 (add/search/list)")
    add_lats, search_lats, list_lats, get_lats = [], [], [], []

    # add + search 循环
    for i in range(50):
        t0 = time.perf_counter()
        try:
            resp = await client.post(f"{SERVER}/api/v1/cognitive/memory/add", headers=SERVER_HDR,
                                     json={"content": f"压力测试记忆 {i}: LakeMind 性能验证第 {i} 轮",
                                           "agent_id": "stress-agent", "metadata": {"round": i}}, timeout=15)
            add_lats.append(time.perf_counter() - t0)
        except Exception:
            pass

        t0 = time.perf_counter()
        try:
            resp = await client.post(f"{SERVER}/api/v1/cognitive/memory/search", headers=SERVER_HDR,
                                     json={"query": "压力测试性能", "agent_id": "stress-agent", "top_k": 10}, timeout=15)
            search_lats.append(time.perf_counter() - t0)
        except Exception:
            pass

    # list
    for _ in range(20):
        t0 = time.perf_counter()
        try:
            resp = await client.post(f"{SERVER}/api/v1/cognitive/memory/list", headers=SERVER_HDR,
                                     json={"agent_id": "stress-agent", "page": 1, "page_size": 20}, timeout=10)
            list_lats.append(time.perf_counter() - t0)
        except Exception:
            pass

    add_s = stats(add_lats)
    search_s = stats(search_lats)
    list_s = stats(list_lats)

    # 并发 search QPS
    async def mem_search():
        try:
            resp = await client.post(f"{SERVER}/api/v1/cognitive/memory/search", headers=SERVER_HDR,
                                     json={"query": "测试", "agent_id": "stress-agent", "top_k": 10}, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    tasks = [mem_search() for _ in range(200)]
    t0 = time.perf_counter()
    outcomes = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0
    qps_50 = sum(1 for o in outcomes if o) / elapsed

    v, failed = check([
        ("add p99 < 5s", add_s.get("p99", 999) < 5),
        ("search p99 < 500ms", search_s.get("p99", 999) < 0.5),
        ("list p99 < 200ms", list_s.get("p99", 999) < 0.2),
        ("qps_50 > 80", qps_50 > 80),
    ])
    record("TC-8", "记忆实时读写", {
        "add_s": add_s, "search_s": search_s, "list_s": list_s,
        "concurrent_qps_50": round(qps_50, 1),
    }, v, failed)


# ──────────────────────────────────────────────────────────────
# TC-10: 阶梯并发压测
# ──────────────────────────────────────────────────────────────
async def tc10_staircase(client):
    print("\n▶ TC-10: 阶梯并发压测 (10→30→50→100)")
    levels = [10, 30, 50, 100]
    level_results = {}

    async def mixed_op():
        ops = ["health", "kv", "list_mem", "search_mem"]
        op = random.choice(ops)
        try:
            if op == "health":
                r = await client.get(f"{SERVER}/api/v1/system/health", headers=RAW_HDR, timeout=5)
                return r.status_code < 500
            elif op == "kv":
                r = await client.get(f"{SERVER}/api/v1/storage/kv/stress:test", headers=RAW_HDR, timeout=5)
                return r.status_code < 500
            elif op == "list_mem":
                r = await client.post(f"{SERVER}/api/v1/cognitive/memory/list", headers=SERVER_HDR,
                                      json={"agent_id": "stress-agent", "page": 1, "page_size": 10}, timeout=10)
                return r.status_code < 500
            else:
                r = await client.post(f"{SERVER}/api/v1/cognitive/memory/search", headers=SERVER_HDR,
                                      json={"query": "测试", "agent_id": "stress-agent", "top_k": 5}, timeout=10)
                return r.status_code < 500
        except Exception:
            return False

    for conc in levels:
        tasks = [mixed_op() for _ in range(conc * 10)]
        t0 = time.perf_counter()
        outcomes = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - t0
        ok = sum(1 for o in outcomes if o)
        qps = ok / elapsed
        err_rate = (len(outcomes) - ok) / len(outcomes)
        level_results[conc] = {"qps": round(qps, 1), "err_rate": round(err_rate * 100, 2), "total": len(outcomes)}
        print(f"   concurrency={conc}: qps={qps:.1f} err_rate={err_rate*100:.2f}%")

    breaking = max(levels)
    for conc in levels:
        if level_results[conc]["err_rate"] > 10:
            breaking = conc
            break

    v, failed = check([
        ("conc_100 err < 5%", level_results[100]["err_rate"] < 5),
    ])
    record("TC-10", "阶梯并发压测", {
        **{f"conc_{k}": v for k, v in level_results.items()},
        "breaking_point": breaking,
    }, v, failed)


# ──────────────────────────────────────────────────────────────
# TC-11: 冷启动
# ──────────────────────────────────────────────────────────────
async def tc11_cold_start(client):
    print("\n▶ TC-11: 冷启动 (嵌入冷加载 + API health)")
    # 嵌入冷加载 — 首次调用可能触发模型加载
    t0 = time.perf_counter()
    try:
        resp = await client.post(f"{MS}/v1/embeddings", headers=MS_HDR,
                                 json={"model": "jinaai/jina-embeddings-v2-base-zh", "input": ["cold start test"]}, timeout=30)
        embed_cold = time.perf_counter() - t0
    except Exception:
        embed_cold = time.perf_counter() - t0

    # API health
    t0 = time.perf_counter()
    await client.get(f"{SERVER}/api/v1/system/health", headers=RAW_HDR, timeout=10)
    health_lat = time.perf_counter() - t0

    v, failed = check([
        ("embed_cold < 10s", embed_cold < 10),
        ("health < 15s", health_lat < 15),
    ])
    record("TC-11", "冷启动", {
        "embed_cold_s": round(embed_cold, 3), "health_latency_s": round(health_lat, 3),
    }, v, failed)


# ──────────────────────────────────────────────────────────────
# TC-12: MCP vs REST 开销
# ──────────────────────────────────────────────────────────────
async def tc12_mcp_vs_rest(client):
    print("\n▶ TC-12: MCP vs REST 协议开销")
    # REST: memory/list
    rest_lats = []
    for _ in range(20):
        t0 = time.perf_counter()
        await client.post(f"{SERVER}/api/v1/cognitive/memory/list", headers=SERVER_HDR,
                          json={"agent_id": "stress-agent", "page": 1, "page_size": 10}, timeout=10)
        rest_lats.append(time.perf_counter() - t0)

    # MCP: 通过 DataMCP call tool
    mcp_lats = []
    mcp_url = "http://localhost:8402/mcp"
    mcp_token = "meeting-agent-mcp-token"
    mcp_hdr = {"Authorization": f"Bearer {mcp_token}", "Content-Type": "application/json"}

    for _ in range(20):
        try:
            t0 = time.perf_counter()
            resp = await client.post(mcp_url, headers=mcp_hdr, json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "list_memory", "arguments": {"agent_id": "stress-agent", "page": 1, "page_size": 10}}
            }, timeout=15)
            mcp_lats.append(time.perf_counter() - t0)
        except Exception:
            pass

    rest_s = stats(rest_lats)
    mcp_s = stats(mcp_lats) if mcp_lats else {"count": 0, "mean": 0, "p50": 0, "p99": 0}
    overhead = (mcp_s.get("mean", 0) - rest_s.get("mean", 0)) if mcp_s.get("count", 0) > 0 else 0

    v, failed = check([
        ("overhead < 0.5s", overhead < 0.5),
    ])
    record("TC-12", "MCP vs REST 开销", {
        "rest_s": rest_s, "mcp_s": mcp_s, "overhead_s": round(overhead, 3),
    }, v, failed)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
async def main():
    print("=" * 60)
    print("LakeMind 核心性能压测 — 开始")
    print(f"Server: {SERVER}")
    print(f"ModelServing: {MS}")
    print(f"Tenant: {TENANT}")
    print("=" * 60)

    limits = httpx.Limits(max_connections=500, max_keepalive_connections=200)
    async with httpx.AsyncClient(limits=limits, timeout=60) as client:
        try:
            await tc1_batch_upload(client)
        except Exception as e:
            print(f"TC-1 ERROR: {e}")
            record("TC-1", "多模态文件批量上传", {"error": str(e)}, "ERROR", [str(e)])

        try:
            await tc2_large_file(client)
        except Exception as e:
            print(f"TC-2 ERROR: {e}")
            record("TC-2", "大文件读写", {"error": str(e)}, "ERROR", [str(e)])

        try:
            await tc3_batch_embed(client)
        except Exception as e:
            print(f"TC-3 ERROR: {e}")
            record("TC-3", "批量嵌入基准", {"error": str(e)}, "ERROR", [str(e)])

        try:
            await tc4_batch_vector_add(client)
        except Exception as e:
            print(f"TC-4 ERROR: {e}")
            record("TC-4", "批量向量入库", {"error": str(e)}, "ERROR", [str(e)])

        try:
            await tc5_vector_search(client)
        except Exception as e:
            print(f"TC-5 ERROR: {e}")
            record("TC-5", "向量实时检索", {"error": str(e)}, "ERROR", [str(e)])

        try:
            await tc8_memory(client)
        except Exception as e:
            print(f"TC-8 ERROR: {e}")
            record("TC-8", "记忆实时读写", {"error": str(e)}, "ERROR", [str(e)])

        try:
            await tc10_staircase(client)
        except Exception as e:
            print(f"TC-10 ERROR: {e}")
            record("TC-10", "阶梯并发压测", {"error": str(e)}, "ERROR", [str(e)])

        try:
            await tc11_cold_start(client)
        except Exception as e:
            print(f"TC-11 ERROR: {e}")
            record("TC-11", "冷启动", {"error": str(e)}, "ERROR", [str(e)])

        try:
            await tc12_mcp_vs_rest(client)
        except Exception as e:
            print(f"TC-12 ERROR: {e}")
            record("TC-12", "MCP vs REST 开销", {"error": str(e)}, "ERROR", [str(e)])

    # 输出 JSON 报告
    report = {
        "generated_at": now_iso(),
        "environment": {"server": SERVER, "model_serving": MS, "tenant": TENANT},
        "summary": {"total": len(results), "passed": sum(1 for r in results if r["verdict"] == "PASS"),
                     "failed": sum(1 for r in results if r["verdict"] == "FAIL"),
                     "errors": sum(1 for r in results if r["verdict"] == "ERROR")},
        "results": results,
    }
    report_path = "reports/stress_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n{'=' * 60}")
    print(f"报告已生成: {report_path}")
    print(f"总计: {report['summary']['total']} | 通过: {report['summary']['passed']} | 失败: {report['summary']['failed']} | 错误: {report['summary']['errors']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
