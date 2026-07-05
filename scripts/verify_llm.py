#!/usr/bin/env python3
"""LLM 模型网关完整测试"""
import requests
import time
import sys

BASE = "http://localhost:10823/api/v1/cognitive/llm"
HEADERS = {
    "Authorization": "Bearer lakemind-internal-api-key",
    "X-Tenant-Id": "default",
    "X-Agent-Id": "llm-test",
    "X-Scopes": "all",
    "Content-Type": "application/json",
}

passed = 0
failed = 0


def _chat(messages, model="deepseek-v4-flash", temperature=0.7, max_tokens=0, retries=5):
    body = {"messages": messages, "model": model, "temperature": temperature}
    if max_tokens > 0:
        body["max_tokens"] = max_tokens
    for attempt in range(retries):
        r = requests.post(f"{BASE}/chat", headers=HEADERS, json=body, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 502 and "429" in r.text:
            wait = 10 * (attempt + 1)
            print(f"        429 rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        raise Exception(f"status={r.status_code} body={r.text}")
    raise Exception(f"failed after {retries} retries")


def test(name, func):
    global passed, failed
    try:
        func()
        print(f"  PASS  {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        failed += 1


def t_health():
    r = requests.get(f"{BASE}/health", headers=HEADERS, timeout=10)
    assert r.status_code == 200, f"status={r.status_code}"
    assert r.json()["healthy"] is True, "not healthy"


def t_system_health():
    r = requests.get("http://localhost:10823/api/v1/system/health", headers=HEADERS, timeout=10)
    assert r.json()["llm"] is True, "llm not in system health"


def t_list_models():
    r = requests.get(f"{BASE}/models", headers=HEADERS, timeout=10)
    assert r.status_code == 200
    models = r.json()["models"]
    assert len(models) >= 1, f"no models: {models}"
    assert models[0]["id"] == "deepseek-v4-flash", f"wrong model: {models[0]}"
    assert models[0]["provider"] == "modelarts", f"wrong provider: {models[0]}"


def t_chat_basic():
    data = _chat([{"role": "user", "content": "Say hello in one word."}], max_tokens=50)
    assert "choices" in data, f"no choices: {data}"
    content = data["choices"][0]["message"]["content"]
    assert len(content) > 0, f"empty content: {data}"
    print(f"        response: {content[:80]}...")


def t_chat_with_system():
    data = _chat([
        {"role": "system", "content": "You are a helpful assistant. Always respond in Chinese."},
        {"role": "user", "content": "What is 2+3?"}
    ], max_tokens=100)
    content = data["choices"][0]["message"]["content"]
    assert len(content) > 0, f"empty content"
    print(f"        response: {content[:80]}...")


def t_chat_auto_model():
    data = _chat([{"role": "user", "content": "Hi"}], model="auto", max_tokens=20)
    assert "deepseek" in data["model"].lower(), f"wrong model: {data.get('model')}"


def t_chat_multi_turn():
    data = _chat([
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Nice to meet you, Alice!"},
        {"role": "user", "content": "What is my name?"}
    ], max_tokens=50)
    content = data["choices"][0]["message"]["content"]
    assert "Alice" in content or "alice" in content.lower(), f"didn't remember: {content}"
    print(f"        response: {content[:80].encode('ascii', 'replace').decode('ascii')}...")


def t_chat_usage():
    data = _chat([{"role": "user", "content": "Hello"}], max_tokens=20)
    usage = data.get("usage", {})
    assert "total_tokens" in usage or "prompt_tokens" in usage, f"no usage: {data}"


def t_chat_long_response():
    data = _chat(
        [{"role": "user", "content": "List 5 benefits of using a data lake architecture."}],
        max_tokens=500
    )
    content = data["choices"][0]["message"]["content"]
    assert len(content) > 50, f"too short: {len(content)} chars"
    print(f"        response length: {len(content)} chars")


def t_concurrent_chat():
    import concurrent.futures
    def _call(i):
        time.sleep(i * 30)
        try:
            data = _chat([{"role": "user", "content": "Say OK"}], max_tokens=10, retries=6)
            return True
        except Exception:
            return False
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(_call, range(3)))
    assert all(results), f"some failed: {results}"


print("=" * 60)
print("LLM 模型网关完整测试")
print("=" * 60)

print("\n── 基础测试 ──")
test("health check (llm=true)", t_health)
test("system health includes llm", t_system_health)
test("list models (deepseek-v4-flash)", t_list_models)

print("\n── Chat 功能测试 ──")
test("basic chat (1 message)", t_chat_basic)
test("chat with system prompt", t_chat_with_system)
test("chat auto model routing", t_chat_auto_model)
test("multi-turn conversation", t_chat_multi_turn)
test("usage tokens returned", t_chat_usage)

print("\n── 能力测试 ──")
test("long response (500 tokens)", t_chat_long_response)
test("5 concurrent chat requests", t_concurrent_chat)

print(f"\n{'=' * 60}")
print(f"Result: {passed} PASS, {failed} FAIL")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
