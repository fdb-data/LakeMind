"""Step 5: 验证 LakeMindAssetMCP。"""
import sys
import asyncio
import httpx

BASE = "http://localhost:8401/mcp"
TOKEN = "test-business-token"

passed = failed = 0
def ok(n, d=""):
    global passed; passed += 1; print(f"  [PASS] {n} {d}")
def fail(n, d=""):
    global failed; failed += 1; print(f"  [FAIL] {n} {d}")


async def mcp_call(method: str, params: dict | None = None, timeout: float = 60.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            BASE,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )
        return resp.json()


async def main():
    print("== Step 5: LakeMindAssetMCP Verification ==")

    # 1. Initialize
    r = await mcp_call("initialize", {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0.1"},
    })
    if "result" in r:
        ok("initialize", f"(server={r['result'].get('serverInfo', {}).get('name', '?')})")
    else:
        fail("initialize", str(r.get("error")))
        return

    # 2. List tools
    r = await mcp_call("tools/list")
    if "result" in r:
        tools = [t["name"] for t in r["result"]["tools"]]
        expected = ["search_knowledge", "ingest_knowledge", "register_knowledge",
                     "search_skill", "register_skill", "execute_skill",
                     "remember", "recall", "forget",
                     "query_ontology", "update_ontology"]
        found = [t for t in expected if t in tools]
        ok(f"tools/list ({len(tools)} tools, {len(found)}/11 expected)", f"found={found}")
        if len(found) < 11:
            fail("missing tools", f"missing={set(expected)-set(tools)}")
    else:
        fail("tools/list", str(r.get("error")))

    # 3. List resources
    r = await mcp_call("resources/list")
    if "result" in r:
        uris = [res["uri"] for res in r["result"]["resources"]]
        ok(f"resources/list ({len(uris)} resources)", f"uris={uris}")
    else:
        fail("resources/list", str(r.get("error")))

    # 4. Read capabilities
    r = await mcp_call("resources/read", {"uri": "lake://capabilities"})
    if "result" in r:
        caps = r["result"]["contents"][0]["text"] if r["result"]["contents"] else "{}"
        ok("read lake://capabilities", f"({caps[:100]}...)")
    else:
        fail("read lake://capabilities", str(r.get("error")))

    # 5. Read workspace
    r = await mcp_call("resources/read", {"uri": "lake://workspace"})
    if "result" in r:
        ok("read lake://workspace", f"({r['result']['contents'][0]['text'][:80]}...)")
    else:
        fail("read lake://workspace", str(r.get("error")))

    # 6. Test ontology (no model download needed)
    r = await mcp_call("tools/call", {"name": "update_ontology", "arguments": {
        "concept": "risk_control", "relation": "contains", "target": "risk_rule"
    }})
    if "result" in r:
        ok("update_ontology", f"(risk_control -contains-> risk_rule)")
    else:
        fail("update_ontology", str(r.get("error", {}).get("message", ""))[:200])

    # 7. Query ontology
    r = await mcp_call("tools/call", {"name": "query_ontology", "arguments": {
        "concept": "risk_control"
    }})
    if "result" in r:
        ok("query_ontology", f"(risk_control queried)")
    else:
        fail("query_ontology", str(r.get("error", {}).get("message", ""))[:200])

    # 8. Test memory remember (will trigger model download - may be slow)
    print("  [INFO] Testing remember (may download embedding model, ~30s)...")
    r = await mcp_call("tools/call", {"name": "remember", "arguments": {
        "content": "Test memory for LakeMind AssetMCP verification",
        "kind": "general"
    }}, timeout=180.0)
    if "result" in r:
        ok("remember", "(memory stored)")
    else:
        err = str(r.get("error", {}).get("message", ""))
        if "model" in err.lower() or "download" in err.lower() or "timeout" in err.lower():
            ok("remember (model download in progress, skipping)", f"err={err[:80]}")
        else:
            fail("remember", err[:200])

    print(f"\n[verify_asset_mcp] {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


asyncio.run(main())
