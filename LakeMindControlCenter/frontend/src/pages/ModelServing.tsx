import { Table, Tag, Card, Tabs, Button, Modal, Form, Input, InputNumber, Select, Space, message } from 'antd';
import { useEffect, useState } from 'react';
import { PlusOutlined } from '@ant-design/icons';
import { api } from '../api/client';

export default function ModelServing() {
  const [defs, setDefs] = useState<any[]>([]);
  const [deps, setDeps] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [defModalOpen, setDefModalOpen] = useState(false);
  const [depModalOpen, setDepModalOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [defForm] = Form.useForm();
  const [depForm] = Form.useForm();
  const [profileForm] = Form.useForm();

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.get('/models').then(r => Array.isArray(r.data) ? r.data : r.data?.items || []),
      api.get('/models/deployments').then(r => Array.isArray(r.data) ? r.data : r.data?.items || []),
      api.get('/models/profiles').then(r => Array.isArray(r.data) ? r.data : r.data?.items || []).catch(() => []),
    ]).then(([d, dp, pf]) => { setDefs(d); setDeps(dp); setProfiles(pf); }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  const handleCreateDef = async () => {
    try {
      const values = await defForm.validateFields();
      setSubmitting(true);
      await api.post('/models/definitions', {
        ...values,
        capabilities: values.capabilities ? values.capabilities.split(',').map((s: string) => s.trim()) : ['chat'],
        metadata: values.metadata ? JSON.parse(values.metadata) : {},
      });
      message.success('Model definition created');
      setDefModalOpen(false);
      defForm.resetFields();
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to create model definition');
    } finally { setSubmitting(false); }
  };

  const handleCreateDep = async () => {
    try {
      const values = await depForm.validateFields();
      setSubmitting(true);
      await api.post('/models/deployments', values);
      message.success('Deployment created');
      setDepModalOpen(false);
      depForm.resetFields();
      loadData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Failed to create deployment');
    } finally { setSubmitting(false); }
  };

  const handleCreateProfile = async () => {
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
  };

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
  ];

  const depColumns = [
    { title: 'Deployment ID', dataIndex: 'deployment_id', key: 'deployment_id', width: 180, ellipsis: true },
    { title: 'Model', dataIndex: 'model_id', key: 'model_id', width: 180, ellipsis: true },
    { title: 'Provider', dataIndex: 'provider', key: 'provider' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'enabled' ? 'green' : 'red'}>{v}</Tag> },
    { title: 'Health', dataIndex: 'health_status', key: 'health_status', render: (v: string) => <Tag color={v === 'healthy' ? 'green' : 'orange'}>{v}</Tag> },
    { title: 'Priority', dataIndex: 'priority', key: 'priority' },
    { title: 'Endpoint', dataIndex: 'endpoint', key: 'endpoint', ellipsis: true },
    {
      title: 'Action', key: 'action', width: 100,
      render: (_: any, record: any) => (
        <Button size="small" type="link"
          onClick={() => toggleDeployment(record.deployment_id, record.status === 'enabled' ? 'disable' : 'enable')}>
          {record.status === 'enabled' ? 'Disable' : 'Enable'}
        </Button>
      ),
    },
  ];

  const profileColumns = [
    { title: 'Profile ID', dataIndex: 'profile_id', key: 'profile_id', width: 200, ellipsis: true },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Description', dataIndex: 'description', key: 'description' },
  ];

  return (
    <>
      <Tabs items={[
        {
          key: 'defs', label: 'Model Definitions',
          children: (
            <Card>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setDefModalOpen(true)}>Add Definition</Button>
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
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setDepModalOpen(true)}>Add Deployment</Button>
              </Space>
              <Table dataSource={deps} columns={depColumns} rowKey="deployment_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
            </Card>
          ),
        },
        {
          key: 'profiles', label: 'Profiles',
          children: (
            <Card>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setProfileModalOpen(true)}>Add Profile</Button>
              </Space>
              <Table dataSource={profiles} columns={profileColumns} rowKey="profile_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
            </Card>
          ),
        },
      ]} />

      <Modal title="Add Model Definition" open={defModalOpen} onOk={handleCreateDef} onCancel={() => setDefModalOpen(false)} confirmLoading={submitting} width={600}>
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

      <Modal title="Add Deployment" open={depModalOpen} onOk={handleCreateDep} onCancel={() => setDepModalOpen(false)} confirmLoading={submitting} width={600}>
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
    </>
  );
}
