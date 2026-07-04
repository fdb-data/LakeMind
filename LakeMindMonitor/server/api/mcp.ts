const MCP_HEADERS = {
  'Accept': 'application/json, text/event-stream',
  'Content-Type': 'application/json',
}

export async function mcpRead(url: string, token: string, uri: string) {
  const res = await $fetch(url, {
    method: 'POST',
    headers: { ...MCP_HEADERS, Authorization: `Bearer ${token}` },
    body: { jsonrpc: '2.0', id: 1, method: 'resources/read', params: { uri } },
  })
  return res
}

export async function mcpCall(url: string, token: string, tool: string, args: any = {}) {
  const res = await $fetch(url, {
    method: 'POST',
    headers: { ...MCP_HEADERS, Authorization: `Bearer ${token}` },
    body: { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: tool, arguments: args } },
  })
  return res
}

export function extractText(result: any): string {
  if (result?.result?.contents?.[0]?.text) return result.result.contents[0].text
  if (result?.result?.content?.[0]?.text) return result.result.content[0].text
  return JSON.stringify(result)
}
