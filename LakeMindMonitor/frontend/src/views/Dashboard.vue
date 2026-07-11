<template>
<div class="dashboard">
  <div class="dash-header">
    <h2>系统总览</h2>
    <div class="dash-actions">
      <el-switch v-model="autoRefresh" active-text="自动刷新" @change="toggleRefresh" />
      <span class="refresh-info" v-if="autoRefresh">每 15s 刷新</span>
      <el-button :icon="Refresh" circle size="small" @click="loadData" :loading="loading" />
    </div>
  </div>

  <el-row :gutter="16" class="section">
    <el-col :span="24">
      <el-card shadow="never">
        <template #header><span class="card-title">容器状态 ({{ containers.length }})</span></template>
        <div class="container-grid">
          <div v-for="c in containers" :key="c.name" class="container-item" :class="`status-${c.status}`">
            <span class="dot" :class="`dot-${c.status}`"></span>
            <span class="name">{{ c.name }}</span>
            <span class="port" v-if="c.port">:{{ c.port }}</span>
            <span class="cat">{{ c.category }}</span>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>

  <el-row :gutter="16" class="section">
    <el-col :span="24">
      <el-card shadow="never">
        <template #header>
          <span class="card-title">引擎健康 ({{ healthyEngines }}/{{ engines.length }})</span>
        </template>
        <div class="engine-grid">
          <div v-for="e in engines" :key="e.key" class="engine-item" :class="{ 'engine-ok': e.status, 'engine-err': !e.status }">
            <el-icon><component :is="e.status ? 'CircleCheck' : 'CircleClose'" /></el-icon>
            <span class="label">{{ e.label }}</span>
            <span class="plugin">{{ e.plugin }}</span>
            <span class="cat">{{ e.category }}</span>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>

  <el-row :gutter="16" class="section">
    <el-col :span="8">
      <el-card shadow="never">
        <template #header><span class="card-title">资产计数</span></template>
        <div class="stat-list">
          <div class="stat-row"><span>知识库</span><b>{{ data.assets?.knowledgeCount ?? '-' }}</b></div>
          <div class="stat-row"><span>技能</span><b>{{ data.assets?.skillCount ?? '-' }}</b></div>
          <div class="stat-row"><span>记忆</span><b>{{ data.assets?.memoryTotal ?? '-' }}</b></div>
          <div class="stat-row"><span>本体节点</span><b>{{ data.assets?.ontologyNodes ?? '-' }}</b></div>
          <div class="stat-row"><span>本体边</span><b>{{ data.assets?.ontologyEdges ?? '-' }}</b></div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card shadow="never">
        <template #header><span class="card-title">数据计数</span></template>
        <div class="stat-list">
          <div class="stat-row"><span>Iceberg 表</span><b>{{ data.data?.tableCount ?? '-' }}</b></div>
          <div class="stat-row"><span>向量表</span><b>{{ data.data?.vectorCount ?? '-' }}</b></div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card shadow="never">
        <template #header><span class="card-title">平台信息</span></template>
        <div class="stat-list">
          <div class="stat-row"><span>租户</span><b>{{ data.platform?.tenantCount ?? '-' }}</b></div>
          <div class="stat-row"><span>用户</span><b>{{ data.platform?.userCount ?? '-' }}</b></div>
          <div class="stat-row"><span>Token</span><b>{{ data.platform?.tokenCount ?? '-' }}</b></div>
          <div class="stat-row"><span>资产类型</span><b>{{ data.platform?.assetTypeCount ?? '-' }}</b></div>
          <div class="stat-row"><span>模型服务</span><b>{{ modelServingStatus }}</b></div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import api from '../api.js'

const loading = ref(false)
const data = ref({})
const autoRefresh = ref(true)
const modelServingStatus = ref('-')
let timer = null

const containers = computed(() => data.value.containers || [])
const engines = computed(() => data.value.engines || [])
const healthyEngines = computed(() => engines.value.filter(e => e.status).length)

async function loadData() {
  loading.value = true
  try { data.value = await api.dashboard() }
  catch { data.value = {} }
  finally { loading.value = false }
  try {
    const ms = await api.modelServingHealth()
    const s = ms.services || {}
    const parts = []
    if (s.gateway) parts.push('LLM')
    if (s.embedding) parts.push('Embed')
    if (s.asr) parts.push('ASR')
    modelServingStatus.value = parts.length ? parts.join('+') : 'ERR'
  } catch { modelServingStatus.value = 'ERR' }
}

function toggleRefresh(val) {
  if (timer) clearInterval(timer)
  if (val) timer = setInterval(loadData, 15000)
}

onMounted(() => { loadData(); if (autoRefresh.value) timer = setInterval(loadData, 15000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.dashboard { max-width: 1400px; margin: 0 auto; }
.dash-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.dash-header h2 { margin: 0; font-size: 20px; }
.dash-actions { display: flex; align-items: center; gap: 12px; }
.refresh-info { font-size: 12px; color: var(--text-secondary); }
.section { margin-bottom: 16px; }
.card-title { font-size: 14px; font-weight: 600; }
.container-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }
.container-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 6px; background: var(--bg-tertiary); font-size: 13px; }
.container-item .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-ok { background: var(--success); box-shadow: 0 0 6px var(--success); }
.dot-error { background: var(--danger); box-shadow: 0 0 6px var(--danger); }
.dot-unknown { background: var(--text-secondary); }
.container-item .name { font-weight: 600; }
.container-item .port { color: var(--text-secondary); font-size: 12px; }
.container-item .cat { margin-left: auto; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; }
.engine-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.engine-item { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 6px; background: var(--bg-tertiary); font-size: 13px; }
.engine-ok { border-left: 3px solid var(--success); }
.engine-err { border-left: 3px solid var(--danger); }
.engine-item .label { font-weight: 600; }
.engine-item .plugin { color: var(--text-secondary); font-size: 12px; }
.engine-item .cat { margin-left: auto; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; }
.stat-list { display: flex; flex-direction: column; gap: 12px; }
.stat-row { display: flex; justify-content: space-between; align-items: center; }
.stat-row span { color: var(--text-secondary); font-size: 14px; }
.stat-row b { font-size: 20px; font-weight: 700; color: var(--accent); }
</style>
