<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { get } from './api'

const route = useRoute()
const mcpConnected = ref<boolean | null>(null)
const navItems = [
  { path: '/', icon: '📊', label: '总览' },
  { path: '/health', icon: '💚', label: '组件健康' },
  { path: '/data', icon: '🗄️', label: '数据地图' },
  { path: '/knowledge', icon: '📚', label: '知识库' },
  { path: '/skills', icon: '🛠️', label: '技能' },
  { path: '/memory', icon: '🧠', label: '记忆' },
  { path: '/experience', icon: '📝', label: '经验' },
  { path: '/chat', icon: '💬', label: '对话' },
]

async function refreshHealth() {
  try {
    const h = await get<any>('/health')
    mcpConnected.value = h.mcp_connected
  } catch {
    mcpConnected.value = false
  }
}
onMounted(() => { refreshHealth(); setInterval(refreshHealth, 10000) })
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside width="200px" style="background: #304156">
      <div style="padding: 20px; color: #fff; font-size: 18px; font-weight: bold">LakeMind Monitor</div>
      <el-menu :default-active="route.path" router background-color="#304156" text-color="#bfcbd9" active-text-color="#409eff">
        <el-menu-item v-for="item in navItems" :key="item.path" :index="item.path">
          <span>{{ item.icon }} {{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #eee">
        <h3 style="margin: 0">{{ route.meta.title || 'LakeMind Monitor' }}</h3>
        <el-tag :type="mcpConnected ? 'success' : 'danger'" effect="dark">
          MCP {{ mcpConnected ? '已连接' : '未连接' }}
        </el-tag>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
