<template>
<div class="data-page">
  <h2>数据引擎</h2>
  <el-tabs v-model="activeTab" @tab-change="onTabChange">
    <el-tab-pane label="Iceberg 表" name="iceberg">
      <el-table :data="tableList" v-loading="loading.iceberg" stripe>
        <el-table-column prop="namespace" label="Namespace" width="150" />
        <el-table-column prop="name" label="表名" min-width="180" />
        <el-table-column prop="column_count" label="列数" width="80" />
        <el-table-column prop="row_count" label="行数" width="100" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="describeTable(row)">描述</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="向量表" name="vectors">
      <el-table :data="vectorList" v-loading="loading.vectors" stripe>
        <el-table-column prop="name" label="表名" min-width="200" />
        <el-table-column prop="dim" label="维度" width="100" />
        <el-table-column prop="row_count" label="行数" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="S3 对象" name="s3">
      <div class="filter-bar">
        <el-input v-model="s3Prefix" placeholder="前缀过滤" clearable style="width:300px" @keyup.enter="loadS3" />
        <el-button type="primary" @click="loadS3">搜索</el-button>
      </div>
      <el-table :data="s3List" v-loading="loading.s3" stripe>
        <el-table-column prop="key" label="Key" min-width="300" show-overflow-tooltip />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="last_modified" label="修改时间" width="180" />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="KV" name="kv">
      <div class="filter-bar">
        <el-input v-model="kvPrefix" placeholder="前缀过滤" clearable style="width:300px" @keyup.enter="loadKV" />
        <el-button type="primary" @click="loadKV">扫描</el-button>
      </div>
      <el-table :data="kvList" v-loading="loading.kv" stripe>
        <el-table-column prop="key" label="Key" min-width="200" show-overflow-tooltip />
        <el-table-column label="Value (预览)" min-width="300" show-overflow-tooltip>
          <template #default="{ row }">{{ String(row.value || '').slice(0, 100) }}</template>
        </el-table-column>
        <el-table-column label="TTL" width="100">
          <template #default="{ row }">{{ row.ttl > 0 ? row.ttl + 's' : '永久' }}</template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="图" name="graph">
      <el-card shadow="never" v-loading="loading.graph">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="节点数">{{ graphData.node_count || graphData.nodes?.length || 0 }}</el-descriptions-item>
          <el-descriptions-item label="边数">{{ graphData.edge_count || graphData.edges?.length || 0 }}</el-descriptions-item>
          <el-descriptions-item label="关系类型">
            <el-tag v-for="r in relationTypes" :key="r" size="small" style="margin-right:4px">{{ r }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <h4 style="margin-top:20px">采样节点</h4>
        <el-table :data="graphNodes" stripe size="small">
          <el-table-column prop="id" label="节点" min-width="150" />
          <el-table-column prop="type" label="类型" width="120" />
          <el-table-column prop="edge_count" label="关联边数" width="100" />
        </el-table>
      </el-card>
    </el-tab-pane>
  </el-tabs>

  <el-dialog v-model="schemaDialogVisible" :title="`表结构: ${currentTable}`" width="600px">
    <el-table :data="schemaColumns" stripe size="small">
      <el-table-column prop="name" label="列名" min-width="150" />
      <el-table-column prop="type" label="类型" width="120" />
      <el-table-column prop="comment" label="注释" min-width="200" />
    </el-table>
  </el-dialog>
</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../api.js'

const activeTab = ref('iceberg')
const loading = reactive({ iceberg: false, vectors: false, s3: false, kv: false, graph: false })
const tableList = ref([])
const vectorList = ref([])
const s3List = ref([])
const kvList = ref([])
const graphData = ref({})
const s3Prefix = ref('')
const kvPrefix = ref('')
const schemaDialogVisible = ref(false)
const currentTable = ref('')
const schemaColumns = ref([])

function normalizeList(data) {
  if (Array.isArray(data)) return data
  if (data?.tables) return data.tables
  if (data?.items) return data.items
  if (data?.results) return data.results
  return []
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

const graphNodes = computed(() => graphData.value.nodes || graphData.value.node_list || [])
const relationTypes = computed(() => {
  const edges = graphData.value.edges || graphData.value.edge_list || []
  return [...new Set(edges.map(e => e.relation || e.type).filter(Boolean))]
})

async function loadTables() {
  loading.iceberg = true
  try { tableList.value = normalizeList(await api.dataTables()) }
  catch { tableList.value = [] }
  finally { loading.iceberg = false }
}
async function loadVectors() {
  loading.vectors = true
  try { vectorList.value = normalizeList(await api.dataVectors()) }
  catch { vectorList.value = [] }
  finally { loading.vectors = false }
}
async function loadS3() {
  loading.s3 = true
  try { s3List.value = normalizeList(await api.dataS3(s3Prefix.value)) }
  catch { s3List.value = [] }
  finally { loading.s3 = false }
}
async function loadKV() {
  loading.kv = true
  try { kvList.value = normalizeList(await api.dataKV(kvPrefix.value)) }
  catch { kvList.value = [] }
  finally { loading.kv = false }
}
async function loadGraph() {
  loading.graph = true
  try { graphData.value = await api.dataGraph() }
  catch { graphData.value = {} }
  finally { loading.graph = false }
}

async function describeTable(row) {
  const ns = row.namespace || 'default'
  const name = row.name || row.table_name
  currentTable.value = `${ns}.${name}`
  schemaDialogVisible.value = true
  try {
    const schema = await api.dataTableDescribe(ns, name)
    schemaColumns.value = schema.columns || schema.schema || schema.fields || []
  } catch { schemaColumns.value = [] }
}

function onTabChange(tab) {
  if (tab === 'iceberg' && !tableList.value.length) loadTables()
  if (tab === 'vectors' && !vectorList.value.length) loadVectors()
  if (tab === 's3' && !s3List.value.length) loadS3()
  if (tab === 'kv' && !kvList.value.length) loadKV()
  if (tab === 'graph' && !Object.keys(graphData.value).length) loadGraph()
}

onMounted(() => { loadTables(); loadVectors(); loadGraph() })
</script>

<style scoped>
.data-page { max-width: 1400px; margin: 0 auto; }
.data-page h2 { margin: 0 0 20px; font-size: 20px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
h4 { color: var(--text-secondary); font-size: 14px; }
</style>
