<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get } from '../api'
import { useSystemHealth, healthTag } from '../stores/health'

const { health, load } = useSystemHealth()
const caps = ref<Record<string, any>>({})
const workspace = ref<any>(null)
const counts = ref({ data: 0, knowledge: 0, skills: 0, experience: 0 })

async function loadAll() {
  await load()
  try { caps.value = await get('/capabilities') } catch {}
  try { workspace.value = await get('/workspace') } catch {}
  try { counts.value.data = (await get<any[]>('/data')).length } catch {}
  try { counts.value.knowledge = (await get<any[]>('/knowledge')).length } catch {}
  try { counts.value.skills = (await get<any[]>('/skills')).length } catch {}
  try { counts.value.experience = (await get<any[]>('/experience')).length } catch {}
}
onMounted(loadAll)
</script>

<template>
  <el-row :gutter="16">
    <el-col :span="24">
      <el-card header="组件健康">
        <el-space>
          <el-tag v-for="(v, k) in health" :key="k" :type="healthTag(v)" effect="dark" size="large">
            {{ k }}: {{ v }}
          </el-tag>
        </el-space>
      </el-card>
    </el-col>
  </el-row>
  <el-row :gutter="16" style="margin-top: 16px">
    <el-col :span="8">
      <el-card header="能力图">
        <el-descriptions :column="1" border>
          <el-descriptions-item v-for="(v, k) in caps" :key="k" :label="String(k)">
            <el-tag :type="v.enabled ? 'success' : 'info'" size="small">{{ v.enabled ? '启用' : '未启用' }}</el-tag>
            {{ v.capabilities?.join(', ') }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card header="资产计数">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="数据集">{{ counts.data }}</el-descriptions-item>
          <el-descriptions-item label="知识库">{{ counts.knowledge }}</el-descriptions-item>
          <el-descriptions-item label="技能">{{ counts.skills }}</el-descriptions-item>
          <el-descriptions-item label="经验">{{ counts.experience }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card header="工作区">
        <el-descriptions :column="1" border v-if="workspace">
          <el-descriptions-item label="agent_id">{{ workspace.agent_id }}</el-descriptions-item>
          <el-descriptions-item label="tenant_id">{{ workspace.tenant_id }}</el-descriptions-item>
          <el-descriptions-item label="scopes">{{ workspace.scopes?.join(', ') }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
  </el-row>
</template>
