import { Table, Tag, Card, Input } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Assets() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/assets', { params: { page_size: 100 } }).then(r => {
      const items = r.data?.items || r.data || [];
      setData(Array.isArray(items) ? items : []);
    }).finally(() => setLoading(false));
  }, []);

  const columns = [
    { title: 'Asset ID', dataIndex: 'asset_id', key: 'asset_id', width: 200, ellipsis: true },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Type', dataIndex: 'asset_type', key: 'asset_type', render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: 'Tenant', dataIndex: 'tenant_id', key: 'tenant_id' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'READY' ? 'green' : 'orange'}>{v}</Tag> },
    { title: 'Created', dataIndex: 'created_at', key: 'created_at', render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
  ];

  return (
    <Card title="Assets">
      <Table dataSource={data} columns={columns} rowKey="asset_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
    </Card>
  );
}
