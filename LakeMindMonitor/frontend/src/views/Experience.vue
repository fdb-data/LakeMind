<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get } from '../api'
const items = ref<any[]>([])
const loading = ref(false)
async function load() { loading.value = true; try { items.value = await get('/experience') } catch { items.value = [] }; loading.value = false }
onMounted(load)
const typeColor: Record<string, string> = { success: 'success', failure: 'danger', reflection: 'warning' }
</script>
<template>
  <el-card header="经验记录">
    <el-table :data="items" :loading="loading">
      <el-table-column prop="exp_id" label="ID" width="140" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }"><el-tag :type="(typeColor[row.type] as any) || 'info'" size="small">{{ row.type }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="content" label="内容" show-overflow-tooltip />
      <el-table-column label="标签">
        <template #default="{ row }">{{ row.tags?.join(', ') }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="200" />
    </el-table>
  </el-card>
</template>
