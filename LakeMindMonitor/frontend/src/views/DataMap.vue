<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get } from '../api'

const tables = ref<any[]>([])
const detail = ref<any>(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try { tables.value = await get('/data') } catch { tables.value = [] }
  loading.value = false
}
async function show(row: any) {
  try { detail.value = await get(`/data/${row.name}`) } catch { detail.value = { error: '加载失败' } }
}
onMounted(load)
</script>

<template>
  <el-card header="数据集列表">
    <el-table :data="tables" :loading="loading" @row-click="show" highlight-current-row>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="row_count" label="行数" />
      <el-table-column label="列">
        <template #default="{ row }">{{ row.columns?.length || row.schema?.length || '-' }}</template>
      </el-table-column>
    </el-table>
  </el-card>
  <el-dialog v-model="detail" title="数据集详情" width="60%" v-if="detail">
    <pre style="background: #f5f5f5; padding: 12px; overflow: auto">{{ JSON.stringify(detail, null, 2) }}</pre>
  </el-dialog>
</template>
