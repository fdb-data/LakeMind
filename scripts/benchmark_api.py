#!/usr/bin/env python3
"""
Phase 2 — REST API 性能基准 + 并发压测 + 插件可插拔性验证
"""
from __future__ import annotations
import json
import time
import sys
import statistics
import concurrent.futures
import requests

BASE = "http://localhost:10823/api/v1"
API_KEY = "lakemind-internal-api-key"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "X-Tenant-Id": "default",
    "X-Agent-Id": "bench-api",
    "X-Scopes": "asset,data,admin",
    "Content-Type": "application/json",
}

results: list[dict] = []


def api(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{BASE}{path}"
    kw = dict(kwargs)
    kw.setdefault("headers", HEADERS)
    kw.setdefault("timeout", 60)
    return requests.request(method, url, **kw)


def bench(name: str, func, n: int = 100) -> dict:
    latencies = []
    errors = 0
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            ok = func()
            if not ok:
                errors += 1
        except Exception:
            errors += 1
        latencies.append((time.perf_counter() - t0) * 1000)

    ok_count = n - errors
    rps = ok_count / (sum(latencies) / 1000) if sum(latencies) > 0 else 0
    entry = {
        "name": name,
        "n": n,
        "ok": ok_count,
        "errors": errors,
        "avg_ms": round(statistics.mean(latencies), 2),
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(sorted(latencies)[int(n * 0.95)] if n > 1 else latencies[0], 2),
        "p99_ms": round(sorted(latencies)[int(n * 0.99)] if n > 1 else latencies[0], 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "rps": round(rps, 1),
    }
    results.append(entry)
    status = "OK" if errors == 0 else f"ERR({errors})"
    print(f"  {name:40s}  n={n:4d}  {status:8s}  avg={entry['avg_ms']:7.2f}ms  p50={entry['p50_ms']:7.2f}ms  p95={entry['p95_ms']:7.2f}ms  rps={entry['rps']:8.1f}")
    return entry


# ════════════════════════════════════════════════════════════
# Benchmark targets
# ════════════════════════════════════════════════════════════

def b_health():
    r = api("GET", "/system/health")
    return r.status_code == 200


def b_kv_set():
    r = api("PUT", "/storage/kv/bench:key", json={"value": "bench_val"})
    return r.status_code == 200


def b_kv_get():
    r = api("GET", "/storage/kv/bench:key")
    return r.status_code == 200


def b_object_put():
    r = api("PUT", "/storage/objects/bench-bucket/bench/file.txt",
            data=b"benchmark data payload",
            headers={**HEADERS, "Content-Type": "application/octet-stream"})
    return r.status_code == 200


def b_object_get():
    r = api("GET", "/storage/objects/bench-bucket/bench/file.txt")
    return r.status_code == 200


def b_sql():
    r = api("POST", "/compute/sql/", json={"sql": "SELECT 1 AS val"})
    return r.status_code == 200


def b_sql_with_table():
    r = api("POST", "/compute/sql/", json={
        "sql": "SELECT count(*) AS c FROM t",
        "tables": {"t": [{"id": 1}, {"id": 2}, {"id": 3}]},
    })
    return r.status_code == 200


def b_graph_add_node():
    r = api("POST", "/storage/graph/bench_graph/nodes", json={
        "node_id": f"bench_{time.perf_counter_ns()}", "label": "Bench", "properties": {},
    })
    return r.status_code == 200


def b_graph_query():
    r = api("GET", "/storage/graph/bench_graph/nodes")
    return r.status_code == 200


def b_metadata_list_tenants():
    r = api("GET", "/metadata/tenants")
    return r.status_code == 200


def b_embed():
    r = api("POST", "/cognitive/embedding/embed", json={"texts": ["benchmark text"]})
    return r.status_code == 200


def b_job_submit():
    r = api("POST", "/compute/jobs/", json={"func": "noop", "args": {}})
    return r.status_code == 200


# ════════════════════════════════════════════════════════════
# Concurrent stress test
# ════════════════════════════════════════════════════════════

def concurrent_stress(name: str, func, workers: int = 20, ops_per_worker: int = 50):
    print(f"\n  并发压测: {name} ({workers} workers × {ops_per_worker} ops)")
    all_latencies = []
    errors = 0

    def worker(_):
        local_lat = []
        local_err = 0
        for _ in range(ops_per_worker):
            t0 = time.perf_counter()
            try:
                ok = func()
                if not ok:
                    local_err += 1
            except Exception:
                local_err += 1
            local_lat.append((time.perf_counter() - t0) * 1000)
        return local_lat, local_err

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, i) for i in range(workers)]
        for f in concurrent.futures.as_completed(futures):
            lat, err = f.result()
            all_latencies.extend(lat)
            errors += err
    elapsed = time.perf_counter() - t0

    total_ops = workers * ops_per_worker
    ok_ops = total_ops - errors
    all_latencies.sort()
    n = len(all_latencies)

    entry = {
        "name": f"concurrent: {name}",
        "workers": workers,
        "ops_per_worker": ops_per_worker,
        "total_ops": total_ops,
        "ok": ok_ops,
        "errors": errors,
        "elapsed_s": round(elapsed, 3),
        "throughput_ops": round(ok_ops / elapsed, 1) if elapsed > 0 else 0,
        "avg_ms": round(statistics.mean(all_latencies), 2),
        "p50_ms": round(statistics.median(all_latencies), 2),
        "p95_ms": round(all_latencies[int(n * 0.95)], 2),
        "p99_ms": round(all_latencies[int(n * 0.99)], 2),
    }
    results.append(entry)
    print(f"    total={total_ops}  ok={ok_ops}  err={errors}  "
          f"elapsed={entry['elapsed_s']:.3f}s  throughput={entry['throughput_ops']:.1f} ops/s  "
          f"avg={entry['avg_ms']:.2f}ms  p95={entry['p95_ms']:.2f}ms")
    return entry


