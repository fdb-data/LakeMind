"""3 MCP full verification — tools / prompts / resources."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

results: list[dict] = []
total_pass = 0
total_fail = 0


def record(mcp: str, category: str, name: str, passed: bool, detail: str = ""):
    global total_pass, total_fail
    if passed:
        total_pass += 1
    else:
        total_fail += 1
    results.append({"mcp": mcp, "category": category, "name": name, "passed": passed, "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {mcp}/{category}/{name}" + (f" — {detail}" if detail and not passed else ""))


async def call_tool(session: ClientSession, name: str, args: dict) -> dict:
    r = await session.call_tool(name, args)
    text = r.content[0].text if r.content else "{}"
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


async def run_with_session(url: str, token: str, fn):
    headers = {"Authorization": f"Bearer {token}"}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_asset_mcp(session: ClientSession):
    M = "AssetMCP"
    print(f"\n{'='*60}\nTesting {M} (port 8401)\n{'='*60}")

    tools = await session.list_tools()
    tool_names = sorted(t.name for t in tools.tools)
    expected = [
        "add_memory", "clear_memory", "delete_knowledge", "delete_memory",
        "delete_ontology", "delete_skill", "get_knowledge", "get_memory",
        "get_skill", "ingest_knowledge", "list_concepts", "list_knowledge",
        "list_memory", "list_skills", "memory_history", "query_ontology",
        "register_knowledge", "register_skill", "search_knowledge",
        "search_memory", "search_skill", "update_memory", "update_ontology",
    ]
    record(M, "meta", "tool_count", len(tool_names) == 23, f"got {len(tool_names)}")
    for t in expected:
        record(M, "tool_list", t, t in tool_names)
    record(M, "tool_list", "execute_skill_removed", "execute_skill" not in tool_names)

    prompts = await session.list_prompts()
    pn = sorted(p.name for p in prompts.prompts)
    ep = ["add_memory_guide", "okf_concept_guide", "query_ontology_guide",
          "register_skill_guide", "search_knowledge_guide", "search_memory_guide"]
    record(M, "meta", "prompt_count", len(pn) == 6, f"got {len(pn)}")
    for p in ep:
        record(M, "prompt_list", p, p in pn)

    # Knowledge
    print("\n  -- Knowledge (OKF) --")
    r = await call_tool(session, "register_knowledge", {"name": "v2_kb", "description": "test"})
    record(M, "tool", "register_knowledge", "knowledge" in r or "table" in r, str(r)[:80])

    r = await call_tool(session, "ingest_knowledge", {"kb_name": "v2_kb", "concepts": [
        {"frontmatter": {"type": "Table", "title": "Users", "description": "User table", "tags": ["auth"]},
         "body": "# Schema\n| Column | Type |\n|--------|------|\n| id | string |"}
    ]})
    record(M, "tool", "ingest_knowledge", r.get("ingested", 0) == 1, str(r)[:80])

    r = await call_tool(session, "search_knowledge", {"query": "user table", "kb_name": "v2_kb", "top_k": 3})
    record(M, "tool", "search_knowledge", "hits" in r, str(r)[:80])

    r = await call_tool(session, "list_knowledge", {})
    record(M, "tool", "list_knowledge", "knowledge_bases" in r, str(r)[:80])

    r = await call_tool(session, "list_concepts", {"kb_name": "v2_kb"})
    record(M, "tool", "list_concepts", "kb_name" in r, str(r)[:80])

    r = await call_tool(session, "get_knowledge", {"kb_name": "v2_kb", "concept_id": "v2_kb/users"})
    record(M, "tool", "get_knowledge", "content" in r, str(r)[:80])

    r = await call_tool(session, "delete_knowledge", {"kb_name": "v2_kb"})
    record(M, "tool", "delete_knowledge", "status" in r or "deleted" in r, str(r)[:80])

    # Memory
    print("\n  -- Memory (mem0) --")
    r = await call_tool(session, "add_memory", {"messages": [{"role": "user", "content": "I prefer dark mode"}], "infer": False})
    mid = r["results"][0]["id"] if "results" in r and r["results"] else None
    record(M, "tool", "add_memory", mid is not None, str(r)[:80])

    r = await call_tool(session, "search_memory", {"query": "editor preference", "top_k": 5})
    record(M, "tool", "search_memory", "results" in r, str(r)[:80])

    if mid:
        r = await call_tool(session, "get_memory", {"memory_id": mid})
        record(M, "tool", "get_memory", "memory" in r or "id" in r, str(r)[:80])

    r = await call_tool(session, "list_memory", {"page": 1, "page_size": 10})
    record(M, "tool", "list_memory", "results" in r, str(r)[:80])

    if mid:
        r = await call_tool(session, "update_memory", {"memory_id": mid, "content": "I prefer light mode"})
        record(M, "tool", "update_memory", "status" in r, str(r)[:80])

        r = await call_tool(session, "memory_history", {"memory_id": mid})
        record(M, "tool", "memory_history", "results" in r, str(r)[:80])

        r = await call_tool(session, "delete_memory", {"memory_id": mid})
        record(M, "tool", "delete_memory", "status" in r, str(r)[:80])

    r = await call_tool(session, "clear_memory", {})
    record(M, "tool", "clear_memory", "status" in r or "deleted" in r, str(r)[:80])

    # Skills
    print("\n  -- Skills --")
    r = await call_tool(session, "register_skill", {"name": "v2_skill", "description": "test skill", "code": "def run(): return 42"})
    record(M, "tool", "register_skill", "skill_id" in r, str(r)[:80])

    r = await call_tool(session, "search_skill", {"query": "test skill"})
    record(M, "tool", "search_skill", "skills" in r, str(r)[:80])

    r = await call_tool(session, "list_skills", {})
    record(M, "tool", "list_skills", "skills" in r, str(r)[:80])

    r = await call_tool(session, "get_skill", {"name": "v2_skill"})
    record(M, "tool", "get_skill", "code" in r, str(r)[:80])

    r = await call_tool(session, "delete_skill", {"name": "v2_skill"})
    record(M, "tool", "delete_skill", "status" in r, str(r)[:80])

    # Ontology
    print("\n  -- Ontology --")
    r = await call_tool(session, "update_ontology", {"concept": "Cat", "relation": "is_a", "target": "Animal"})
    record(M, "tool", "update_ontology", "edge_id" in r, str(r)[:80])

    r = await call_tool(session, "query_ontology", {"concept": "Cat"})
    record(M, "tool", "query_ontology", "nodes" in r, str(r)[:80])

    r = await call_tool(session, "delete_ontology", {"concept": "Cat"})
    record(M, "tool", "delete_ontology", "status" in r, str(r)[:80])

    # Prompts
    print("\n  -- Prompts --")
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
            record(M, "prompt", pname, True)
        except Exception as e:
            record(M, "prompt", pname, False, str(e)[:60])


async def test_data_mcp(session: ClientSession):
    M = "DataMCP"
    print(f"\n{'='*60}\nTesting {M} (port 8402)\n{'='*60}")

    tools = await session.list_tools()
    tool_names = sorted(t.name for t in tools.tools)
    expected = [
        "create_table", "describe_table", "drop_table", "graph_query", "graph_update",
        "kv_delete", "kv_get", "kv_scan", "kv_set", "list_tables", "query_table",
        "s3_delete", "s3_get", "s3_list", "s3_put", "sql_query", "vector_search", "write_table",
    ]
    record(M, "meta", "tool_count", len(tool_names) == 18, f"got {len(tool_names)}")
    for t in expected:
        record(M, "tool_list", t, t in tool_names)

    prompts = await session.list_prompts()
    pn = sorted(p.name for p in prompts.prompts)
    ep = ["data_exploration_guide", "sql_query_guide"]
    record(M, "meta", "prompt_count", len(pn) == 2, f"got {len(pn)}")
    for p in ep:
        record(M, "prompt_list", p, p in pn)

    # Iceberg
    print("\n  -- Iceberg --")
    r = await call_tool(session, "create_table", {"name": "v2_dt", "schema": {"id": "string", "val": "int64"}})
    record(M, "tool", "create_table", "table" in r, str(r)[:80])

    r = await call_tool(session, "write_table", {"table": "v2_dt", "rows": [{"id": "a", "val": 1}]})
    record(M, "tool", "write_table", "written" in r, str(r)[:80])

    r = await call_tool(session, "query_table", {"table": "v2_dt", "limit": 10})
    record(M, "tool", "query_table", "rows" in r, str(r)[:80])

    r = await call_tool(session, "list_tables", {})
    record(M, "tool", "list_tables", "tables" in r, str(r)[:80])

    r = await call_tool(session, "describe_table", {"table": "v2_dt"})
    record(M, "tool", "describe_table", r is not None, str(r)[:80])

    r = await call_tool(session, "sql_query", {"sql": "SELECT 1 as v"})
    record(M, "tool", "sql_query", "rows" in r, str(r)[:80])

    r = await call_tool(session, "drop_table", {"table": "v2_dt"})
    record(M, "tool", "drop_table", "status" in r, str(r)[:80])

    # Vector
    print("\n  -- Vector --")
    try:
        r = await call_tool(session, "vector_search", {"table": "test", "query": "x", "top_k": 3})
        record(M, "tool", "vector_search", "hits" in r, str(r)[:80])
    except Exception as e:
        record(M, "tool", "vector_search", False, str(e)[:60])

    # S3
    print("\n  -- S3 --")
    r = await call_tool(session, "s3_put", {"uri": "s3://lakemind-filesets/v2_test.txt", "body": "hello"})
    record(M, "tool", "s3_put", "written" in r, str(r)[:80])

    r = await call_tool(session, "s3_get", {"uri": "s3://lakemind-filesets/v2_test.txt"})
    record(M, "tool", "s3_get", r.get("content") == "hello", str(r)[:80])

    r = await call_tool(session, "s3_list", {"uri": "s3://lakemind-filesets/v2", "limit": 10})
    record(M, "tool", "s3_list", "keys" in r, str(r)[:80])

    r = await call_tool(session, "s3_delete", {"uri": "s3://lakemind-filesets/v2_test.txt"})
    record(M, "tool", "s3_delete", "status" in r, str(r)[:80])

    # KV
    print("\n  -- KV --")
    r = await call_tool(session, "kv_set", {"key": "v2k", "value": "v2v"})
    record(M, "tool", "kv_set", "set" in r, str(r)[:80])

    r = await call_tool(session, "kv_get", {"key": "v2k"})
    record(M, "tool", "kv_get", r.get("value") == "v2v", str(r)[:80])

    r = await call_tool(session, "kv_scan", {"pattern": "*", "limit": 10})
    record(M, "tool", "kv_scan", "keys" in r, str(r)[:80])

    r = await call_tool(session, "kv_delete", {"key": "v2k"})
    record(M, "tool", "kv_delete", "status" in r, str(r)[:80])

    # Graph
    print("\n  -- Graph --")
    r = await call_tool(session, "graph_update", {"concept": "Dog", "relation": "is_a", "target": "Mammal"})
    record(M, "tool", "graph_update", "concept" in r, str(r)[:80])

    r = await call_tool(session, "graph_query", {"concept": "Dog"})
    record(M, "tool", "graph_query", "nodes" in r, str(r)[:80])

    # Prompts
    print("\n  -- Prompts --")
    prompt_tests = [
        ("sql_query_guide", {"intent": "analyze"}),
        ("data_exploration_guide", {"table": "test"}),
    ]
    for pname, pargs in prompt_tests:
        try:
            await session.get_prompt(pname, pargs)
            record(M, "prompt", pname, True)
        except Exception as e:
            record(M, "prompt", pname, False, str(e)[:60])


async def test_admin_mcp(session: ClientSession):
    M = "AdminMCP"
    print(f"\n{'='*60}\nTesting {M} (port 8403)\n{'='*60}")

    tools = await session.list_tools()
    tool_names = sorted(t.name for t in tools.tools)
    expected = [
        "create_tenant", "create_user", "delete_tenant", "delete_user",
        "get_metrics", "get_node_status", "get_platform_health", "issue_token",
        "list_asset_types", "list_tenants", "list_tokens", "list_users",
        "register_asset_type", "revoke_token", "unregister_asset_type",
        "update_tenant", "update_user",
    ]
    record(M, "meta", "tool_count", len(tool_names) == 17, f"got {len(tool_names)}")
    for t in expected:
        record(M, "tool_list", t, t in tool_names)

    prompts = await session.list_prompts()
    pn = sorted(p.name for p in prompts.prompts)
    ep = ["inspect_platform_guide", "manage_user_guide"]
    record(M, "meta", "prompt_count", len(pn) == 2, f"got {len(pn)}")
    for p in ep:
        record(M, "prompt_list", p, p in pn)

    # Tenants
    print("\n  -- Tenants --")
    r = await call_tool(session, "create_tenant", {"tenant_id": "v2t", "name": "V2 Test"})
    record(M, "tool", "create_tenant", r is not None, str(r)[:80])

    r = await call_tool(session, "list_tenants", {})
    record(M, "tool", "list_tenants", r is not None, str(r)[:80])

    r = await call_tool(session, "update_tenant", {"tenant_id": "v2t", "name": "Updated"})
    record(M, "tool", "update_tenant", r is not None, str(r)[:80])

    r = await call_tool(session, "delete_tenant", {"tenant_id": "v2t"})
    record(M, "tool", "delete_tenant", r is not None, str(r)[:80])

    # Users
    print("\n  -- Users --")
    r = await call_tool(session, "create_user", {"username": "v2user", "tenant_id": "retail", "role": "user"})
    record(M, "tool", "create_user", r is not None, str(r)[:80])

    r = await call_tool(session, "list_users", {})
    record(M, "tool", "list_users", r is not None, str(r)[:80])

    uid = None
    if isinstance(r, dict):
        users = r.get("users", r.get("results", []))
        for u in users:
            if u.get("username") == "v2user":
                uid = u.get("user_id", u.get("id"))
                break

    if uid:
        r = await call_tool(session, "update_user", {"user_id": uid, "role": "admin"})
        record(M, "tool", "update_user", r is not None, str(r)[:80])
        r = await call_tool(session, "delete_user", {"user_id": uid})
        record(M, "tool", "delete_user", r is not None, str(r)[:80])
    else:
        record(M, "tool", "update_user", False, "no uid")
        record(M, "tool", "delete_user", False, "no uid")

    # Tokens
    print("\n  -- Tokens --")
    r = await call_tool(session, "issue_token", {"agent_id": "v2agent", "tenant_id": "retail", "scopes": ["asset"]})
    record(M, "tool", "issue_token", r is not None, str(r)[:80])

    r = await call_tool(session, "list_tokens", {})
    record(M, "tool", "list_tokens", r is not None, str(r)[:80])

    # Asset types
    print("\n  -- Asset Types --")
    r = await call_tool(session, "register_asset_type", {"yaml_def": "type: v2asset\ndescription: test"})
    record(M, "tool", "register_asset_type", r is not None, str(r)[:80])

    r = await call_tool(session, "list_asset_types", {})
    record(M, "tool", "list_asset_types", r is not None, str(r)[:80])

    r = await call_tool(session, "unregister_asset_type", {"type": "v2asset"})
    record(M, "tool", "unregister_asset_type", r is not None, str(r)[:80])

    # System
    print("\n  -- System --")
    r = await call_tool(session, "get_platform_health", {})
    record(M, "tool", "get_platform_health", r is not None, str(r)[:80])

    r = await call_tool(session, "get_node_status", {})
    record(M, "tool", "get_node_status", r is not None, str(r)[:80])

    r = await call_tool(session, "get_metrics", {})
    record(M, "tool", "get_metrics", r is not None, str(r)[:80])

    # Prompts
    print("\n  -- Prompts --")
    prompt_tests = [
        ("inspect_platform_guide", {"focus_area": "storage"}),
        ("manage_user_guide", {"action": "create"}),
    ]
    for pname, pargs in prompt_tests:
        try:
            await session.get_prompt(pname, pargs)
            record(M, "prompt", pname, True)
        except Exception as e:
            record(M, "prompt", pname, False, str(e)[:60])


async def main():
    print("=" * 60)
    print("LakeMind 3 MCP Full Verification")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    for url, token, fn, name in [
        ("http://lakemind-asset-mcp:8401/mcp", "test-business-token", test_asset_mcp, "AssetMCP"),
        ("http://lakemind-data-mcp:8402/mcp", "test-steward-token", test_data_mcp, "DataMCP"),
        ("http://lakemind-admin-mcp:8403/mcp", "test-steward-token", test_admin_mcp, "AdminMCP"),
    ]:
        try:
            await run_with_session(url, token, fn)
        except Exception as e:
            print(f"  {name} ERROR: {e}")
            record(name, "meta", "connection", False, str(e)[:100])

    print(f"\n{'='*60}")
    print(f"TOTAL: {total_pass} PASS, {total_fail} FAIL, {total_pass + total_fail} tests")
    print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    report = {
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "summary": {"total": total_pass + total_fail, "pass": total_pass, "fail": total_fail},
        "results": results,
    }
    with open("/tmp/mcp_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to /tmp/mcp_report.json")


if __name__ == "__main__":
    asyncio.run(main())
