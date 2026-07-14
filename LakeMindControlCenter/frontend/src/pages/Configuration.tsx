import { Card, Descriptions, Spin } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Configuration() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/configuration').then(r => setData(r.data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" />;
  if (!data) return <div>No configuration data</div>;

  const entries = Object.entries(data).filter(([_, v]) => typeof v !== 'object' || v === null);

  return (
    <Card title="Configuration">
      <Descriptions bordered column={2}>
        {entries.map(([k, v]) => (
          <Descriptions.Item key={k} label={k}>{String(v)}</Descriptions.Item>
        ))}
      </Descriptions>
    </Card>
  );
}
