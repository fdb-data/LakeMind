import asyncio, sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from verify_full import (
    test_l3, test_l4, test_l5, test_l6, test_l7, test_l8, test_l9,
    mcp_session, results,
    ASSET_URL, ASSET_TOKEN, DATA_URL, DATA_TOKEN, ADMIN_URL, ADMIN_TOKEN,
)

async def main():
    # L3-L5: MCP tools
    for url, token, fn, name in [
        (ASSET_URL, ASSET_TOKEN, test_l3, "AssetMCP"),
        (DATA_URL, DATA_TOKEN, test_l4, "DataMCP"),
        (ADMIN_URL, ADMIN_TOKEN, test_l5, "AdminMCP"),
    ]:
        try:
            print(f"\n--- Starting {name} ---", flush=True)
            await asyncio.wait_for(mcp_session(url, token, fn), timeout=120)
        except asyncio.TimeoutError:
            print(f"  {name} TIMEOUT (120s)", flush=True)
        except Exception as e:
            print(f"  {name} ERROR: {e}", flush=True)

    # L6: Security
    try:
        print("\n--- Starting L6 ---", flush=True)
        await asyncio.wait_for(test_l6(), timeout=60)
    except asyncio.TimeoutError:
        print("  L6 TIMEOUT", flush=True)
    except Exception as e:
        print(f"  L6 ERROR: {e}", flush=True)

    # L7: Steward + Monitor
    try:
        print("\n--- Starting L7 ---", flush=True)
        test_l7()
    except Exception as e:
        print(f"  L7 ERROR: {e}", flush=True)

    # L8: E2E
    try:
        print("\n--- Starting L8 ---", flush=True)
        await asyncio.wait_for(mcp_session(ASSET_URL, ASSET_TOKEN, test_l8), timeout=120)
    except asyncio.TimeoutError:
        print("  L8 TIMEOUT", flush=True)
    except Exception as e:
        print(f"  L8 ERROR: {e}", flush=True)

    # L9: Performance
    try:
        print("\n--- Starting L9 ---", flush=True)
        await asyncio.wait_for(test_l9(), timeout=600)
    except asyncio.TimeoutError:
        print("  L9 TIMEOUT", flush=True)
    except Exception as e:
        print(f"  L9 ERROR: {e}", flush=True)

    # Summary
    passed = sum(1 for r in results if r['passed'] is True)
    failed = sum(1 for r in results if r['passed'] is False)
    skipped = sum(1 for r in results if r['passed'] is None)
    print(f"\nL3-L9 Results: {passed} PASS, {failed} FAIL, {skipped} SKIP, {len(results)} total")
    for r in results:
        if r['passed'] is not True:
            status = 'FAIL' if r['passed'] is False else 'SKIP'
            print(f"  {status}: {r['layer']}/{r['category']}/{r['name']} - {r['detail'][:120]}")

asyncio.run(main())
