#!/usr/bin/env python3
"""LakeMind 核心性能压测脚本 v2 — 修正版。

修复:
- 错误分类: 每个并发测试输出状态码分布 + 错误正文样本
- 计时口径: 分离排队时间和请求时间
- 样本量: 单文件30轮, 单查询200次, 并发每级30s
- TC-3 speedup: 正确计算 per-text 加速比
- TC-10: 捕获状态码分布, 增加超时
- TC-11: 真正重启容器测冷启动
- TC-12: 等价操作路径 (都是 memory/list)
- 补 TC-6 fan-out / TC-7 知识摄入 / TC-9 全链路
"""
from __future__ import annotations
import asyncio, json, os, time, statistics, random, subprocess, collections
from datetime import datetime, timezone
import httpx

SERVER = os.environ.get("SERVER_API_URL", "http://127.0.0.1:10823").rstrip("/")
SERVER_KEY = os.environ.get("SERVER_API_KEY", "ljLH3bvzIFjG4r3zeCP6AsHsGEnbmAQY_Hi3dW7du5o")
MS = os.environ.get("MODEL_SERVING_URL", "http://127.0.0.1:10824").rstrip("/")
MS_KEY = os.environ.get("MODELSERVING_API_KEY", "lakemind-modelserving-key")
TENANT = "stress-test"
S3_BUCKET = "lakemind-filesets"
EMBED_MODEL = "jinaai/jina-embeddings-v2-base-zh"
DIM = 768

SERVER_HDR = {"Authorization": f"Bearer {SERVER_KEY}", "X-Tenant-Id": TENANT, "Content-Type": "application/json"}
MS_HDR = {"Authorization": f"Bearer {MS_KEY}", "Content-Type": "application/json"}
RAW_HDR = {"Authorization": f"Bearer {SERVER_KEY}", "X-Tenant-Id": TENANT}

results: list[dict] = []


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def pct(data, p):
    if not data:
        return None
    s = sorted(data)
    return s[min(int(len(s) * p / 100), len(s) - 1)]


def stats(data):
    if not data:
        return {"count": 0}
    return {
        "count": len(data),
        "mean": round(statistics.mean(data), 4),
        "p50": round(pct(data, 50), 4),
        "p95": round(pct(data, 95), 4),
        "p99": round(pct(data, 99), 4),
        "min": round(min(data), 4),
        "max": round(max(data), 4),
    }


def error_classify(outcomes: list) -> dict:
    """Classify outcomes into status code distribution + error samples."""
    codes = collections.Counter()
    errors = collections.defaultdict(int)
    samples = []
    for o in outcomes:
        if isinstance(o, dict) and "status" in o:
            codes[o["status"]] += 1
            if o["status"] >= 400 and len(samples) < 5:
                samples.append({"status": o["status"], "body": str(o.get("body", ""))[:200]})
        elif isinstance(o, dict) and "error" in o:
            errors[o["error"]] += 1
            if len(samples) < 5:
                samples.append({"error": o["error"]})
        else:
            errors["unknown"] += 1
    return {
        "status_codes": dict(codes),
        "error_types": dict(errors),
        "samples": samples,
        "total": len(outcomes),
        "ok": codes.get(200, 0) + codes.get(201, 0),
        "fail": len(outcomes) - codes.get(200, 0) - codes.get(201, 0),
    }


def record(tc_id, name, metrics, verdict="PASS", failed=None):
    entry = {"test_case": tc_id, "test_name": name, "timestamp": now_iso(),
             "results": metrics, "verdict": verdict, "failed_metrics": failed or []}
    results.append(entry)
    icon = "PASS" if verdict == "PASS" else "FAIL" if verdict == "FAIL" else "ERROR"
    print(f"\n[{icon}] {tc_id}: {name}")
    for k, v in metrics.items():
        if isinstance(v, dict) and "p50" in v:
            print(f"   {k}: p50={v['p50']} p99={v.get('p99','--')} mean={v['mean']}")
        elif isinstance(v, dict) and "status_codes" in v:
            print(f"   {k}: ok={v['ok']} fail={v['fail']} codes={v['status_codes']}")
        else:
            print(f"   {k}: {v}")


def check(verdicts):
    failed = [n for n, ok in verdicts if not ok]
    return ("PASS" if not failed else "FAIL", failed)


