export default defineNuxtConfig({
  ssr: true,
  runtimeConfig: {
    assetMcpUrl: 'http://lakemind-asset-mcp:8401/mcp',
    dataMcpUrl: 'http://lakemind-data-mcp:8402/mcp',
    adminMcpUrl: 'http://lakemind-admin-mcp:8403/mcp',
    stewardUrl: 'http://lakemind-steward:8500',
    assetToken: 'test-monitor-token',
    adminToken: 'test-steward-token',
  },
  app: {
    head: { title: 'LakeMind Monitor' }
  }
})
