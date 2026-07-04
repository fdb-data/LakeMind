"""
LakeMind Monitor 验证脚本
验证所有 API 路由 + 静态页面
"""
import sys
import json
import urllib.request
import urllib.error

BASE = "http://localhost:3000"
passed = 0
failed = 0


def check(name, url, method="GET", body=None, expect_json=True):
    global passed, failed
    try:
        data = None
        headers = {}
        if body:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            content = resp.read().decode()
        print(f"  PASS  {name}  [{status}]")
        passed += 1
        if not expect_json:
            return None
        return json.loads(content) if content else None
    except Exception as e:
        print(f"  FAIL  {name}  {e}")
        failed += 1
        return None


print("=" * 60)
print("LakeMind Monitor Verification")
print("=" * 60)

print("\n--- 1. Static Page ---")
check("GET / (index.html)", f"{BASE}/", expect_json=False)

print("\n--- 2. Health ---")
h = check("GET /api/health", f"{BASE}/api/health")
if h:
    for k, v in h.items():
        status = "PASS" if v == "ok" else "FAIL"
        print(f"  {status}  health.{k} = {v}")
        if v == "ok":
            passed += 1
        else:
            failed += 1

print("\n--- 3. Asset Routes ---")
check("GET /api/asset/capabilities", f"{BASE}/api/asset/capabilities")
check("GET /api/asset/knowledge", f"{BASE}/api/asset/knowledge")
check("GET /api/asset/skills", f"{BASE}/api/asset/skills")
check("GET /api/asset/memory", f"{BASE}/api/asset/memory")
check("GET /api/asset/ontology", f"{BASE}/api/asset/ontology")

print("\n--- 4. Data Routes ---")
check("GET /api/data/tables", f"{BASE}/api/data/tables")

print("\n--- 5. Admin Routes ---")
check("GET /api/admin/health", f"{BASE}/api/admin/health")
check("GET /api/admin/tenants", f"{BASE}/api/admin/tenants")
check("GET /api/admin/users", f"{BASE}/api/admin/users")
check("GET /api/admin/tokens", f"{BASE}/api/admin/tokens")

print("\n--- 6. Chat Route ---")
check("POST /api/chat", f"{BASE}/api/chat", method="POST", body={"message": "hello"})

print("\n--- 7. Inspect Route ---")
check("POST /api/inspect", f"{BASE}/api/inspect", method="POST", body={})

print("\n" + "=" * 60)
print(f"Result: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