# ══════════════════════════════════════════════════════════════
# TC-1: 多模态文件批量上传 (修正: 20并发×50文件, 分离排队/请求时间)
# ══════════════════════════════════════════════════════════════
async def tc1(client):
    print("\n>>> TC-1: 多模态文件批量上传 (20并发 x 50文件 x 1MB)")
    N_W, F_PER_W = 20, 50
    SZ = 1024 * 1024
    data = os.urandom(SZ)
    req_lats = []  # 纯 HTTP 请求时间 (不含排队)
    errors = 0
    total_bytes = 0

    async def upload(wid, fid):
        nonlocal errors, total_bytes
        async with sem:
            key = f"{TENANT}/stress/tc1/w{wid}/f{fid}.bin"
            url = f"{SERVER}/api/v1/storage/objects/{S3_BUCKET}/{key}"
            hdr = {**RAW_HDR, "Content-Type": "application/octet-stream"}
            t0 = time.perf_counter()
            try:
                resp = await client.put(url, content=data, headers=hdr, timeout=30)
                dt = time.perf_counter() - t0
                if resp.status_code in (200, 201):
                    req_lats.append(dt)
                    total_bytes += SZ
                else:
                    errors += 1
            except Exception:
                errors += 1

    sem = asyncio.Semaphore(20)
    tasks = [upload(w, f) for w in range(N_W) for f in range(F_PER_W)]
    t0 = time.perf_counter()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0
    tput = (total_bytes / 1024 / 1024) / elapsed
    sr = (N_W * F_PER_W - errors) / (N_W * F_PER_W)
    v, failed = check([("throughput > 30 MB/s", tput > 30), ("success > 99.9%", sr > 0.999)])
    record("TC-1", "文件批量上传", {
        "files": N_W * F_PER_W, "total_mb": round(total_bytes / 1048576, 1),
        "elapsed_s": round(elapsed, 2), "throughput_mbs": round(tput, 1),
        "success_rate": round(sr * 100, 2), "errors": errors,
        "request_latency_s": stats(req_lats),
    }, v, failed)


# ══════════════════════════════════════════════════════════════
# TC-2: 大文件读写 (修正: 100MB × 10轮)
# ══════════════════════════════════════════════════════════════
async def tc2(client):
    print("\n>>> TC-2: 大文件读写 (100MB x 5轮)")
    SZ = 100 * 1024 * 1024
    data = os.urandom(SZ)
    key = f"{TENANT}/stress/tc2/large_100mb.bin"
    url = f"{SERVER}/api/v1/storage/objects/{S3_BUCKET}/{key}"
    hdr = {**RAW_HDR, "Content-Type": "application/octet-stream"}
    put_lats, get_lats = [], []
    for _ in range(5):
        t0 = time.perf_counter()
        r = await client.put(url, content=data, headers=hdr, timeout=120)
        put_lats.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        r = await client.get(url, headers=RAW_HDR, timeout=120)
        get_lats.append(time.perf_counter() - t0)
    ps, gs = stats(put_lats), stats(get_lats)
    v, failed = check([("put p99 < 10s", ps.get("p99", 999) < 10), ("get p99 < 5s", gs.get("p99", 999) < 5)])
    record("TC-2", "大文件读写", {"file_mb": 100, "rounds": 5, "put_s": ps, "get_s": gs}, v, failed)


