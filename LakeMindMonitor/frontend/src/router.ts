import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: '总览' } },
    { path: '/health', name: 'health', component: () => import('./views/Health.vue'), meta: { title: '组件健康' } },
    { path: '/data', name: 'data', component: () => import('./views/DataMap.vue'), meta: { title: '数据地图' } },
    { path: '/knowledge', name: 'knowledge', component: () => import('./views/Knowledge.vue'), meta: { title: '知识库' } },
    { path: '/skills', name: 'skills', component: () => import('./views/Skills.vue'), meta: { title: '技能' } },
    { path: '/memory', name: 'memory', component: () => import('./views/Memory.vue'), meta: { title: '记忆' } },
    { path: '/experience', name: 'experience', component: () => import('./views/Experience.vue'), meta: { title: '经验' } },
    { path: '/chat', name: 'chat', component: () => import('./views/Chat.vue'), meta: { title: '对话' } },
  ],
})
