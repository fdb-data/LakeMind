export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const body = await readBody(event)
  try {
    const res = await $fetch(`${config.stewardUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { message: body.message },
      timeout: 30000,
    })
    return res
  } catch (e) {
    return { reply: 'Steward 未就绪', mode: 'unavailable' }
  }
})