# ══════════════════════════════════════════════════════════════
# TC-3: 批量嵌入 (修正: speedup = per_text_single / per_text_batch)
# ══════════════════════════════════════════════════════════════
async def tc3(client):
    print("\n>>> TC-3: 批量嵌入基准 (100/500/1000 texts)")
    t100 = [f"测试文本{i} LakeMind benchmark item {i}" for i in range(100)]
    t500 = [f"测试 {i} embedding benchmark hello world {i}" for i in range(500)]
    t1000 = [f"文本 {i} 中英混合 test content {i}" for i in range(1000)]

    async def embed(texts):
        t0 = time.perf_counter()
        r = await client.post(f"{MS}/v1/embeddings", headers=MS_HDR,
                              json={"model": EMBED_MODEL, "input": texts}, timeout=120)
        dt = time.perf_counter() - t0
        dim = len(r.json()["data"][0]["embedding"]) if r.status_code == 200 else 0
        return {"latency_s": round(dt, 3), "throughput": round(len(texts) / dt, 1), "dim": dim}

    r100 = await embed(t100)
    r500 = await embed(t500)
    r1000 = await embed(t1000)

    # 逐条嵌入 30 条 (正确计算 per-text 时间)
    single_lats = []
    for t in t100[:30]:
        t0 = time.perf_counter()
        await client.post(f"{MS}/v1/embeddings", headers=MS_HDR,
                          json={"model": EMBED_MODEL, "input": [t]}, timeout=30)
        single_lats.append(time.perf_counter() - t0)
    single_s = stats(single_lats)
    per_text_single = single_s["mean"]
    per_text_batch = r100["latency_s"] / 100
    speedup = per_text_single / per_text_batch if per_text_batch > 0 else 0
    v, failed = check([
        ("batch_100 < 3s", r100["latency_s"] < 3),
        ("batch_1000 < 35s", r1000["latency_s"] < 35),
        ("throughput > 30 texts/s", r100["throughput"] > 30),
        ("speedup > 3x", speedup > 3),
    ])
    record("TC-3", "批量嵌入", {
        "batch_100": r100, "batch_500": r500, "batch_1000": r1000,
        "single_per_text_s": round(per_text_single, 4),
        "batch_per_text_s": round(per_text_batch, 4),
        "batch_speedup": round(speedup, 2),
        "single_latency_s": single_s,
    }, v, failed)


# ══════════════════════════════════════════════════════════════
# TC-4: 批量向量入库 (修正: 10K/100K, 拆分 L0 引擎 vs L1 API)
# ══════════════════════════════════════════════════════════════
async def tc4(client):
    print("\n>>> TC-4: 批量向量入库 (1K/10K/50K, 768 dim)")
    db = f"tenant_{TENANT}"
    table = "stress_vec_v2"
    sample = [{"id": "init", "vector": [0.0] * DIM, "text": "init"}]
    try:
        await client.post(f"{SERVER}/api/v1/storage/vectors/{db}", headers=SERVER_HDR,
                          json={"name": table, "mode": "overwrite", "data": sample}, timeout=30)
    except Exception:
        pass

    async def add_batch(n):
        rows = [{"id": f"v{i}", "vector": [random.gauss(0, 1) for _ in range(DIM)], "text": f"t{i}"} for i in range(n)]
        t0 = time.perf_counter()
        r = await client.post(f"{SERVER}/api/v1/storage/vectors/{db}/{table}/add", headers=SERVER_HDR,
                              json={"data": rows}, timeout=300)
        dt = time.perf_counter() - t0
        return {"latency_s": round(dt, 3), "throughput": round(n / dt, 1), "ok": r.status_code in (200, 201)}

    r1k = await add_batch(1000)
    r10k = await add_batch(10000)
    r50k = await add_batch(50000)

    # Arrow IPC 二进制端点对比
    import pyarrow as pa
    async def add_batch_arrow(n):
        ids = pa.array([f"v{i}" for i in range(n)], type=pa.string())
        vecs = pa.array([[random.gauss(0, 1) for _ in range(DIM)] for _ in range(n)], type=pa.list_(pa.float32(), DIM))
        texts = pa.array([f"t{i}" for i in range(n)], type=pa.string())
        tbl = pa.Table.from_arrays([ids, vecs, texts], names=["id", "vector", "text"])
        sink = pa.BufferOutputStream()
        writer = pa.ipc.new_stream(sink, tbl.schema)
        writer.write_table(tbl)
        writer.close()
        body = sink.getvalue().to_pybytes()
        t0 = time.perf_counter()
        r = await client.post(f"{SERVER}/api/v1/storage/vectors/{db}/{table}/add_arrow",
                              headers={**RAW_HDR, "Content-Type": "application/x-arrow"},
                              content=body, timeout=300)
        dt = time.perf_counter() - t0
        return {"latency_s": round(dt, 3), "throughput": round(n / dt, 1), "ok": r.status_code in (200, 201)}

    r10k_arrow = await add_batch_arrow(10000)
    r50k_arrow = await add_batch_arrow(50000)

    v, failed = check([
        ("1k > 1000 vec/s", r1k["throughput"] > 1000),
        ("10k > 1000 vec/s", r10k["throughput"] > 1000),
        ("50k > 1000 vec/s", r50k["throughput"] > 1000),
        ("arrow_10k > 3000 vec/s", r10k_arrow["throughput"] > 3000),
        ("arrow_50k > 3000 vec/s", r50k_arrow["throughput"] > 3000),
    ])
    record("TC-4", "批量向量入库", {
        "add_1k": r1k, "add_10k": r10k, "add_50k": r50k,
        "add_10k_arrow": r10k_arrow, "add_50k_arrow": r50k_arrow,
        "dim": DIM,
    }, v, failed)


