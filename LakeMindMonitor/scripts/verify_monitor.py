"""LakeMindMonitor 端到端验证。

前置：LakeMindServer + LakeMindMCP + LakeMindMonitor 容器均在跑。
运行：python scripts/verify_monitor.py
"""
import sys, json, urllib.request

BASE = "http://localhost:3000"

passed = failed = 0
def ok(n, d=""):
    global passed; passed += 1; print(f"  [PASS] {n} {d}")
def fail(n, d=""):
    global failed; failed += 1; print(f"  [FAIL] {n} {d}")

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as r:
        return json.loads(r.read())

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def post_query(path, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(f"{BASE}{path}?{qs}", method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


# 1. BFF 健康 + MCP 连通
h = get("/api/health")
assert h["monitor"] == "ok" and h["mcp_connected"] is True, h
ok("BFF health + MCP connected", f"({h})")

# 2. 系统组件健康（4 项 ok）
sh = get("/api/system-health")
assert all(sh[k] == "ok" for k in ("s3", "dragonfly", "gravitino", "embedding")), sh
ok("system health 4/4 ok", f"({sh})")

# 3. 能力图（6 类资产）
caps = get("/api/capabilities")
assert set(caps.keys()) == {"data", "knowledge", "memory", "skill", "experience", "ontology"}, caps
assert caps["ontology"]["enabled"] is False
ok("capabilities 6 types", f"({list(caps.keys())})")

# 4. 工作区
ws = get("/api/workspace")
assert ws["tenant_id"] == "platform" and "data" in ws["scopes"], ws
ok("workspace", f"(tenant={ws['tenant_id']}, scopes={ws['scopes']})")

# 5. 数据地图（platform 租户；可能为空，但端点可用）
data = get("/api/data")
ok("data map", f"({len(data)} datasets)")

# 6. 知识库 / 技能 / 记忆 / 经验 端点可用
kb = get("/api/knowledge"); ok("knowledge", f"({len(kb)} kb)")
sk = get("/api/skills"); ok("skills", f"({len(sk)} skills)")
mem = get("/api/memory"); ok("memory", f"(long={mem.get('long_term_count')})")
exp = get("/api/experience"); ok("experience", f"({len(exp)} records)")

# 7. 静态首页可访问
with urllib.request.urlopen(f"{BASE}/", timeout=10) as r:
    html = r.read().decode()
assert "LakeMind Monitor" in html, "首页未含标题"
ok("frontend index.html served")

# 8. Chat 降级模式：意图识别
for kw, label in [("健康", "组件健康"), ("数据", "数据集列表"), ("知识", "知识库列表"), ("技能", "Skill 列表"), ("记忆", "记忆概况"), ("经验", "经验记录")]:
    r = post_query("/api/chat", message=kw)
    assert r["mode"] == "readonly-direct", r
    assert label in r["reply"], f"chat {kw} 未含 {label}: {r}"
    ok(f"chat intent '{kw}'", f"(mode={r['mode']})")

# 9. Chat 未知意图 → 提示
r = post_query("/api/chat", message="随便说点什么xyz")
assert r["mode"] == "readonly-direct"
ok("chat unknown intent hint", f"({r['reply'][:40]}...)")

# 10. Prometheus 指标
with urllib.request.urlopen(f"{BASE}/metrics", timeout=10) as r:
    metrics = r.read().decode()
assert "monitor_bff_requests_total" in metrics, metrics
ok("metrics endpoint", "(prometheus)")

print(f"\n[verify_monitor] {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
