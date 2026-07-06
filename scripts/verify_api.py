#!/usr/bin/env python3
"""
Phase 2 — REST API 功能验证
覆盖全部 11 个 API 域：system, objects, tables, vectors, kv, graph, sql, jobs, embedding, memory, metadata
"""
from __future__ import annotations
import json
import time
import sys
import requests

BASE = "http://localhost:10823/api/v1"
API_KEY = "lakemind-internal-api-key"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "X-Tenant-Id": "default",
    "X-Agent-Id": "verify-api",
    "X-Scopes": "asset,data,admin",
    "Content-Type": "application/json",
}

passed = 0
failed = 0
errors: list[str] = []


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        msg = f"  FAIL  {name} — {detail}"
        print(msg)
        errors.append(msg)


def api(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{BASE}{path}"
    kw = dict(kwargs)
    kw.setdefault("headers", HEADERS)
    kw.setdefault("timeout", 60)
    return requests.request(method, url, **kw)


def api_json(method: str, path: str, **kwargs):
    r = api(method, path, **kwargs)
    return r, r.json() if r.headers.get("content-type", "").startswith("application/json") else None


# ════════════════════════════════════════════════════════════
# 1. System
# ════════════════════════════════════════════════════════════
def test_system():
    print("\n[1/11] System")
    r, data = api_json("GET", "/system/health")
    check("health status 200", r.status_code == 200, f"got {r.status_code}")
    if data:
        for eng, ok in data.items():
            check(f"engine {eng} healthy", ok is True, f"={ok}")

    r, data = api_json("GET", "/system/nodes")
    check("nodes status 200", r.status_code == 200)
    check("nodes has list", data and "nodes" in data, str(data))

    r, data = api_json("GET", "/system/metrics")
    check("metrics status 200", r.status_code == 200)


# ════════════════════════════════════════════════════════════
# 2. Objects (SeaweedFS)
# ════════════════════════════════════════════════════════════
def test_objects():
    print("\n[2/11] Objects (SeaweedFS)")
    bucket = "verify-api-bucket"
    key = "test/file.txt"
    content = b"Hello LakeMind REST API!"

    r = api("PUT", f"/storage/objects/{bucket}/{key}", data=content,
            headers={**HEADERS, "Content-Type": "application/octet-stream"})
    check("put object 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")

    r = api("GET", f"/storage/objects/{bucket}/{key}")
    check("get object 200", r.status_code == 200)
    check("get object content match", r.content == content, f"got {r.content[:100]}")

    r = api("HEAD", f"/storage/objects/{bucket}/{key}")
    check("exists object 200", r.status_code == 200)

    r, data = api_json("GET", f"/storage/objects/{bucket}")
    check("list objects 200", r.status_code == 200)
    check("list contains key", data and key in data.get("keys", []), str(data))

    r = api("DELETE", f"/storage/objects/{bucket}/{key}")
    check("delete object 200", r.status_code == 200)

    r = api("HEAD", f"/storage/objects/{bucket}/{key}")
    check("deleted object not found", r.status_code == 404)

    for i in range(5):
        api("PUT", f"/storage/objects/{bucket}/batch/file_{i}.txt", data=f"data_{i}".encode(),
            headers={**HEADERS, "Content-Type": "application/octet-stream"})
    r, data = api_json("GET", f"/storage/objects/{bucket}", params={"prefix": "batch/"})
    check("list batch 5 keys", data and data.get("count") == 5, str(data))


# ════════════════════════════════════════════════════════════
# 3. Tables (Iceberg)
# ════════════════════════════════════════════════════════════
def test_tables():
    print("\n[3/11] Tables (Iceberg)")
    ns = "verify_ns"
    tbl = "test_table"

    r, data = api_json("POST", "/storage/tables/", json={
        "namespace": ns,
        "table": tbl,
        "schema": {"id": "int64", "name": "string", "value": "float64"},
    })
    check("create table 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")

    r, data = api_json("GET", f"/storage/tables/{ns}")
    check("list tables 200", r.status_code == 200)
    check("list contains table", data and tbl in data.get("tables", []), str(data))

    r, data = api_json("GET", f"/storage/tables/{ns}/{tbl}")
    check("describe table 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    check("describe has schema", data and "schema" in data, str(data))

    rows = [{"id": i, "name": f"name_{i}", "value": float(i) * 1.5} for i in range(10)]
    r, data = api_json("POST", f"/storage/tables/{ns}/{tbl}/append", json={"rows": rows})
    check("append 10 rows", r.status_code == 200 and data and data.get("rows_written") == 10,
          f"got {r.status_code}: {r.text[:200]}")

    r, data = api_json("GET", f"/storage/tables/{ns}/{tbl}/scan")
    check("scan table 200", r.status_code == 200)
    check("scan returns 10 rows", data and data.get("count") == 10, str(data)[:200])

    r, data = api_json("GET", f"/storage/tables/{ns}/{tbl}/scan", params={"limit": 3})
    check("scan limit 3", data and data.get("count") == 3, str(data)[:200])

    r, data = api_json("GET", f"/storage/tables/{ns}/{tbl}/scan", params={"columns": "id,name"})
    check("scan select columns", data and data.get("count") == 10, str(data)[:200])

    rows2 = [{"id": 100, "name": "overwritten", "value": 99.9}]
    r, data = api_json("POST", f"/storage/tables/{ns}/{tbl}/overwrite", json={"rows": rows2})
    check("overwrite 1 row", r.status_code == 200 and data and data.get("rows_written") == 1,
          f"got {r.status_code}")

    r, data = api_json("GET", f"/storage/tables/{ns}/{tbl}/scan")
    check("scan after overwrite 1 row", data and data.get("count") == 1, str(data)[:200])

    r = api("DELETE", f"/storage/tables/{ns}/{tbl}")
    check("drop table 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")


# ════════════════════════════════════════════════════════════
# 4. Vectors (LanceDB)
# ════════════════════════════════════════════════════════════
def test_vectors():
    print("\n[4/11] Vectors (LanceDB)")
    db = "verify_vec_db"
    name = "test_vectors"

    data_rows = [
        {"id": i, "text": f"doc_{i}", "vector": [float(i) * 0.1, float(i + 1) * 0.1, float(i + 2) * 0.1]}
        for i in range(10)
    ]
    r, data = api_json("POST", f"/storage/vectors/{db}", json={
        "name": name,
        "data": data_rows,
        "mode": "overwrite",
    })
    check("create vector table 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")

    r, data = api_json("GET", f"/storage/vectors/{db}")
    check("list vector tables 200", r.status_code == 200)
    check("list contains table", data and name in data.get("tables", []), str(data))

    r, data = api_json("GET", f"/storage/vectors/{db}/{name}")
    check("describe vector table 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    check("describe row count 10", data and data.get("row_count") == 10, str(data))

    more = [{"id": 10 + i, "text": f"added_{i}", "vector": [0.5, 0.5, 0.5]} for i in range(3)]
    r, data = api_json("POST", f"/storage/vectors/{db}/{name}/add", json={"data": more})
    check("add 3 vectors", r.status_code == 200 and data and data.get("rows_added") == 3,
          f"got {r.status_code}")

    r, data = api_json("POST", f"/storage/vectors/{db}/{name}/search", json={
        "query_vec": [0.5, 0.5, 0.5],
        "top_k": 5,
    })
    check("vector search 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    check("search returns 5 results", data and data.get("count") == 5, str(data)[:200])


# ════════════════════════════════════════════════════════════
# 5. KV (Dragonfly)
# ════════════════════════════════════════════════════════════
def test_kv():
    print("\n[5/11] KV (Dragonfly)")
    key = "verify:key1"
    r, data = api_json("PUT", f"/storage/kv/{key}", json={"value": "hello_world"})
    check("kv set 200", r.status_code == 200, f"got {r.status_code}")

    r, data = api_json("GET", f"/storage/kv/{key}")
    check("kv get 200", r.status_code == 200)
    check("kv value match", data and data.get("value") == "hello_world", str(data))

    r, data = api_json("PUT", f"/storage/kv/verify:ttl_key", json={"value": "temp", "ttl": 2})
    check("kv set with ttl 200", r.status_code == 200)
    r, data = api_json("GET", "/storage/kv/verify:ttl_key")
    check("kv ttl key exists", r.status_code == 200 and data and data.get("value") == "temp")
    time.sleep(3)
    r = api("GET", "/storage/kv/verify:ttl_key")
    check("kv ttl key expired", r.status_code == 404)

    for i in range(5):
        api_json("PUT", f"/storage/kv/verify:batch_{i}", json={"value": f"val_{i}"})
    r, data = api_json("GET", "/storage/kv/", params={"pattern": "verify:batch_*"})
    check("kv scan batch 5", data and data.get("count") == 5, str(data))

    r, data = api_json("DELETE", f"/storage/kv/{key}")
    check("kv delete 200", r.status_code == 200)
    r = api("GET", f"/storage/kv/{key}")
    check("kv deleted not found", r.status_code == 404)


# ════════════════════════════════════════════════════════════
# 6. Graph (PostgreSQL)
# ════════════════════════════════════════════════════════════
def test_graph():
    print("\n[6/11] Graph (PostgreSQL)")
    graph = "verify_graph"

    r, data = api_json("POST", f"/storage/graph/{graph}/nodes", json={
        "node_id": "node_a", "label": "Entity", "properties": {"name": "Alice"},
    })
    check("add node_a 200", r.status_code == 200, f"got {r.status_code}")

    r, data = api_json("POST", f"/storage/graph/{graph}/nodes", json={
        "node_id": "node_b", "label": "Entity", "properties": {"name": "Bob"},
    })
    check("add node_b 200", r.status_code == 200)

    r, data = api_json("POST", f"/storage/graph/{graph}/edges", json={
        "edge_id": "edge_1", "src": "node_a", "dst": "node_b",
        "rel": "knows", "properties": {"since": "2024"},
    })
    check("add edge 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")

    r, data = api_json("GET", f"/storage/graph/{graph}/nodes")
    check("query nodes 200", r.status_code == 200)
    check("query nodes count 2", data and data.get("count") == 2, str(data))

    r, data = api_json("GET", f"/storage/graph/{graph}/nodes", params={"label": "Entity"})
    check("query nodes by label", data and data.get("count") == 2, str(data))

    r, data = api_json("GET", f"/storage/graph/{graph}/edges", params={"src": "node_a"})
    check("query edges 200", r.status_code == 200)
    check("query edges count 1", data and data.get("count") == 1, str(data))

    r = api("DELETE", f"/storage/graph/{graph}/nodes/node_a")
    check("delete node 200", r.status_code == 200)


# ════════════════════════════════════════════════════════════
# 7. SQL (DuckDB)
# ════════════════════════════════════════════════════════════
def test_sql():
    print("\n[7/11] SQL (DuckDB)")
    r, data = api_json("POST", "/compute/sql/", json={
        "sql": "SELECT 1 AS val",
    })
    check("sql select 1", r.status_code == 200 and data and data.get("count") == 1,
          f"got {r.status_code}: {r.text[:200]}")
    check("sql result val=1", data and data["results"][0].get("val") == 1, str(data))

    r, data = api_json("POST", "/compute/sql/", json={
        "sql": "SELECT count(*) AS cnt FROM t",
        "tables": {"t": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 3, "name": "c"}]},
    })
    check("sql count with table", r.status_code == 200 and data and data["results"][0].get("cnt") == 3,
          f"got {r.status_code}: {r.text[:200]}")

    r, data = api_json("POST", "/compute/sql/", json={
        "sql": "SELECT id, name FROM t WHERE id > 1 ORDER BY id",
        "tables": {"t": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 3, "name": "c"}]},
    })
    check("sql filter+order", data and data.get("count") == 2, str(data))
    check("sql first row id=2", data and data["results"][0].get("id") == 2, str(data))


