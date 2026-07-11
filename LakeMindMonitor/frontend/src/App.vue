<template>
<div class="app-layout">
  <header class="app-header">
    <div class="header-left">
      <span class="logo">LakeMind</span>
      <span class="version">v0.1.0</span>
    </div>
    <div class="header-right">
      <el-tag :type="stewardStatus === 'ok' ? 'success' : 'danger'" size="small" effect="dark">
        <el-icon><component :is="stewardStatus === 'ok' ? 'CircleCheck' : 'CircleClose'" /></el-icon>
        Steward {{ stewardStatus === 'ok' ? '已连接' : '未连接' }}
      </el-tag>
    </div>
  </header>
  <div class="app-body">
    <nav class="app-nav">
      <router-link v-for="r in routes" :key="r.path" :to="r.path" class="nav-item">
        <el-icon><component :is="r.meta.icon" /></el-icon>
        <span>{{ r.meta.title }}</span>
      </router-link>
    </nav>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from './api.js'

const router = useRouter()
const routes = router.options.routes.filter(r => r.meta)
const stewardStatus = ref('checking')
let timer = null

async function checkSteward() {
  try {
    const r = await api.stewardHealth()
    stewardStatus.value = r.status === 'ok' ? 'ok' : 'error'
  } catch { stewardStatus.value = 'error' }
}

