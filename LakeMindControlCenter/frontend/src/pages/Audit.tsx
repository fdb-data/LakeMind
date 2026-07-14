import { Table, Tag, Card } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Audit() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/audit', { params: { page_size: 100 } }).then(r => {
      const items = r.data?.items || r.data || [];
      setData(Array.isArray(items) ? items : []);
    }).finally(() => setLoading(false));
  }, []);

  const columns = [
    { title: 'Audit ID', dataIndex: 'audit_id', key: 'audit_id', width: 200, ellipsis: true },
    { title: 'Event', dataIndex: 'event_type', key: 'event_type', render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: 'Action', dataIndex: 'action', key: 'action' },
    { title: 'Result', dataIndex: 'result', key: 'result', render: (v: string) => <Tag color={v === 'success' ? 'green' : 'red'}>{v}</Tag> },
    { title: 'Principal', dataIndex: 'principal_id', key: 'principal_id', width: 180, ellipsis: true },
    { title: 'Tenant', dataIndex: 'tenant_id', key: 'tenant_id' },
    { title: 'Resource', dataIndex: 'resource_id', key: 'resource_id', width: 180, ellipsis: true },
    { title: 'Time', dataIndex: 'created_at', key: 'created_at', render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
  ];

  return (
    <Card title="Audit Log">
      <Table dataSource={data} columns={columns} rowKey="audit_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
    </Card>
  );
}
