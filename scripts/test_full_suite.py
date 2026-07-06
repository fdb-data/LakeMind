"""
LakeMind 全面功能测试 — 资产面 / 数据面 / 管理面
覆盖：增删改查、批量、并发、引擎可用性、scope 隔离
"""
import json
import time
import urllib.request
import urllib.error
import concurrent.futures
import threading
import sys
import os
from datetime import datetime

ASSET_MCP = "http://localhost:8401/mcp"
DATA_MCP = "http://localhost:8402/mcp"
ADMIN_MCP = "http://localhost:8403/mcp"

TOKEN_BUSINESS = "test-business-token"
TOKEN_STEWARD = "test-steward-token"
TOKEN_MONITOR = "test-monitor-token"

results = []
lock = threading.Lock()


def mcp_call(url, token, method, params=None):
    if params is None:
        params = {}
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
        if raw.startswith("data: "):
            raw = raw[6:].strip()
        if raw.startswith("event: "):
            lines = raw.split("\n")
            for l in lines:
                if l.startswith("data: "):
                    raw = l[6:].strip()
                    break
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}


def tool_call(url, token, tool, args=None):
    return mcp_call(url, token, "tools/call", {"name": tool, "arguments": args or {}})


def resource_read(url, token, uri):
    return mcp_call(url, token, "resources/read", {"uri": uri})


def extract_text(r):
    if isinstance(r, dict) and "error" in r and "result" not in r:
        return None, r.get("error")
    try:
        c = r.get("result", {}).get("content", [])
        if c and isinstance(c, list) and c[0].get("text"):
            return c[0]["text"], None
        c2 = r.get("result", {}).get("contents", [])
        if c2 and isinstance(c2, list) and c2[0].get("text"):
            return c2[0]["text"], None
    except:
        pass
    return None, "no text"


def extract_json(r):
    text, err = extract_text(r)
    if err:
        return None, err
    if text is None:
        return None, "no text"
    try:
        return json.loads(text), None
    except:
        return text, None


def record(category, test_name, passed, detail=""):
    with lock:
        status = "PASS" if passed else "FAIL"
        results.append({"category": category, "test": test_name, "status": status, "detail": detail})
        print(f"  {status}  [{category}] {test_name}" + (f"  — {detail}" if detail and not passed else ""))


def check_error(r):
    if isinstance(r, dict) and "error" in r and "result" not in r:
        return r["error"]
    return None


# ═══════════════════════════════════════════════════════════════
# 1. 资产面测试 (AssetMCP)
# ═══════════════════════════════════════════════════════════════

def test_asset_health():
    r = mcp_call(ASSET_MCP, TOKEN_BUSINESS, "initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}
    })
    record("Asset-Health", "initialize", "result" in r)

    r = mcp_call(ASSET_MCP, TOKEN_BUSINESS, "tools/list")
    tools = r.get("result", {}).get("tools", [])
    record("Asset-Health", f"tools/list ({len(tools)} tools)", len(tools) == 11)

    r = mcp_call(ASSET_MCP, TOKEN_BUSINESS, "resources/list")
    res = r.get("result", {}).get("resources", [])
    record("Asset-Health", f"resources/list ({len(res)} resources)", len(res) >= 6)


def test_knowledge():
    cat = "Asset-Knowledge"
    kb_name = f"test_kb_{int(time.time())}"

    # register
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "register_knowledge", {"name": kb_name, "description": "test kb"})
    err = check_error(r)
    record(cat, "register_knowledge", err is None or "exists" in str(err).lower(), str(err) if err else "")

    # ingest
    docs = [
        {"title": "Python Guide", "content": "Python is a high-level programming language for general-purpose programming."},
        {"title": "Java Guide", "content": "Java is a class-based object-oriented programming language."},
        {"title": "Rust Guide", "content": "Rust is a systems programming language focused on safety and performance."},
    ]
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "ingest_knowledge", {"kb": kb_name, "documents": docs})
    err = check_error(r)
    record(cat, "ingest_knowledge (3 docs)", err is None, str(err) if err else "")

    # search
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "search_knowledge", {"kb": kb_name, "query": "programming language", "top_k": 3})
    data, err = extract_json(r)
    passed = err is None and data is not None
    if passed and isinstance(data, dict):
        passed = len(data.get("results", data.get("rows", []))) > 0
    record(cat, "search_knowledge (semantic)", passed, str(err) if err else f"found results")

    # search with filter
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "search_knowledge", {"kb": kb_name, "query": "safety", "top_k": 1})
    data, err = extract_json(r)
    record(cat, "search_knowledge (top_k=1)", err is None, str(err) if err else "")


