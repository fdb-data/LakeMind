<template>
<div class="admin-page">
  <h2>管理 <el-tag type="info" size="small" effect="dark">只读</el-tag></h2>
  <el-tabs v-model="activeTab" @tab-change="onTabChange">
    <el-tab-pane label="租户" name="tenants">
      <el-table :data="tenantList" v-loading="loading.tenants" stripe>
        <el-table-column prop="tenant_id" label="ID" min-width="150" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.deleted ? 'danger' : 'success'" size="small" effect="dark">{{ row.deleted ? '禁用' : '活跃' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="用户" name="users">
      <el-table :data="userList" v-loading="loading.users" stripe>
        <el-table-column prop="user_id" label="ID" min-width="120" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="tenant_id" label="租户" min-width="120" />
        <el-table-column prop="role" label="角色" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.deleted ? 'danger' : 'success'" size="small" effect="dark">{{ row.deleted ? '禁用' : '活跃' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="Token" name="tokens">
      <el-alert type="info" :closable="false" style="margin-bottom:16px">
        Token 已脱敏展示，此页面为只读，无法签发或吊销 Token。
      </el-alert>
      <el-table :data="tokenList" v-loading="loading.tokens" stripe>
        <el-table-column prop="token_id" label="ID" min-width="120" show-overflow-tooltip />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="scope" label="Scope" width="100" />
        <el-table-column prop="tenant_id" label="租户" min-width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.revoked ? 'danger' : 'success'" size="small" effect="dark">{{ row.revoked ? '已吊销' : '有效' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="资产类型" name="assetTypes">
      <el-table :data="assetTypeList" v-loading="loading.assetTypes" stripe>
        <el-table-column prop="name" label="类型" min-width="120" />
        <el-table-column label="能力" min-width="300">
          <template #default="{ row }">
            <el-tag v-for="c in (row.capabilities || row.tools || [])" :key="c" size="small" style="margin-right:4px">{{ c }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="engine" label="引擎" width="150" />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="平台健康" name="health">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span class="card-title">引擎健康详情</span></template>
            <el-table :data="engineRows" v-loading="loading.health" stripe size="small">
              <el-table-column prop="label" label="引擎" min-width="120" />
              <el-table-column prop="category" label="类别" width="100" />
              <el-table-column label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.healthy ? 'success' : 'danger'" size="small" effect="dark">{{ row.healthy ? 'OK' : 'ERR' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="plugin" label="插件" min-width="120" />
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span class="card-title">节点状态</span></template>
            <el-table :data="nodeList" v-loading="loading.health" stripe size="small">
              <el-table-column prop="name" label="节点" min-width="150" />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'active' || row.status === 'ok' ? 'success' : 'danger'" size="small" effect="dark">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="port" label="端口" width="100" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </el-tab-pane>
  </el-tabs>
</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../api.js'

const activeTab = ref('tenants')
const loading = reactive({ tenants: false, users: false, tokens: false, assetTypes: false, health: false })
const tenantList = ref([])
const userList = ref([])
const tokenList = ref([])
const assetTypeList = ref([])
const healthData = ref({})
const nodeData = ref({})

const ENGINE_LABELS = {
  object_storage: { label: '对象存储', category: 'storage', plugin: 'SeaweedFS' },
  tabular: { label: '表格式', category: 'storage', plugin: 'Iceberg' },
  vector: { label: '向量', category: 'storage', plugin: 'Lance' },
  kv: { label: 'KV', category: 'storage', plugin: 'Valkey' },
  graph: { label: '图', category: 'storage', plugin: 'PostgreSQL' },
  metadata: { label: '元数据', category: 'storage', plugin: 'PostgreSQL' },
  sql: { label: 'SQL', category: 'compute', plugin: 'DuckDB' },
  distributed: { label: '分布式', category: 'compute', plugin: 'Ray' },
  memory: { label: '记忆', category: 'cognitive', plugin: 'mem0' },
  model_serving: { label: '模型服务', category: 'cognitive', plugin: 'litellm+fastembed+FunASR' },
}

const engineRows = computed(() => {
  return Object.entries(healthData.value).map(([key, val]) => ({
    key,
    label: ENGINE_LABELS[key]?.label || key,
    category: ENGINE_LABELS[key]?.category || '',
    plugin: ENGINE_LABELS[key]?.plugin || '',
    healthy: val === true || val === 'ok',
  }))
})
const nodeList = computed(() => nodeData.value.nodes || nodeData.value || [])

function normalizeList(data) {
  if (Array.isArray(data)) return data
  if (data?.tenants) return data.tenants
  if (data?.users) return data.users
  if (data?.tokens) return data.tokens
  if (data?.items) return data.items
  if (data?.results) return data.results
  return []
}

async function loadTenants() {
  loading.tenants = true
  try { tenantList.value = normalizeList(await api.adminTenants()) }
  catch { tenantList.value = [] }
  finally { loading.tenants = false }
}
async function loadUsers() {
  loading.users = true
  try { userList.value = normalizeList(await api.adminUsers()) }
  catch { userList.value = [] }
  finally { loading.users = false }
}
async function loadTokens() {
  loading.tokens = true
  try { tokenList.value = normalizeList(await api.adminTokens()) }
  catch { tokenList.value = [] }
  finally { loading.tokens = false }
}
async function loadAssetTypes() {
  loading.assetTypes = true
  try { assetTypeList.value = normalizeList(await api.adminAssetTypes()) }
  catch { assetTypeList.value = [] }
  finally { loading.assetTypes = false }
}
async function loadHealth() {
  loading.health = true
  try {
    healthData.value = await api.adminHealth()
    nodeData.value = await api.adminNodes()
  } catch { healthData.value = {}; nodeData.value = {} }
  finally { loading.health = false }
}

function onTabChange(tab) {
  if (tab === 'tenants' && !tenantList.value.length) loadTenants()
  if (tab === 'users' && !userList.value.length) loadUsers()
  if (tab === 'tokens' && !tokenList.value.length) loadTokens()
  if (tab === 'assetTypes' && !assetTypeList.value.length) loadAssetTypes()
  if (tab === 'health' && !Object.keys(healthData.value).length) loadHealth()
}

onMounted(() => { loadTenants(); loadUsers(); loadTokens(); loadAssetTypes(); loadHealth() })
</script>

<style scoped>
.admin-page { max-width: 1400px; margin: 0 auto; }
.admin-page h2 { margin: 0 0 20px; font-size: 20px; display: flex; align-items: center; gap: 12px; }
.card-title { font-size: 14px; font-weight: 600; }
</style>
