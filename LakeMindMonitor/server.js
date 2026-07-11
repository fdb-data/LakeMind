const express = require('express')
const path = require('path')

const app = express()
const PORT = 3000

const MCP_HEADERS = {
  'Accept': 'application/json, text/event-stream',
  'Content-Type': 'application/json',
}

const ASSET_MCP = process.env.ASSET_MCP_URL || 'http://lakemind-asset-mcp:8401/mcp'
const DATA_MCP = process.env.DATA_MCP_URL || 'http://lakemind-data-mcp:8402/mcp'
const ADMIN_MCP = process.env.ADMIN_MCP_URL || 'http://lakemind-admin-mcp:8403/mcp'
const STEWARD = process.env.STEWARD_URL || 'http://lakemind-steward:8500'
const ASSET_TOKEN = process.env.ASSET_TOKEN || 'test-monitor-token'
const DATA_TOKEN = process.env.DATA_TOKEN || 'test-steward-token'
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || 'test-steward-token'

app.use(express.json())
app.use(express.static(path.join(__dirname, 'public')))

async function mcpRead(url, token, uri) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { ...MCP_HEADERS, Authorization: `Bearer ${token}` },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'resources/read', params: { uri } }),
  })
  return resp.json()
}

async function mcpCall(url, token, tool, args = {}) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { ...MCP_HEADERS, Authorization: `Bearer ${token}` },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: tool, arguments: args } }),
  })
  return resp.json()
}

function extractText(r) {
  if (r?.result?.contents?.[0]?.text) return r.result.contents[0].text
  if (r?.result?.content?.[0]?.text) return r.result.content[0].text
  return JSON.stringify(r)
}

function parseResult(r) {
  const text = extractText(r)
  try { return JSON.parse(text) } catch { return text }
}

function safe(fn) {
  return async (req, res) => {
    try { await fn(req, res) }
    catch (e) { res.status(500).json({ error: String(e) }) }
  }
}

const CONTAINERS = [
  { name: 'server-api', port: 10823, category: 'data' },
  { name: 'postgres', port: 5432, category: 'data' },
  { name: 'seaweedfs', port: 8333, category: 'data' },
  { name: 'valkey', port: 6379, category: 'data' },
  { name: 'ray-head', port: 8265, category: 'compute' },
  { name: 'ray-worker-1', port: null, category: 'compute' },
  { name: 'ray-worker-2', port: null, category: 'compute' },
  { name: 'asset-mcp', port: 8401, category: 'mcp' },
  { name: 'data-mcp', port: 8402, category: 'mcp' },
  { name: 'admin-mcp', port: 8403, category: 'mcp' },
  { name: 'model-serving', port: 10824, category: 'runtime' },
  { name: 'steward', port: 8500, category: 'runtime' },
  { name: 'monitor', port: 3000, category: 'runtime' },
]

const CONTAINER_HEALTH_URLS = {
  'server-api': 'http://lakemind-server-api:10823/api/v1/system/health',
  'postgres': null,
  'seaweedfs': null,
  'valkey': null,
  'ray-head': null,
  'ray-worker-1': null,
  'ray-worker-2': null,
  'asset-mcp': 'http://lakemind-asset-mcp:8401/health',
  'data-mcp': 'http://lakemind-data-mcp:8402/health',
  'admin-mcp': 'http://lakemind-admin-mcp:8403/health',
  'model-serving': 'http://lakemind-model-serving:10824/health',
  'steward': 'http://lakemind-steward:8500/health',
  'monitor': null,
}