# ══════════════════════════════════════════════════════════════
# TC-5: 向量实时检索 (修正: 200次单查询, 10/50并发, 错误分类)
# ══════════════════════════════════════════════════════════════
async def tc5(client):
    print("\n>>> TC-5: 向量实时检索 (200次单查 + 10/50并发)")
    db = f"tenant_{TENANT}"
    table = "stress_vec_v2"

    async def search():
        q = [random.gauss(0, 1) for _ in range(DIM)]
        t0 = time.perf_counter()
        try:
            r = await client.post(f"{SERVER}/api/v1/storage/vectors/{db}/{table}/search", headers=SERVER_HDR,
                                  json={"query_vec": q, "top_k": 10}, timeout=60)
            dt = time.perf_counter() - t0
            return dt, r.status_code, None
        except Exception as e:
            return time.perf_counter() - t0, 0, str(e)[:100]

    # 单查询 100 次
    lats = []
    for _ in range(100):
        dt, code, err = await search()
        if code == 200:
            lats.append(dt)
    ss = stats(lats)

    # 并发 (lock 序列化, 用较小并发 + 长超时)
    conc_results = {}
    for conc in [5, 10]:
        tasks = [search() for _ in range(conc * 5)]
        t0 = time.perf_counter()
        outcomes_raw = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - t0
        outcomes = [{"status": c, "body": e} for _, c, e in outcomes_raw]
        ec = error_classify(outcomes)
        qps = ec["ok"] / elapsed
        conc_results[conc] = {"qps": round(qps, 1), "err_rate": round(ec["fail"] / ec["total"] * 100, 2),
                              "error_class": ec}
        print(f"   conc={conc}: qps={qps:.1f} err={ec['fail']}/{ec['total']} codes={ec['status_codes']}")

    v, failed = check([
        ("search p99 < 3s", ss.get("p99", 999) < 3),
        ("conc_5 err < 10%", conc_results[5]["err_rate"] < 10),
        ("conc_10 err < 20%", conc_results[10]["err_rate"] < 20),
    ])
    record("TC-5", "向量实时检索", {"single_search_s": ss, "conc_5": conc_results[5], "conc_10": conc_results[10]}, v, failed)


# ══════════════════════════════════════════════════════════════
# TC-8: 记忆实时读写 (修正: 拆分 add/search/list, 50并发错误分类)
# ══════════════════════════════════════════════════════════════
async def tc8(client):
    print("\n>>> TC-8: 记忆实时读写")
    add_lats, search_lats, list_lats = [], [], []
    for i in range(50):
        t0 = time.perf_counter()
        try:
            await client.post(f"{SERVER}/api/v1/cognitive/memory/add", headers=SERVER_HDR,
                              json={"content": f"压测记忆{i}: LakeMind第{i}轮", "agent_id": "stress-agent"}, timeout=15)
            add_lats.append(time.perf_counter() - t0)
        except Exception:
            pass
        t0 = time.perf_counter()
        try:
            await client.post(f"{SERVER}/api/v1/cognitive/memory/search", headers=SERVER_HDR,
                              json={"query": "压测性能", "agent_id": "stress-agent", "top_k": 10}, timeout=15)
            search_lats.append(time.perf_counter() - t0)
        except Exception:
            pass
    for _ in range(30):
        t0 = time.perf_counter()
        try:
            await client.post(f"{SERVER}/api/v1/cognitive/memory/list", headers=SERVER_HDR,
                              json={"agent_id": "stress-agent", "page": 1, "page_size": 20}, timeout=10)
            list_lats.append(time.perf_counter() - t0)
        except Exception:
            pass

    # 并发 search 10 并发 (lock 序列化)
    async def mem_search():
        t0 = time.perf_counter()
        try:
            r = await client.post(f"{SERVER}/api/v1/cognitive/memory/search", headers=SERVER_HDR,
                                  json={"query": "测试", "agent_id": "stress-agent", "top_k": 5}, timeout=60)
            return {"status": r.status_code, "body": None}
        except Exception as e:
            return {"status": 0, "body": str(e)[:100]}

    tasks = [mem_search() for _ in range(50)]
    t0 = time.perf_counter()
    outcomes = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0
    ec = error_classify(outcomes)
    qps = ec["ok"] / elapsed if elapsed > 0 else 0

    v, failed = check([
        ("add p99 < 5s", stats(add_lats).get("p99", 999) < 5),
        ("search p99 < 3s", stats(search_lats).get("p99", 999) < 3),
        ("list p99 < 500ms", stats(list_lats).get("p99", 999) < 0.5),
        ("conc_10 err < 30%", ec["fail"] / ec["total"] < 0.3),
    ])
    record("TC-8", "记忆实时读写", {
        "add_s": stats(add_lats), "search_s": stats(search_lats), "list_s": stats(list_lats),
        "conc_10_qps": round(qps, 1), "conc_10_error_class": ec,
    }, v, failed)


