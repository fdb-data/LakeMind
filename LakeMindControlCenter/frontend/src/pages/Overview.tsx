import { Card, Col, Row, Statistic, Table, Tag, Spin } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Overview() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/overview').then(r => setData(r.data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" />;
  if (!data) return <div>No data</div>;

  const auditColumns = [
    { title: 'Event', dataIndex: 'event_type', key: 'event_type' },
    { title: 'Action', dataIndex: 'action', key: 'action' },
    { title: 'Result', dataIndex: 'result', key: 'result', render: (v: string) => <Tag color={v === 'success' ? 'green' : 'red'}>{v}</Tag> },
    { title: 'Time', dataIndex: 'created_at', key: 'created_at', render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="Instances" value={data.instances?.length || 0} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Total Assets" value={data.assets_total || 0} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Total Jobs" value={data.jobs_total || 0} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Recent Audit" value={data.recent_audit?.length || 0} /></Card>
        </Col>
      </Row>
      <Card title="Recent Audit Events">
        <Table
          dataSource={data.recent_audit || []}
          columns={auditColumns}
          rowKey="audit_id"
          pagination={{ pageSize: 5 }}
          size="small"
        />
      </Card>
    </div>
  );
}
