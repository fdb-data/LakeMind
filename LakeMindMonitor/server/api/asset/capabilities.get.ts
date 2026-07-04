import { mcpRead, extractText } from '../mcp'

export default defineEventHandler(async () => {
  const config = useRuntimeConfig()
  const r = await mcpRead(config.assetMcpUrl, config.assetToken, 'lake://capabilities')
  return JSON.parse(extractText(r) || '{}')
})
