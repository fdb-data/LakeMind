import urllib.request
import json
import sys

headers = {
    'Authorization': 'Bearer lakemind-internal-api-key',
    'X-Tenant-Id': 'test',
    'X-Agent-Id': 'agent-1',
    'X-Scopes': 'asset,data,admin',
}

ms_headers = {
    'Authorization': 'Bearer lakemind-modelserving-key',
}

tests = []

def test(name, ok, detail=''):
    tests.append((name, ok, detail))
    status = 'PASS' if ok else 'FAIL'
    print(f'{status}: {name} {detail}')

# 1. Server health
r = urllib.request.urlopen('http://localhost:10823/api/v1/system/health')
h = json.loads(r.read())
engines_ok = sum(1 for v in h.values() if v)
test('Server health', engines_ok >= 9, f'({engines_ok}/11 engines, embedding={h.get("embedding")}, llm={h.get("llm")})')

# 2. ModelServing health
r = urllib.request.urlopen('http://localhost:10824/health')
ms = json.loads(r.read())
test('ModelServing health', ms['services']['gateway'] and ms['services']['embedding'],
     f'(gateway={ms["services"]["gateway"]}, embedding={ms["services"]["embedding"]}, asr={ms["services"]["asr"]})')

# 3. ModelServing models
req = urllib.request.Request('http://localhost:10824/v1/models', headers=ms_headers)
r = urllib.request.urlopen(req)
models = json.loads(r.read())['data']
test('ModelServing models', len(models) >= 3, f'({len(models)} models)')

# 4. Embedding via ModelServing
data = json.dumps({'model': 'jina-embeddings-v2-base-zh', 'input': ['test text']}).encode()
req = urllib.request.Request('http://localhost:10824/v1/embeddings', data=data,
                             headers={**ms_headers, 'Content-Type': 'application/json'})
r = urllib.request.urlopen(req)
emb = json.loads(r.read())
test('Embedding via ModelServing', len(emb['data'][0]['embedding']) == 768,
     f'(dim={len(emb["data"][0]["embedding"])})')

# 5. Memory add via Server
data = json.dumps({'messages': [{'role': 'user', 'content': 'verification test memory item'}]}).encode()
req = urllib.request.Request('http://localhost:10823/api/v1/cognitive/memory/add', data=data,
                             headers={**headers, 'Content-Type': 'application/json'})
r = urllib.request.urlopen(req)
add_result = json.loads(r.read())
test('Memory add (via ModelServing embedding)', len(add_result.get('results', [])) > 0,
     f'({len(add_result.get("results", []))} memories)')

# 6. Memory search via Server
data = json.dumps({'query': 'verification', 'top_k': 3}).encode()
req = urllib.request.Request('http://localhost:10823/api/v1/cognitive/memory/search', data=data,
                             headers={**headers, 'Content-Type': 'application/json'})
r = urllib.request.urlopen(req)
search_result = json.loads(r.read())
test('Memory search (via ModelServing embedding)', len(search_result) > 0,
     f'({len(search_result)} results)')

# 7. LLM endpoint removed from Server
try:
    req = urllib.request.Request('http://localhost:10823/api/v1/cognitive/llm/health', headers=headers)
    r = urllib.request.urlopen(req)
    test('LLM endpoint removed from Server', False, '(still exists!)')
except urllib.error.HTTPError as e:
    test('LLM endpoint removed from Server', e.code == 404, f'(status={e.code})')

# 8. Embedding endpoint removed from Server
try:
    data = json.dumps({'texts': ['test']}).encode()
    req = urllib.request.Request('http://localhost:10823/api/v1/cognitive/embedding/embed', data=data,
                                 headers={**headers, 'Content-Type': 'application/json'})
    r = urllib.request.urlopen(req)
    test('Embedding endpoint removed from Server', False, '(still exists!)')
except urllib.error.HTTPError as e:
    test('Embedding endpoint removed from Server', e.code == 404, f'(status={e.code})')

# 9. Model registration
data = json.dumps({
    'model_id': 'test-model',
    'type': 'llm',
    'provider': 'openai',
    'litellm_model': 'openai/gpt-4o-mini',
    'api_key': 'test-key',
    'tags': ['chat'],
}).encode()
req = urllib.request.Request('http://localhost:10824/v1/models/register', data=data,
                             headers={**ms_headers, 'Content-Type': 'application/json'})
r = urllib.request.urlopen(req)
reg = json.loads(r.read())
test('Model registration', reg.get('status') == 'ok', f'({reg})')

# 10. Model deregistration
req = urllib.request.Request('http://localhost:10824/v1/models/test-model', method='DELETE',
                             headers=ms_headers)
r = urllib.request.urlopen(req)
dereg = json.loads(r.read())
test('Model deregistration', dereg.get('status') == 'ok', f'({dereg})')

# 11. MCP health checks
for name, port in [('AssetMCP', 8401), ('DataMCP', 8402), ('AdminMCP', 8403)]:
    try:
        r = urllib.request.urlopen(f'http://localhost:{port}/health')
        h = json.loads(r.read())
        test(f'{name} health', h.get('status') == 'ok', f'({h.get("service")})')
    except Exception as e:
        test(f'{name} health', False, str(e))

# 12. Steward health
try:
    r = urllib.request.urlopen('http://localhost:8500/health')
    h = json.loads(r.read())
    test('Steward health', h.get('status') == 'ok' or 'ok' in str(h), f'({h})')
except Exception as e:
    test('Steward health', False, str(e))

# 13. Monitor health
try:
    r = urllib.request.urlopen('http://localhost:3000/api/health')
    h = json.loads(r.read())
    test('Monitor health', True, f'(responding)')
except Exception as e:
    try:
        r = urllib.request.urlopen('http://localhost:3000/')
        test('Monitor health', True, '(responding)')
    except Exception as e2:
        test('Monitor health', False, str(e2))

passed = sum(1 for _, ok, _ in tests if ok)
failed = sum(1 for _, ok, _ in tests if not ok)
print(f'\nResult: {passed} passed, {failed} failed')
sys.exit(0 if failed == 0 else 1)
