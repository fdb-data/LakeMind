import { mcpCall, extractText } from '../mcp'

export default defineEventHandler(async () => {
  const config = useRuntimeConfig()
  const r = await mcpCall(config.adminMcpUrl, config.adminToken, 'list_users', {})
  try { return JSON.parse(extractText(r) || '{}') } catch { return extractText(r) }
})