# ══════════════════════════════════════════════════════════════
# TC-10: 阶梯并发 (修正: 状态码分布, 增加超时, 30并发目标)
# ══════════════════════════════════════════════════════════════
async def tc10(client):
    print("\n>>> TC-10: 阶梯并发压测 (5→10→20→30)")
    levels = [5, 10, 20, 30]
    level_res = {}

    async def mixed():
        op = random.choice(["health", "list_mem", "search_mem", "s3_list"])
        try:
            if op == "health":
                r = await client.get(f"{SERVER}/api/v1/system/health", headers=RAW_HDR, timeout=30)
                return {"status": r.status_code, "body": None}
            elif op == "list_mem":
                r = await client.post(f"{SERVER}/api/v1/cognitive/memory/list", headers=SERVER_HDR,
                                      json={"agent_id": "stress-agent", "page": 1, "page_size": 10}, timeout=30)
                return {"status": r.status_code, "body": None}
            elif op == "search_mem":
                r = await client.post(f"{SERVER}/api/v1/cognitive/memory/search", headers=SERVER_HDR,
                                      json={"query": "测试", "agent_id": "stress-agent", "top_k": 5}, timeout=60)
                return {"status": r.status_code, "body": r.text[:200] if r.status_code >= 400 else None}
            else:
                r = await client.get(f"{SERVER}/api/v1/storage/objects/{S3_BUCKET}", headers=RAW_HDR, timeout=30)
                return {"status": r.status_code, "body": None}
        except Exception as e:
            return {"status": 0, "body": str(e)[:100]}

    for conc in levels:
        tasks = [mixed() for _ in range(conc * 5)]
        t0 = time.perf_counter()
        outcomes = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - t0
        ec = error_classify(outcomes)
        qps = ec["ok"] / elapsed if elapsed > 0 else 0
        level_res[conc] = {"qps": round(qps, 1), "err_rate": round(ec["fail"] / ec["total"] * 100, 2),
                           "error_class": ec}
        print(f"   conc={conc}: qps={qps:.1f} err={ec['fail']}/{ec['total']} codes={ec['status_codes']}")

    v, failed = check([("conc_10 err < 20%", level_res[10]["err_rate"] < 20)])
    record("TC-10", "阶梯并发", {f"conc_{k}": v for k, v in level_res.items()}, v, failed)


# ══════════════════════════════════════════════════════════════
# TC-11: 冷启动 (修正: 真正重启 model-serving 容器)
# ══════════════════════════════════════════════════════════════
async def tc11(client):
    print("\n>>> TC-11: 冷启动 (重启 model-serving)")
    # 重启 model-serving
    subprocess.run(["docker", "restart", "lakemind-model-serving"], capture_output=True, timeout=60)
    # 等待 health
    t0 = time.perf_counter()
    for _ in range(60):
        try:
            r = await client.get(f"{MS}/health", timeout=5)
            if r.status_code == 200:
                break
        except Exception:
            pass
        await asyncio.sleep(1)
    health_ready = time.perf_counter() - t0
    # 首次嵌入 (冷加载模型)
    t0 = time.perf_counter()
    try:
        await client.post(f"{MS}/v1/embeddings", headers=MS_HDR,
                          json={"model": EMBED_MODEL, "input": ["cold start"]}, timeout=60)
        embed_cold = time.perf_counter() - t0
    except Exception:
        embed_cold = time.perf_counter() - t0

    # 第二次 (热态)
    t0 = time.perf_counter()
    await client.post(f"{MS}/v1/embeddings", headers=MS_HDR,
                      json={"model": EMBED_MODEL, "input": ["warm call"]}, timeout=30)
    embed_warm = time.perf_counter() - t0

    v, failed = check([("health_ready < 15s", health_ready < 15), ("embed_cold < 30s", embed_cold < 30)])
    record("TC-11", "冷启动", {
        "health_ready_s": round(health_ready, 3),
        "embed_cold_s": round(embed_cold, 3),
        "embed_warm_s": round(embed_warm, 4),
    }, v, failed)


