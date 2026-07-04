<template>
  <div>
    <h1>Chat with Steward</h1>
    <NuxtLink to="/">← Back</NuxtLink>
    <div class="chat-box">
      <div v-for="(msg, i) in messages" :key="i" class="msg" :class="msg.role">
        <strong>{{ msg.role }}:</strong> {{ msg.text }}
      </div>
    </div>
    <input v-model="input" @keyup.enter="send" placeholder="Ask Steward..." />
    <button @click="send">Send</button>
    <p v-if="stewardDown" class="warn">Steward 未就绪</p>
  </div>
</template>

<script setup>
const input = ref('')
const messages = ref([])
const stewardDown = ref(false)

async function send() {
  if (!input.value.trim()) return
  const userMsg = input.value
  messages.value.push({ role: 'user', text: userMsg })
  input.value = ''
  try {
    const res = await $fetch('/api/chat', { method: 'POST', body: { message: userMsg } })
    messages.value.push({ role: 'steward', text: res.reply || JSON.stringify(res) })
    stewardDown.value = false
  } catch (e) {
    stewardDown.value = true
    messages.value.push({ role: 'steward', text: 'Steward 未就绪' })
  }
}
</script>

<style>
.chat-box { border: 1px solid #ddd; padding: 12px; min-height: 300px; margin: 12px 0; }
.msg { margin: 4px 0; }
.msg.user { color: #0066cc; }
.msg.steward { color: #006600; }
.warn { color: #cc6600; }
input { width: 70%; padding: 8px; }
button { padding: 8px 16px; }
</style>