const ENGINE_INFO = [
  { key: 'object_storage', label: '对象存储', category: 'storage', plugin: 'SeaweedFS' },
  { key: 'tabular', label: '表格式', category: 'storage', plugin: 'Iceberg' },
  { key: 'vector', label: '向量', category: 'storage', plugin: 'Lance/LanceDB' },
  { key: 'kv', label: 'KV', category: 'storage', plugin: 'Valkey' },
  { key: 'graph', label: '图', category: 'storage', plugin: 'PostgreSQL' },
  { key: 'metadata', label: '元数据', category: 'storage', plugin: 'PostgreSQL' },
  { key: 'sql', label: 'SQL', category: 'compute', plugin: 'DuckDB' },
  { key: 'distributed', label: '分布式', category: 'compute', plugin: 'Ray' },
  { key: 'memory', label: '记忆', category: 'cognitive', plugin: 'mem0' },
  { key: 'model_serving', label: '模型服务', category: 'cognitive', plugin: 'litellm+fastembed+FunASR' },
]

async function probeContainers(engineHealth) {
  const results = []
  for (const c of CONTAINERS) {
    const url = CONTAINER_HEALTH_URLS[c.name]
    if (!url) {
      const inferred = inferContainerStatus(c.name, engineHealth)
      results.push({ ...c, status: inferred })
      continue
    }
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(3000) })
      results.push({ ...c, status: r.ok ? 'ok' : 'error' })
    } catch {
      results.push({ ...c, status: 'error' })
    }
  }
  return results
}

function inferContainerStatus(name, engineHealth) {
  const h = (k) => engineHealth?.[k] === true || engineHealth?.[k] === 'ok'
  switch (name) {
    case 'postgres': return h('metadata') ? 'ok' : 'error'
    case 'valkey': return h('kv') ? 'ok' : 'error'
    case 'seaweedfs': return h('object_storage') ? 'ok' : 'error'
    case 'ray-head': return h('distributed') ? 'ok' : 'error'
    case 'ray-worker-1': return h('distributed') ? 'ok' : 'error'
    case 'ray-worker-2': return h('distributed') ? 'ok' : 'error'
    case 'monitor': return 'ok'
    default: return 'unknown'
  }
}

function countFromResult(data, ...paths) {
  try {
    let val = data
    for (const p of paths) val = val?.[p]
    if (Array.isArray(val)) return val.length
    if (typeof val === 'number') return val
    return 0
  } catch { return 0 }
}

app.get('/api/health', safe(async (req, res) => {
  const services = {}
  for (const [name, port] of [['asset-mcp', 8401], ['data-mcp', 8402], ['admin-mcp', 8403], ['model-serving', 10824], ['steward', 8500]]) {
    try {
      const r = await fetch(`http://lakemind-${name}:${port}/health`, { signal: AbortSignal.timeout(3000) })
      services[name] = r.ok ? 'ok' : 'error'
    } catch { services[name] = 'error' }
  }
  res.json(services)
}))

