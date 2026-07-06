import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import Asset from './views/Asset.vue'
import Data from './views/Data.vue'
import Admin from './views/Admin.vue'
import Chat from './views/Chat.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: Dashboard, meta: { title: 'Dashboard', icon: 'Odometer' } },
    { path: '/asset', component: Asset, meta: { title: 'Asset', icon: 'FolderOpened' } },
    { path: '/data', component: Data, meta: { title: 'Data', icon: 'Coin' } },
    { path: '/admin', component: Admin, meta: { title: 'Admin', icon: 'Setting' } },
    { path: '/chat', component: Chat, meta: { title: 'Chat', icon: 'ChatDotRound' } },
  ],
})

const app = createApp(App)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')
