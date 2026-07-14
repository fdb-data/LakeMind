import { Table, Tag, Card, Button, Space, message } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Operations() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    api.get('/operations', { params: { page_size: 100 } }).then(r => {
      const items = r.data?.items || r.data || [];
      setData(Array.isArray(items) ? items : []);
    }).finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function approve(opId: string) {
    try { await api.post(`/operations/${opId}/approve`); message.success('Operation approved'); load(); }
    catch { message.error('Approve failed'); }
  }

  const columns = [
    { title: 'Operation ID', dataIndex: 'operation_id', key: 'operation_id', width: 200, ellipsis: true },
    { title: 'Type', dataIndex: 'op_type', key: 'op_type' },
    { title: 'Target', dataIndex: 'target_resource', key: 'target_resource' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (v: string) => {
      const color = v === 'APPROVED' ? 'green' : v === 'REJECTED' ? 'red' : v === 'PENDING' ? 'orange' : 'blue';
      return <Tag color={color}>{v}</Tag>;
    }},
    { title: 'Risk', dataIndex: 'risk_level', key: 'risk_level', render: (v: string) => <Tag color={v === 'HIGH' ? 'red' : 'orange'}>{v}</Tag> },
    { title: 'Initiator', dataIndex: 'initiator_id', key: 'initiator_id' },
    { title: 'Actions', key: 'actions', render: (_: any, row: any) => (
      <Space>
        {row.status === 'PENDING' && <Button size="small" type="primary" onClick={() => approve(row.operation_id)}>Approve</Button>}
      </Space>
    )},
  ];

  return (
    <Card title="Operations">
      <Table dataSource={data} columns={columns} rowKey="operation_id" loading={loading} pagination={{ pageSize: 20 }} size="small" />
    </Card>
  );
}
