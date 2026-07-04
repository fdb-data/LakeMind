<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useSystemHealth, healthTag } from '../stores/health'
import { get } from '../api'

const { health, load } = useSystemHealth()
const mcpConnected = ref<boolean | null>(null)
let timer: any
async function refresh() {
  await load()
  try { mcpConnected.value = (await get<any>('/health')).mcp_connected } catch { mcpConnected.value = false }
}
onMounted(() => { refresh(); timer = setInterval(refresh, 10000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <el-card header="MCP 连通性">
    <el-tag :type="mcpConnected ? 'success' : 'danger'" effect="dark" size="large">
      MCP {{ mcpConnected ? '已连接' : '未连接' }}
    </el-tag>
  </el-card>
  <el-card header="数据平面组件" style="margin-top: 16px">
    <el-table :data="Object.entries(health || {}).map(([k, v]) => ({ component: k, status: v }))">
      <el-table-column prop="component" label="组件" />
      <el-table-column label="状态">
        <template #default="{ row }">
          <el-tag :type="healthTag(row.status)" effect="dark">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
    <p style="color: #999; font-size: 12px">每 10 秒自动刷新</p>
  </el-card>
</template>
