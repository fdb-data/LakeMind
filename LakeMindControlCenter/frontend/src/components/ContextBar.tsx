import { Select, Space, Typography, Tag, Input, Badge, Button, Dropdown, Avatar } from 'antd';
import { SearchOutlined, BellOutlined, EnvironmentOutlined, UserOutlined, LogoutOutlined } from '@ant-design/icons';
import { useCapabilities } from '../CapabilityContext';
import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useNavigate } from 'react-router-dom';

const { Text } = Typography;

export default function ContextBar({ onLogout }: { onLogout: () => void }) {
  const { me, switchTenant } = useCapabilities();
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (!me) return;
    const interval = setInterval(async () => {
      try {
        const resp = await api.get('/notifications/unread-count');
        setUnreadCount(resp.data.count || 0);
      } catch {}
    }, 30000);
    return () => clearInterval(interval);
  }, [me]);

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
  }

  async function handleTenantChange(tenantId: string) {
    await switchTenant(tenantId);
  }

  const tenantOptions = (me?.available_tenants || []).map((t) => ({
    value: t.tenant_id,
    label: t.name,
  }));

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '0 16px', flex: 1 }}>
      <Input
        prefix={<SearchOutlined />}
        placeholder="Search..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        onPressEnter={handleSearch}
        style={{ maxWidth: 300 }}
        allowClear
      />

      {tenantOptions.length > 0 && (
        <Select
          value={me?.active_tenant_id}
          options={tenantOptions}
          onChange={handleTenantChange}
          style={{ width: 180 }}
          showSearch
          optionFilterProp="label"
        />
      )}

      <Tag icon={<EnvironmentOutlined />} color="blue">dev</Tag>

      <Badge count={unreadCount} size="small">
        <Button icon={<BellOutlined />} type="text" onClick={() => navigate('/notifications')} />
      </Badge>

      <Dropdown menu={{
        items: [
          { key: 'profile', label: me?.username || me?.principal_id, icon: <UserOutlined /> },
          { type: 'divider' as const },
          { key: 'logout', label: 'Logout', icon: <LogoutOutlined />, danger: true },
        ],
        onClick: ({ key }) => key === 'logout' && onLogout(),
      }}>
        <Avatar size="small" style={{ cursor: 'pointer', background: '#1677ff' }}>
          {(me?.username || me?.principal_id || '?')[0]?.toUpperCase()}
        </Avatar>
      </Dropdown>
    </div>
  );
}
