import { Table, Tag, Card, Tabs } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function ModelServing() {
  const [defs, setDefs] = useState<any[]>([]);
  const [deps, setDeps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/models').then(r => Array.isArray(r.data) ? r.data : r.data?.items || []),
      api.get('/models/deployments').then(r => Array.isArray(r.data) ? r.data : r.data?.items || []),
    ]).then(([d, dp]) => { setDefs(d); setDeps(dp); }).finally(() => setLoading(false));
  }, []);

  const defColumns = [
    { title: 'Model ID', dataIndex: 'model_id', key: 'model_id', width: 200, ellipsis: true },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Type', dataIndex: 'model_type', key: 'model_type', render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: 'Provider', dataIndex: 'provider_family', key: 'provider_family' },
    { title: 'Context', dataIndex: 'context_length', key: 'context_length' },
    { title: 'Embed Dim', dataIndex: 'embedding_dim', key: 'embedding_dim' },
  ];

  const depColumns = [
    { title: 'Deployment ID', dataIndex: 'deployment_id', key: 'deployment_id', width: 200, ellipsis: true },
    { title: 'Model', dataIndex: 'model_id', key: 'model_id', width: 200, ellipsis: true },
    { title: 'Provider', dataIndex: 'provider', key: 'provider' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={v === 'enabled' ? 'green' : 'red'}>{v}</Tag> },
    { title: 'Health', dataIndex: 'health_status', key: 'health_status', render: (v: string) => <Tag color={v === 'healthy' ? 'green' : 'orange'}>{v}</Tag> },
    { title: 'Priority', dataIndex: 'priority', key: 'priority' },
    { title: 'Endpoint', dataIndex: 'endpoint', key: 'endpoint', ellipsis: true },
  ];

  return (
    <Tabs items={[
      { key: 'defs', label: 'Model Definitions', children: <Card><Table dataSource={defs} columns={defColumns} rowKey="model_id" loading={loading} pagination={{ pageSize: 20 }} size="small" /></Card> },
      { key: 'deps', label: 'Deployments', children: <Card><Table dataSource={deps} columns={depColumns} rowKey="deployment_id" loading={loading} pagination={{ pageSize: 20 }} size="small" /></Card> },
    ]} />
  );
}
