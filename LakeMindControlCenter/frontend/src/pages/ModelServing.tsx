import { Table, Tag, Card, Tabs, Button, Modal, Form, Input, InputNumber, Select, Space, message, Descriptions, Tooltip, Popconfirm, Radio } from 'antd';
import { useEffect, useState } from 'react';
import { PlusOutlined, EditOutlined, ExperimentOutlined, DeleteOutlined } from '@ant-design/icons';
import { api } from '../api/client';

interface TestResult {
  model_id: string;
  name: string;
  model_type: string;
  source: string;
  success: boolean;
  latency_ms: number | null;
  error: string | null;
  response_preview: string | null;
  health_status: string;
}

const MODEL_TYPES = ['chat', 'embedding', 'asr'];
const PROVIDERS = ['openai', 'anthropic', 'modelarts', 'ollama', 'fastembed', 'faster-whisper', 'funasr'];

export default function ModelServing() {
  const [models, setModels] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modelModalOpen, setModelModalOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<any>(null);
  const [editingProfile, setEditingProfile] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [modelForm] = Form.useForm();
  const [profileForm] = Form.useForm();
  const [sourceType, setSourceType] = useState<string>('external');

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.get('/models').then(r => Array.isArray(r.data) ? r.data : r.data?.data || r.data?.items || []),
      api.get('/profiles').then(r => r.data?.data || r.data?.items || Array.isArray(r.data) ? r.data : []).catch(() => []),
    ]).then(([m, p]) => { setModels(m); setProfiles(p); }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  async function handleTest(modelId: string) {
    setTesting(modelId);
    setTestResult(null);
    try {
      const r = await api.post(`/models/${modelId}/test`);
      setTestResult(r.data);
      if (r.data.success) message.success(`Test passed (${r.data.latency_ms}ms)`);
      else message.error(`Test failed: ${r.data.error || ''}`);
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Test failed');
    } finally { setTesting(null); }
  }

  function openAddModel() {
    setEditingModel(null);
    setSourceType('external');
    modelForm.resetFields();
    modelForm.setFieldsValue({ source: 'external', model_type: 'chat', provider: 'openai', priority: 100, status: 'enabled' });
    setModelModalOpen(true);
  }

  function openEditModel(record: any) {
    setEditingModel(record);
    const src = record.source || 'external';
    setSourceType(src);
    modelForm.setFieldsValue({
      name: record.name,
      model_type: record.model_type,
      provider: record.provider,
      source: src,
      litellm_model: record.litellm_model,
      api_key: record.api_key,
      base_url: record.base_url,
      model_path: record.model_path,
      config: record.model_config ? JSON.stringify(record.model_config) : '{}',
      capabilities: (record.capabilities || []).join(', '),
      context_length: record.context_length,
      embedding_dim: record.embedding_dim,
      priority: record.priority,
    });
    setModelModalOpen(true);
  }

  async function handleSaveModel() {
    try {
      const values = await modelForm.validateFields();
      setSubmitting(true);
      const payload: any = {
        name: values.name,
        model_type: values.model_type,
        provider: values.provider,
        source: values.source,
        priority: values.priority || 100,
      };
      if (values.source === 'external') {
        payload.litellm_model = values.litellm_model;
        payload.api_key = values.api_key;
        payload.base_url = values.base_url;
        payload.context_length = values.context_length;
      } else {
        payload.model_path = values.model_path;
        payload.config = values.config ? JSON.parse(values.config) : {};
        payload.embedding_dim = values.embedding_dim;
      }
      if (values.capabilities) payload.capabilities = values.capabilities.split(',').map((s: string) => s.trim());

      if (editingModel) {
        await api.put(`/models/${editingModel.model_id}`, payload);
        message.success('Model updated');
      } else {
        await api.post('/models', payload);
        message.success('Model created');
      }
      setModelModalOpen(false);
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || 'Failed to save model');
    } finally { setSubmitting(false); }
  }

  async function handleDeleteModel(modelId: string) {
    try {
      await api.delete(`/models/${modelId}`);
      message.success('Model deleted');
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to delete model');
    }
  }

  const toggleModel = async (id: string, action: 'enable' | 'disable') => {
    try {
      await api.post(`/models/${id}/${action}`);
      message.success(`Model ${action}d`);
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || `Failed to ${action} model`);
    }
  };

  function openAddProfile() {
    setEditingProfile(null);
    profileForm.resetFields();
    setProfileModalOpen(true);
  }

  function openEditProfile(record: any) {
    setEditingProfile(record);
    profileForm.setFieldsValue({
      name: record.name,
      model_type: record.model_type,
      model_id: record.model_id,
      fallback_model_id: record.fallback_model_id,
      description: record.description,
    });
    setProfileModalOpen(true);
  }

  async function handleSaveProfile() {
    try {
      const values = await profileForm.validateFields();
      setSubmitting(true);
      if (editingProfile) {
        await api.put(`/profiles/${editingProfile.profile_id}`, values);
        message.success('Profile updated');
      } else {
        await api.post('/profiles', values);
        message.success('Profile created');
      }
      setProfileModalOpen(false);
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to save profile');
    } finally { setSubmitting(false); }
  }

  async function handleDeleteProfile(profileId: string) {
    try {
      await api.delete(`/profiles/${profileId}`);
      message.success('Profile deleted');
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to delete profile');
    }
  }

  const modelColumns = [
    { title: 'Name', dataIndex: 'name', key: 'name', render: (v: string) => <strong>{v}</strong> },
    { title: 'Type', dataIndex: 'model_type', key: 'model_type', render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: 'Provider', dataIndex: 'provider', key: 'provider' },
    { title: 'Source', dataIndex: 'source', key: 'source', render: (v: string) => <Tag color={v === 'local' ? 'blue' : 'green'}>{v}</Tag> },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'enabled' ? 'green' : 'red'}>{v}</Tag> },
    { title: 'Health', dataIndex: 'health_status', key: 'health_status', render: (v: string) => <Tag color={v === 'healthy' ? 'green' : v === 'unhealthy' ? 'red' : 'default'}>{v}</Tag> },
    {
      title: 'Detail', key: 'detail', ellipsis: true,
      render: (_: any, record: any) => {
        if (record.source === 'external') return <Tooltip title={record.base_url}>{record.litellm_model || record.provider}</Tooltip>;
        return <Tooltip title={record.model_path}>{record.model_path || '—'}</Tooltip>;
      },
    },
    {
      title: 'Actions', key: 'actions', width: 240,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button size="small" type="link" icon={<ExperimentOutlined />}
            loading={testing === record.model_id}
            onClick={() => handleTest(record.model_id)}>Test</Button>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEditModel(record)}>Edit</Button>
          <Button size="small" type="link"
            onClick={() => toggleModel(record.model_id, record.status === 'enabled' ? 'disable' : 'enable')}>
            {record.status === 'enabled' ? 'Disable' : 'Enable'}
          </Button>
          <Popconfirm title="Delete this model?" onConfirm={() => handleDeleteModel(record.model_id)}>
            <Button size="small" type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const profileColumns = [
    { title: 'Name', dataIndex: 'name', key: 'name', render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: 'Type', dataIndex: 'model_type', key: 'model_type', render: (v: string) => <Tag color="purple">{v}</Tag> },
    {
      title: 'Model', key: 'model', render: (_: any, record: any) => {
        const m = models.find(m => m.model_id === record.model_id);
        return m ? m.name : record.model_id;
      },
    },
    {
      title: 'Fallback', key: 'fallback', render: (_: any, record: any) => {
        if (!record.fallback_model_id) return '—';
        const m = models.find(m => m.model_id === record.fallback_model_id);
        return m ? m.name : record.fallback_model_id;
      },
    },
    { title: 'Tenant', dataIndex: 'tenant_id', key: 'tenant_id', render: (v: string) => v || '—' },
    {
      title: 'Actions', key: 'actions', width: 120,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEditProfile(record)}>Edit</Button>
          <Popconfirm title="Delete this profile?" onConfirm={() => handleDeleteProfile(record.profile_id)}>
            <Button size="small" type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Tabs items={[
        {
          key: 'models', label: 'Models',
          children: (
            <Card>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={openAddModel}>Add Model</Button>
              </Space>
              <Table dataSource={models} columns={modelColumns} rowKey="model_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
              {testResult && (
                <Modal title="Test Result" open={!!testResult} onCancel={() => setTestResult(null)} footer={null} width={700}>
                  <Descriptions column={1} bordered size="small">
                    <Descriptions.Item label="Result"><Tag color={testResult.success ? 'green' : 'red'}>{testResult.success ? 'PASSED' : 'FAILED'}</Tag></Descriptions.Item>
                    <Descriptions.Item label="Model">{testResult.name} ({testResult.model_type})</Descriptions.Item>
                    <Descriptions.Item label="Source">{testResult.source}</Descriptions.Item>
                    <Descriptions.Item label="Latency">{testResult.latency_ms != null ? `${testResult.latency_ms}ms` : '—'}</Descriptions.Item>
                    <Descriptions.Item label="Health">{testResult.health_status}</Descriptions.Item>
                    {testResult.error && <Descriptions.Item label="Error"><span style={{ color: 'red' }}>{testResult.error}</span></Descriptions.Item>}
                    {testResult.response_preview && <Descriptions.Item label="Preview"><pre style={{ maxHeight: 200, overflow: 'auto', fontSize: 11 }}>{testResult.response_preview}</pre></Descriptions.Item>}
                  </Descriptions>
                </Modal>
              )}
            </Card>
          ),
        },
        {
          key: 'profiles', label: 'Profiles',
          children: (
            <Card>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={openAddProfile}>Add Profile</Button>
              </Space>
              <Table dataSource={profiles} columns={profileColumns} rowKey="profile_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
            </Card>
          ),
        },
      ]} />

      <Modal title={editingModel ? "Edit Model" : "Add Model"} open={modelModalOpen} onOk={handleSaveModel} onCancel={() => setModelModalOpen(false)} confirmLoading={submitting} width={600}>
        <Form form={modelForm} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input placeholder="e.g. deepseek-v4-flash" /></Form.Item>
          <Form.Item name="model_type" label="Type" rules={[{ required: true }]}>
            <Select options={MODEL_TYPES.map(t => ({ value: t }))} />
          </Form.Item>
          <Form.Item name="source" label="Source" rules={[{ required: true }]}>
            <Radio.Group onChange={(e) => setSourceType(e.target.value)}>
              <Radio.Button value="external">External API</Radio.Button>
              <Radio.Button value="local">Local (offline files)</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
            <Select options={PROVIDERS.map(p => ({ value: p }))} />
          </Form.Item>

          {sourceType === 'external' ? (
            <>
              <Form.Item name="litellm_model" label="litellm Model"><Input placeholder="openai/deepseek-v4-flash" /></Form.Item>
              <Form.Item name="api_key" label="API Key"><Input.Password placeholder="sk-xxx" /></Form.Item>
              <Form.Item name="base_url" label="Base URL"><Input placeholder="https://api.openai.com/v1" /></Form.Item>
              <Form.Item name="context_length" label="Context Length"><InputNumber style={{ width: '100%' }} /></Form.Item>
            </>
          ) : (
            <>
              <Form.Item name="model_path" label="Model Path" rules={[{ required: true }]}><Input placeholder="/data/asr_models/whisper-large-v3-turbo" /></Form.Item>
              <Form.Item name="config" label="Config (JSON)"><Input.TextArea rows={2} placeholder='{"device": "cpu", "compute_type": "int8"}' /></Form.Item>
              <Form.Item name="embedding_dim" label="Embedding Dim"><InputNumber style={{ width: '100%' }} /></Form.Item>
            </>
          )}

          <Form.Item name="capabilities" label="Capabilities (comma-separated)"><Input placeholder="chat, vision" /></Form.Item>
          <Form.Item name="priority" label="Priority" initialValue={100}><InputNumber style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>

      <Modal title={editingProfile ? "Edit Profile" : "Add Profile"} open={profileModalOpen} onOk={handleSaveProfile} onCancel={() => setProfileModalOpen(false)} confirmLoading={submitting}>
        <Form form={profileForm} layout="vertical">
          <Form.Item name="name" label="Profile Name" rules={[{ required: true }]}><Input placeholder="e.g. meeting-minutes" /></Form.Item>
          <Form.Item name="model_type" label="Type" rules={[{ required: true }]}>
            <Select options={MODEL_TYPES.map(t => ({ value: t }))} />
          </Form.Item>
          <Form.Item name="model_id" label="Model" rules={[{ required: true }]}>
            <Select options={models.map(m => ({ value: m.model_id, label: `${m.name} (${m.model_type}) [${m.status}]` }))} />
          </Form.Item>
          <Form.Item name="fallback_model_id" label="Fallback Model">
            <Select allowClear options={models.map(m => ({ value: m.model_id, label: m.name }))} />
          </Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
        </Form>
      </Modal>
    </>
  );
}