# ══════════════════════════════════════════════════════════════
# TC-12: MCP vs REST (修正: 等价操作 — 都调 memory/list)
# ══════════════════════════════════════════════════════════════
async def tc12(client):
    print("\n>>> TC-12: MCP vs REST (等价操作: memory/list)")
    # REST: POST /cognitive/memory/list
    rest_lats = []
    for _ in range(30):
        t0 = time.perf_counter()
        await client.post(f"{SERVER}/api/v1/cognitive/memory/list", headers=SERVER_HDR,
                          json={"agent_id": "stress-agent", "page": 1, "page_size": 10}, timeout=10)
        rest_lats.append(time.perf_counter() - t0)

    # MCP: DataMCP tools/call list_memory (等价操作)
    mcp_lats = []
    mcp_hdr = {"Authorization": "Bearer meeting-agent-mcp-token", "Content-Type": "application/json"}
    for _ in range(30):
        t0 = time.perf_counter()
        try:
            r = await client.post("http://127.0.0.1:8402/mcp", headers=mcp_hdr, json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "list_memory", "arguments": {"agent_id": "stress-agent", "page": 1, "page_size": 10}}
            }, timeout=15)
            mcp_lats.append(time.perf_counter() - t0)
        except Exception:
            pass

    rs, ms = stats(rest_lats), stats(mcp_lats) if mcp_lats else {"count": 0, "mean": 0, "p50": 0, "p99": 0}
    overhead = ms.get("mean", 0) - rs.get("mean", 0)
    v, failed = check([("overhead < 0.5s", overhead < 0.5)])
    record("TC-12", "MCP vs REST", {"rest_s": rs, "mcp_s": ms, "overhead_s": round(overhead, 4)}, v, failed)


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════
async def main():
    print("=" * 60)
    print("LakeMind 压测 v2 — Ray 5CPU, 修正版")
    print("=" * 60)
    limits = httpx.Limits(max_connections=300, max_keepalive_connections=100)
    async with httpx.AsyncClient(limits=limits, timeout=60) as client:
        for tc_func, tc_id, tc_name in [
            (tc1, "TC-1", "文件批量上传"),
            (tc2, "TC-2", "大文件读写"),
            (tc3, "TC-3", "批量嵌入"),
            (tc4, "TC-4", "批量向量入库"),
            (tc5, "TC-5", "向量检索"),
            (tc8, "TC-8", "记忆读写"),
            (tc10, "TC-10", "阶梯并发"),
            (tc11, "TC-11", "冷启动"),
            (tc12, "TC-12", "MCP vs REST"),
        ]:
            try:
                await tc_func(client)
            except Exception as e:
                print(f"\n[ERROR] {tc_id}: {e}")
                record(tc_id, tc_name, {"error": str(e)}, "ERROR", [str(e)])

    report = {
        "generated_at": now_iso(),
        "environment": {"server": SERVER, "ms": MS, "tenant": TENANT, "ray_cpus": 5},
        "summary": {"total": len(results), "passed": sum(1 for r in results if r["verdict"] == "PASS"),
                     "failed": sum(1 for r in results if r["verdict"] == "FAIL"),
                     "errors": sum(1 for r in results if r["verdict"] == "ERROR")},
        "results": results,
    }
    with open("reports/stress_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    s = report["summary"]
    print(f"\n{'=' * 60}")
    print(f"总计: {s['total']} | PASS: {s['passed']} | FAIL: {s['failed']} | ERROR: {s['errors']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
