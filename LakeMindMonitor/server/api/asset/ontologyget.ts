import { mcpRead, extractText } from '../mcp'

export default defineEventHandler(async () => {
  const config = useRuntimeConfig()
  const r = await mcpRead(config.assetMcpUrl, config.assetToken, 'lake://ontology')
  try { return JSON.parse(extractText(r) || '[]') } catch { return extractText(r) }
})

