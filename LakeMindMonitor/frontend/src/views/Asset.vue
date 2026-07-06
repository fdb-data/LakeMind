<template>
<div class="asset-page">
  <h2>认知资产</h2>
  <el-tabs v-model="activeTab" @tab-change="onTabChange">
    <el-tab-pane label="知识库" name="knowledge">
      <el-table :data="knowledgeList" v-loading="loading.knowledge" stripe size="default">
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="concept_count" label="概念数" width="100" />
        <el-table-column label="类型分布" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="(v, k) in row.type_distribution || row.types || {}" :key="k" size="small" style="margin-right:4px">{{ k }}: {{ v }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="showKbDetail(row.name || row.kb_name)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="技能" name="skills">
      <el-table :data="skillList" v-loading="loading.skills" stripe>
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="description" label="描述" min-width="240" show-overflow-tooltip />
        <el-table-column label="标签" width="200">
          <template #default="{ row }">
            <el-tag v-for="t in (row.tags || []).slice(0,3)" :key="t" size="small" style="margin-right:4px">{{ t }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="s3_uri" label="S3 URI" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="记忆" name="memory">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card shadow="never">
            <div class="mem-stat"><span>总计</span><b>{{ memoryOverview.total || memoryOverview.total_count || 0 }}</b></div>
            <div class="mem-stat" v-for="(v, k) in memoryOverview.by_kind || memoryOverview.kinds || {}" :key="k">
              <span>{{ k }}</span><b>{{ v }}</b>
            </div>
          </el-card>
        </el-col>
        <el-col :span="18">
          <el-table :data="memoryList" v-loading="loading.memory" stripe>
            <el-table-column label="内容摘要" min-width="300" show-overflow-tooltip>
              <template #default="{ row }">{{ row.content || row.text || row.summary || JSON.stringify(row).slice(0,80) }}</template>
            </el-table-column>
            <el-table-column prop="kind" label="类型" width="100" />
            <el-table-column prop="score" label="分数" width="80" />
            <el-table-column prop="created_at" label="时间" width="180" />
          </el-table>
        </el-col>
      </el-row>
    </el-tab-pane>

    <el-tab-pane label="本体" name="ontology">
      <el-card shadow="never" v-loading="loading.ontology">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="节点数">{{ ontologyData.node_count || ontologyData.nodes || 0 }}</el-descriptions-item>
          <el-descriptions-item label="边数">{{ ontologyData.edge_count || ontologyData.edges || 0 }}</el-descriptions-item>
          <el-descriptions-item label="顶层概念">
            <el-tag v-for="c in (ontologyData.top_concepts || ontologyData.top_level || []).slice(0,5)" :key="c" size="small" style="margin-right:4px">{{ c }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-tab-pane>
  </el-tabs>

  <el-dialog v-model="kbDialogVisible" :title="`知识库: ${currentKb}`" width="700px">
    <el-table :data="kbConceptList" v-loading="kbDialogLoading" stripe size="small">
      <el-table-column prop="concept_id" label="ID" width="120" />
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column prop="type" label="类型" width="100" />
      <el-table-column label="标签" min-width="160">
        <template #default="{ row }">
          <el-tag v-for="t in (row.tags || []).slice(0,3)" :key="t" size="small" style="margin-right:4px">{{ t }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>
</div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api.js'

const activeTab = ref('knowledge')
const loading = reactive({ knowledge: false, skills: false, memory: false, ontology: false })
const knowledgeList = ref([])
const skillList = ref([])
const memoryOverview = ref({})
const memoryList = ref([])
const ontologyData = ref({})
const kbDialogVisible = ref(false)
const kbDialogLoading = ref(false)
const currentKb = ref('')
const kbConceptList = ref([])

function normalizeList(data) {
  if (Array.isArray(data)) return data
  if (data?.knowledge_bases) return data.knowledge_bases
  if (data?.skills) return data.skills
  if (data?.items) return data.items
  if (data?.results) return data.results
  return []
}

async function loadKnowledge() {
  loading.knowledge = true
  try { knowledgeList.value = normalizeList(await api.assetKnowledge()) }
  catch { knowledgeList.value = [] }
  finally { loading.knowledge = false }
}
async function loadSkills() {
  loading.skills = true
  try { skillList.value = normalizeList(await api.assetSkills()) }
  catch { skillList.value = [] }
  finally { loading.skills = false }
}
async function loadMemory() {
  loading.memory = true
  try {
    memoryOverview.value = await api.assetMemory()
    const list = await api.assetMemoryList(20, 0)
    memoryList.value = normalizeList(list)
  } catch { memoryOverview.value = {}; memoryList.value = [] }
  finally { loading.memory = false }
}
async function loadOntology() {
  loading.ontology = true
  try { ontologyData.value = await api.assetOntology() }
  catch { ontologyData.value = {} }
  finally { loading.ontology = false }
}

async function showKbDetail(kb) {
  currentKb.value = kb
  kbDialogVisible.value = true
  kbDialogLoading.value = true
  try {
    const detail = await api.assetKnowledgeDetail(kb)
    kbConceptList.value = detail.concepts || detail.items || normalizeList(detail) || []
  } catch { kbConceptList.value = [] }
  finally { kbDialogLoading.value = false }
}

function onTabChange(tab) {
  if (tab === 'knowledge' && !knowledgeList.value.length) loadKnowledge()
  if (tab === 'skills' && !skillList.value.length) loadSkills()
  if (tab === 'memory' && !memoryList.value.length) loadMemory()
  if (tab === 'ontology' && !Object.keys(ontologyData.value).length) loadOntology()
}

onMounted(() => { loadKnowledge(); loadSkills(); loadMemory(); loadOntology() })
</script>

<style scoped>
.asset-page { max-width: 1400px; margin: 0 auto; }
.asset-page h2 { margin: 0 0 20px; font-size: 20px; }
.mem-stat { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-color); }
.mem-stat span { color: var(--text-secondary); }
.mem-stat b { font-size: 18px; color: var(--accent); }
</style>
