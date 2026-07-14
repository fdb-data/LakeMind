import { Table, Tag, Card, Button, Space, message } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Jobs() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    api.get('/jobs', { params: { page_size: 100 } }).then(r => {
      const items = r.data?.items || r.data || [];
      setData(Array.isArray(items) ? items : []);
    }).finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function retry(jobId: string) {
    try { await api.post(`/jobs/${jobId}/retry`); message.success('Job retry submitted'); load(); }
    catch { message.error('Retry failed'); }
  }

  async function cancel(jobId: string) {
    try { await api.post(`/jobs/${jobId}/cancel`); message.success('Job cancelled'); load(); }
    catch { message.error('Cancel failed'); }
  }

  const columns = [
    { title: 'Job ID', dataIndex: 'job_id', key: 'job_id', width: 200, ellipsis: true },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (v: string) => {
      const color = v === 'SUCCEEDED' ? 'green' : v === 'FAILED' ? 'red' : v === 'RUNNING' ? 'blue' : 'orange';
      return <Tag color={color}>{v}</Tag>;
    }},
    { title: 'Tenant', dataIndex: 'tenant_id', key: 'tenant_id' },
    { title: 'Initiator', dataIndex: 'initiator_id', key: 'initiator_id' },
    { title: 'Created', dataIndex: 'created_at', key: 'created_at', render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
    { title: 'Actions', key: 'actions', render: (_: any, row: any) => (
      <Space>
        <Button size="small" onClick={() => retry(row.job_id)}>Retry</Button>
        <Button size="small" danger onClick={() => cancel(row.job_id)}>Cancel</Button>
      </Space>
    )},
  ];

  return (
    <Card title="Jobs">
      <Table dataSource={data} columns={columns} rowKey="job_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
    </Card>
  );
}