def test_knowledge_batch():
    cat = "Asset-Knowledge-Batch"
    kb_name = f"batch_kb_{int(time.time())}"

    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "register_knowledge", {"name": kb_name, "description": "batch test"})
    docs = [{"title": f"doc_{i}", "content": f"Document number {i} about topic {i % 5}. Content for testing batch ingest."} for i in range(50)]
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "ingest_knowledge", {"kb": kb_name, "documents": docs})
    err = check_error(r)
    record(cat, "batch ingest (50 docs)", err is None, str(err) if err else "")

    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "search_knowledge", {"kb": kb_name, "query": "topic 3", "top_k": 10})
    data, err = extract_json(r)
    record(cat, "batch search after 50 docs", err is None, str(err) if err else "")


def test_knowledge_concurrent():
    cat = "Asset-Knowledge-Concurrent"
    kb_name = f"conc_kb_{int(time.time())}"
    tool_call(ASSET_MCP, TOKEN_BUSINESS, "register_knowledge", {"name": kb_name, "description": "concurrent test"})

    def do_search(idx):
        r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "search_knowledge", {"kb": kb_name, "query": f"topic {idx}", "top_k": 5})
        return check_error(r) is None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(do_search, i) for i in range(50)]
        passed = all(f.result() for f in futures)
    record(cat, "50 concurrent searches (20 workers)", passed, "")


def test_skill():
    cat = "Asset-Skill"

    # search (empty ok)
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "search_skill", {"query": "data processing"})
    err = check_error(r)
    record(cat, "search_skill", err is None, str(err) if err else "")

    # register
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "register_skill", {
        "name": f"test_skill_{int(time.time())}",
        "description": "A test skill for verification",
        "code": "def run(inputs): return {'result': inputs['value'] * 2}",
        "version": "1.0.0",
    })
    err = check_error(r)
    record(cat, "register_skill", err is None or "exists" in str(err).lower(), str(err) if err else "")

    # search after register
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "search_skill", {"query": "verification"})
    data, err = extract_json(r)
    record(cat, "search_skill after register", err is None, str(err) if err else "")


def test_memory():
    cat = "Asset-Memory"

    # remember (short-term, with TTL)
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "remember", {"content": "The user likes Python", "context": "preference", "ttl": 300})
    err = check_error(r)
    record(cat, "remember (short-term TTL)", err is None, str(err) if err else "")

    # remember (long-term, no TTL)
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "remember", {"content": "Project uses PostgreSQL for metadata", "context": "architecture", "kind": "experience"})
    err = check_error(r)
    record(cat, "remember (long-term)", err is None, str(err) if err else "")

    # recall
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "recall", {"query": "Python preference", "limit": 5})
    data, err = extract_json(r)
    record(cat, "recall", err is None, str(err) if err else "")

    # recall with kind filter
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "recall", {"query": "database", "limit": 5, "kind": "experience"})
    err = check_error(r)
    record(cat, "recall (kind=experience)", err is None, str(err) if err else "")

    # forget
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "forget", {"query": "Python preference"})
    err = check_error(r)
    record(cat, "forget", err is None, str(err) if err else "")


def test_memory_concurrent():
    cat = "Asset-Memory-Concurrent"

    def do_remember(idx):
        r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "remember", {"content": f"concurrent fact {idx}", "context": "test"})
        return check_error(r) is None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(do_remember, i) for i in range(30)]
        passed = all(f.result() for f in futures)
    record(cat, "30 concurrent remember (20 workers)", passed, "")

    def do_recall(idx):
        r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "recall", {"query": f"fact {idx}", "limit": 3})
        return check_error(r) is None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(do_recall, i) for i in range(30)]
        passed = all(f.result() for f in futures)
    record(cat, "30 concurrent recall (20 workers)", passed, "")