app.get('/api/dashboard/overview', safe(async (req, res) => {
  const results = await Promise.allSettled([
    mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'get_platform_health', {}).then(parseResult),
    mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'get_node_status', {}).then(parseResult),
    mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'get_metrics', {}).then(parseResult),
    mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://knowledge').then(parseResult),
    mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://skills').then(parseResult),
    mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://memory').then(parseResult),
    mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://ontology').then(parseResult),
    mcpCall(DATA_MCP, DATA_TOKEN, 'list_tables', {}).then(parseResult),
    mcpRead(DATA_MCP, DATA_TOKEN, 'lake://vectors').then(parseResult),
    mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_tenants', {}).then(parseResult),
    mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_users', {}).then(parseResult),
    mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_tokens', {}).then(parseResult),
    mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_asset_types', {}).then(parseResult),
  ])

  const v = (i, fallback = null) => results[i].status === 'fulfilled' ? results[i].value : fallback
  const rawEngineHealth = v(0, {})
  const nodes = v(1, {})
  const metrics = v(2, {})
  const knowledge = v(3, [])
  const skills = v(4, [])
  const memory = v(5, {})
  const ontology = v(6, [])
  const tables = v(7, {})
  const vectors = v(8, [])
  const tenants = v(9, {})
  const users = v(10, {})
  const tokens = v(11, {})
  const assetTypes = v(12, [])

  let modelServingOk = false
  try {
    const msR = await fetch('http://lakemind-model-serving:10824/health', { signal: AbortSignal.timeout(3000) })
    modelServingOk = msR.ok
  } catch { modelServingOk = false }

  const engineHealth = {}
  for (const e of ENGINE_INFO) {
    if (e.key === 'model_serving') {
      engineHealth.model_serving = modelServingOk
    } else {
      engineHealth[e.key] = rawEngineHealth[e.key]
    }
  }

  const containers = await probeContainers(engineHealth)

  const engineList = ENGINE_INFO.map(e => ({
    ...e,
    status: engineHealth[e.key] === true || engineHealth[e.key] === 'ok',
  }))

  res.json({
    containers,
    engines: engineList,
    engineHealthRaw: engineHealth,
    nodes: nodes.nodes || nodes || [],
    metrics,
    assets: {
      knowledgeCount: Array.isArray(knowledge) ? knowledge.length : countFromResult(knowledge, 'knowledge_bases'),
      skillCount: Array.isArray(skills) ? skills.length : countFromResult(skills, 'skills'),
      memoryTotal: typeof memory === 'object' ? (memory.total || memory.total_count || 0) : 0,
      memoryByKind: typeof memory === 'object' ? (memory.by_kind || memory.kinds || {}) : {},
      ontologyNodes: typeof ontology === 'object' ? (ontology.node_count || ontology.count || (Array.isArray(ontology.nodes) ? ontology.nodes.length : ontology.nodes) || 0) : 0,
      ontologyEdges: typeof ontology === 'object' ? (ontology.edge_count || (Array.isArray(ontology.edges) ? ontology.edges.length : ontology.edges) || 0) : 0,
    },
    data: {
      tableCount: countFromResult(tables, 'tables') || (Array.isArray(tables) ? tables.length : 0),
      vectorCount: Array.isArray(vectors) ? vectors.length : countFromResult(vectors, 'tables'),
    },
    platform: {
      tenantCount: countFromResult(tenants, 'tenants') || (Array.isArray(tenants) ? tenants.length : 0),
      userCount: countFromResult(users, 'users') || (Array.isArray(users) ? users.length : 0),
      tokenCount: countFromResult(tokens, 'tokens') || (Array.isArray(tokens) ? tokens.length : 0),
      assetTypeCount: Array.isArray(assetTypes) ? assetTypes.length : countFromResult(assetTypes, 'asset_types') || countFromResult(assetTypes, 'types') || assetTypes?.count || 0,
    },
    raw: { knowledge, skills, memory, ontology, tables, vectors, tenants, users, tokens, assetTypes },
  })
}))

app.get('/api/asset/capabilities', safe(async (req, res) => {
  const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://capabilities')
  res.json(parseResult(r))
}))

app.get('/api/asset/knowledge', safe(async (req, res) => {
  const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://knowledge')
  res.json(parseResult(r))
}))

app.get('/api/asset/knowledge/:kb', safe(async (req, res) => {
  const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, `lake://knowledge/${req.params.kb}`)
  res.json(parseResult(r))
}))

app.get('/api/asset/skills', safe(async (req, res) => {
  const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://skills')
  res.json(parseResult(r))
}))

app.get('/api/asset/memory', safe(async (req, res) => {
  const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://memory')
  res.json(parseResult(r))
}))

app.get('/api/asset/memory/list', safe(async (req, res) => {
  const args = { limit: parseInt(req.query.limit) || 20, offset: parseInt(req.query.offset) || 0 }
  const r = await mcpCall(ASSET_MCP, ASSET_TOKEN, 'list_memory', args)
  res.json(parseResult(r))
}))

app.get('/api/asset/ontology', safe(async (req, res) => {
  const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://ontology')
  res.json(parseResult(r))
}))

app.get('/api/data/tables', safe(async (req, res) => {
  const r = await mcpCall(DATA_MCP, DATA_TOKEN, 'list_tables', {})
  res.json(parseResult(r))
}))

