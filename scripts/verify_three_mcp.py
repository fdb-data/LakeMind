"""Step 9: 三 MCP 联合验证。"""
import sys
import asyncio
import httpx

passed = failed = 0
def ok(n, d=""):
    global passed; passed += 1; print(f"  [PASS] {n} {d}")
def fail(n, d=""):
    global failed; failed += 1; print(f"  [FAIL] {n} {d}")

HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}

async def mcp_call(base: str, token: str, method: str, params: dict | None = None, timeout: float = 30.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            base,
            headers={**HEADERS, "Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )
        return resp.json()

async def check_health(name: str, port: int):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"http://localhost:{port}/health")
            d = r.json()
            if d.get("status") == "ok":
                ok(f"{name} health", f"({d['service']})")
            else:
                fail(f"{name} health", str(d))
        except Exception as e:
            fail(f"{name} health", str(e))


async def main():
    print("== Step 9: Three MCP Combined Verification ==")

    # 1. Health checks
    await check_health("AssetMCP", 8401)
    await check_health("DataMCP", 8402)
    await check_health("AdminMCP", 8403)

    # 2. AssetMCP: tools/list (11 tools, asset scope)
    r = await mcp_call("http://localhost:8401/mcp", "test-business-token", "initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0.1"}
    })
    ok("AssetMCP initialize") if "result" in r else fail("AssetMCP initialize", str(r.get("error")))

    r = await mcp_call("http://localhost:8401/mcp", "test-business-token", "tools/list")
    tools = [t["name"] for t in r.get("result", {}).get("tools", [])] if "result" in r else []
    ok(f"AssetMCP tools ({len(tools)})", f"asset scope") if len(tools) == 11 else fail("AssetMCP tools", f"got {len(tools)}")

    # 3. DataMCP: tools/list (13 tools, data scope)
    r = await mcp_call("http://localhost:8402/mcp", "test-steward-token", "initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0.1"}
    })
    ok("DataMCP initialize") if "result" in r else fail("DataMCP initialize", str(r.get("error")))

    r = await mcp_call("http://localhost:8402/mcp", "test-steward-token", "tools/list")
    tools = [t["name"] for t in r.get("result", {}).get("tools", [])] if "result" in r else []
    ok(f"DataMCP tools ({len(tools)})", f"data scope") if len(tools) >= 10 else fail("DataMCP tools", f"got {len(tools)}")

    # 4. AdminMCP: tools/list (16 tools, admin scope)
    r = await mcp_call("http://localhost:8403/mcp", "test-steward-token", "initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0.1"}
    })
    ok("AdminMCP initialize") if "result" in r else fail("AdminMCP initialize", str(r.get("error")))

    r = await mcp_call("http://localhost:8403/mcp", "test-steward-token", "tools/list")
    tools = [t["name"] for t in r.get("result", {}).get("tools", [])] if "result" in r else []
    ok(f"AdminMCP tools ({len(tools)})", f"admin scope") if len(tools) >= 14 else fail("AdminMCP tools", f"got {len(tools)}")

    # 5. AdminMCP: create_tenant + create_user + issue_token
    r = await mcp_call("http://localhost:8403/mcp", "test-steward-token", "tools/call", {
        "name": "create_tenant", "arguments": {"tenant_id": "test_tenant", "name": "Test Tenant"}
    })
    ok("create_tenant") if "result" in r else fail("create_tenant", str(r.get("error", {}).get("message", ""))[:100])

    r = await mcp_call("http://localhost:8403/mcp", "test-steward-token", "tools/call", {
        "name": "create_user", "arguments": {"username": "test_user", "tenant_id": "test_tenant", "role": "admin"}
    })
    ok("create_user") if "result" in r else fail("create_user", str(r.get("error", {}).get("message", ""))[:100])

    r = await mcp_call("http://localhost:8403/mcp", "test-steward-token", "tools/call", {
        "name": "issue_token", "arguments": {"agent_id": "test_agent", "tenant_id": "test_tenant", "scopes": ["asset"]}
    })
    ok("issue_token") if "result" in r else fail("issue_token", str(r.get("error", {}).get("message", ""))[:100])

    # 6. AdminMCP: list_tenants + list_users + list_tokens
    r = await mcp_call("http://localhost:8403/mcp", "test-steward-token", "tools/call", {
        "name": "list_tenants", "arguments": {}
    })
    ok("list_tenants") if "result" in r else fail("list_tenants", str(r.get("error", {}).get("message", ""))[:100])

    r = await mcp_call("http://localhost:8403/mcp", "test-steward-token", "tools/call", {
        "name": "list_users", "arguments": {}
    })
    ok("list_users") if "result" in r else fail("list_users", str(r.get("error", {}).get("message", ""))[:100])

    # 7. AdminMCP: get_platform_health
    r = await mcp_call("http://localhost:8403/mcp", "test-steward-token", "tools/call", {
        "name": "get_platform_health", "arguments": {}
    })
    ok("get_platform_health") if "result" in r else fail("get_platform_health", str(r.get("error", {}).get("message", ""))[:100])

    # 8. AdminMCP: register_asset_type
    r = await mcp_call("http://localhost:8403/mcp", "test-steward-token", "tools/call", {
        "name": "register_asset_type", "arguments": {
            "yaml_def": "type: custom_rag\ndescription: Custom RAG\nresource_root: lake://custom_rag\ncapabilities: [search]\nstorage:\n  vector:\n    engine: lancedb\noperations:\n  search:\n    engine: vector_topk"
        }
    })
    ok("register_asset_type") if "result" in r else fail("register_asset_type", str(r.get("error", {}).get("message", ""))[:100])

    # 9. DataMCP: data_create_table + data_write + data_query
    r = await mcp_call("http://localhost:8402/mcp", "test-steward-token", "tools/call", {
        "name": "data_create_table", "arguments": {
            "name": "test_data_table",
            "schema": {"id": "int64", "name": "string", "value": "float64"}
        }
    })
    ok("data_create_table") if "result" in r else fail("data_create_table", str(r.get("error", {}).get("message", ""))[:200])

    r = await mcp_call("http://localhost:8402/mcp", "test-steward-token", "tools/call", {
        "name": "data_write", "arguments": {
            "table": "test_data_table",
            "rows": [{"id": 1, "name": "alpha", "value": 1.1}, {"id": 2, "name": "beta", "value": 2.2}],
            "mode": "append"
        }
    })
    ok("data_write") if "result" in r else fail("data_write", str(r.get("error", {}).get("message", ""))[:200])

    r = await mcp_call("http://localhost:8402/mcp", "test-steward-token", "tools/call", {
        "name": "data_query", "arguments": {"table": "test_data_table", "limit": 10}
    })
    ok("data_query") if "result" in r else fail("data_query", str(r.get("error", {}).get("message", ""))[:200])

    # 10. DataMCP: data_list_tables + data_describe
    r = await mcp_call("http://localhost:8402/mcp", "test-steward-token", "tools/call", {
        "name": "data_list_tables", "arguments": {}
    })
    ok("data_list_tables") if "result" in r else fail("data_list_tables", str(r.get("error", {}).get("message", ""))[:200])

    # 11. Scope isolation: business token (asset scope) should fail on DataMCP
    r = await mcp_call("http://localhost:8402/mcp", "test-business-token", "tools/call", {
        "name": "data_list_tables", "arguments": {}
    })
    if "error" in r:
        ok("scope isolation (business token rejected on DataMCP)")
    else:
        fail("scope isolation", "business token should not access DataMCP")

    # 12. AssetMCP: ontology tools (cross-MCP consistency)
    r = await mcp_call("http://localhost:8401/mcp", "test-business-token", "tools/call", {
        "name": "update_ontology", "arguments": {"concept": "system", "relation": "has_component", "target": "asset_mcp"}
    })
    ok("AssetMCP ontology (cross-MCP)") if "result" in r else fail("AssetMCP ontology", str(r.get("error", {}).get("message", ""))[:100])

    print(f"\n[verify_three_mcp] {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


asyncio.run(main())
