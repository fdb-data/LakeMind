import { mcpCall, extractText } from '../mcp'

export default defineEventHandler(async () => {
  const config = useRuntimeConfig()
  const r = await mcpCall(config.adminMcpUrl, config.adminToken, 'get_platform_health', {})
  try { return JSON.parse(extractText(r) || '{}') } catch { return extractText(r) }
})