app.get('/api/data/tables/:ns/:t', safe(async (req, res) => {
  const r = await mcpCall(DATA_MCP, DATA_TOKEN, 'describe_table', { table: `${req.params.ns}.${req.params.t}` })
  res.json(parseResult(r))
}))

app.get('/api/data/vectors', safe(async (req, res) => {
  const r = await mcpRead(DATA_MCP, DATA_TOKEN, 'lake://vectors')
  res.json(parseResult(r))
}))

app.get('/api/data/s3', safe(async (req, res) => {
  const prefix = req.query.prefix || ''
  const r = await mcpCall(DATA_MCP, DATA_TOKEN, 's3_list', { prefix })
  res.json(parseResult(r))
}))

app.get('/api/data/kv', safe(async (req, res) => {
  const prefix = req.query.prefix || ''
  const r = await mcpCall(DATA_MCP, DATA_TOKEN, 'kv_scan', { prefix, limit: 50 })
  res.json(parseResult(r))
}))

app.get('/api/data/graph', safe(async (req, res) => {
  const r = await mcpCall(DATA_MCP, DATA_TOKEN, 'graph_query', { limit: 50 })
  res.json(parseResult(r))
}))

app.get('/api/admin/health', safe(async (req, res) => {
  const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'get_platform_health', {})
  const health = parseResult(r)
  const filtered = {}
  for (const k of ['object_storage','tabular','vector','kv','graph','metadata','sql','distributed','memory']) {
    filtered[k] = health[k]
  }
  try {
    const msR = await fetch('http://lakemind-model-serving:10824/health', { signal: AbortSignal.timeout(3000) })
    filtered.model_serving = msR.ok
  } catch { filtered.model_serving = false }
  res.json(filtered)
}))

app.get('/api/admin/nodes', safe(async (req, res) => {
  const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'get_node_status', {})
  res.json(parseResult(r))
}))

app.get('/api/admin/metrics', safe(async (req, res) => {
  const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'get_metrics', {})
  res.json(parseResult(r))
}))

app.get('/api/admin/tenants', safe(async (req, res) => {
  const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_tenants', {})
  res.json(parseResult(r))
}))

app.get('/api/admin/users', safe(async (req, res) => {
  const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_users', {})
  res.json(parseResult(r))
}))

app.get('/api/admin/tokens', safe(async (req, res) => {
  const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_tokens', {})
  res.json(parseResult(r))
}))

app.get('/api/admin/asset-types', safe(async (req, res) => {
  const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_asset_types', {})
  res.json(parseResult(r))
}))

app.post('/api/chat', safe(async (req, res) => {
  const r = await fetch(`${STEWARD}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ message: req.body.message }),
    signal: AbortSignal.timeout(30000),
  })
  res.json(await r.json())
}))

app.post('/api/inspect', safe(async (req, res) => {
  const r = await fetch(`${STEWARD}/inspect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({}),
    signal: AbortSignal.timeout(60000),
  })
  res.json(await r.json())
}))

app.get('/api/steward/health', safe(async (req, res) => {
  try {
    const r = await fetch(`${STEWARD}/health`, { signal: AbortSignal.timeout(3000) })
    res.json({ status: r.ok ? 'ok' : 'error', ...await r.json() })
  } catch {
    res.json({ status: 'error' })
  }
}))

app.get('/api/model-serving/health', safe(async (req, res) => {
  try {
    const r = await fetch('http://lakemind-model-serving:10824/health', { signal: AbortSignal.timeout(3000) })
    res.json({ status: r.ok ? 'ok' : 'error', ...await r.json() })
  } catch {
    res.json({ status: 'error' })
  }
}))

app.get('/api/model-serving/models', safe(async (req, res) => {
  try {
    const r = await fetch('http://lakemind-model-serving:10824/v1/models', { signal: AbortSignal.timeout(5000) })
    res.json(await r.json())
  } catch {
    res.json({ data: [] })
  }
}))

app.listen(PORT, () => console.log(`LakeMind Monitor on :${PORT}`))
