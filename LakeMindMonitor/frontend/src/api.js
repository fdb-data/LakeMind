import axios from 'axios'

const client = axios.create({ baseURL: '/api', timeout: 30000 })

export default {
  health: () => client.get('/health').then(r => r.data),
  dashboard: () => client.get('/dashboard/overview').then(r => r.data),

  assetCapabilities: () => client.get('/asset/capabilities').then(r => r.data),
  assetKnowledge: () => client.get('/asset/knowledge').then(r => r.data),
  assetKnowledgeDetail: (kb) => client.get(`/asset/knowledge/${kb}`).then(r => r.data),
  assetSkills: () => client.get('/asset/skills').then(r => r.data),
  assetMemory: () => client.get('/asset/memory').then(r => r.data),
  assetMemoryList: (limit = 20, offset = 0) => client.get('/asset/memory/list', { params: { limit, offset } }).then(r => r.data),
  assetOntology: () => client.get('/asset/ontology').then(r => r.data),

  dataTables: () => client.get('/data/tables').then(r => r.data),
  dataTableDescribe: (ns, t) => client.get(`/data/tables/${ns}/${t}`).then(r => r.data),
  dataVectors: () => client.get('/data/vectors').then(r => r.data),
  dataS3: (prefix = '') => client.get('/data/s3', { params: { prefix } }).then(r => r.data),
  dataKV: (prefix = '') => client.get('/data/kv', { params: { prefix } }).then(r => r.data),
  dataGraph: () => client.get('/data/graph').then(r => r.data),

  adminHealth: () => client.get('/admin/health').then(r => r.data),
  adminNodes: () => client.get('/admin/nodes').then(r => r.data),
  adminMetrics: () => client.get('/admin/metrics').then(r => r.data),
  adminTenants: () => client.get('/admin/tenants').then(r => r.data),
  adminUsers: () => client.get('/admin/users').then(r => r.data),
  adminTokens: () => client.get('/admin/tokens').then(r => r.data),
  adminAssetTypes: () => client.get('/admin/asset-types').then(r => r.data),

  chat: (message) => client.post('/chat', { message }).then(r => r.data),
  inspect: () => client.post('/inspect', {}).then(r => r.data),
  stewardHealth: () => client.get('/steward/health').then(r => r.data),
  modelServingHealth: () => client.get('/model-serving/health').then(r => r.data),
  modelServingModels: () => client.get('/model-serving/models').then(r => r.data),
}
