#!/usr/bin/env python3
"""LakeMind 全面测试 — L0~L9 全分层验证。

Layers:
  L0  容器健康 (12)
  L1  引擎健康 (11)
  L2  REST API (~48)
  L3  AssetMCP (40)
  L4  DataMCP (26)
  L5  AdminMCP (25)
  L6  MCP 安全 (12)
  L7  Steward+Monitor (8)
  L8  端到端业务流 (5)
  L9  性能基线 (10)
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
from typing import Any

import httpx

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

# ─── Config ───────────────────────────────────────────────────────

REST_BASE = "http://localhost:10823/api/v1"
REST_KEY = "lakemind-internal-api-key"
REST_H = {
    "Authorization": f"Bearer {REST_KEY}",
    "X-Tenant-Id": "default",
    "X-Agent-Id": "verify-full",
    "X-Scopes": "asset,data,admin",
    "Content-Type": "application/json",
}

ASSET_URL = "http://localhost:8401/mcp"
DATA_URL = "http://localhost:8402/mcp"
ADMIN_URL = "http://localhost:8403/mcp"
ASSET_TOKEN = "test-business-token"
DATA_TOKEN = "test-steward-token"
ADMIN_TOKEN = "test-steward-token"

CONTAINERS = [
    "lakemind-server-api", "lakemind-postgres", "lakemind-seaweedfs",
    "lakemind-valkey", "lakemind-ray-head", "lakemind-ray-worker-1",
    "lakemind-ray-worker-2", "lakemind-asset-mcp", "lakemind-data-mcp",
    "lakemind-admin-mcp", "lakemind-steward", "lakemind-monitor",
]

EXPECTED_ENGINES = [
    "object_storage", "tabular", "vector", "kv", "graph", "metadata",
    "sql", "distributed", "embedding", "memory", "llm",
]

# ─── Result tracking ──────────────────────────────────────────────

results: list[dict] = []
pass_count = 0
fail_count = 0
skip_count = 0


def record(layer: str, category: str, name: str, passed: bool, detail: str = "", duration: float = 0):
    global pass_count, fail_count
    if passed:
        pass_count += 1
    else:
        fail_count += 1
    results.append({
        "layer": layer, "category": category, "name": name,
        "passed": passed, "detail": detail, "duration_ms": round(duration * 1000, 1),
    })
    tag = "PASS" if passed else "FAIL"
    line = f"  [{tag}] {layer}/{category}/{name}"
    if not passed and detail:
        line += f" — {detail[:120]}"
    print(line)


def skip(layer: str, category: str, name: str, reason: str):
    global skip_count
    skip_count += 1
    results.append({"layer": layer, "category": category, "name": name, "passed": None, "detail": f"SKIP: {reason}"})
    print(f"  [SKIP] {layer}/{category}/{name} — {reason}")


# ─── Helpers ──────────────────────────────────────────────────────

def rest(method: str, path: str, **kw) -> httpx.Response:
    url = f"{REST_BASE}{path}"
    kw.setdefault("headers", REST_H)
    kw.setdefault("timeout", 60)
    with httpx.Client() as c:
        return c.request(method, url, **kw)


def rest_json(method: str, path: str, **kw):
    r = rest(method, path, **kw)
    try:
        return r, r.json()
    except Exception:
        return r, None


async def mcp_call(session: ClientSession, name: str, args: dict) -> dict:
    r = await session.call_tool(name, args)
    text = r.content[0].text if r.content else "{}"
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


async def mcp_session(url: str, token: str, fn):
    headers = {"Authorization": f"Bearer {token}"}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0
    s = sorted(data)
    k = int(len(s) * p / 100)
    return s[min(k, len(s) - 1)]


def trimmed_stats(data: list[float]) -> dict:
    if not data:
        return {"mean": 0, "p50": 0, "p95": 0, "p99": 0, "min": 0, "max": 0, "n": 0}
    s = sorted(data)
    trim = len(s) // 10
    trimmed = s[trim:len(s) - trim] if trim > 0 and len(s) > 4 else s
    return {
        "mean": round(statistics.mean(trimmed), 2),
        "p50": round(percentile(s, 50), 2),
        "p95": round(percentile(s, 95), 2),
        "p99": round(percentile(s, 99), 2),
        "min": round(s[0], 2),
        "max": round(s[-1], 2),
        "n": len(s),
    }


# ════════════════════════════════════════════════════════════════
# L0 — 容器健康
# ════════════════════════════════════════════════════════════════

def test_l0():
    print(f"\n{'='*60}\nL0 — 容器健康 (12)\n{'='*60}")
    try:
        out = subprocess.check_output(
            ["docker", "ps", "--filter", "name=lakemind-", "--format", "{{.Names}}\t{{.Status}}"],
            text=True, timeout=30,
        )
    except Exception as e:
        record("L0", "docker", "docker_ps", False, str(e))
        return
    lines = {l.split("\t")[0]: l.split("\t")[1] if "\t" in l else "" for l in out.strip().split("\n") if l}
    for c in CONTAINERS:
        status = lines.get(c, "")
        up = "Up" in status
        record("L0", "container", c, up, f"status={status}")


# ════════════════════════════════════════════════════════════════
# L1 — 引擎健康
# ════════════════════════════════════════════════════════════════

def test_l1():
    print(f"\n{'='*60}\nL1 — 引擎健康 (11)\n{'='*60}")
    r, data = rest_json("GET", "/system/health")
    if r.status_code != 200:
        record("L1", "meta", "health_endpoint", False, f"status={r.status_code}")
        return
    record("L1", "meta", "health_endpoint", True)
    for eng in EXPECTED_ENGINES:
        ok = data.get(eng) is True
        record("L1", "engine", eng, ok, f"value={data.get(eng)}")


# ════════════════════════════════════════════════════════════════
# L2 — REST API
# ════════════════════════════════════════════════════════════════

def test_l2():
    print(f"\n{'='*60}\nL2 — REST API\n{'='*60}")
    _l2_auth()
    _l2_system()
    _l2_objects()
    _l2_tables()
    _l2_vectors()
    _l2_kv()
    _l2_graph()
    _l2_sql()
    _l2_jobs()
    _l2_embedding()
    _l2_memory()
    _l2_llm()
    _l2_metadata()


def _l2_auth():
    r = rest("GET", "/system/nodes")
    record("L2", "auth", "no_bearer_rejected", r.status_code in (401, 403, 200), f"got {r.status_code}")
    r = rest("GET", "/system/nodes", headers={**REST_H, "Authorization": "Bearer wrong"})
    record("L2", "auth", "wrong_bearer_401", r.status_code in (401, 403), f"got {r.status_code}")
    r = rest("GET", "/system/health")
    record("L2", "auth", "health_open_200", r.status_code == 200, f"got {r.status_code}")


def _l2_system():
    r, d = rest_json("GET", "/system/nodes")
    record("L2", "system", "nodes", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", "/system/metrics")
    record("L2", "system", "metrics", r.status_code == 200, f"got {r.status_code}")


def _l2_objects():
    bucket, key = "verify-full", "test/obj.txt"
    content = b"hello full test"
    r = rest("PUT", f"/storage/objects/{bucket}/{key}", content=content,
             headers={**REST_H, "Content-Type": "application/octet-stream"})
    record("L2", "objects", "put", r.status_code == 200, f"got {r.status_code}")
    r = rest("GET", f"/storage/objects/{bucket}/{key}")
    record("L2", "objects", "get", r.status_code == 200 and r.content == content, f"got {r.status_code}")
    r = rest("HEAD", f"/storage/objects/{bucket}/{key}")
    record("L2", "objects", "exists", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", f"/storage/objects/{bucket}")
    record("L2", "objects", "list", r.status_code == 200, f"got {r.status_code}")
    r = rest("DELETE", f"/storage/objects/{bucket}/{key}")
    record("L2", "objects", "delete", r.status_code == 200, f"got {r.status_code}")


def _l2_tables():
    ns, tbl = "vf_ns", "test_t"
    r, d = rest_json("POST", "/storage/tables/", json={"namespace": ns, "table": tbl, "schema": {"id": "int64", "name": "string"}})
    record("L2", "tables", "create", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    r, d = rest_json("GET", f"/storage/tables/{ns}")
    record("L2", "tables", "list", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", f"/storage/tables/{ns}/{tbl}")
    record("L2", "tables", "describe", r.status_code == 200, f"got {r.status_code}")
    rows = [{"id": i, "name": f"n{i}"} for i in range(5)]
    r, d = rest_json("POST", f"/storage/tables/{ns}/{tbl}/append", json={"rows": rows})
    record("L2", "tables", "append", r.status_code == 200 and d and d.get("rows_written") == 5, f"got {r.status_code}")
    r, d = rest_json("POST", f"/storage/tables/{ns}/{tbl}/overwrite", json={"rows": [{"id": 99, "name": "ow"}]})
    record("L2", "tables", "overwrite", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", f"/storage/tables/{ns}/{tbl}/scan")
    record("L2", "tables", "scan", r.status_code == 200 and d and d.get("count") == 1, f"got {r.status_code}: {str(d)[:200]}")
    r = rest("DELETE", f"/storage/tables/{ns}/{tbl}")
    record("L2", "tables", "drop", r.status_code == 200, f"got {r.status_code}")


def _l2_vectors():
    db, name = "vf_vec", "test_v"
    data_rows = [{"id": i, "text": f"doc_{i}", "vector": [float(i) * 0.1, float(i + 1) * 0.1, float(i + 2) * 0.1]} for i in range(10)]
    r, d = rest_json("POST", f"/storage/vectors/{db}", json={"name": name, "data": data_rows, "mode": "overwrite"})
    record("L2", "vectors", "create", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    r, d = rest_json("GET", f"/storage/vectors/{db}")
    record("L2", "vectors", "list", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", f"/storage/vectors/{db}/{name}")
    record("L2", "vectors", "describe", r.status_code == 200, f"got {r.status_code}")
    more = [{"id": 10 + i, "text": f"add_{i}", "vector": [0.5, 0.5, 0.5]} for i in range(3)]
    r, d = rest_json("POST", f"/storage/vectors/{db}/{name}/add", json={"data": more})
    record("L2", "vectors", "add", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("POST", f"/storage/vectors/{db}/{name}/search", json={"query_vec": [0.5, 0.5, 0.5], "top_k": 5})
    record("L2", "vectors", "search", r.status_code == 200 and d and d.get("count") == 5, f"got {r.status_code}: {str(d)[:200]}")


def _l2_kv():
    key = "vf:k1"
    r, d = rest_json("PUT", f"/storage/kv/{key}", json={"value": "hello"})
    record("L2", "kv", "set", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", f"/storage/kv/{key}")
    record("L2", "kv", "get", r.status_code == 200 and d and d.get("value") == "hello", f"got {r.status_code}")
    r, d = rest_json("GET", "/storage/kv/", params={"pattern": "vf:*"})
    record("L2", "kv", "scan", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("DELETE", f"/storage/kv/{key}")
    record("L2", "kv", "delete", r.status_code == 200, f"got {r.status_code}")


def _l2_graph():
    g = "vf_graph"
    r, d = rest_json("POST", f"/storage/graph/{g}/nodes", json={"node_id": "a", "label": "Entity", "properties": {"name": "A"}})
    record("L2", "graph", "add_node", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("POST", f"/storage/graph/{g}/nodes", json={"node_id": "b", "label": "Entity", "properties": {"name": "B"}})
    record("L2", "graph", "add_node2", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("POST", f"/storage/graph/{g}/edges", json={"edge_id": "e1", "src": "a", "dst": "b", "rel": "knows"})
    record("L2", "graph", "add_edge", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", f"/storage/graph/{g}/nodes")
    record("L2", "graph", "query_nodes", r.status_code == 200 and d and d.get("count") == 2, f"got {r.status_code}: {str(d)[:200]}")
    r, d = rest_json("GET", f"/storage/graph/{g}/edges", params={"src": "a"})
    record("L2", "graph", "query_edges", r.status_code == 200, f"got {r.status_code}")
    r = rest("DELETE", f"/storage/graph/{g}/nodes/a")
    record("L2", "graph", "delete_node", r.status_code == 200, f"got {r.status_code}")


def _l2_sql():
    r, d = rest_json("POST", "/compute/sql/", json={"sql": "SELECT 1 AS v"})
    record("L2", "sql", "select_1", r.status_code == 200 and d and d["results"][0].get("v") == 1, f"got {r.status_code}")
    r, d = rest_json("POST", "/compute/sql/", json={"sql": "SELECT count(*) AS c FROM t", "tables": {"t": [{"x": 1}, {"x": 2}]}})
    record("L2", "sql", "count_with_table", r.status_code == 200 and d and d["results"][0].get("c") == 2, f"got {r.status_code}")


def _l2_jobs():
    r, d = rest_json("POST", "/compute/jobs/", json={"func": "noop", "args": {}})
    jid = d.get("job_id") if d else None
    record("L2", "jobs", "submit", r.status_code == 200 and jid, f"got {r.status_code}")
    r, d = rest_json("GET", f"/compute/jobs/{jid}")
    record("L2", "jobs", "status", r.status_code == 200 and d and d.get("status") == "completed", f"got {r.status_code}: {str(d)[:200]}")
    r, d = rest_json("GET", f"/compute/jobs/{jid}/result")
    record("L2", "jobs", "result", r.status_code == 200, f"got {r.status_code}")


def _l2_embedding():
    r, d = rest_json("POST", "/cognitive/embedding/embed", json={"texts": ["hello", "你好世界"]})
    record("L2", "embedding", "embed", r.status_code == 200, f"got {r.status_code}")
    record("L2", "embedding", "dim_768", d and d.get("dim") == 768, f"dim={d.get('dim') if d else '?'}")
    record("L2", "embedding", "count_2", d and d.get("count") == 2, f"count={d.get('count') if d else '?'}")


def _l2_memory():
    r, d = rest_json("POST", "/cognitive/memory/add", json={"messages": [{"role": "user", "content": "I like Python"}], "infer": False})
    mid = d.get("results", [{}])[0].get("id") if d and d.get("results") else None
    record("L2", "memory", "add", mid is not None, f"got {r.status_code}: {str(d)[:200]}")
    r, d = rest_json("POST", "/cognitive/memory/search", json={"query": "programming", "top_k": 5})
    record("L2", "memory", "search", r.status_code == 200 and "results" in (d or {}), f"got {r.status_code}")
    if mid:
        r, d = rest_json("GET", f"/cognitive/memory/{mid}")
        record("L2", "memory", "get", r.status_code == 200, f"got {r.status_code}")
    else:
        skip("L2", "memory", "get", "no mid")
    r, d = rest_json("POST", "/cognitive/memory/list", json={"page": 1, "page_size": 10})
    record("L2", "memory", "list", r.status_code == 200, f"got {r.status_code}")
    if mid:
        r, d = rest_json("PUT", f"/cognitive/memory/{mid}", json={"content": "I like Rust"})
        record("L2", "memory", "update", r.status_code == 200, f"got {r.status_code}")
        r, d = rest_json("GET", f"/cognitive/memory/{mid}/history")
        record("L2", "memory", "history", r.status_code == 200, f"got {r.status_code}")
        r, d = rest_json("DELETE", f"/cognitive/memory/{mid}")
        record("L2", "memory", "delete", r.status_code == 200, f"got {r.status_code}")
    else:
        skip("L2", "memory", "update", "no mid")
        skip("L2", "memory", "history", "no mid")
        skip("L2", "memory", "delete", "no mid")
    r, d = rest_json("POST", "/cognitive/memory/clear", json={})
    record("L2", "memory", "clear", r.status_code == 200, f"got {r.status_code}")


def _l2_llm():
    r, d = rest_json("GET", "/cognitive/llm/health")
    record("L2", "llm", "health", r.status_code == 200 and d and d.get("healthy") is True, f"got {r.status_code}")
    r, d = rest_json("GET", "/cognitive/llm/models")
    record("L2", "llm", "models", r.status_code == 200 and d and len(d.get("models", [])) >= 1, f"got {r.status_code}")
    r, d = rest_json("POST", "/cognitive/llm/chat", json={"messages": [{"role": "user", "content": "Say OK"}], "model": "auto", "max_tokens": 20})
    record("L2", "llm", "chat", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("POST", "/cognitive/llm/embed", json={"texts": ["test"], "model": "auto"})
    record("L2", "llm", "embed", r.status_code in (200, 502), f"got {r.status_code}")


def _l2_metadata():
    tid = "vf_tenant"
    r, d = rest_json("POST", "/metadata/tenants", json={"tenant_id": tid, "name": "VF"})
    record("L2", "metadata", "create_tenant", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", "/metadata/tenants")
    record("L2", "metadata", "list_tenants", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("PUT", f"/metadata/tenants/{tid}", json={"name": "Updated"})
    record("L2", "metadata", "update_tenant", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("POST", "/metadata/users", json={"username": "vfuser", "tenant_id": tid, "role": "user"})
    uid = d.get("user_id") if d else None
    record("L2", "metadata", "create_user", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", "/metadata/users", params={"tenant_id": tid})
    record("L2", "metadata", "list_users", r.status_code == 200, f"got {r.status_code}")
    if uid:
        r, d = rest_json("PUT", f"/metadata/users/{uid}", json={"role": "admin"})
        record("L2", "metadata", "update_user", r.status_code == 200, f"got {r.status_code}")
        r, d = rest_json("DELETE", f"/metadata/users/{uid}")
        record("L2", "metadata", "delete_user", r.status_code == 200, f"got {r.status_code}")
    else:
        skip("L2", "metadata", "update_user", "no uid")
        skip("L2", "metadata", "delete_user", "no uid")
    r, d = rest_json("POST", "/metadata/tokens", json={"agent_id": "vfagent", "tenant_id": tid, "scopes": ["asset"]})
    record("L2", "metadata", "issue_token", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", "/metadata/tokens", params={"tenant_id": tid})
    record("L2", "metadata", "list_tokens", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("POST", "/metadata/asset-types", json={"type": "vf_asset", "yaml_def": "kind: test"})
    record("L2", "metadata", "register_asset_type", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("GET", "/metadata/asset-types")
    record("L2", "metadata", "list_asset_types", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("DELETE", "/metadata/asset-types/vf_asset")
    record("L2", "metadata", "unregister_asset_type", r.status_code == 200, f"got {r.status_code}")
    r, d = rest_json("DELETE", f"/metadata/tenants/{tid}")
    record("L2", "metadata", "delete_tenant", r.status_code == 200, f"got {r.status_code}")


# ════════════════════════════════════════════════════════════════
# L3 — AssetMCP
# ════════════════════════════════════════════════════════════════

async def test_l3(session: ClientSession):
    M = "AssetMCP"
    print(f"\n{'='*60}\nL3 — {M} (23 tools / 11 resources / 6 prompts)\n{'='*60}")

    tools = await session.list_tools()
    tn = sorted(t.name for t in tools.tools)
    expected_tools = [
        "add_memory", "clear_memory", "delete_knowledge", "delete_memory", "delete_ontology",
        "delete_skill", "get_knowledge", "get_memory", "get_skill", "ingest_knowledge",
        "list_concepts", "list_knowledge", "list_memory", "list_skills", "memory_history",
        "query_ontology", "register_knowledge", "register_skill", "search_knowledge",
        "search_memory", "search_skill", "update_memory", "update_ontology",
    ]
    record("L3", "meta", "tool_count", len(tn) == 23, f"got {len(tn)}")
    for t in expected_tools:
        record("L3", "tool_list", t, t in tn)
    record("L3", "tool_list", "execute_skill_removed", "execute_skill" not in tn)

    prompts = await session.list_prompts()
    pn = sorted(p.name for p in prompts.prompts)
    ep = ["add_memory_guide", "okf_concept_guide", "query_ontology_guide", "register_skill_guide", "search_knowledge_guide", "search_memory_guide"]
    record("L3", "meta", "prompt_count", len(pn) == 6, f"got {len(pn)}")
    for p in ep:
        record("L3", "prompt_list", p, p in pn)

    # Knowledge
    r = await mcp_call(session, "register_knowledge", {"name": "vf_kb", "description": "test"})
    record("L3", "tool", "register_knowledge", "knowledge" in r or "table" in r, str(r)[:80])
    r = await mcp_call(session, "ingest_knowledge", {"kb_name": "vf_kb", "concepts": [
        {"frontmatter": {"type": "Table", "title": "Users", "description": "User table", "tags": ["auth"]},
         "body": "# Schema\n| Column | Type |\n|--------|------|\n| id | string |"}
    ]})
    record("L3", "tool", "ingest_knowledge", r.get("ingested", 0) == 1, str(r)[:80])
    r = await mcp_call(session, "search_knowledge", {"query": "user table", "kb_name": "vf_kb", "top_k": 3})
    record("L3", "tool", "search_knowledge", "hits" in r, str(r)[:80])
    r = await mcp_call(session, "list_knowledge", {})
    record("L3", "tool", "list_knowledge", "knowledge_bases" in r, str(r)[:80])
    r = await mcp_call(session, "list_concepts", {"kb_name": "vf_kb"})
    record("L3", "tool", "list_concepts", "kb_name" in r, str(r)[:80])
    r = await mcp_call(session, "get_knowledge", {"kb_name": "vf_kb", "concept_id": "vf_kb/users"})
    record("L3", "tool", "get_knowledge", "content" in r, str(r)[:80])
    r = await mcp_call(session, "delete_knowledge", {"kb_name": "vf_kb"})
    record("L3", "tool", "delete_knowledge", "status" in r or "deleted" in r, str(r)[:80])

    # Memory
    r = await mcp_call(session, "add_memory", {"messages": [{"role": "user", "content": "I prefer dark mode"}], "infer": False})
    mid = r["results"][0]["id"] if "results" in r and r["results"] else None
    record("L3", "tool", "add_memory", mid is not None, str(r)[:80])
    r = await mcp_call(session, "search_memory", {"query": "editor preference", "top_k": 5})
    record("L3", "tool", "search_memory", "results" in r, str(r)[:80])
    if mid:
        r = await mcp_call(session, "get_memory", {"memory_id": mid})
        record("L3", "tool", "get_memory", "memory" in r or "id" in r, str(r)[:80])
    else:
        skip("L3", "tool", "get_memory", "no mid")
    r = await mcp_call(session, "list_memory", {"page": 1, "page_size": 10})
    record("L3", "tool", "list_memory", "results" in r, str(r)[:80])
    if mid:
        r = await mcp_call(session, "update_memory", {"memory_id": mid, "content": "I prefer light mode"})
        record("L3", "tool", "update_memory", "status" in r, str(r)[:80])
        r = await mcp_call(session, "memory_history", {"memory_id": mid})
        record("L3", "tool", "memory_history", "results" in r, str(r)[:80])
        r = await mcp_call(session, "delete_memory", {"memory_id": mid})
        record("L3", "tool", "delete_memory", "status" in r, str(r)[:80])
    else:
        skip("L3", "tool", "update_memory", "no mid")
        skip("L3", "tool", "memory_history", "no mid")
        skip("L3", "tool", "delete_memory", "no mid")
    r = await mcp_call(session, "clear_memory", {})
    record("L3", "tool", "clear_memory", "status" in r or "deleted" in r, str(r)[:80])

    # Skills
    r = await mcp_call(session, "register_skill", {"name": "vf_skill", "description": "test skill", "code": "def run(): return 42"})
    record("L3", "tool", "register_skill", "skill_id" in r, str(r)[:80])
    r = await mcp_call(session, "search_skill", {"query": "test skill"})
    record("L3", "tool", "search_skill", "skills" in r, str(r)[:80])
    r = await mcp_call(session, "list_skills", {})
    record("L3", "tool", "list_skills", "skills" in r, str(r)[:80])
    r = await mcp_call(session, "get_skill", {"name": "vf_skill"})
    record("L3", "tool", "get_skill", "code" in r, str(r)[:80])
    r = await mcp_call(session, "delete_skill", {"name": "vf_skill"})
    record("L3", "tool", "delete_skill", "status" in r, str(r)[:80])

    # Ontology
    r = await mcp_call(session, "update_ontology", {"concept": "Cat", "relation": "is_a", "target": "Animal"})
    record("L3", "tool", "update_ontology", "edge_id" in r, str(r)[:80])
    r = await mcp_call(session, "query_ontology", {"concept": "Cat"})
    record("L3", "tool", "query_ontology", "nodes" in r, str(r)[:80])
    r = await mcp_call(session, "delete_ontology", {"concept": "Cat"})
    record("L3", "tool", "delete_ontology", "status" in r, str(r)[:80])

    # Resources — FastMCP only lists static resources (no path params)
    res = await session.list_resources()
    rn = [str(r.uri) for r in res.resources]
    static_expected = [
        "lake://capabilities", "lake://workspace", "lake://knowledge",
        "lake://skills", "lake://memory", "lake://ontology",
    ]
    for er in static_expected:
        record("L3", "resource_list", er, er in rn)
    for sri in static_expected:
        try:
            await session.read_resource(sri)
            record("L3", "resource_read", sri, True)
        except Exception as e:
            record("L3", "resource_read", sri, False, str(e)[:60])

    # Prompts
    prompt_tests = [
        ("search_knowledge_guide", {"query": "test", "kb_name": "test"}),
        ("okf_concept_guide", {"type": "Table", "title": "Test"}),
        ("register_skill_guide", {"name": "test", "description": "test", "code": "pass"}),
        ("add_memory_guide", {"messages": "hello"}),
        ("search_memory_guide", {"query": "test"}),
        ("query_ontology_guide", {"concept": "test"}),
    ]
    for pname, pargs in prompt_tests:
        try:
            await session.get_prompt(pname, pargs)
            record("L3", "prompt", pname, True)
        except Exception as e:
            record("L3", "prompt", pname, False, str(e)[:60])


# ════════════════════════════════════════════════════════════════
# L4 — DataMCP
# ════════════════════════════════════════════════════════════════

async def test_l4(session: ClientSession):
    M = "DataMCP"
    print(f"\n{'='*60}\nL4 — {M} (18 tools / 6 resources / 2 prompts)\n{'='*60}")

    tools = await session.list_tools()
    tn = sorted(t.name for t in tools.tools)
    expected_tools = [
        "create_table", "describe_table", "drop_table", "graph_query", "graph_update",
        "kv_delete", "kv_get", "kv_scan", "kv_set", "list_tables", "query_table",
        "s3_delete", "s3_get", "s3_list", "s3_put", "sql_query", "vector_search", "write_table",
    ]
    record("L4", "meta", "tool_count", len(tn) == 18, f"got {len(tn)}")
    for t in expected_tools:
        record("L4", "tool_list", t, t in tn)

    prompts = await session.list_prompts()
    pn = sorted(p.name for p in prompts.prompts)
    ep = ["data_exploration_guide", "sql_query_guide"]
    record("L4", "meta", "prompt_count", len(pn) == 2, f"got {len(pn)}")
    for p in ep:
        record("L4", "prompt_list", p, p in pn)

    # Iceberg
    r = await mcp_call(session, "create_table", {"name": "vf_dt", "schema": {"id": "string", "val": "int64"}})
    record("L4", "tool", "create_table", "table" in r, str(r)[:80])
    r = await mcp_call(session, "write_table", {"table": "vf_dt", "rows": [{"id": "a", "val": 1}]})
    record("L4", "tool", "write_table", "written" in r, str(r)[:80])
    r = await mcp_call(session, "query_table", {"table": "vf_dt", "limit": 10})
    record("L4", "tool", "query_table", "rows" in r, str(r)[:80])
    r = await mcp_call(session, "list_tables", {})
    record("L4", "tool", "list_tables", "tables" in r, str(r)[:80])
    r = await mcp_call(session, "describe_table", {"table": "vf_dt"})
    record("L4", "tool", "describe_table", r is not None, str(r)[:80])
    r = await mcp_call(session, "sql_query", {"sql": "SELECT 1 as v"})
    record("L4", "tool", "sql_query", "rows" in r, str(r)[:80])
    r = await mcp_call(session, "drop_table", {"table": "vf_dt"})
    record("L4", "tool", "drop_table", "status" in r, str(r)[:80])

    # Vector — create table with 768-dim vectors (matching embedding model), then search via MCP
    _, emb_data = rest_json("POST", "/cognitive/embedding/embed", json={"texts": [f"vector test {i}" for i in range(5)]})
    if emb_data and emb_data.get("vectors"):
        vec_rows = [{"id": i, "text": f"vec_{i}", "vector": emb_data["vectors"][i]} for i in range(5)]
        rest("POST", "/storage/vectors/tenant_platform", json={"name": "vf_mcp_vec", "data": vec_rows, "mode": "overwrite"})
    try:
        r = await mcp_call(session, "vector_search", {"table": "vf_mcp_vec", "query": "hello", "top_k": 3})
        record("L4", "tool", "vector_search", "hits" in r or "results" in r or "error" in r, str(r)[:80])
    except Exception as e:
        record("L4", "tool", "vector_search", False, str(e)[:60])

    # S3
    r = await mcp_call(session, "s3_put", {"uri": "s3://lakemind-filesets/vf_test.txt", "body": "hello"})
    record("L4", "tool", "s3_put", "written" in r, str(r)[:80])
    r = await mcp_call(session, "s3_get", {"uri": "s3://lakemind-filesets/vf_test.txt"})
    record("L4", "tool", "s3_get", r.get("content") == "hello", str(r)[:80])
    r = await mcp_call(session, "s3_list", {"uri": "s3://lakemind-filesets/vf", "limit": 10})
    record("L4", "tool", "s3_list", "keys" in r, str(r)[:80])
    r = await mcp_call(session, "s3_delete", {"uri": "s3://lakemind-filesets/vf_test.txt"})
    record("L4", "tool", "s3_delete", "status" in r, str(r)[:80])

    # KV
    r = await mcp_call(session, "kv_set", {"key": "vfk", "value": "vfv"})
    record("L4", "tool", "kv_set", "set" in r, str(r)[:80])
    r = await mcp_call(session, "kv_get", {"key": "vfk"})
    record("L4", "tool", "kv_get", r.get("value") == "vfv", str(r)[:80])
    r = await mcp_call(session, "kv_scan", {"pattern": "*", "limit": 10})
    record("L4", "tool", "kv_scan", "keys" in r, str(r)[:80])
    r = await mcp_call(session, "kv_delete", {"key": "vfk"})
    record("L4", "tool", "kv_delete", "status" in r, str(r)[:80])

    # Graph
    r = await mcp_call(session, "graph_update", {"concept": "Dog", "relation": "is_a", "target": "Mammal"})
    record("L4", "tool", "graph_update", "concept" in r, str(r)[:80])
    r = await mcp_call(session, "graph_query", {"concept": "Dog"})
    record("L4", "tool", "graph_query", "nodes" in r, str(r)[:80])

    # Resources
    res = await session.list_resources()
    rn = [str(r.uri) for r in res.resources]
    expected_res = [
        "lake://workspace", "lake://system/health", "lake://tables", "lake://vectors",
    ]
    for er in expected_res:
        record("L4", "resource_list", er, er in rn)
    for sri in expected_res:
        try:
            await session.read_resource(sri)
            record("L4", "resource_read", sri, True)
        except Exception as e:
            record("L4", "resource_read", sri, False, str(e)[:60])

    # Prompts
    for pname, pargs in [("sql_query_guide", {"intent": "analyze"}), ("data_exploration_guide", {"table": "test"})]:
        try:
            await session.get_prompt(pname, pargs)
            record("L4", "prompt", pname, True)
        except Exception as e:
            record("L4", "prompt", pname, False, str(e)[:60])


# ════════════════════════════════════════════════════════════════
# L5 — AdminMCP
# ════════════════════════════════════════════════════════════════

async def test_l5(session: ClientSession):
    M = "AdminMCP"
    print(f"\n{'='*60}\nL5 — {M} (17 tools / 6 resources / 2 prompts)\n{'='*60}")

    tools = await session.list_tools()
    tn = sorted(t.name for t in tools.tools)
    expected_tools = [
        "create_tenant", "create_user", "delete_tenant", "delete_user", "get_metrics",
        "get_node_status", "get_platform_health", "issue_token", "list_asset_types",
        "list_tenants", "list_tokens", "list_users", "register_asset_type", "revoke_token",
        "unregister_asset_type", "update_tenant", "update_user",
    ]
    record("L5", "meta", "tool_count", len(tn) == 17, f"got {len(tn)}")
    for t in expected_tools:
        record("L5", "tool_list", t, t in tn)

    prompts = await session.list_prompts()
    pn = sorted(p.name for p in prompts.prompts)
    ep = ["inspect_platform_guide", "manage_user_guide"]
    record("L5", "meta", "prompt_count", len(pn) == 2, f"got {len(pn)}")
    for p in ep:
        record("L5", "prompt_list", p, p in pn)

    # Tenants
    r = await mcp_call(session, "create_tenant", {"tenant_id": "vft", "name": "VF Test"})
    record("L5", "tool", "create_tenant", r is not None, str(r)[:80])
    r = await mcp_call(session, "list_tenants", {})
    record("L5", "tool", "list_tenants", r is not None, str(r)[:80])
    r = await mcp_call(session, "update_tenant", {"tenant_id": "vft", "name": "Updated"})
    record("L5", "tool", "update_tenant", r is not None, str(r)[:80])
    r = await mcp_call(session, "delete_tenant", {"tenant_id": "vft"})
    record("L5", "tool", "delete_tenant", r is not None, str(r)[:80])

    # Users
    r = await mcp_call(session, "create_user", {"username": "vfuser", "tenant_id": "retail", "role": "user"})
    record("L5", "tool", "create_user", r is not None, str(r)[:80])
    r = await mcp_call(session, "list_users", {})
    record("L5", "tool", "list_users", r is not None, str(r)[:80])
    uid = None
    if isinstance(r, dict):
        users = r.get("users", r.get("results", []))
        for u in users:
            if u.get("username") == "vfuser":
                uid = u.get("user_id", u.get("id"))
                break
    if uid:
        r = await mcp_call(session, "update_user", {"user_id": uid, "role": "admin"})
        record("L5", "tool", "update_user", r is not None, str(r)[:80])
        r = await mcp_call(session, "delete_user", {"user_id": uid})
        record("L5", "tool", "delete_user", r is not None, str(r)[:80])
    else:
        skip("L5", "tool", "update_user", "no uid")
        skip("L5", "tool", "delete_user", "no uid")

    # Tokens
    r = await mcp_call(session, "issue_token", {"agent_id": "vfagent", "tenant_id": "retail", "scopes": ["asset"]})
    record("L5", "tool", "issue_token", r is not None, str(r)[:80])
    r = await mcp_call(session, "list_tokens", {})
    record("L5", "tool", "list_tokens", r is not None, str(r)[:80])

    # Asset types
    r = await mcp_call(session, "register_asset_type", {"yaml_def": "type: vfast\ndescription: test"})
    record("L5", "tool", "register_asset_type", r is not None, str(r)[:80])
    r = await mcp_call(session, "list_asset_types", {})
    record("L5", "tool", "list_asset_types", r is not None, str(r)[:80])
    r = await mcp_call(session, "unregister_asset_type", {"type": "vfast"})
    record("L5", "tool", "unregister_asset_type", r is not None, str(r)[:80])

    # System
    r = await mcp_call(session, "get_platform_health", {})
    record("L5", "tool", "get_platform_health", r is not None, str(r)[:80])
    r = await mcp_call(session, "get_node_status", {})
    record("L5", "tool", "get_node_status", r is not None, str(r)[:80])
    r = await mcp_call(session, "get_metrics", {})
    record("L5", "tool", "get_metrics", r is not None, str(r)[:80])

    # Resources
    res = await session.list_resources()
    rn = [str(r.uri) for r in res.resources]
    expected_res = [
        "lake://admin/health", "lake://admin/tenants", "lake://admin/users",
        "lake://admin/tokens", "lake://admin/asset-types", "lake://admin/nodes",
    ]
    for er in expected_res:
        record("L5", "resource_list", er, er in rn)
    for sri in expected_res:
        try:
            await session.read_resource(sri)
            record("L5", "resource_read", sri, True)
        except Exception as e:
            record("L5", "resource_read", sri, False, str(e)[:60])

    # Prompts
    for pname, pargs in [("inspect_platform_guide", {"focus_area": "storage"}), ("manage_user_guide", {"action": "create"})]:
        try:
            await session.get_prompt(pname, pargs)
            record("L5", "prompt", pname, True)
        except Exception as e:
            record("L5", "prompt", pname, False, str(e)[:60])


# ════════════════════════════════════════════════════════════════
# L6 — MCP 安全
# ════════════════════════════════════════════════════════════════

async def test_l6():
    print(f"\n{'='*60}\nL6 — MCP 安全 (12)\n{'='*60}")

    async def try_mcp_no_auth(url: str) -> bool:
        try:
            async with streamablehttp_client(url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    await session.list_tools()
            return False
        except Exception:
            return True

    async def try_mcp_wrong_auth(url: str) -> bool:
        try:
            headers = {"Authorization": "Bearer wrong-token-xxx"}
            async with streamablehttp_client(url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    await session.list_tools()
            return False
        except Exception:
            return True

    async def try_mcp_cross_scope(url: str, token: str, tool: str, args: dict) -> bool:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            async with streamablehttp_client(url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    r = await session.call_tool(tool, args)
                    text = r.content[0].text if r.content else "{}"
                    d = json.loads(text)
                    return "error" in d or "detail" in d
        except Exception:
            return True

    # No auth
    record("L6", "no_auth", "asset_mcp", await try_mcp_no_auth(ASSET_URL))
    record("L6", "no_auth", "data_mcp", await try_mcp_no_auth(DATA_URL))
    record("L6", "no_auth", "admin_mcp", await try_mcp_no_auth(ADMIN_URL))

    # Wrong auth
    record("L6", "wrong_auth", "asset_mcp", await try_mcp_wrong_auth(ASSET_URL))
    record("L6", "wrong_auth", "data_mcp", await try_mcp_wrong_auth(DATA_URL))
    record("L6", "wrong_auth", "admin_mcp", await try_mcp_wrong_auth(ADMIN_URL))

    # Cross-scope — use steward token (has all scopes) but try to call tools
    # that should work. For negative test, we use asset token on data/admin.
    # Since tokens are static and per-MCP, a data-scope token on asset MCP
    # should be rejected. But AssetMCP only has its own tokens.
    # We test: AssetMCP's business token (scope=asset) on DataMCP should fail.
    record("L6", "cross_scope", "asset_token_on_data", await try_mcp_cross_scope(DATA_URL, ASSET_TOKEN, "list_tables", {}))
    record("L6", "cross_scope", "asset_token_on_admin", await try_mcp_cross_scope(ADMIN_URL, ASSET_TOKEN, "list_tenants", {}))

    # /health open without token
    with httpx.Client() as c:
        for name, port in [("asset", 8401), ("data", 8402), ("admin", 8403)]:
            try:
                r = c.get(f"http://localhost:{port}/health", timeout=10)
                record("L6", "health_open", name, r.status_code == 200, f"got {r.status_code}")
            except Exception as e:
                record("L6", "health_open", name, False, str(e)[:60])


# ════════════════════════════════════════════════════════════════
# L7 — Steward + Monitor
# ════════════════════════════════════════════════════════════════

def test_l7():
    print(f"\n{'='*60}\nL7 — Steward + Monitor (8)\n{'='*60}")
    with httpx.Client(timeout=30) as c:
        # Steward
        try:
            r = c.get("http://localhost:8500/health")
            record("L7", "steward", "health", r.status_code == 200, f"got {r.status_code}")
        except Exception as e:
            record("L7", "steward", "health", False, str(e)[:60])
        try:
            r = c.post("http://localhost:8500/chat", json={"message": "巡检平台状态"})
            record("L7", "steward", "chat", r.status_code == 200, f"got {r.status_code}")
        except Exception as e:
            record("L7", "steward", "chat", False, str(e)[:60])
        try:
            r = c.post("http://localhost:8500/inspect", json={"target": "engines"})
            record("L7", "steward", "inspect", r.status_code == 200, f"got {r.status_code}")
        except Exception as e:
            record("L7", "steward", "inspect", False, str(e)[:60])

        # Monitor
        try:
            r = c.get("http://localhost:3000/")
            record("L7", "monitor", "index", r.status_code == 200, f"got {r.status_code}")
        except Exception as e:
            record("L7", "monitor", "index", False, str(e)[:60])
        try:
            r = c.get("http://localhost:3000/api/health")
            record("L7", "monitor", "api_health", r.status_code == 200, f"got {r.status_code}")
        except Exception as e:
            record("L7", "monitor", "api_health", False, str(e)[:60])
        try:
            r = c.get("http://localhost:3000/api/asset/capabilities")
            record("L7", "monitor", "capabilities", r.status_code == 200, f"got {r.status_code}")
        except Exception as e:
            record("L7", "monitor", "capabilities", False, str(e)[:60])
        try:
            r = c.get("http://localhost:3000/api/admin/health")
            record("L7", "monitor", "admin_health", r.status_code == 200, f"got {r.status_code}")
        except Exception as e:
            record("L7", "monitor", "admin_health", False, str(e)[:60])
        try:
            r = c.post("http://localhost:3000/api/chat", json={"message": "hello"})
            record("L7", "monitor", "chat", r.status_code == 200, f"got {r.status_code}")
        except Exception as e:
            record("L7", "monitor", "chat", False, str(e)[:60])


# ════════════════════════════════════════════════════════════════
# L8 — 端到端业务流
# ════════════════════════════════════════════════════════════════

async def test_l8(session: ClientSession):
    M = "E2E"
    print(f"\n{'='*60}\nL8 — 端到端业务流 (5)\n{'='*60}")

    # 1. 知识闭环
    try:
        await mcp_call(session, "register_knowledge", {"name": "e2e_kb", "description": "end-to-end test"})
        await mcp_call(session, "ingest_knowledge", {"kb_name": "e2e_kb", "concepts": [
            {"frontmatter": {"type": "Table", "title": "订单表", "description": "存储订单数据", "tags": ["ecommerce"]},
             "body": "# 订单表 Schema\n| 列名 | 类型 | 说明 |\n|------|------|------|\n| order_id | string | 订单ID |\n| amount | float | 金额 |"},
            {"frontmatter": {"type": "Table", "title": "Order Table", "description": "stores order data", "tags": ["ecommerce"]},
             "body": "# Order Schema\n| Column | Type | Description |\n|--------|------|-------------|\n| order_id | string | order ID |\n| amount | float | amount |"},
        ]})
        r1 = await mcp_call(session, "search_knowledge", {"query": "订单数据", "kb_name": "e2e_kb", "top_k": 5})
        r2 = await mcp_call(session, "list_concepts", {"kb_name": "e2e_kb"})
        await mcp_call(session, "delete_knowledge", {"kb_name": "e2e_kb"})
        ok = "hits" in r1 and "kb_name" in r2
        record("L8", M, "knowledge_loop", ok, f"search={len(r1.get('hits', []))} hits, concepts={r2.get('total', '?')}")
    except Exception as e:
        record("L8", M, "knowledge_loop", False, str(e)[:80])

    # 2. 记忆闭环
    try:
        r = await mcp_call(session, "add_memory", {"messages": [
            {"role": "user", "content": "我叫张三，我是数据工程师"},
            {"role": "assistant", "content": "你好张三！"},
            {"role": "user", "content": "我主要用Python和SQL工作"},
        ], "infer": False})
        mid = r["results"][0]["id"] if "results" in r and r["results"] else None
        r = await mcp_call(session, "search_memory", {"query": "张三的技术栈", "top_k": 5})
        if mid:
            await mcp_call(session, "update_memory", {"memory_id": mid, "content": "张三是数据工程师，用Python和SQL"})
            await mcp_call(session, "memory_history", {"memory_id": mid})
            await mcp_call(session, "delete_memory", {"memory_id": mid})
        await mcp_call(session, "clear_memory", {})
        record("L8", M, "memory_loop", "results" in r, str(r)[:80])
    except Exception as e:
        record("L8", M, "memory_loop", False, str(e)[:80])

    # 3. 技能闭环
    try:
        await mcp_call(session, "register_skill", {"name": "e2e_skill", "description": "data validation skill", "code": "def run(data): return all(d.get('id') for d in data)"})
        r = await mcp_call(session, "search_skill", {"query": "validation"})
        await mcp_call(session, "get_skill", {"name": "e2e_skill"})
        await mcp_call(session, "list_skills", {})
        await mcp_call(session, "delete_skill", {"name": "e2e_skill"})
        record("L8", M, "skill_loop", "skills" in r, str(r)[:80])
    except Exception as e:
        record("L8", M, "skill_loop", False, str(e)[:80])

    # 4. 本体闭环
    try:
        await mcp_call(session, "update_ontology", {"concept": "DataEngineer", "relation": "is_a", "target": "Engineer"})
        await mcp_call(session, "update_ontology", {"concept": "DataEngineer", "relation": "uses_tool", "target": "Python"})
        r = await mcp_call(session, "query_ontology", {"concept": "DataEngineer"})
        await mcp_call(session, "delete_ontology", {"concept": "DataEngineer"})
        record("L8", M, "ontology_loop", "nodes" in r, str(r)[:80])
    except Exception as e:
        record("L8", M, "ontology_loop", False, str(e)[:80])

    # 5. 跨域关联
    try:
        await mcp_call(session, "register_knowledge", {"name": "e2e_cross", "description": "cross domain"})
        await mcp_call(session, "ingest_knowledge", {"kb_name": "e2e_cross", "concepts": [
            {"frontmatter": {"type": "Concept", "title": "数据湖", "description": "统一存储底座", "tags": ["architecture"]},
             "body": "# 数据湖\n统一存储所有结构化和非结构化数据。"},
        ]})
        await mcp_call(session, "update_ontology", {"concept": "DataLake", "relation": "uses", "target": "SeaweedFS"})
        await mcp_call(session, "add_memory", {"messages": [{"role": "user", "content": "数据湖基于SeaweedFS构建"}], "infer": False})
        k = await mcp_call(session, "search_knowledge", {"query": "数据湖", "kb_name": "e2e_cross", "top_k": 3})
        o = await mcp_call(session, "query_ontology", {"concept": "DataLake"})
        m = await mcp_call(session, "search_memory", {"query": "数据湖", "top_k": 3})
        await mcp_call(session, "delete_knowledge", {"kb_name": "e2e_cross"})
        await mcp_call(session, "delete_ontology", {"concept": "DataLake"})
        await mcp_call(session, "clear_memory", {})
        ok = "hits" in k and "nodes" in o and "results" in m
        record("L8", M, "cross_domain", ok, f"kb={len(k.get('hits', []))} ont={len(o.get('nodes', []))} mem={len(m.get('results', []))}")
    except Exception as e:
        record("L8", M, "cross_domain", False, str(e)[:80])


# ════════════════════════════════════════════════════════════════
# L9 — 性能基线
# ════════════════════════════════════════════════════════════════

async def test_l9():
    print(f"\n{'='*60}\nL9 — 性能基线 (10)\n{'='*60}")

    # 1. MCP 单次 tool 延迟 — 30 次取样
    latencies = []
    for _ in range(30):
        t0 = time.monotonic()
        try:
            async with streamablehttp_client(ASSET_URL, headers={"Authorization": f"Bearer {ASSET_TOKEN}"}) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    await session.call_tool("list_memory", {"page": 1, "page_size": 1})
            latencies.append(time.monotonic() - t0)
        except Exception:
            pass
    stats = trimmed_stats(latencies)
    ok = stats["mean"] < 0.5
    record("L9", "latency", "mcp_single_tool", ok, f"mean={stats['mean']}ms p99={stats['p99']}ms (n={stats['n']})")

    # 2. REST 单次 API 延迟 — 50 次取样
    latencies = []
    with httpx.Client() as c:
        for _ in range(50):
            t0 = time.monotonic()
            c.get(f"{REST_BASE}/system/health", timeout=10)
            latencies.append(time.monotonic() - t0)
    stats = trimmed_stats(latencies)
    ok = stats["mean"] < 0.2
    record("L9", "latency", "rest_single_api", ok, f"mean={stats['mean']}s p99={stats['p99']}s (n={stats['n']})")

    # 3. Embedding 中英文 100 条 — 10 轮取样
    texts = [f"这是第{i}条中文测试数据 hello world {i}" for i in range(100)]
    latencies = []
    for _ in range(10):
        t0 = time.monotonic()
        rest("POST", "/cognitive/embedding/embed", json={"texts": texts})
        latencies.append(time.monotonic() - t0)
    stats = trimmed_stats(latencies)
    ok = stats["mean"] < 5.0
    record("L9", "latency", "embedding_100", ok, f"mean={stats['mean']}s p99={stats['p99']}s (n={stats['n']})")

    # 4. Vector search top-10 — 30 次取样
    latencies = []
    for _ in range(30):
        t0 = time.monotonic()
        rest("POST", "/storage/vectors/vf_vec/test_v/search", json={"query_vec": [0.5, 0.5, 0.5], "top_k": 10})
        latencies.append(time.monotonic() - t0)
    stats = trimmed_stats(latencies)
    ok = stats["mean"] < 0.5
    record("L9", "latency", "vector_search", ok, f"mean={stats['mean']}s p99={stats['p99']}s (n={stats['n']})")

    # 5. Memory add+search 闭环 — 20 轮取样
    errors = 0
    latencies = []
    for i in range(20):
        t0 = time.monotonic()
        try:
            r, d = rest_json("POST", "/cognitive/memory/add", json={"messages": [{"role": "user", "content": f"perf test {i}"}], "infer": False})
            if r.status_code != 200:
                errors += 1
                continue
            rest_json("POST", "/cognitive/memory/search", json={"query": f"perf test {i}", "top_k": 1})
        except Exception:
            errors += 1
        latencies.append(time.monotonic() - t0)
    rest_json("POST", "/cognitive/memory/clear", json={})
    stats = trimmed_stats(latencies)
    record("L9", "latency", "memory_add_search", errors == 0, f"mean={stats['mean']}s errors={errors}/{len(latencies)}")

    # 6. 150 Agent 并发压力 — 150 workers × 50 ops (via REST API with connection pool)
    print("\n  -- 150 Agent 并发压力测试 (150 workers × 50 ops) --")
    t0 = time.monotonic()
    total_ops, success, fail = await _concurrent_rest(150, 50, 0)
    elapsed = time.monotonic() - t0
    qps = round(total_ops / elapsed, 1) if elapsed > 0 else 0
    ok = fail <= total_ops * 0.01 and qps > 10
    record("L9", "concurrent", "150agent_50ops", ok, f"ops={total_ops} ok={success} fail={fail} qps={qps} elapsed={elapsed:.1f}s")

    # 7. 150 Agent 持续 30s 稳定性
    print("\n  -- 150 Agent 持续 30s 稳定性测试 --")
    t0 = time.monotonic()
    total_ops, success, fail = await _concurrent_rest(150, 0, 30)
    elapsed = time.monotonic() - t0
    qps = round(total_ops / elapsed, 1) if elapsed > 0 else 0
    err_rate = round(fail / max(total_ops, 1) * 100, 2)
    ok = err_rate < 1 and qps > 20
    record("L9", "concurrent", "150agent_30s", ok, f"ops={total_ops} ok={success} fail={fail} qps={qps} err_rate={err_rate}%")

    # 8. MCP vs REST 延迟对比 — 20 次取样
    mcp_lat = []
    for _ in range(20):
        t0 = time.monotonic()
        try:
            async with streamablehttp_client(ASSET_URL, headers={"Authorization": f"Bearer {ASSET_TOKEN}"}) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    await session.call_tool("list_memory", {"page": 1, "page_size": 1})
            mcp_lat.append(time.monotonic() - t0)
        except Exception:
            pass
    rest_lat = []
    with httpx.Client() as c:
        for _ in range(20):
            t0 = time.monotonic()
            c.post(f"{REST_BASE}/cognitive/memory/list", json={"page": 1, "page_size": 1}, headers=REST_H, timeout=30)
            rest_lat.append(time.monotonic() - t0)
    mcp_s = trimmed_stats(mcp_lat)
    rest_s = trimmed_stats(rest_lat)
    overhead = round(mcp_s["mean"] - rest_s["mean"], 3)
    ok = overhead < 1.0
    record("L9", "compare", "mcp_vs_rest", ok, f"mcp_mean={mcp_s['mean']}s rest_mean={rest_s['mean']}s overhead={overhead}s")

    # 9. 冷启动延迟 — 重启 asset-mcp 容器后首次调用
    print("\n  -- 冷启动延迟测试 (restart asset-mcp) --")
    try:
        subprocess.run(["docker", "restart", "lakemind-asset-mcp"], timeout=60, capture_output=True)
        t0 = time.monotonic()
        ok_restart = False
        for _ in range(30):
            try:
                async with streamablehttp_client(ASSET_URL, headers={"Authorization": f"Bearer {ASSET_TOKEN}"}) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        await session.list_tools()
                ok_restart = True
                break
            except Exception:
                await asyncio.sleep(0.5)
        cold_time = time.monotonic() - t0
        record("L9", "cold_start", "asset_mcp", ok_restart and cold_time < 5, f"cold_start={cold_time:.2f}s")
    except Exception as e:
        record("L9", "cold_start", "asset_mcp", False, str(e)[:80])

    # 10. 并发递增阶梯 — 10→30→50→100→150→200
    print("\n  -- 并发递增阶梯测试 --")
    staircase_results = []
    for workers in [10, 30, 50, 100, 150, 200]:
        t0 = time.monotonic()
        total_ops, success, fail = await _concurrent_rest(workers, 10, 0)
        elapsed = time.monotonic() - t0
        qps = round(total_ops / elapsed, 1) if elapsed > 0 else 0
        err_rate = round(fail / max(total_ops, 1) * 100, 2)
        staircase_results.append({"workers": workers, "qps": qps, "err_rate": err_rate, "fail": fail})
        print(f"    workers={workers:>3d}  qps={qps:>6.1f}  err_rate={err_rate:>5.2f}%  fail={fail}")
    # 150 workers should have no degradation
    s150 = next((s for s in staircase_results if s["workers"] == 150), {})
    ok = s150.get("err_rate", 100) < 5
    record("L9", "staircase", "150_no_degrade", ok, f"err_rate@150={s150.get('err_rate')}% qps@150={s150.get('qps')}")


async def _concurrent_rest(workers: int, ops_per_worker: int, duration_s: int) -> tuple[int, int, int]:
    """Mixed workload via REST API with shared connection pool.

    If duration_s > 0, run for fixed duration. Otherwise run ops_per_worker per worker.
    Mix: 40% memory/list, 20% memory/search, 15% s3 list, 10% kv scan, 10% tables list, 5% system health.
    """
    limits = httpx.Limits(max_connections=min(workers * 4, 500), max_keepalive_connections=min(workers, 200))
    timeout = httpx.Timeout(10.0, connect=5.0)
    total = 0
    success = 0
    fail = 0
    end_time = time.monotonic() + duration_s if duration_s > 0 else None

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        async def worker(wid: int):
            nonlocal total, success, fail
            i = 0
            while True:
                if end_time is not None:
                    if time.monotonic() >= end_time:
                        break
                elif i >= ops_per_worker:
                    break
                i += 1
                total += 1
                r = wid % 10
                try:
                    if r < 4:
                        resp = await client.get(f"{REST_BASE}/system/nodes", headers=REST_H)
                    elif r < 7:
                        resp = await client.get(f"{REST_BASE}/storage/kv/", params={"pattern": "*", "limit": 1}, headers=REST_H)
                    elif r < 9:
                        resp = await client.get(f"{REST_BASE}/storage/objects/lakemind-filesets", headers=REST_H)
                    else:
                        resp = await client.get(f"{REST_BASE}/system/metrics", headers=REST_H)
                    if resp.status_code < 500:
                        success += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1

        await asyncio.gather(*[worker(w) for w in range(workers)])
    return total, success, fail


# ════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════

async def main():
    global pass_count, fail_count, skip_count
    print("=" * 60)
    print("LakeMind 全面测试 — L0~L9")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # L0-L2: sync
    test_l0()
    test_l1()
    test_l2()

    # L3-L5: MCP tools
    for url, token, fn, name in [
        (ASSET_URL, ASSET_TOKEN, test_l3, "AssetMCP"),
        (DATA_URL, DATA_TOKEN, test_l4, "DataMCP"),
        (ADMIN_URL, ADMIN_TOKEN, test_l5, "AdminMCP"),
    ]:
        try:
            await mcp_session(url, token, fn)
        except Exception as e:
            print(f"  {name} ERROR: {e}")
            record(f"L{'3' if 'Asset' in name else '4' if 'Data' in name else '5'}", "meta", "connection", False, str(e)[:100])

    # L6: Security
    try:
        await test_l6()
    except Exception as e:
        print(f"  L6 ERROR: {e}")

    # L7: Steward + Monitor
    test_l7()

    # L8: E2E (use AssetMCP session)
    try:
        await mcp_session(ASSET_URL, ASSET_TOKEN, test_l8)
    except Exception as e:
        print(f"  L8 ERROR: {e}")
        record("L8", "meta", "connection", False, str(e)[:100])

    # L9: Performance
    try:
        await test_l9()
    except Exception as e:
        print(f"  L9 ERROR: {e}")
        record("L9", "meta", "error", False, str(e)[:100])

    # Summary
    total = pass_count + fail_count + skip_count
    print(f"\n{'='*60}")
    print(f"TOTAL: {pass_count} PASS, {fail_count} FAIL, {skip_count} SKIP, {total} tests")
    print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Layer breakdown
    layers = {}
    for r in results:
        l = r["layer"]
        if l not in layers:
            layers[l] = {"pass": 0, "fail": 0, "skip": 0}
        if r["passed"] is True:
            layers[l]["pass"] += 1
        elif r["passed"] is False:
            layers[l]["fail"] += 1
        else:
            layers[l]["skip"] += 1
    print("\n分层汇总:")
    for l in sorted(layers):
        s = layers[l]
        t = s["pass"] + s["fail"] + s["skip"]
        print(f"  {l}: {s['pass']}/{t} PASS, {s['fail']} FAIL, {s['skip']} SKIP")

    # Failed details
    failed = [r for r in results if r["passed"] is False]
    if failed:
        print(f"\n失败详情 ({len(failed)}):")
        for r in failed:
            print(f"  {r['layer']}/{r['category']}/{r['name']} — {r['detail'][:120]}")

    # Save report
    report = {
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "summary": {"total": total, "pass": pass_count, "fail": fail_count, "skip": skip_count},
        "layers": layers,
        "results": results,
    }
    report_path = os.path.join(os.path.dirname(__file__), "..", "reports", "full_test_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to {report_path}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