def test_ontology():
    cat = "Asset-Ontology"

    # update (add concept)
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "update_ontology", {
        "concept": "ProgrammingLanguage",
        "relation": "subtype_of",
        "target": "Language",
    })
    err = check_error(r)
    record(cat, "update_ontology (add relation)", err is None, str(err) if err else "")

    # query
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "query_ontology", {"concept": "ProgrammingLanguage"})
    data, err = extract_json(r)
    record(cat, "query_ontology", err is None, str(err) if err else "")

    # query with relation
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "query_ontology", {"concept": "ProgrammingLanguage", "relation": "subtype_of"})
    err = check_error(r)
    record(cat, "query_ontology (with relation)", err is None, str(err) if err else "")

    # add more
    r = tool_call(ASSET_MCP, TOKEN_BUSINESS, "update_ontology", {
        "concept": "Python",
        "relation": "instance_of",
        "target": "ProgrammingLanguage",
    })
    err = check_error(r)
    record(cat, "update_ontology (second relation)", err is None, str(err) if err else "")


def test_asset_resources():
    cat = "Asset-Resources"

    for uri in ["lake://capabilities", "lake://workspace", "lake://system/health",
                "lake://knowledge", "lake://skills", "lake://memory", "lake://ontology"]:
        r = resource_read(ASSET_MCP, TOKEN_BUSINESS, uri)
        err = check_error(r)
        record(cat, f"read {uri}", err is None, str(err) if err else "")


# ═══════════════════════════════════════════════════════════════
# 2. 数据面测试 (DataMCP)
# ═══════════════════════════════════════════════════════════════

def test_data_health():
    cat = "Data-Health"
    r = mcp_call(DATA_MCP, TOKEN_STEWARD, "tools/list")
    tools = r.get("result", {}).get("tools", [])
    record(cat, f"tools/list ({len(tools)} tools)", len(tools) == 13, f"got {len(tools)}")


def test_data_iceberg():
    cat = "Data-Iceberg"
    tbl = f"verify_{int(time.time())}"

    # create_table
    r = tool_call(DATA_MCP, TOKEN_STEWARD, "data_create_table", {
        "name": tbl,
        "schema": [{"name": "id", "type": "int64"}, {"name": "name", "type": "string"}, {"name": "value", "type": "double"}],
    })
    err = check_error(r)
    record(cat, "data_create_table", err is None, str(err) if err else "")

    # write
    r = tool_call(DATA_MCP, TOKEN_STEWARD, "data_write", {
        "table": tbl,
        "rows": [{"id": 1, "name": "alpha", "value": 10.5}, {"id": 2, "name": "beta", "value": 20.3}, {"id": 3, "name": "gamma", "value": 30.7}],
        "mode": "append",
    })
    err = check_error(r)
    record(cat, "data_write (3 rows)", err is None, str(err) if err else "")

    # query
    r = tool_call(DATA_MCP, TOKEN_STEWARD, "data_query", {"table": tbl, "limit": 10})
    data, err = extract_json(r)
    record(cat, "data_query", err is None, str(err) if err else "")

    # list_tables
    r = tool_call(DATA_MCP, TOKEN_STEWARD, "data_list_tables")
    data, err = extract_json(r)
    record(cat, "data_list_tables", err is None, str(err) if err else "")

    # describe
    r = tool_call(DATA_MCP, TOKEN_STEWARD, "data_describe", {"table": tbl})
    err = check_error(r)
    record(cat, "data_describe", err is None, str(err) if err else "")


def test_data_duckdb():
    cat = "Data-DuckDB"
    r = tool_call(DATA_MCP, TOKEN_STEWARD, "data_sql", {"sql": "SELECT 1 as test_val, 'hello' as msg"})
    data, err = extract_json(r)
    record(cat, "data_sql (SELECT literal)", err is None, str(err) if err else "")


def test_data_lancedb():
    cat = "Data-LanceDB"
    r = tool_call(DATA_MCP, TOKEN_STEWARD, "lance_query", {"table": "knowledge", "query": "test", "top_k": 3})
    err = check_error(r)
    record(cat, "lance_query", err is None, str(err) if err else "")


