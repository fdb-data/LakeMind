const express = require('express')
const httpProxy = require('http-proxy')
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

app.get('/api/health', async (req, res) => {
  const services = {}
  for (const [name, port] of [['asset-mcp', 8401], ['data-mcp', 8402], ['admin-mcp', 8403], ['steward', 8500]]) {
    try {
      const r = await fetch(`http://lakemind-${name}:${port}/health`, { signal: AbortSignal.timeout(3000) })
      services[name] = r.ok ? 'ok' : 'error'
    } catch { services[name] = 'error' }
  }
  res.json(services)
})

app.get('/api/asset/capabilities', async (req, res) => {
  try { const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://capabilities'); res.json(JSON.parse(extractText(r) || '{}')) } catch (e) { res.json({ error: String(e) }) }
})
app.get('/api/asset/knowledge', async (req, res) => {
  try { const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://knowledge'); res.json(JSON.parse(extractText(r) || '[]')) } catch (e) { res.json({ error: String(e) }) }
})
app.get('/api/asset/skills', async (req, res) => {
  try { const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://skills'); res.json(JSON.parse(extractText(r) || '[]')) } catch (e) { res.json({ error: String(e) }) }
})
app.get('/api/asset/memory', async (req, res) => {
  try { const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://memory'); res.json(JSON.parse(extractText(r) || '{}')) } catch (e) { res.json({ error: String(e) }) }
})
app.get('/api/asset/ontology', async (req, res) => {
  try { const r = await mcpRead(ASSET_MCP, ASSET_TOKEN, 'lake://ontology'); res.json(JSON.parse(extractText(r) || '[]')) } catch (e) { res.json({ error: String(e) }) }
})

app.get('/api/data/tables', async (req, res) => {
  try { const r = await mcpCall(DATA_MCP, ADMIN_TOKEN, 'data_list_tables', {}); res.json(JSON.parse(extractText(r) || '{}')) } catch (e) { res.json({ error: String(e) }) }
})

app.get('/api/admin/health', async (req, res) => {
  try { const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'get_platform_health', {}); res.json(JSON.parse(extractText(r) || '{}')) } catch (e) { res.json({ error: String(e) }) }
})
app.get('/api/admin/tenants', async (req, res) => {
  try { const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_tenants', {}); res.json(JSON.parse(extractText(r) || '{}')) } catch (e) { res.json({ error: String(e) }) }
})
app.get('/api/admin/users', async (req, res) => {
  try { const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_users', {}); res.json(JSON.parse(extractText(r) || '{}')) } catch (e) { res.json({ error: String(e) }) }
})
app.get('/api/admin/tokens', async (req, res) => {
  try { const r = await mcpCall(ADMIN_MCP, ADMIN_TOKEN, 'list_tokens', {}); res.json(JSON.parse(extractText(r) || '{}')) } catch (e) { res.json({ error: String(e) }) }
})

app.post('/api/chat', async (req, res) => {
  try {
    const r = await fetch(`${STEWARD}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: req.body.message }),
      signal: AbortSignal.timeout(30000),
    })
    res.json(await r.json())
  } catch (e) {
    res.json({ reply: 'Steward 未就绪', mode: 'unavailable' })
  }
})

app.listen(PORT, () => console.log(`LakeMind Monitor on :${PORT}`))