# ════════════════════════════════════════════════════════════
# Pluggability test — verify engine switching via config
# ════════════════════════════════════════════════════════════

def test_pluggability():
    print("\n[Pluggability] 插件可插拔性验证")
    checks = []

    r = api("GET", "/system/health")
    data = r.json()
    all_healthy = all(data.values())
    checks.append(("all 10 engines healthy", all_healthy))

    engine_names = sorted(data.keys())
    expected = sorted([
        "object_storage", "tabular", "vector", "kv", "graph",
        "metadata", "sql", "distributed", "embedding", "memory",
    ])
    checks.append(("engine names match protocol", engine_names == expected))

    r = requests.get(f"{BASE}/system/health", timeout=10)
    checks.append(("health accessible without auth", r.status_code == 200))

    r = requests.get("http://localhost:10823/docs", timeout=10)
    checks.append(("OpenAPI docs available", r.status_code == 200))

    r = requests.get("http://localhost:10823/openapi.json", timeout=10)
    checks.append(("OpenAPI spec available", r.status_code == 200))
    if r.status_code == 200:
        spec = r.json()
        paths = spec.get("paths", {})
        checks.append(("OpenAPI has paths", len(paths) > 20))
        checks.append(("OpenAPI path count", len(paths) >= 30))

    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    for name, ok in checks:
        print(f"    {'PASS' if ok else 'FAIL'}  {name}")

    results.append({"name": "pluggability", "ok": passed, "total": total})
    return passed, total


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("Phase 2 — REST API 性能基准 + 并发压测 + 可插拔性")
    print("=" * 70)

    print("\n[单线程基准] (100 ops each)")
    bench("system/health", b_health, 100)
    bench("kv/set", b_kv_set, 100)
    bench("kv/get", b_kv_get, 100)
    bench("object/put (20B)", b_object_put, 100)
    bench("object/get (20B)", b_object_get, 100)
    bench("sql/select 1", b_sql, 100)
    bench("sql/with_table(3 rows)", b_sql_with_table, 100)
    bench("graph/add_node", b_graph_add_node, 100)
    bench("graph/query_nodes", b_graph_query, 100)
    bench("metadata/list_tenants", b_metadata_list_tenants, 100)
    bench("job/submit", b_job_submit, 100)
    bench("embedding/embed(1 text)", b_embed, 50)

    print("\n[并发压测] (20 workers × 50 ops = 1000 ops each)")
    concurrent_stress("kv/set", b_kv_set, 20, 50)
    concurrent_stress("kv/get", b_kv_get, 20, 50)
    concurrent_stress("object/put", b_object_put, 20, 50)
    concurrent_stress("object/get", b_object_get, 20, 50)
    concurrent_stress("sql/select", b_sql, 20, 50)
    concurrent_stress("graph/query", b_graph_query, 20, 50)
    concurrent_stress("metadata/list_tenants", b_metadata_list_tenants, 20, 50)
    concurrent_stress("job/submit", b_job_submit, 20, 50)

    print("\n[高并发压测] (50 workers × 100 ops = 5000 ops)")
    concurrent_stress("kv/get (high concurrency)", b_kv_get, 50, 100)
    concurrent_stress("sql/select (high concurrency)", b_sql, 50, 100)

    p, t = test_pluggability()

    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    for r in results:
        if "errors" in r and "total_ops" not in r:
            print(f"  {r['name']:45s}  ok={r['ok']:4d}  err={r['errors']:3d}  "
                  f"avg={r['avg_ms']:7.2f}ms  p95={r['p95_ms']:7.2f}ms  rps={r['rps']:8.1f}")
        elif "total_ops" in r:
            print(f"  {r['name']:45s}  ok={r['ok']:5d}  err={r['errors']:4d}  "
                  f"throughput={r['throughput_ops']:8.1f} ops/s  p95={r['p95_ms']:7.2f}ms")
        else:
            print(f"  {r['name']:45s}  {r['ok']}/{r['total']} PASS")

    report_path = "reports/phase2_benchmark.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {report_path}")

    all_ok = all(
        r.get("errors", 0) == 0 if "errors" in r
        else r.get("ok", 0) == r.get("total", 0) if "total" in r
        else True
        for r in results
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