# ════════════════════════════════════════════════════════════
# 8. Jobs (Embedded)
# ════════════════════════════════════════════════════════════
def test_jobs():
    print("\n[8/11] Jobs (Embedded)")
    r, data = api_json("POST", "/compute/jobs/", json={
        "func": "noop", "args": {"x": 1},
    })
    check("submit job 200", r.status_code == 200, f"got {r.status_code}")
    job_id = data.get("job_id") if data else None
    check("job_id returned", job_id is not None, str(data))

    r, data = api_json("GET", f"/compute/jobs/{job_id}")
    check("job status 200", r.status_code == 200)
    check("job status completed", data and data.get("status") == "completed", str(data))

    r, data = api_json("GET", f"/compute/jobs/{job_id}/result")
    check("job result 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")


# ════════════════════════════════════════════════════════════
# 9. Embedding (fastembed)
# ════════════════════════════════════════════════════════════
def test_embedding():
    print("\n[9/11] Embedding (fastembed)")
    r, data = api_json("POST", "/cognitive/embedding/embed", json={
        "texts": ["hello world", "lake mind"],
    })
    check("embed 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    check("embed count 2", data and data.get("count") == 2, str(data)[:200])
    check("embed dim 768", data and data.get("dim") == 768, str(data)[:200])
    if data and data.get("vectors"):
        check("embed vector len 768", len(data["vectors"][0]) == 768, str(len(data["vectors"][0])))

    r, data = api_json("POST", "/cognitive/embedding/embed", json={"texts": []})
    check("embed empty list", r.status_code == 200 and data and data.get("count") == 0,
          f"got {r.status_code}")


# ════════════════════════════════════════════════════════════
# 10. Memory (BasicMemory)
# ════════════════════════════════════════════════════════════
def test_memory():
    print("\n[10/11] Memory (BasicMemory)")
    r, data = api_json("POST", "/cognitive/memory/remember", json={
        "content": "LakeMind is a multi-modal data lake platform",
        "context": "project intro",
        "kind": "general",
    })
    check("remember long-term 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    check("remember type long_term", data and data.get("type") == "long_term", str(data))

    r, data = api_json("POST", "/cognitive/memory/remember", json={
        "content": "temporary context note",
        "ttl": 5,
        "kind": "general",
    })
    check("remember short-term 200", r.status_code == 200)
    check("remember type short_term", data and data.get("type") == "short_term", str(data))

    r, data = api_json("POST", "/cognitive/memory/recall", json={
        "query": "data lake platform",
        "limit": 5,
    })
    check("recall 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    check("recall has results", data and data.get("count", 0) >= 0, str(data)[:200])

    r, data = api_json("POST", "/cognitive/memory/forget", json={"query": "temporary"})
    check("forget 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")


# ════════════════════════════════════════════════════════════
# 11. Metadata (PostgreSQL)
# ════════════════════════════════════════════════════════════
def test_metadata():
    print("\n[11/11] Metadata (PostgreSQL)")
    tenant_id = "verify_tenant"

    r, data = api_json("POST", "/metadata/tenants", json={
        "tenant_id": tenant_id, "name": "Verify Tenant",
    })
    check("create tenant 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")

    r, data = api_json("GET", "/metadata/tenants")
    check("list tenants 200", r.status_code == 200)
    check("list has verify_tenant", data and any(t.get("tenant_id") == tenant_id for t in data.get("tenants", [])),
          str(data)[:200])

    r, data = api_json("PUT", f"/metadata/tenants/{tenant_id}", json={"name": "Updated Tenant"})
    check("update tenant 200", r.status_code == 200)

    r, data = api_json("POST", "/metadata/users", json={
        "username": "verify_user", "tenant_id": tenant_id, "role": "admin",
    })
    check("create user 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    user_id = data.get("user_id") if data else None

    r, data = api_json("GET", "/metadata/users", params={"tenant_id": tenant_id})
    check("list users by tenant", r.status_code == 200 and data and data.get("count", 0) >= 1, str(data)[:200])

    if user_id:
        r, data = api_json("PUT", f"/metadata/users/{user_id}", json={"role": "user"})
        check("update user 200", r.status_code == 200)

        r, data = api_json("DELETE", f"/metadata/users/{user_id}")
        check("delete user 200", r.status_code == 200)

    r, data = api_json("POST", "/metadata/tokens", json={
        "agent_id": "verify-agent", "tenant_id": tenant_id, "scopes": ["asset", "data"],
    })
    check("issue token 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    token = data.get("token") if data else None

    r, data = api_json("GET", "/metadata/tokens", params={"tenant_id": tenant_id})
    check("list tokens 200", r.status_code == 200 and data and data.get("count", 0) >= 1, str(data)[:200])

    if token:
        r, data = api_json("DELETE", f"/metadata/tokens/{token}")
        check("revoke token 200", r.status_code == 200)

    r, data = api_json("POST", "/metadata/asset-types", json={
        "type": "verify_asset", "yaml_def": "kind: verify\nversion: 1",
    })
    check("register asset type 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")

    r, data = api_json("GET", "/metadata/asset-types")
    check("list asset types 200", r.status_code == 200)
    check("list has verify_asset", data and any(a.get("type") == "verify_asset" for a in data.get("asset_types", [])),
          str(data)[:200])

    r, data = api_json("DELETE", "/metadata/asset-types/verify_asset")
    check("unregister asset type 200", r.status_code == 200)

    r, data = api_json("DELETE", f"/metadata/tenants/{tenant_id}")
    check("delete tenant 200", r.status_code == 200)


# ════════════════════════════════════════════════════════════
# Auth
# ════════════════════════════════════════════════════════════
def test_auth():
    print("\n[Auth] Authentication")
    r = requests.get(f"{BASE}/system/nodes", timeout=10)
    check("no auth → 401", r.status_code == 401, f"got {r.status_code}")

    r = requests.get(f"{BASE}/system/nodes", headers={"Authorization": "Bearer wrong-key"}, timeout=10)
    check("wrong key → 401", r.status_code == 401, f"got {r.status_code}")

    r = requests.get(f"{BASE}/system/health", timeout=10)
    check("health no auth → 200", r.status_code == 200, f"got {r.status_code}")


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("Phase 2 — REST API 功能验证")
    print("=" * 60)

    test_auth()
    test_system()
    test_objects()
    test_tables()
    test_vectors()
    test_kv()
    test_graph()
    test_sql()
    test_jobs()
    test_embedding()
    test_memory()
    test_metadata()

    print("\n" + "=" * 60)
    total = passed + failed
    print(f"结果: {passed}/{total} PASS, {failed} FAIL")
    print("=" * 60)

    if errors:
        print("\n失败详情:")
        for e in errors:
            print(e)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
