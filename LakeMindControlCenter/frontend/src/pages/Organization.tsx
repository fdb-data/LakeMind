import { Card, Tabs, Table, Button, Space, Modal, Form, Input, Select, message } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useCapabilities } from '../CapabilityContext';
import RouteGuard from '../components/RouteGuard';
import DataExplorer from '../components/DataExplorer';
import StatusBadge from '../components/StatusBadge';

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
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [form] = Form.useForm();

  async function loadTenants() {
    setLoading(true);
    try {
      const resp = await api.get('/tenants');
      setTenants(resp.data.items || []);
    } catch {
      setTenants([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadMembers(tenantId: string) {
    try {
      const resp = await api.get(`/tenants/${tenantId}/memberships`);
      setMembers(resp.data.items || []);
    } catch {
      setMembers([]);
    }
  }

  useEffect(() => {
    loadTenants();
  }, []);

  async function handleCreate() {
    try {
      const values = await form.validateFields();
      await api.post('/tenants', values);
      message.success('Tenant created');
      setCreateModalOpen(false);
      form.resetFields();
      loadTenants();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to create tenant');
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
                  <Button type="primary" onClick={() => setCreateModalOpen(true)}>Create Tenant</Button>
                )}
              >
                <Table
                  dataSource={tenants}
                  rowKey="tenant_id"
                  loading={loading}
                  columns={[
                    { title: 'Name', dataIndex: 'name', key: 'name' },
                    { title: 'Status', dataIndex: 'status', key: 'status', render: (s: string) => <StatusBadge status={s} /> },
                    { title: 'Created', dataIndex: 'created_at', key: 'created_at', render: (v: string) => v ? new Date(v).toLocaleDateString() : '--' },
                    {
                      title: 'Actions', key: 'actions',
                      render: (_, record) => (
                        <Space>
                          <Button size="small" onClick={() => { setSelectedTenant(record); loadMembers(record.tenant_id); }}>Details</Button>
                          {hasCapability('tenant:suspend') && record.status === 'ACTIVE' && (
                            <Button size="small" danger onClick={() => handleSuspend(record.tenant_id)}>Suspend</Button>
                          )}
                          {hasCapability('tenant:suspend') && record.status === 'SUSPENDED' && (
                            <Button size="small" onClick={() => handleResume(record.tenant_id)}>Resume</Button>
                          )}
                        </Space>
                      ),
                    },
                  ]}
                  onRow={(record) => ({ onClick: () => { setSelectedTenant(record); loadMembers(record.tenant_id); }, style: { cursor: 'pointer' } })}
                />
              </Card>
            ),
          },
          {
            key: 'members',
            label: 'Members',
            children: selectedTenant ? (
              <Card title={`Members of ${selectedTenant.name}`}>
                <Table
                  dataSource={members}
                  rowKey="id"
                  columns={[
                    { title: 'Principal', dataIndex: 'principal_name', key: 'principal_name' },
                    { title: 'Type', dataIndex: 'principal_type', key: 'principal_type' },
                    { title: 'Status', dataIndex: 'membership_status', key: 'membership_status', render: (s: string) => <StatusBadge status={s} /> },
                    { title: 'Joined', dataIndex: 'joined_at', key: 'joined_at', render: (v: string) => v ? new Date(v).toLocaleDateString() : '--' },
                  ]}
                />
              </Card>
            ) : <Card><p>Select a tenant to view members</p></Card>,
          },
        ]}
      />

      <Modal
        title="Create Tenant"
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => setCreateModalOpen(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="admin_principal_id" label="Admin Principal ID" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
