<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get } from '../api'
const items = ref<any[]>([])
const loading = ref(false)
async function load() { loading.value = true; try { items.value = await get('/skills') } catch { items.value = [] }; loading.value = false }
onMounted(load)
</script>
<template>
  <el-card header="技能列表">
    <el-table :data="items" :loading="loading">
      <el-table-column prop="skill_id" label="ID" width="140" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column prop="version" label="版本" width="100" />
    </el-table>
  </el-card>
</template>
