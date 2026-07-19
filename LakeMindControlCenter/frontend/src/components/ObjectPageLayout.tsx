import { Card, Tabs, Space, Button, Descriptions, Tag } from 'antd';
import { ReactNode } from 'react';
import StatusBadge from './StatusBadge';

interface ObjectPageLayoutProps {
  title: string;
  subtitle?: string;
  status?: string;
  badges?: ReactNode[];
  description?: { label: string; value: ReactNode }[];
  tabs?: { key: string; label: string; content: ReactNode }[];
  actions?: ReactNode[];
  loading?: boolean;
}

export default function ObjectPageLayout({
  title, subtitle, status, badges, description, tabs, actions, loading,
}: ObjectPageLayoutProps) {
  return (
    <div>
      <Card loading={loading}>
        <Space style={{ justifyContent: 'space-between', width: '100%', alignItems: 'flex-start' }}>
          <div>
            <Space align="center">
              <h2 style={{ margin: 0 }}>{title}</h2>
              {status && <StatusBadge status={status} />}
              {badges}
            </Space>
            {subtitle && <div style={{ color: '#888', marginTop: 4 }}>{subtitle}</div>}
          </div>
          {actions && <Space>{actions}</Space>}
        </Space>

        {description && (
          <Descriptions style={{ marginTop: 16 }} column={3} size="small">
            {description.map((item) => (
              <Descriptions.Item key={item.label} label={item.label}>{item.value}</Descriptions.Item>
            ))}
          </Descriptions>
        )}
      </Card>

      {tabs && tabs.length > 0 && (
        <Card style={{ marginTop: 16 }}>
          <Tabs
            items={tabs.map((tab) => ({
              key: tab.key,
              label: tab.label,
              children: tab.content,
            }))}
          />
        </Card>
      )}
    </div>
  );
}