def test_data_s3():
    cat = "Data-S3"
    test_uri = f"s3://lakemind-filesets/test_{int(time.time())}.txt"
    test_body = b"Hello from LakeMind test"

    r = tool_call(DATA_MCP, TOKEN_STEWARD, "s3_put", {"uri": test_uri, "body": test_body.decode()})
    err = check_error(r)
    record(cat, "s3_put", err is None, str(err) if err else "")

    r = tool_call(DATA_MCP, TOKEN_STEWARD, "s3_get", {"uri": test_uri})
    err = check_error(r)
    record(cat, "s3_get", err is None, str(err) if err else "")


def test_data_kv():
    cat = "Data-Dragonfly"
    key = f"test:{int(time.time())}"

    r = tool_call(DATA_MCP, TOKEN_STEWARD, "kv_set", {"key": key, "value": "test_value", "ttl": 60})
    err = check_error(r)
    record(cat, "kv_set (with TTL)", err is None, str(err) if err else "")

    r = tool_call(DATA_MCP, TOKEN_STEWARD, "kv_get", {"key": key})
    data, err = extract_json(r)
    record(cat, "kv_get", err is None, str(err) if err else "")


def test_data_graph():
    cat = "Data-Graph"
    r = tool_call(DATA_MCP, TOKEN_STEWARD, "graph_query", {"cypher": "MATCH (n) RETURN count(n) as cnt"})
    err = check_error(r)
    record(cat, "graph_query", err is None, str(err) if err else "")

    r = tool_call(DATA_MCP, TOKEN_STEWARD, "graph_update", {"cypher": "CREATE (n:TestNode {name: 'verify'})"})
    err = check_error(r)
    record(cat, "graph_update", err is None, str(err) if err else "")


def test_data_concurrent():
    cat = "Data-Concurrent"

    def do_kv(idx):
        k = f"conc:{idx}:{int(time.time())}"
        r1 = tool_call(DATA_MCP, TOKEN_STEWARD, "kv_set", {"key": k, "value": f"val_{idx}"})
        r2 = tool_call(DATA_MCP, TOKEN_STEWARD, "kv_get", {"key": k})
        return check_error(r1) is None and check_error(r2) is None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(do_kv, i) for i in range(50)]
        passed = all(f.result() for f in futures)
    record(cat, "50 concurrent kv set+get (20 workers)", passed, "")


# ═══════════════════════════════════════════════════════════════
# 3. 管理面测试 (AdminMCP)
# ═══════════════════════════════════════════════════════════════

def test_admin_health():
    cat = "Admin-Health"
    r = mcp_call(ADMIN_MCP, TOKEN_STEWARD, "tools/list")
    tools = r.get("result", {}).get("tools", [])
    record(cat, f"tools/list ({len(tools)} tools)", len(tools) == 15, f"got {len(tools)}")


def test_admin_tenant():
    cat = "Admin-Tenant"
    tid = f"verify_t_{int(time.time())}"

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "create_tenant", {"tenant_id": tid, "name": "Verify Tenant"})
    err = check_error(r)
    record(cat, "create_tenant", err is None, str(err) if err else "")

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "list_tenants")
    data, err = extract_json(r)
    record(cat, "list_tenants", err is None, str(err) if err else "")

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "update_tenant", {"tenant_id": tid, "name": "Updated Tenant"})
    err = check_error(r)
    record(cat, "update_tenant", err is None, str(err) if err else "")

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "delete_tenant", {"tenant_id": tid})
    err = check_error(r)
    record(cat, "delete_tenant", err is None, str(err) if err else "")


def test_admin_user():
    cat = "Admin-User"
    ts = int(time.time())

    # ensure tenant exists
    tool_call(ADMIN_MCP, TOKEN_STEWARD, "create_tenant", {"tenant_id": "test_tenant", "name": "Test Tenant"})

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "create_user", {"username": f"verify_u_{ts}", "tenant_id": "test_tenant", "role": "user"})
    data, err = extract_json(r)
    uid = None
    if data and isinstance(data, dict):
        uid = data.get("user_id") or data.get("id")
    if not uid and not err:
        text, _ = extract_text(r)
        if text:
            try:
                d2 = json.loads(text)
                uid = d2.get("user_id") or d2.get("id")
            except:
                pass
    record(cat, "create_user", uid is not None or err is None, str(err) if err else f"uid={uid}")

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "list_users")
    data, err = extract_json(r)
    record(cat, "list_users", err is None, str(err) if err else "")

    if uid:
        r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "update_user", {"user_id": uid, "role": "admin"})
        err = check_error(r)
        record(cat, "update_user", err is None, str(err) if err else "")

        r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "delete_user", {"user_id": uid})
        err = check_error(r)
        record(cat, "delete_user", err is None, str(err) if err else "")
    else:
        record(cat, "update_user", False, "no user_id from create")
        record(cat, "delete_user", False, "no user_id from create")