onMounted(() => {
  checkSteward()
  timer = setInterval(checkSteward, 10000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style>
:root {
  --bg-primary: #0d1117;
  --bg-secondary: #161b22;
  --bg-tertiary: #21262d;
  --border-color: #30363d;
  --text-primary: #f0f6fc;
  --text-secondary: #c9d1d9;
  --text-tertiary: #8b949e;
  --accent: #58a6ff;
  --success: #3fb950;
  --danger: #f85149;
  --warning: #d29922;
}
html { color-scheme: dark; }
body { margin: 0; }
.app-layout { display: flex; flex-direction: column; height: 100vh; background: var(--bg-primary); color: var(--text-primary); font-family: system-ui, -apple-system, sans-serif; }
.app-header { display: flex; align-items: center; justify-content: space-between; padding: 0 24px; height: 56px; background: var(--bg-secondary); border-bottom: 1px solid var(--border-color); }
.header-left { display: flex; align-items: center; gap: 12px; }
.logo { font-size: 20px; font-weight: 700; background: linear-gradient(135deg, #58a6ff, #bc8cff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.version { font-size: 12px; color: var(--text-tertiary); }
.header-right { display: flex; align-items: center; gap: 12px; }
.app-body { display: flex; flex: 1; overflow: hidden; }
.app-nav { width: 200px; background: var(--bg-secondary); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; padding: 16px 0; gap: 4px; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 10px 24px; color: var(--text-secondary); text-decoration: none; font-size: 14px; transition: all .2s; }
.nav-item:hover { color: var(--text-primary); background: var(--bg-tertiary); }
.nav-item.router-link-active { color: var(--accent); background: rgba(88,166,255,.1); border-right: 2px solid var(--accent); }
.app-main { flex: 1; overflow-y: auto; padding: 24px; }

.el-card { background: var(--bg-secondary) !important; border-color: var(--border-color) !important; color: var(--text-primary) !important; }
.el-card__header { border-bottom-color: var(--border-color) !important; color: var(--text-primary) !important; }
.el-table { background: var(--bg-secondary) !important; color: var(--text-primary) !important; }
.el-table th.el-table__cell { background: var(--bg-tertiary) !important; color: var(--text-primary) !important; }
.el-table th.el-table__cell .cell { color: var(--text-primary) !important; }
.el-table tr { background: var(--bg-secondary) !important; }
.el-table tr.el-table__row--striped { background: var(--bg-primary) !important; }
.el-table tr.el-table__row--striped td.el-table__cell { background: var(--bg-primary) !important; }
.el-table td.el-table__cell { color: var(--text-primary) !important; }
.el-table td.el-table__cell .cell { color: var(--text-primary) !important; }
.el-table--enable-row-hover .el-table__body tr:hover > td { background: var(--bg-tertiary) !important; }
.el-table td.el-table__cell, .el-table th.el-table__cell { border-bottom-color: var(--border-color) !important; }
.el-table__empty-text { color: var(--text-secondary) !important; }
.el-table__inner-wrapper { background: var(--bg-secondary) !important; }
.el-table__body-wrapper { background: var(--bg-secondary) !important; }
.el-table--border .el-table__cell { border-right-color: var(--border-color) !important; }
.el-input__wrapper { background-color: var(--bg-tertiary) !important; box-shadow: 0 0 0 1px var(--border-color) inset !important; }
.el-input__inner { color: var(--text-primary) !important; }
.el-input__inner::placeholder { color: var(--text-tertiary) !important; }
.el-tabs__item { color: var(--text-secondary) !important; }
.el-tabs__item.is-active { color: var(--accent) !important; }
.el-tabs__active-bar { background-color: var(--accent) !important; }
.el-tabs__nav-wrap::after { background-color: var(--border-color) !important; }
.el-dialog { background: var(--bg-secondary) !important; }
.el-dialog__title { color: var(--text-primary) !important; }
.el-dialog__body { color: var(--text-primary) !important; }
.el-descriptions { color: var(--text-primary) !important; }
.el-descriptions__label { color: var(--text-secondary) !important; background-color: var(--bg-tertiary) !important; }
.el-descriptions__content { color: var(--text-primary) !important; background-color: var(--bg-secondary) !important; }
.el-descriptions__cell { background-color: var(--bg-secondary) !important; }
.el-descriptions__label.el-descriptions__cell.is-bordered-label { background-color: var(--bg-tertiary) !important; }
.el-tag { background-color: var(--bg-tertiary) !important; color: var(--text-primary) !important; border-color: var(--border-color) !important; }
.el-tag--dark { border-color: transparent !important; }
.el-tag--success { background-color: rgba(63,185,80,.15) !important; color: var(--success) !important; border-color: rgba(63,185,80,.3) !important; }
.el-tag--danger { background-color: rgba(248,81,73,.15) !important; color: var(--danger) !important; border-color: rgba(248,81,73,.3) !important; }
.el-tag--info { background-color: rgba(139,148,158,.15) !important; color: var(--text-secondary) !important; border-color: var(--border-color) !important; }
.el-tag--warning { background-color: rgba(210,153,34,.15) !important; color: var(--warning) !important; border-color: rgba(210,153,34,.3) !important; }
.el-alert { background-color: var(--bg-tertiary) !important; border: 1px solid var(--border-color) !important; }
.el-alert__content { color: var(--text-primary) !important; }
.el-alert__title { color: var(--text-primary) !important; }
.el-alert__description { color: var(--text-secondary) !important; }
.el-empty__description p { color: var(--text-secondary) !important; }
.el-button--primary:not(.is-link):not(.is-text) { background-color: var(--accent) !important; border-color: var(--accent) !important; }
.el-button--default { background-color: var(--bg-tertiary) !important; border-color: var(--border-color) !important; color: var(--text-primary) !important; }
.el-button--default:hover { color: var(--accent) !important; border-color: var(--accent) !important; }
.el-button.is-link { color: var(--accent) !important; }
.el-button.is-link:hover { color: #7ab7ff !important; }
.el-button--primary.is-link { color: var(--accent) !important; }
.el-button--primary.is-link:hover { color: #7ab7ff !important; }
.el-loading-mask { background-color: rgba(13,17,23,.8) !important; }
.el-loading-spinner .el-loading-text { color: var(--text-secondary) !important; }
.el-loading-spinner .path { stroke: var(--accent) !important; }
.el-switch__label { color: var(--text-secondary) !important; }
.el-switch.is-checked .el-switch__label { color: var(--accent) !important; }
.el-link--primary { color: var(--accent) !important; }
.el-pagination button { color: var(--text-secondary) !important; background-color: var(--bg-secondary) !important; }
.el-pagination .el-pager li { color: var(--text-secondary) !important; background-color: var(--bg-secondary) !important; }
.el-pagination .el-pager li.is-active { color: var(--accent) !important; }
.el-select__wrapper { background-color: var(--bg-tertiary) !important; box-shadow: 0 0 0 1px var(--border-color) inset !important; }
.el-select__placeholder { color: var(--text-primary) !important; }
.el-tooltip__trigger { color: var(--text-primary) !important; }
.el-popover.el-popper { background: var(--bg-secondary) !important; color: var(--text-primary) !important; border-color: var(--border-color) !important; }
.el-popper.is-light { background: var(--bg-secondary) !important; color: var(--text-primary) !important; border-color: var(--border-color) !important; }
</style>
