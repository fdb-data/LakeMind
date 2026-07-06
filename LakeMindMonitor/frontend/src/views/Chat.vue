<template>
<div class="chat-page">
  <el-row :gutter="16">
    <el-col :span="17">
      <el-card shadow="never" class="chat-card">
        <template #header>
          <div class="chat-header">
            <span class="card-title">Steward 对话</span>
            <el-tag :type="stewardOk ? 'success' : 'danger'" size="small" effect="dark">
              {{ stewardOk ? '已连接' : '未连接' }}
            </el-tag>
          </div>
        </template>

        <div class="quick-cmds">
          <el-button v-for="cmd in quickCmds" :key="cmd" size="small" round @click="sendQuick(cmd)">{{ cmd }}</el-button>
        </div>

        <div class="msg-list" ref="msgList">
          <div v-if="!messages.length" class="empty-hint">发送消息开始对话，或点击上方快捷指令</div>
          <div v-for="(msg, i) in messages" :key="i" class="msg" :class="msg.role">
            <div class="msg-role">{{ msg.role === 'user' ? 'You' : 'Steward' }}</div>
            <div class="msg-content">{{ msg.text }}</div>
          </div>
          <div v-if="sending" class="msg steward">
            <div class="msg-role">Steward</div>
            <div class="msg-content typing">正在输入...</div>
          </div>
        </div>

        <div class="chat-input">
          <el-input v-model="input" placeholder="输入消息..." @keyup.enter="send" :disabled="sending" />
          <el-button type="primary" @click="send" :loading="sending" :disabled="!input.trim()">发送</el-button>
        </div>
      </el-card>
    </el-col>

    <el-col :span="7">
      <el-card shadow="never" class="inspect-card">
        <template #header><span class="card-title">巡检</span></template>
        <el-button type="primary" @click="runInspect" :loading="inspecting" style="width:100%;margin-bottom:16px">运行巡检</el-button>

        <div v-if="inspectResult" class="inspect-result">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="状态">
              <el-tag :type="inspectResult.healthy ? 'success' : 'danger'" size="small" effect="dark">
                {{ inspectResult.healthy ? '全部健康' : '发现问题' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="报告">{{ inspectResult.report }}</el-descriptions-item>
            <el-descriptions-item label="问题" v-if="inspectResult.issues?.length">
              <el-tag v-for="iss in inspectResult.issues" :key="iss" type="danger" size="small" effect="dark" style="margin-right:4px">{{ iss }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <h4 style="margin-top:16px">引擎详情</h4>
          <div class="engine-health-grid">
            <div v-for="(val, key) in (inspectResult.health || {})" :key="key" class="engine-health-item">
              <span class="dot" :class="val === true || val === 'ok' ? 'dot-ok' : 'dot-err'"></span>
              {{ key }}
            </div>
          </div>
        </div>
        <el-empty v-else description="点击运行巡检" :image-size="60" />
      </el-card>
    </el-col>
  </el-row>
</div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import api from '../api.js'

const input = ref('')
const messages = ref([])
const sending = ref(false)
const stewardOk = ref(false)
const inspectResult = ref(null)
const inspecting = ref(false)
const msgList = ref(null)

const quickCmds = ['健康检查', '列出用户', '查看租户', '查看知识库', '查看技能', '查看记忆', '查看数据表']

const STORAGE_KEY = 'lakemind-chat-history'

function loadHistory() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) messages.value = JSON.parse(saved)
  } catch {}
}
function saveHistory() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value.slice(-50))) } catch {}
}

async function checkSteward() {
  try {
    const r = await api.stewardHealth()
    stewardOk.value = r.status === 'ok'
  } catch { stewardOk.value = false }
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return
  messages.value.push({ role: 'user', text })
  input.value = ''
  sending.value = true
  saveHistory()
  await scrollToBottom()
  try {
    const r = await api.chat(text)
    messages.value.push({ role: 'steward', text: r.reply || r.message || JSON.stringify(r) })
  } catch {
    messages.value.push({ role: 'steward', text: 'Steward 未就绪' })
  }
  sending.value = false
  saveHistory()
  await scrollToBottom()
}

function sendQuick(cmd) {
  input.value = cmd
  send()
}

async function runInspect() {
  inspecting.value = true
  try { inspectResult.value = await api.inspect() }
  catch { inspectResult.value = { report: '巡检失败', healthy: false, issues: ['Steward 未就绪'], health: {} } }
  finally { inspecting.value = false }
}

async function scrollToBottom() {
  await nextTick()
  if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
}

onMounted(() => { loadHistory(); checkSteward(); scrollToBottom() })
</script>

<style scoped>
.chat-page { max-width: 1400px; margin: 0 auto; }
.card-title { font-size: 14px; font-weight: 600; }
.chat-header { display: flex; justify-content: space-between; align-items: center; }
.quick-cmds { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.msg-list { height: 400px; overflow-y: auto; background: var(--bg-primary); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.empty-hint { color: var(--text-secondary); text-align: center; padding: 40px 0; font-size: 14px; }
.msg { margin: 8px 0; padding: 10px 14px; border-radius: 8px; max-width: 85%; }
.msg.user { background: rgba(88,166,255,.15); margin-left: auto; text-align: right; }
.msg.steward { background: var(--bg-tertiary); margin-right: auto; }
.msg-role { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.msg-content { font-size: 14px; line-height: 1.6; white-space: pre-wrap; word-break: break-all; color: var(--text-primary); }
.typing { color: var(--text-secondary); font-style: italic; }
.chat-input { display: flex; gap: 12px; }
.chat-input .el-input { flex: 1; }
.inspect-card { height: 100%; }
.engine-health-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.engine-health-item { display: flex; align-items: center; gap: 6px; font-size: 13px; padding: 4px 0; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-ok { background: var(--success); }
.dot-err { background: var(--danger); }
h4 { color: var(--text-secondary); font-size: 13px; }
</style>
