export default defineEventHandler(async () => {
  const config = useRuntimeConfig()
  const services: Record<string, string> = {}
  for (const [name, port] of [['asset-mcp', 8401], ['data-mcp', 8402], ['admin-mcp', 8403], ['steward', 8500]]) {
    try {
      await $fetch(`http://lakemind-${name}:${port}/health`, { timeout: 3000 })
      services[name] = 'ok'
    } catch {
      services[name] = 'error'
    }
  }
  return services
})
