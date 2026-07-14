import { Table, Tag, Card } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Security() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/security/principals').then(r => {
      const items = r.data?.items || r.data || [];
      setData(Array.isArray(items) ? items : []);
    }).finally(() => setLoading(false));
  }, []);

  const columns = [
    { title: 'Principal ID', dataIndex: 'principal_id', key: 'principal_id', width: 200, ellipsis: true },
    { title: 'Type', dataIndex: 'principal_type', key: 'principal_type', render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: 'Tenant', dataIndex: 'tenant_id', key: 'tenant_id' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v}</Tag> },
  ];

  return (
    <Card title="Security Principals">
      <Table dataSource={data} columns={columns} rowKey="principal_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
    </Card>
  );
}
