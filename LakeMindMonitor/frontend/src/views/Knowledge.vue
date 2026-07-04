<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get } from '../api'
const items = ref<any[]>([])
const loading = ref(false)
async function load() { loading.value = true; try { items.value = await get('/knowledge') } catch { items.value = [] }; loading.value = false }
onMounted(load)
</script>
<template>
  <el-card header="知识库">
    <el-table :data="items" :loading="loading">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="row_count" label="文档数" />
      <el-table-column label="schema">
        <template #default="{ row }">{{ Array.isArray(row.schema) ? row.schema.join(', ') : '-' }}</template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
