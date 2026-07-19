import { Card, Row, Col, Statistic, Spin, Alert, Typography, List, Tag, Space } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useNavigate } from 'react-router-dom';
import StatusBadge from '../components/StatusBadge';

const { Text, Link } = Typography;

interface CardData {
  value: any;
  observed_at: string | null;
  freshness_seconds: number | null;
  stale: boolean;
  partial: boolean;
  total?: number;
}

interface MissionControlView {
  _meta: {
    request_id: string;
    partial: boolean;
    partial_failure: string[];
    observed_at: string;
  };
  pending_approvals: CardData;
  failed_jobs: CardData;
  degraded_assets: CardData;
  unhealthy_deployments: CardData;
  service_health: CardData;
  cpu_usage: CardData;
  memory_usage: CardData;
  storage_usage: CardData;
  job_queue_depth: CardData;
  recent_changes: CardData;
  outbox_backlog: CardData;
}

function MetricCard({ title, data, href, suffix, navigate }: {
  title: string; data: CardData | undefined; href: string; suffix?: string; navigate: (path: string) => void;
}) {
  if (!data) {
    return <Card><Statistic title={title} value="--" /></Card>;
  }
  const staleWarn = data.stale;
  return (
    <Card hoverable onClick={() => navigate(href)} style={{ cursor: 'pointer' }}>
      <Statistic
        title={<Space>{title}{data.partial && <Tag color="orange">partial</Tag>}{staleWarn && <Tag color="red">stale</Tag>}</Space>}
        value={data.value ?? '--'}
        suffix={suffix}
      />
      {data.observed_at && (
        <Text type="secondary" style={{ fontSize: 11 }}>
          {new Date(data.observed_at).toLocaleTimeString()}
        </Text>
      )}
    </Card>
  );
}

export default function MissionControl() {
  const navigate = useNavigate();
  const [view, setView] = useState<MissionControlView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get('/view/mission-control');
      setView(resp.data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !view) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin size="large" /></div>;
  }

  if (error && !view) {
    return <Alert type="error" message="Failed to load Mission Control" description={error} />;
  }

  if (!view) return null;

  return (
    <div>
      <h2>Mission Control</h2>

      {view._meta?.partial && (
        <Alert
          type="warning"
          message="Some data sources are unavailable"
          description={`Partial failures: ${Array.isArray(view._meta?.partial_failure) ? view._meta.partial_failure.join(', ') : 'unknown'}`}
          style={{ marginBottom: 16 }}
        />
      )}

      <h3>Needs Attention</h3>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={4}><MetricCard title="Pending Approvals" data={view.pending_approvals} href="/operations?status=APPROVAL_REQUIRED" navigate={navigate} /></Col>
        <Col span={4}><MetricCard title="Failed Jobs" data={view.failed_jobs} href="/jobs?status=FAILED" navigate={navigate} /></Col>
        <Col span={4}><MetricCard title="Degraded Assets" data={view.degraded_assets} href="/assets?health=DEGRADED" navigate={navigate} /></Col>
        <Col span={4}><MetricCard title="Unhealthy Models" data={view.unhealthy_deployments} href="/models?health=UNHEALTHY" navigate={navigate} /></Col>
        <Col span={4}><MetricCard title="Config Drifts" data={view.outbox_backlog} href="/configuration?drift=true" navigate={navigate} /></Col>
        <Col span={4}><MetricCard title="Outbox Backlog" data={view.outbox_backlog} href="/services" navigate={navigate} /></Col>
      </Row>

      <h3>Platform Health</h3>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}><MetricCard title="Service Health" data={view.service_health} href="/services" navigate={navigate} /></Col>
        <Col span={6}><MetricCard title="CPU Usage" data={view.cpu_usage} href="/services" suffix="%" navigate={navigate} /></Col>
        <Col span={6}><MetricCard title="Memory Usage" data={view.memory_usage} href="/services" suffix="%" navigate={navigate} /></Col>
        <Col span={6}><MetricCard title="Storage Usage" data={view.storage_usage} href="/services" suffix="%" navigate={navigate} /></Col>
      </Row>

      <h3>Recent Changes</h3>
      <Card>
        <List
          dataSource={Array.isArray(view.recent_changes?.value) ? view.recent_changes.value : []}
          renderItem={(item: any) => (
            <List.Item>
              <List.Item.Meta
                title={<Space>{item.action} <StatusBadge status={item.result || 'unknown'} /></Space>}
                description={`${item.principal_id} • ${new Date(item.created_at).toLocaleString()}`}
              />
            </List.Item>
          )}
          locale={{ emptyText: 'No recent changes' }}
        />
      </Card>
    </div>
  );
}