def test_admin_token():
    cat = "Admin-Token"
    ts = int(time.time())

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "issue_token", {"agent_id": f"verify_agent_{ts}", "tenant_id": "platform", "scopes": ["asset"]})
    data, err = extract_json(r)
    tok = None
    if data and isinstance(data, dict):
        tok = data.get("token")
    record(cat, "issue_token", tok is not None, str(err) if err else "")

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "list_tokens")
    data, err = extract_json(r)
    record(cat, "list_tokens", err is None, str(err) if err else "")

    if tok:
        r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "revoke_token", {"token": tok})
        err = check_error(r)
        record(cat, "revoke_token", err is None, str(err) if err else "")
    else:
        record(cat, "revoke_token", False, "no token from issue")


def test_admin_asset_type():
    cat = "Admin-AssetType"
    yaml_def = """type: verify_custom
description: "verify custom asset"
resource_root: "lake://verify_custom"
capabilities: [search]
storage:
  vector:
    engine: lancedb
    schema:
      id: string
      content: string
      vector: float32[768]
operations:
  search:
    engine: vector_topk
    params: [query, top_k=5]
"""

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "register_asset_type", {"yaml": yaml_def})
    err = check_error(r)
    record(cat, "register_asset_type", err is None, str(err) if err else "")

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "unregister_asset_type", {"type": "verify_custom"})
    err = check_error(r)
    record(cat, "unregister_asset_type", err is None, str(err) if err else "")


def test_admin_platform():
    cat = "Admin-Platform"
    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "get_platform_health")
    data, err = extract_json(r)
    record(cat, "get_platform_health", err is None, str(err) if err else "")

    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "get_node_status")
    err = check_error(r)
    record(cat, "get_node_status", err is None, str(err) if err else "")


def test_scope_isolation():
    cat = "Scope-Isolation"

    # business token (asset only) on DataMCP → should fail
    r = tool_call(DATA_MCP, TOKEN_BUSINESS, "data_list_tables")
    err = check_error(r)
    record(cat, "business token rejected on DataMCP", err is not None, "unexpectedly allowed" if err is None else "correctly rejected")

    # business token on AdminMCP → should fail
    r = tool_call(ADMIN_MCP, TOKEN_BUSINESS, "list_tenants")
    err = check_error(r)
    record(cat, "business token rejected on AdminMCP", err is not None, "unexpectedly allowed" if err is None else "correctly rejected")

    # monitor token (asset only) on DataMCP → should fail
    r = tool_call(DATA_MCP, TOKEN_MONITOR, "data_list_tables")
    err = check_error(r)
    record(cat, "monitor token rejected on DataMCP", err is not None, "unexpectedly allowed" if err is None else "correctly rejected")

    # steward token on AssetMCP → should work
    r = tool_call(ASSET_MCP, TOKEN_STEWARD, "search_knowledge", {"kb": "test", "query": "x"})
    err = check_error(r)
    record(cat, "steward token allowed on AssetMCP", err is None or "not found" in str(err).lower(), str(err) if err else "")


