<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get } from '../api'
const overview = ref<any>(null)
async function load() { try { overview.value = await get('/memory') } catch { overview.value = null } }
onMounted(load)
</script>
<template>
  <el-card header="记忆概况">
    <el-descriptions :column="1" border v-if="overview">
      <el-descriptions-item label="agent_id">{{ overview.agent_id }}</el-descriptions-item>
      <el-descriptions-item label="tenant_id">{{ overview.tenant_id }}</el-descriptions-item>
      <el-descriptions-item label="长期记忆数">{{ overview.long_term_count }}</el-descriptions-item>
      <el-descriptions-item label="短期记忆键数">{{ overview.short_term_keys?.length }}</el-descriptions-item>
    </el-descriptions>
    <el-empty v-else description="暂无记忆数据" />
  </el-card>
</template>
