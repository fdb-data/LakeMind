import axios from 'axios'

export const api = axios.create({ baseURL: '/api', timeout: 15000 })

export async function get<T = any>(url: string): Promise<T> {
  const { data } = await api.get(url)
  return data
}

export async function post<T = any>(url: string, body: any): Promise<T> {
  const { data } = await api.post(url, body, { params: body && url === '/chat' ? { message: body.message } : undefined })
  return data
}