def test_cross_mcp():
    cat = "Cross-MCP"

    # AdminMCP issue token → use on AssetMCP
    # NOTE: MVP limitation — dynamic tokens stored in PG are not yet shared across MCPs.
    # Each MCP validates tokens against its own config.yaml static list.
    # This is a known limitation, not a bug. Test documents the behavior.
    ts = int(time.time())
    tool_call(ADMIN_MCP, TOKEN_STEWARD, "create_tenant", {"tenant_id": "test_tenant", "name": "Test Tenant"})
    r = tool_call(ADMIN_MCP, TOKEN_STEWARD, "issue_token", {"agent_id": f"cross_{ts}", "tenant_id": "test_tenant", "scopes": ["asset"]})
    data, err = extract_json(r)
    tok = data.get("token") if data and isinstance(data, dict) else None

    if tok:
        r = tool_call(ASSET_MCP, tok, "recall", {"query": "test", "limit": 1})
        err = check_error(r)
        # Expected: 401 because AssetMCP only knows static tokens from config.yaml
        # This is a known MVP limitation — dynamic token sharing is a future enhancement
        record(cat, "AdminMCP-issued token on AssetMCP (MVP: static tokens only)", err is not None,
               "correctly rejected (MVP limitation: dynamic token sharing not yet implemented)" if err else "unexpectedly allowed")
        tool_call(ADMIN_MCP, TOKEN_STEWARD, "revoke_token", {"token": tok})
    else:
        record(cat, "AdminMCP-issued token on AssetMCP (MVP: static tokens only)", False, "no token issued")

    # Steward chat → routes to MCPs
    try:
        body = json.dumps({"message": "platform health"}).encode()
        req = urllib.request.Request("http://localhost:8500/chat", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            r = json.loads(resp.read().decode())
        record(cat, "Steward chat → MCP routing", "reply" in r, str(r.get("error", "")))
    except Exception as e:
        record(cat, "Steward chat → MCP routing", False, str(e))

    # Steward inspect
    try:
        req = urllib.request.Request("http://localhost:8500/inspect", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            r = json.loads(resp.read().decode())
        record(cat, "Steward inspect workflow", "health" in r or "report" in r, str(r))
    except Exception as e:
        record(cat, "Steward inspect workflow", False, str(e))


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("LakeMind Full Functional Test Suite")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    print("\n--- 1. AssetMCP: Health ---")
    test_asset_health()

    print("\n--- 2. AssetMCP: Knowledge (CRUD) ---")
    test_knowledge()

    print("\n--- 3. AssetMCP: Knowledge (Batch) ---")
    test_knowledge_batch()

    print("\n--- 4. AssetMCP: Knowledge (Concurrent) ---")
    test_knowledge_concurrent()

    print("\n--- 5. AssetMCP: Skill (CRUD) ---")
    test_skill()

    print("\n--- 6. AssetMCP: Memory (CRUD) ---")
    test_memory()

    print("\n--- 7. AssetMCP: Memory (Concurrent) ---")
    test_memory_concurrent()

    print("\n--- 8. AssetMCP: Ontology (CRUD) ---")
    test_ontology()

    print("\n--- 9. AssetMCP: Resources ---")
    test_asset_resources()

    print("\n--- 10. DataMCP: Health ---")
    test_data_health()

    print("\n--- 11. DataMCP: Iceberg (create/write/query/list/describe) ---")
    test_data_iceberg()

    print("\n--- 12. DataMCP: DuckDB (SQL) ---")
    test_data_duckdb()

    print("\n--- 13. DataMCP: LanceDB (vector) ---")
    test_data_lancedb()

    print("\n--- 14. DataMCP: S3 (put/get) ---")
    test_data_s3()

    print("\n--- 15. DataMCP: Dragonfly (kv set/get) ---")
    test_data_kv()

    print("\n--- 16. DataMCP: Graph (query/update) ---")
    test_data_graph()

    print("\n--- 17. DataMCP: Concurrent ---")
    test_data_concurrent()

    print("\n--- 18. AdminMCP: Health ---")
    test_admin_health()

    print("\n--- 19. AdminMCP: Tenant (CRUD) ---")
    test_admin_tenant()

    print("\n--- 20. AdminMCP: User (CRUD) ---")
    test_admin_user()

    print("\n--- 21. AdminMCP: Token (issue/list/revoke) ---")
    test_admin_token()

    print("\n--- 22. AdminMCP: Asset Type (register/unregister) ---")
    test_admin_asset_type()

    print("\n--- 23. AdminMCP: Platform (health/status) ---")
    test_admin_platform()

    print("\n--- 24. Scope Isolation ---")
    test_scope_isolation()

    print("\n--- 25. Cross-MCP Integration ---")
    test_cross_mcp()

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    print("\n" + "=" * 70)
    print(f"TOTAL: {total}  |  PASS: {passed}  |  FAIL: {failed}")
    print("=" * 70)

    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  FAIL  [{r['category']}] {r['test']}  — {r['detail']}")

    # Save JSON for report generation
    report_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "test_results.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "total": total, "passed": passed, "failed": failed, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {report_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
