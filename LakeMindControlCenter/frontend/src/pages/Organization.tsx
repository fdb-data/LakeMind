import { Card, Tabs, Table, Button, Space, Modal, Form, Input, Select, message, Drawer, Descriptions, Tag, Popconfirm, Tooltip } from 'antd';
import { PlusOutlined, EditOutlined, EyeOutlined, UserDeleteOutlined, StopOutlined, PlayCircleOutlined, InboxOutlined } from '@ant-design/icons';
import { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import { useCapabilities } from '../CapabilityContext';
import RouteGuard from '../components/RouteGuard';
import StatusBadge from '../components/StatusBadge';

const { TextArea } = Input;

function parseJson(raw: string | undefined | null, fallback: any): any {
  if (!raw) return fallback;
  try { return JSON.parse(raw); } catch { return fallback; }
}

function quotasSummary(quotas: any): string {
  if (!quotas || typeof quotas !== 'object' || Object.keys(quotas).length === 0) return '—';
  const keys = Object.keys(quotas);
  return keys.slice(0, 3).map((k) => `${k}: ${quotas[k]}`).join(', ') + (keys.length > 3 ? ' …' : '');
}

export default function Organization() {
  return (
    <RouteGuard capability="tenant:view">
      <OrganizationContent />
    </RouteGuard>
  );
}

function OrganizationContent() {
  const { hasCapability } = useCapabilities();
  const [tenants, setTenants] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<any | null>(null);
  const [members, setMembers] = useState<any[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingTenant, setEditingTenant] = useState<any | null>(null);
  const [addMemberModalOpen, setAddMemberModalOpen] = useState(false);
  const [detailDrawer, setDetailDrawer] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [memberForm] = Form.useForm();

  const loadTenants = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get('/tenants');
      setTenants(resp.data.items || []);
    } catch {
      setTenants([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMembers = useCallback(async (tenantId: string) => {
    setMembersLoading(true);
    try {
      const resp = await api.get(`/tenants/${tenantId}/memberships`);
      setMembers(resp.data.items || []);
    } catch {
      setMembers([]);
    } finally {
      setMembersLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTenants();
  }, [loadTenants]);

  async function handleCreate() {
    try {
      const values = await createForm.validateFields();
      setSubmitting(true);
      const payload: any = {
        name: values.name,
        admin_principal_id: values.admin_principal_id,
      };
      if (values.quotas) payload.quotas = parseJson(values.quotas, undefined);
      if (values.allowed_models) payload.allowed_models = values.allowed_models;
      if (values.config_template) payload.config_template = values.config_template;
      await api.post('/tenants', payload);
      message.success('Tenant created');
      setCreateModalOpen(false);
      createForm.resetFields();
      loadTenants();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || 'Failed to create tenant');
    } finally {
      setSubmitting(false);
    }
  }

  function openEdit(tenant: any) {
    setEditingTenant(tenant);
    editForm.setFieldsValue({
      quotas: tenant.quotas ? JSON.stringify(tenant.quotas, null, 2) : '',
      allowed_models: Array.isArray(tenant.allowed_models) ? tenant.allowed_models : [],
    });
    setEditModalOpen(true);
  }

  async function handleEdit() {
    if (!editingTenant) return;
    try {
      const values = await editForm.validateFields();
      setSubmitting(true);
      const payload: any = {};
      if (values.quotas !== undefined && values.quotas !== '') {
        const parsed = parseJson(values.quotas, null);
        if (parsed !== null) payload.quotas = parsed;
      }
      if (values.allowed_models !== undefined) payload.allowed_models = values.allowed_models;
      await api.put(`/tenants/${editingTenant.tenant_id}`, payload);
      message.success('Tenant updated');
      setEditModalOpen(false);
      setEditingTenant(null);
      loadTenants();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || 'Failed to update tenant');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSuspend(tenantId: string) {
    try {
      await api.post(`/tenants/${tenantId}/suspend`);
      message.success('Tenant suspended');
      loadTenants();
    } catch {
      message.error('Failed to suspend');
    }
  }

  async function handleResume(tenantId: string) {
    try {
      await api.post(`/tenants/${tenantId}/resume`);
      message.success('Tenant resumed');
      loadTenants();
    } catch {
      message.error('Failed to resume');
    }
  }

  async function handleArchive(tenantId: string) {
    try {
      await api.post(`/tenants/${tenantId}/archive`);
      message.success('Tenant archived');
      loadTenants();
    } catch {
      message.error('Failed to archive');
    }
  }

  async function openDetail(tenant: any) {
    setDetailLoading(true);
    setDetailDrawer({ tenant });
    try {
      const resp = await api.get(`/view/tenant-detail/${tenant.tenant_id}`);
      setDetailDrawer(resp.data);
    } catch {
      message.error('Failed to load tenant detail');
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleAddMember() {
    if (!selectedTenant) return;
    try {
      const values = await memberForm.validateFields();
      setSubmitting(true);
      await api.post(`/tenants/${selectedTenant.tenant_id}/memberships`, {
        principal_id: values.principal_id,
        role_name: values.role_name || 'agent',
      });
      message.success('Member added');
      setAddMemberModalOpen(false);
      memberForm.resetFields();
      loadMembers(selectedTenant.tenant_id);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || 'Failed to add member');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevokeMember(membershipId: string) {
    if (!selectedTenant) return;
    try {
      await api.post(`/tenants/${selectedTenant.tenant_id}/memberships/${membershipId}/revoke`);
      message.success('Member revoked');
      loadMembers(selectedTenant.tenant_id);
    } catch {
      message.error('Failed to revoke member');
    }
  }

  function selectTenant(tenant: any) {
    setSelectedTenant(tenant);
    loadMembers(tenant.tenant_id);
  }

  const tenantColumns = [
    { title: 'Name', dataIndex: 'name', key: 'name', render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (s: string) => <StatusBadge status={s} /> },
    { title: 'Quotas', key: 'quotas', render: (_: any, r: any) => <Tooltip title={r.quotas ? JSON.stringify(r.quotas) : ''}><span>{quotasSummary(r.quotas)}</span></Tooltip> },
    { title: 'Models', key: 'allowed_models', render: (_: any, r: any) => {
      const models = Array.isArray(r.allowed_models) ? r.allowed_models : [];
      return models.length > 0 ? models.slice(0, 2).map((m: string) => <Tag key={m}>{m}</Tag>) : <span>—</span>;
    }},
    { title: 'Created', dataIndex: 'created_at', key: 'created_at', render: (v: string) => v ? new Date(v).toLocaleDateString() : '--' },
    {
      title: 'Actions', key: 'actions', width: 280,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(record)}>Details</Button>
          {hasCapability('tenant:suspend') && record.status !== 'ARCHIVED' && (
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>Edit</Button>
          )}
          {hasCapability('tenant:suspend') && record.status === 'ACTIVE' && (
            <Button size="small" danger icon={<StopOutlined />} onClick={() => handleSuspend(record.tenant_id)}>Suspend</Button>
          )}
          {hasCapability('tenant:suspend') && record.status === 'SUSPENDED' && (
            <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleResume(record.tenant_id)}>Resume</Button>
          )}
          {hasCapability('tenant:suspend') && record.status !== 'ARCHIVED' && (
            <Popconfirm title="Archive this tenant? All memberships will be revoked." onConfirm={() => handleArchive(record.tenant_id)} okText="Archive" okButtonProps={{ danger: true }}>
              <Button size="small" danger icon={<InboxOutlined />}>Archive</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  const memberColumns = [
    { title: 'Principal', dataIndex: 'principal_name', key: 'principal_name' },
    { title: 'Type', dataIndex: 'principal_type', key: 'principal_type', render: (v: string) => v ? <Tag color="cyan">{v}</Tag> : '—' },
    { title: 'Status', dataIndex: 'membership_status', key: 'membership_status', render: (s: string) => <StatusBadge status={s} /> },
    { title: 'Joined', dataIndex: 'joined_at', key: 'joined_at', render: (v: string) => v ? new Date(v).toLocaleDateString() : '--' },
    {
      title: 'Actions', key: 'actions',
      render: (_: any, record: any) => (
        hasCapability('tenant:suspend') && record.membership_status === 'ACTIVE' ? (
          <Popconfirm title="Revoke this membership?" onConfirm={() => handleRevokeMember(record.id)} okText="Revoke" okButtonProps={{ danger: true }}>
            <Button size="small" danger icon={<UserDeleteOutlined />}>Revoke</Button>
          </Popconfirm>
        ) : null
      ),
    },
  ];

  const detailTenant = detailDrawer?.tenant || detailDrawer;

  return (
    <div>
      <h2>Organization</h2>
      <Tabs
        items={[
          {
            key: 'tenants',
            label: 'Tenants',
            children: (
              <Card
                extra={hasCapability('tenant:create') && (
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>Create Tenant</Button>
                )}
              >
                <Table
                  dataSource={tenants}
                  rowKey="tenant_id"
                  loading={loading}
                  columns={tenantColumns}
                  onRow={(record) => ({ onClick: () => selectTenant(record), style: { cursor: 'pointer' } })}
                />
              </Card>
            ),
          },
          {
            key: 'members',
            label: 'Members',
            children: selectedTenant ? (
              <Card
                title={`Members of ${selectedTenant.name}`}
                extra={hasCapability('tenant:create') && selectedTenant.status !== 'ARCHIVED' && (
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddMemberModalOpen(true)}>Add Member</Button>
                )}
              >
                <Table
                  dataSource={members}
                  rowKey="id"
                  loading={membersLoading}
                  columns={memberColumns}
                />
              </Card>
            ) : <Card><p>Select a tenant to view members</p></Card>,
          },
        ]}
      />

      {/* Create Tenant Modal */}
      <Modal
        title="Create Tenant"
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => setCreateModalOpen(false)}
        confirmLoading={submitting}
        width={560}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Name is required' }]}>
            <Input placeholder="e.g. my-team" />
          </Form.Item>
          <Form.Item name="admin_principal_id" label="Admin Principal ID" rules={[{ required: true, message: 'Admin principal is required' }]}>
            <Input placeholder="e.g. usr_xxx" />
          </Form.Item>
          <Form.Item name="allowed_models" label="Allowed Models" tooltip="Model profiles this tenant can use">
            <Select mode="tags" placeholder="Enter model profile names" tokenSeparators={[',']} />
          </Form.Item>
          <Form.Item name="quotas" label="Quotas (JSON)" tooltip='e.g. {"max_jobs": 100, "max_storage_gb": 50}'>
            <TextArea rows={3} placeholder='{"max_jobs": 100, "max_storage_gb": 50}' />
          </Form.Item>
          <Form.Item name="config_template" label="Config Template" tooltip="Configuration template name">
            <Input placeholder="default" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Tenant Modal */}
      <Modal
        title={editingTenant ? `Edit Tenant: ${editingTenant.name}` : 'Edit Tenant'}
        open={editModalOpen}
        onOk={handleEdit}
        onCancel={() => { setEditModalOpen(false); setEditingTenant(null); }}
        confirmLoading={submitting}
        width={560}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="allowed_models" label="Allowed Models" tooltip="Model profiles this tenant can use">
            <Select mode="tags" placeholder="Enter model profile names" tokenSeparators={[',']} />
          </Form.Item>
          <Form.Item name="quotas" label="Quotas (JSON)" tooltip='e.g. {"max_jobs": 100, "max_storage_gb": 50}'>
            <TextArea rows={4} placeholder='{"max_jobs": 100, "max_storage_gb": 50}' />
          </Form.Item>
        </Form>
      </Modal>

      {/* Add Member Modal */}
      <Modal
        title={selectedTenant ? `Add Member to ${selectedTenant.name}` : 'Add Member'}
        open={addMemberModalOpen}
        onOk={handleAddMember}
        onCancel={() => setAddMemberModalOpen(false)}
        confirmLoading={submitting}
        width={480}
      >
        <Form form={memberForm} layout="vertical">
          <Form.Item name="principal_id" label="Principal ID" rules={[{ required: true, message: 'Principal ID is required' }]}>
            <Input placeholder="e.g. usr_xxx" />
          </Form.Item>
          <Form.Item name="role_name" label="Role" initialValue="agent">
            <Select
              options={[
                { value: 'agent', label: 'Agent' },
                { value: 'tenant_admin', label: 'Tenant Admin' },
                { value: 'platform_admin', label: 'Platform Admin' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Tenant Detail Drawer */}
      <Drawer
        title="Tenant Detail"
        open={!!detailDrawer}
        onClose={() => setDetailDrawer(null)}
        width={680}
      >
        {detailLoading ? (
          <p>Loading…</p>
        ) : detailDrawer && detailTenant ? (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="Name">{detailTenant.name}</Descriptions.Item>
              <Descriptions.Item label="Tenant ID">{detailTenant.tenant_id}</Descriptions.Item>
              <Descriptions.Item label="Status"><StatusBadge status={detailTenant.status} /></Descriptions.Item>
              <Descriptions.Item label="Created">{detailTenant.created_at ? new Date(detailTenant.created_at).toLocaleString() : '—'}</Descriptions.Item>
              <Descriptions.Item label="Allowed Models">
                {Array.isArray(detailTenant.allowed_models) && detailTenant.allowed_models.length > 0
                  ? detailTenant.allowed_models.map((m: string) => <Tag key={m}>{m}</Tag>)
                  : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Quotas">
                {detailTenant.quotas ? <pre style={{ margin: 0, fontSize: 11 }}>{JSON.stringify(detailTenant.quotas, null, 2)}</pre> : '—'}
              </Descriptions.Item>
            </Descriptions>

            <h4>Members</h4>
            <Table
              dataSource={detailDrawer.members || []}
              rowKey="id"
              size="small"
              pagination={false}
              columns={[
                { title: 'Principal', dataIndex: 'principal_name', key: 'principal_name' },
                { title: 'Type', dataIndex: 'principal_type', key: 'principal_type' },
                { title: 'Status', dataIndex: 'membership_status', key: 'membership_status', render: (s: string) => <StatusBadge status={s} /> },
              ]}
            />

            <h4>Recent Audit</h4>
            <Table
              dataSource={detailDrawer.recent_audit || []}
              rowKey={(r: any) => r.event_id || r.audit_id || JSON.stringify(r)}
              size="small"
              pagination={false}
              columns={[
                { title: 'Event', dataIndex: 'event_type', key: 'event_type', render: (v: string) => v ? <Tag color="purple">{v}</Tag> : '—' },
                { title: 'Action', dataIndex: 'action', key: 'action' },
                { title: 'Result', dataIndex: 'result', key: 'result', render: (s: string) => s ? <Tag color={s === 'success' ? 'green' : 'red'}>{s}</Tag> : '—' },
                { title: 'Time', dataIndex: 'observed_at', key: 'observed_at', render: (v: string) => v ? new Date(v).toLocaleString() : '—' },
              ]}
            />
          </Space>
        ) : <p>No data</p>}
      </Drawer>
    </div>
  );
}
