import { Table, Tag, Card } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Services() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/instances').then(r => {
      const items = r.data?.items || r.data || [];
      setData(Array.isArray(items) ? items : []);
    }).finally(() => setLoading(false));
  }, []);

  const columns = [
    { title: 'Instance ID', dataIndex: 'instance_id', key: 'instance_id', width: 200, ellipsis: true },
    { title: 'Service', dataIndex: 'service_type', key: 'service_type' },
    { title: 'Version', dataIndex: 'version', key: 'version' },
    { title: 'Endpoint', dataIndex: 'endpoint', key: 'endpoint', ellipsis: true },
    { title: 'Health', dataIndex: 'health_status', key: 'health_status', render: (v: string) => <Tag color={v === 'healthy' ? 'green' : 'orange'}>{v}</Tag> },
    { title: 'Last Heartbeat', dataIndex: 'last_heartbeat', key: 'last_heartbeat', render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
  ];

  return (
    <Card title="Service Instances">
      <Table dataSource={data} columns={columns} rowKey="instance_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
    </Card>
  );
}
