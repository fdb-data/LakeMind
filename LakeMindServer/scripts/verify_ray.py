#!/usr/bin/env python3
"""Ray 引擎完整功能和能力测试"""
import requests
import time
import json
import sys

BASE = "http://localhost:10823/api/v1/compute/jobs"
HEADERS = {
    "Authorization": "Bearer lakemind-internal-api-key",
    "X-Tenant-Id": "default",
    "X-Agent-Id": "ray-test",
    "X-Scopes": "asset:read,asset:write,data:read,data:write,admin:read,admin:write",
    "Content-Type": "application/json",
}

passed = 0
failed = 0


def submit(func, args):
    r = requests.post(BASE + "/", headers=HEADERS, json={"func": func, "args": args})
    assert r.status_code == 200, f"submit failed: {r.status_code} {r.text}"
    return r.json()["job_id"]


def status(job_id):
    r = requests.get(f"{BASE}/{job_id}", headers=HEADERS)
    assert r.status_code == 200, f"status failed: {r.status_code} {r.text}"
    return r.json()


def result(job_id):
    r = requests.get(f"{BASE}/{job_id}/result", headers=HEADERS)
    assert r.status_code == 200, f"result failed: {r.status_code} {r.text}"
    return r.json()["result"]


def wait_done(job_id, timeout=30):
    for _ in range(timeout * 2):
        s = status(job_id)
        if s["status"] == "completed":
            return s
        time.sleep(0.5)
    return status(job_id)


def test(name, func):
    global passed, failed
    try:
        func()
        print(f"  PASS  {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        failed += 1


# ── 功能测试 ──

def t_health():
    r = requests.get("http://localhost:10823/api/v1/system/health", headers=HEADERS).json()
    assert r["distributed"] is True, "distributed engine not healthy"


def t_submit_status_result():
    jid = submit("sum", {"data": [1, 2, 3, 4, 5]})
    s = wait_done(jid)
    assert s["status"] == "completed", f"status={s}"
    res = result(jid)
    assert res == 15, f"sum result={res}"


def t_sleep_test():
    jid = submit("sleep_test", {"n": 2})
    s = status(jid)
    assert s["status"] in ("running", "completed"), f"immediate status={s}"
    s = wait_done(jid, timeout=10)
    assert s["status"] == "completed", f"final status={s}"
    res = result(jid)
    assert "slept" in str(res), f"result={res}"


def t_map():
    jid = submit("map", {"fn": "lambda x: x * x", "items": [1, 2, 3, 4, 5]})
    s = wait_done(jid)
    assert s["status"] == "completed"
    res = result(jid)
    assert res == [1, 4, 9, 16, 25], f"map result={res}"


def t_parallel_map():
    items = list(range(100))
    jid = submit("parallel_map", {"fn": "lambda x: x * 2", "items": items, "num_workers": 4})
    s = wait_done(jid, timeout=15)
    assert s["status"] == "completed"
    res = result(jid)
    expected = [x * 2 for x in items]
    assert res == expected, f"parallel_map mismatch: len={len(res)} vs {len(expected)}"


def t_not_found():
    s = status("job_nonexistent")
    assert s["status"] == "not_found", f"not_found={s}"


def t_generic():
    jid = submit("custom_func", {"key": "value"})
    s = wait_done(jid)
    assert s["status"] == "completed"
    res = result(jid)
    assert res["executed"] is True, f"generic={res}"


# ── 能力测试 ──

def t_pi_monte_carlo():
    jid = submit("pi_monte_carlo", {"n_samples": 4_000_000, "num_workers": 4})
    s = wait_done(jid, timeout=60)
    assert s["status"] == "completed", f"pi status={s}"
    pi_est = result(jid)
    assert 3.0 < pi_est < 3.3, f"pi estimate={pi_est}"
    print(f"        π ≈ {pi_est:.6f}")


def t_matrix_multiply():
    jid = submit("matrix_multiply", {"size": 200})
    s = wait_done(jid, timeout=30)
    assert s["status"] == "completed"
    res = result(jid)
    assert isinstance(res, float) and res > 0, f"matmul={res}"
    print(f"        sum(A@B) = {res:.2f}")


def t_large_parallel_map():
    items = list(range(1000))
    jid = submit("parallel_map", {"fn": "lambda x: x ** 2 + x", "items": items, "num_workers": 8})
    s = wait_done(jid, timeout=30)
    assert s["status"] == "completed"
    res = result(jid)
    expected = [x ** 2 + x for x in items]
    assert res == expected, "large parallel_map mismatch"


def t_concurrent_jobs():
    jids = []
    for i in range(10):
        jids.append(submit("sum", {"data": list(range(100))}))
    for jid in jids:
        s = wait_done(jid, timeout=15)
        assert s["status"] == "completed", f"concurrent {jid} status={s}"
        res = result(jid)
        assert res == 4950, f"concurrent result={res}"


def t_ray_cluster_nodes():
    import subprocess
    out = subprocess.run(
        ["docker", "exec", "lakemind-server-api", "python", "-c",
         "import ray; ray.init(address='ray://lakemind-ray-head:10001', ignore_reinit_error=True, log_to_driver=False); "
         "nodes=ray.nodes(); print(len(nodes))"],
        capture_output=True, text=True, timeout=30
    )
    num_nodes = int(out.stdout.strip().split("\n")[-1])
    assert num_nodes >= 3, f"expected 3 nodes, got {num_nodes}"
    print(f"        Ray cluster nodes: {num_nodes}")


# ── 运行 ──

print("=" * 60)
print("Ray 引擎完整测试")
print("=" * 60)

print("\n── 功能测试 ──")
test("health check (distributed=true)", t_health)
test("submit/status/result (sum)", t_submit_status_result)
test("sleep_test (async task)", t_sleep_test)
test("map (parallel remote tasks)", t_map)
test("parallel_map (batched workers)", t_parallel_map)
test("not_found (invalid job_id)", t_not_found)
test("generic (unknown func fallback)", t_generic)

print("\n── 能力测试 ──")
test("Monte Carlo π (4M samples, 4 workers)", t_pi_monte_carlo)
test("Matrix multiply (200×200)", t_matrix_multiply)
test("Large parallel_map (1000 items, 8 workers)", t_large_parallel_map)
test("10 concurrent jobs", t_concurrent_jobs)
test("Ray cluster has 3 nodes", t_ray_cluster_nodes)

print(f"\n{'=' * 60}")
print(f"Result: {passed} PASS, {failed} FAIL")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
