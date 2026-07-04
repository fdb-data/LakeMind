import { ref } from 'vue'
import { get } from '../api'

export interface SystemHealth { s3: string; dragonfly: string; gravitino: string; embedding: string }

export function useSystemHealth() {
  const health = ref<SystemHealth | null>(null)
  const loading = ref(false)
  async function load() {
    loading.value = true
    try { health.value = await get<SystemHealth>('/system-health') } catch { health.value = null }
    loading.value = false
  }
  return { health, loading, load }
}

export function healthTag(value: string | undefined): 'success' | 'danger' {
  return value === 'ok' ? 'success' : 'danger'
}
