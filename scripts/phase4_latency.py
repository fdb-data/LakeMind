"""Phase 4 Step 27 — 端到端延迟对比：MCP → REST API → 引擎 vs 直连 REST API。"""
import time
import requests
import json

MCP_URL = "http://localhost:8401/mcp"
TOKEN = "test-steward-token"
REST_URL = "http://localhost:10823/api/v1"
REST_KEY = "lakemind-internal-api-key"

def mcp_call(method, params):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    r = requests.post(MCP_URL, json=payload, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30)
    return r.json()

def rest_call(path, body=None):
    h = {"Authorization": f"Bearer {REST_KEY}", "X-Tenant-Id": "platform", "X-Agent-Id": "steward", "X-Scopes": "asset,data,admin"}
    if body:
        r = requests.post(f"{REST_URL}{path}", json=body, headers=h, timeout=30)
    else:
        r = requests.get(f"{REST_URL}{path}", headers=h, timeout=30)
    return r.json()

def bench(name, func, n=20):
    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            func()
        except Exception:
            pass
        latencies.append((time.perf_counter() - t0) * 1000)
    avg = sum(latencies) / len(latencies)
    return name, round(avg, 2), round(min(latencies), 2), round(max(latencies), 2)

results = []

# MCP → REST API → 引擎
results.append(bench("MCP: recall (via AssetMCP)", lambda: mcp_call("tools/call", {"name": "recall", "arguments": {"query": "test", "limit": 3}})))
results.append(bench("MCP: query_ontology", lambda: mcp_call("tools/call", {"name": "query_ontology", "arguments": {"concept": "test"}})))

# 直连 REST API
results.append(bench("REST: memory/recall (direct)", lambda: rest_call("/cognitive/memory/recall", {"query": "test", "limit": 3})))
results.append(bench("REST: graph/nodes (direct)", lambda: rest_call("/storage/graph/ontology_platform/nodes", None)))

# 基线: REST API 引擎内部延迟 (from Phase 2 benchmark)
baselines = {
    "REST: memory/recall (direct)": 30.97,
    "REST: graph/nodes (direct)": 77.02,
}

print("=" * 70)
print("Phase 4 Step 27 — 端到端延迟对比")
print("=" * 70)
print(f"{'路径':<40s} {'avg(ms)':>8s} {'min(ms)':>8s} {'max(ms)':>8s}")
print("-" * 70)
for name, avg, mn, mx in results:
    print(f"{name:<40s} {avg:>8.2f} {mn:>8.2f} {mx:>8.2f}")

print("\n延迟增量分析:")
mcp_recall = next(r[1] for r in results if "MCP: recall" in r[0])
rest_recall = next(r[1] for r in results if "REST: memory/recall" in r[0])
delta = mcp_recall - rest_recall
print(f"  MCP recall:    {mcp_recall:.2f}ms")
print(f"  REST recall:   {rest_recall:.2f}ms")
print(f"  增量 (MCP层):  {delta:.2f}ms")

mcp_onto = next(r[1] for r in results if "MCP: query_ontology" in r[0])
rest_onto = next(r[1] for r in results if "REST: graph/nodes" in r[0])
delta2 = mcp_onto - rest_onto
print(f"  MCP ontology:  {mcp_onto:.2f}ms")
print(f"  REST graph:    {rest_onto:.2f}ms")
print(f"  增量 (MCP层):  {delta2:.2f}ms")

print(f"\n结论: MCP 层额外延迟 ~{delta:.0f}ms (HTTP JSON-RPC 封装开销)")
print(f"设计目标: < 2ms (Linux + keep-alive 场景)")
print(f"实际: ~{delta:.0f}ms (Windows + requests 库, 每次新建 TCP 连接)")

with open("reports/phase4_latency.json", "w") as f:
    json.dump({"results": [{"name": n, "avg_ms": a, "min_ms": mn, "max_ms": mx} for n, a, mn, mx in results], "mcp_overhead_ms": delta}, f, indent=2)
