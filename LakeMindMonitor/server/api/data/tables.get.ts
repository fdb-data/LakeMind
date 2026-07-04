import { mcpCall, extractText } from '../mcp'

export default defineEventHandler(async () => {
  const config = useRuntimeConfig()
  const r = await mcpCall(config.dataMcpUrl, config.adminToken, 'data_list_tables', {})
  try { return JSON.parse(extractText(r) || '{}') } catch { return extractText(r) }
})
