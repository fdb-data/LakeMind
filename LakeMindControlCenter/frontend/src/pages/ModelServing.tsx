import { Table, Tag, Card, Tabs, Button, Modal, Form, Input, InputNumber, Select, Space, message, Descriptions, Tooltip, Popconfirm } from 'antd';
import { useEffect, useState } from 'react';
import { PlusOutlined, EditOutlined, ExperimentOutlined, DeleteOutlined } from '@ant-design/icons';
import { api } from '../api/client';

interface TestResult {
  deployment_id: string;
  endpoint: string;
  model_type: string;
  model_name: string;
  success: boolean;
  latency_ms: number | null;
  status_code: number | null;
  error: string | null;
  response_preview: string | null;
  health_status: string;
}

export default function ModelServing() {
  const [defs, setDefs] = useState<any[]>([]);
  const [deps, setDeps] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [routes, setRoutes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [defModalOpen, setDefModalOpen] = useState(false);
  const [depModalOpen, setDepModalOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [routeModalOpen, setRouteModalOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [editingDef, setEditingDef] = useState<any>(null);
  const [editingDep, setEditingDep] = useState<any>(null);
  const [defForm] = Form.useForm();
  const [depForm] = Form.useForm();
  const [profileForm] = Form.useForm();
  const [routeForm] = Form.useForm();

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.get('/models/definitions').then(r => Array.isArray(r.data) ? r.data : r.data?.items || []),
      api.get('/models/deployments').then(r => Array.isArray(r.data) ? r.data : r.data?.items || []),
      api.get('/models/profiles').then(r => Array.isArray(r.data) ? r.data : r.data?.items || []).catch(() => []),
      api.get('/models/routes').then(r => Array.isArray(r.data) ? r.data : r.data?.items || []).catch(() => []),
    ]).then(([d, dp, pf, rt]) => { setDefs(d); setDeps(dp); setProfiles(pf); setRoutes(rt); }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  async function handleTest(deploymentId: string) {
    setTesting(deploymentId);
    setTestResult(null);
    try {
      const r = await api.post(`/models/deployments/${deploymentId}/test`);
      setTestResult(r.data);
      if (r.data.success) {
        message.success(`Test passed (${r.data.latency_ms}ms)`);
      } else {
        message.error(`Test failed: ${r.data.error || 'HTTP ' + r.data.status_code}`);
      }
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Test failed');
    } finally { setTesting(null); }
  }

  function openAddDef() {
    setEditingDef(null);
    defForm.resetFields();
    setDefModalOpen(true);
  }
  function openEditDef(record: any) {
    setEditingDef(record);
    defForm.setFieldsValue({
      name: record.name,
      model_type: record.model_type,
      provider_family: record.provider_family,
      capabilities: (record.capabilities || []).join(', '),
      context_length: record.context_length,
      embedding_dim: record.embedding_dim,
      metadata: JSON.stringify(record.metadata || {}),
    });
    setDefModalOpen(true);
  }

  async function handleSaveDef() {
    try {
      const values = await defForm.validateFields();
      setSubmitting(true);
      const payload = {
        ...values,
        capabilities: values.capabilities ? values.capabilities.split(',').map((s: string) => s.trim()) : ['chat'],
        metadata: values.metadata ? JSON.parse(values.metadata) : {},
      };
      if (editingDef) {
        await api.patch(`/models/definitions/${editingDef.model_id}`, payload);
        message.success('Model definition updated');
      } else {
        await api.post('/models/definitions', payload);
        message.success('Model definition created');
      }
      setDefModalOpen(false);
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to save model definition');
    } finally { setSubmitting(false); }
  }

  function openAddDep() {
    setEditingDep(null);
    depForm.resetFields();
    setDepModalOpen(true);
  }
  function openEditDep(record: any) {
    setEditingDep(record);
    depForm.setFieldsValue({
      model_id: record.model_id,
      provider: record.provider,
      endpoint: record.endpoint,
      secret_ref: record.secret_ref,
      priority: record.priority,
      timeout_ms: record.timeout_ms,
      max_concurrency: record.max_concurrency,
    });
    setDepModalOpen(true);
  }

  async function handleSaveDep() {
    try {
      const values = await depForm.validateFields();
      setSubmitting(true);
      if (editingDep) {
        await api.patch(`/models/deployments/${editingDep.deployment_id}`, values);
        message.success('Deployment updated');
      } else {
        await api.post('/models/deployments', values);
        message.success('Deployment created');
      }
      setDepModalOpen(false);
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to save deployment');
    } finally { setSubmitting(false); }
  }

  async function handleCreateProfile() {
    try {
      const values = await profileForm.validateFields();
      setSubmitting(true);
      await api.post('/models/profiles', values);
      message.success('Profile created');
      setProfileModalOpen(false);
      profileForm.resetFields();
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to create profile');
    } finally { setSubmitting(false); }
  }

  async function handleAddRoute() {
    try {
      const values = await routeForm.validateFields();
      setSubmitting(true);
      await api.post('/models/routes', values);
      message.success('Route added');
      setRouteModalOpen(false);
      routeForm.resetFields();
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to add route');
    } finally { setSubmitting(false); }
  }

  async function handleDeleteRoute(routeId: string) {
    try {
      await api.delete(`/models/routes/${routeId}`);
      message.success('Route deleted');
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to delete route');
    }
  }

  const toggleDeployment = async (id: string, action: 'enable' | 'disable') => {
    try {
      await api.post(`/models/deployments/${id}/${action}`);
      message.success(`Deployment ${action}d`);
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || `Failed to ${action} deployment`);
    }
  };

  const defColumns = [
    { title: 'Model ID', dataIndex: 'model_id', key: 'model_id', width: 200, ellipsis: true },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Type', dataIndex: 'model_type', key: 'model_type', render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: 'Provider', dataIndex: 'provider_family', key: 'provider_family' },
    { title: 'Context', dataIndex: 'context_length', key: 'context_length' },
    { title: 'Embed Dim', dataIndex: 'embedding_dim', key: 'embedding_dim' },
    {
      title: 'Action', key: 'action', width: 80,
      render: (_: any, record: any) => (
        <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEditDef(record)}>Edit</Button>
      ),
    },
  ];

  const depColumns = [
    { title: 'Deployment ID', dataIndex: 'deployment_id', key: 'deployment_id', width: 180, ellipsis: true },
    {
      title: 'Model', dataIndex: 'model_id', key: 'model_id', width: 180, ellipsis: true,
      render: (v: string) => {
        const d = defs.find(d => d.model_id === v);
        return d ? `${d.name} (${d.model_type})` : v;
      },
    },
    { title: 'Provider', dataIndex: 'provider', key: 'provider' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'enabled' ? 'green' : 'red'}>{v}</Tag> },
    {
      title: 'Health', dataIndex: 'health_status', key: 'health_status',
      render: (v: string) => <Tag color={v === 'healthy' ? 'green' : v === 'unhealthy' ? 'red' : 'default'}>{v}</Tag>,
    },
    { title: 'Priority', dataIndex: 'priority', key: 'priority' },
    {
      title: 'Endpoint', dataIndex: 'endpoint', key: 'endpoint', ellipsis: true,
      render: (v: string) => {
        const isLocalhost = v.includes('localhost');
        return <Tooltip title={v}><span style={{ color: isLocalhost ? '#ff4d4f' : 'inherit' }}>{v}</span></Tooltip>;
      },
    },
    {
      title: 'Action', key: 'action', width: 200,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button size="small" type="link" icon={<ExperimentOutlined />}
            loading={testing === record.deployment_id}
            onClick={() => handleTest(record.deployment_id)}>Test</Button>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEditDep(record)}>Edit</Button>
          <Button size="small" type="link"
            onClick={() => toggleDeployment(record.deployment_id, record.status === 'enabled' ? 'disable' : 'enable')}>
            {record.status === 'enabled' ? 'Disable' : 'Enable'}
          </Button>
        </Space>
      ),
    },
  ];

  const routeColumns = [
    {
      title: 'Profile', dataIndex: 'profile_name', key: 'profile_name',
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: 'Deployment', dataIndex: 'deployment_id', key: 'deployment_id', ellipsis: true,
      render: (v: string) => {
        const d = deps.find(d => d.deployment_id === v);
        const m = d ? defs.find(m => m.model_id === d.model_id) : null;
        return m ? `${m.name}` : v;
      },
    },
    {
      title: 'Endpoint', key: 'endpoint',
      render: (_: any, record: any) => {
        const d = deps.find(d => d.deployment_id === record.deployment_id);
        return d?.endpoint || '--';
      },
    },
    { title: 'Priority', dataIndex: 'priority', key: 'priority' },
    { title: 'Fallback', dataIndex: 'is_fallback', key: 'is_fallback', render: (v: boolean) => v ? <Tag color="orange">fallback</Tag> : <Tag color="green">primary</Tag> },
    {
      title: 'Action', key: 'action', width: 80,
      render: (_: any, record: any) => (
        <Popconfirm title="Delete this route?" onConfirm={() => handleDeleteRoute(record.route_id)}>
          <Button size="small" type="link" danger icon={<DeleteOutlined />}>Delete</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <>
      <Tabs items={[
        {
          key: 'defs', label: 'Model Definitions',
          children: (
            <Card>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={openAddDef}>Add Definition</Button>
              </Space>
              <Table dataSource={defs} columns={defColumns} rowKey="model_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
            </Card>
          ),
        },
        {
          key: 'deps', label: 'Deployments',
          children: (
            <Card>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={openAddDep}>Add Deployment</Button>
                <span style={{ color: '#ff4d4f', fontSize: 12 }}>
                  Note: endpoints with localhost are not reachable from other containers. Use lakemind-model-serving:10824 instead.
                </span>
              </Space>
              <Table dataSource={deps} columns={depColumns} rowKey="deployment_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
              {testResult && (
                <Modal title="Test Result" open={!!testResult} onCancel={() => setTestResult(null)} footer={null} width={700}>
                  <Descriptions column={1} bordered size="small">
                    <Descriptions.Item label="Success">
                      <Tag color={testResult.success ? 'green' : 'red'}>{testResult.success ? 'PASSED' : 'FAILED'}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="Model">{testResult.model_name} ({testResult.model_type})</Descriptions.Item>
                    <Descriptions.Item label="Endpoint">{testResult.endpoint}</Descriptions.Item>
                    <Descriptions.Item label="Status Code">{testResult.status_code ?? '--'}</Descriptions.Item>
                    <Descriptions.Item label="Latency">{testResult.latency_ms != null ? `${testResult.latency_ms}ms` : '--'}</Descriptions.Item>
                    <Descriptions.Item label="Health">{testResult.health_status}</Descriptions.Item>
                    {testResult.error && <Descriptions.Item label="Error"><span style={{ color: 'red' }}>{testResult.error}</span></Descriptions.Item>}
                    {testResult.response_preview && (
                      <Descriptions.Item label="Response Preview">
                        <pre style={{ maxHeight: 200, overflow: 'auto', fontSize: 11 }}>{testResult.response_preview}</pre>
                      </Descriptions.Item>
                    )}
                  </Descriptions>
                </Modal>
              )}
            </Card>
          ),
        },
        {
          key: 'profiles', label: 'Profiles & Routes',
          children: (
            <Card>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setProfileModalOpen(true)}>Add Profile</Button>
                <Button icon={<PlusOutlined />} onClick={() => { routeForm.resetFields(); setRouteModalOpen(true); }}>Add Route</Button>
              </Space>
              <div style={{ marginBottom: 16 }}>
                <h4>Profiles</h4>
                <Table dataSource={profiles} columns={[
                  { title: 'Profile ID', dataIndex: 'profile_id', key: 'profile_id', width: 200, ellipsis: true },
                  { title: 'Name', dataIndex: 'name', key: 'name', render: (v: string) => <Tag color="blue">{v}</Tag> },
                  { title: 'Description', dataIndex: 'description', key: 'description' },
                ]} rowKey="profile_id" loading={loading} pagination={false} size="small" />
              </div>
              <div>
                <h4>Routes (Profile → Deployment mapping)</h4>
                <Table dataSource={routes} columns={routeColumns} rowKey="route_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
              </div>
            </Card>
          ),
        },
      ]} />

      <Modal title={editingDef ? "Edit Model Definition" : "Add Model Definition"} open={defModalOpen} onOk={handleSaveDef} onCancel={() => setDefModalOpen(false)} confirmLoading={submitting} width={600}>
        <Form form={defForm} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input placeholder="e.g. gpt-4o" /></Form.Item>
          <Form.Item name="model_type" label="Type" rules={[{ required: true }]}>
            <Select options={[{ value: 'chat' }, { value: 'completion' }, { value: 'embedding' }, { value: 'asr' }]} />
          </Form.Item>
          <Form.Item name="provider_family" label="Provider Family" rules={[{ required: true }]}><Input placeholder="e.g. openai, fastembed, funasr" /></Form.Item>
          <Form.Item name="capabilities" label="Capabilities (comma-separated)"><Input placeholder="e.g. chat,vision" /></Form.Item>
          <Form.Item name="context_length" label="Context Length"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="embedding_dim" label="Embedding Dim"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="metadata" label="Metadata (JSON)"><Input.TextArea rows={2} placeholder='{"litellm_model": "openai/gpt-4o"}' /></Form.Item>
        </Form>
      </Modal>

      <Modal title={editingDep ? "Edit Deployment" : "Add Deployment"} open={depModalOpen} onOk={handleSaveDep} onCancel={() => setDepModalOpen(false)} confirmLoading={submitting} width={600}>
        <Form form={depForm} layout="vertical">
          <Form.Item name="model_id" label="Model ID" rules={[{ required: true }]}>
            <Select options={defs.map(d => ({ value: d.model_id, label: `${d.name} (${d.model_type})` }))} />
          </Form.Item>
          <Form.Item name="provider" label="Provider" rules={[{ required: true }]}><Input placeholder="e.g. openai" /></Form.Item>
          <Form.Item name="endpoint" label="Endpoint" rules={[{ required: true }]}><Input placeholder="http://lakemind-model-serving:10824/v1/chat/completions" /></Form.Item>
          <Form.Item name="secret_ref" label="Secret Ref" rules={[{ required: true }]}><Input placeholder="secret://default/provider-api-key" /></Form.Item>
          <Form.Item name="priority" label="Priority" initialValue={100}><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="timeout_ms" label="Timeout (ms)" initialValue={30000}><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="max_concurrency" label="Max Concurrency" initialValue={10}><InputNumber style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="Add Profile" open={profileModalOpen} onOk={handleCreateProfile} onCancel={() => setProfileModalOpen(false)} confirmLoading={submitting}>
        <Form form={profileForm} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input placeholder="e.g. default, tenant-retail" /></Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
        </Form>
      </Modal>

      <Modal title="Add Route (Profile → Deployment)" open={routeModalOpen} onOk={handleAddRoute} onCancel={() => setRouteModalOpen(false)} confirmLoading={submitting}>
        <Form form={routeForm} layout="vertical">
          <Form.Item name="profile_name" label="Profile" rules={[{ required: true }]}>
            <Select options={profiles.map(p => ({ value: p.name, label: p.name }))} />
          </Form.Item>
          <Form.Item name="deployment_id" label="Deployment" rules={[{ required: true }]}>
            <Select options={deps.map(d => {
              const m = defs.find(m => m.model_id === d.model_id);
              return { value: d.deployment_id, label: `${m?.name || d.model_id} [${d.status}] ${d.endpoint.substring(0, 50)}...` };
            })} />
          </Form.Item>
          <Form.Item name="priority" label="Priority" initialValue={100}><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="is_fallback" label="Is Fallback" initialValue={false}>
            <Select options={[{ value: false, label: 'Primary' }, { value: true, label: 'Fallback' }]} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
