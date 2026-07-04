<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const messages = ref<{ role: 'user' | 'assistant'; text: string; mode?: string }[]>([])
const input = ref('')
const mode = ref<string>('')
const sending = ref(false)

async function send() {
  if (!input.value.trim() || sending.value) return
  const msg = input.value
  messages.value.push({ role: 'user', text: msg })
  input.value = ''
  sending.value = true
  try {
    const { data } = await api.post('/chat', null, { params: { message: msg } })
    mode.value = data.mode
    messages.value.push({ role: 'assistant', text: JSON.stringify(data.reply, null, 2), mode: data.mode })
  } catch (e: any) {
    messages.value.push({ role: 'assistant', text: '请求失败: ' + (e.response?.data?.detail || e.message) })
  }
  sending.value = false
}
onMounted(() => {
  messages.value.push({ role: 'assistant', text: '请输入问题。当前为只读直连模式（Steward 未就绪），可问：健康、数据、知识、技能、记忆、经验、能力、工作区。' })
})
</script>

<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>Steward 对话窗</span>
        <el-tag :type="mode === 'steward' ? 'success' : 'warning'" size="small">
          {{ mode === 'steward' ? 'Steward 已连接' : '只读直连模式（Steward 未就绪）' }}
        </el-tag>
      </div>
    </template>
    <div style="height: 400px; overflow: auto; background: #f9f9f9; padding: 12px; border-radius: 4px">
      <div v-for="(m, i) in messages" :key="i" :style="{ textAlign: m.role === 'user' ? 'right' : 'left', margin: '8px 0' }">
        <el-tag :type="m.role === 'user' ? 'primary' : 'info'" effect="plain">
          <pre style="margin: 0; white-space: pre-wrap; display: inline">{{ m.text }}</pre>
        </el-tag>
      </div>
    </div>
    <div style="margin-top: 12px; display: flex; gap: 8px">
      <el-input v-model="input" placeholder="输入消息..." @keyup.enter="send" :disabled="sending" />
      <el-button type="primary" @click="send" :loading="sending">发送</el-button>
    </div>
  </el-card>
</template>
