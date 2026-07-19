import { Card, List, Tag, Button, Space, Empty, Spin, Badge } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useNavigate } from 'react-router-dom';
import StatusBadge from '../components/StatusBadge';

interface Notification {
  notification_id: string;
  category: string;
  severity: string;
  title: string;
  message?: string;
  resource_type?: string;
  resource_id?: string;
  read: boolean;
  created_at: string;
}

export default function Notifications() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [unreadOnly, setUnreadOnly] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const resp = await api.get('/notifications', { params: { unread_only: unreadOnly, page_size: 50 } });
      setItems(resp.data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [unreadOnly]);

  async function markRead(id: string) {
    try {
      await api.post(`/notifications/${id}/read`);
      load();
    } catch {}
  }

  return (
    <div>
      <h2>Notifications</h2>
      <Space style={{ marginBottom: 16 }}>
        <Button
          type={unreadOnly ? 'primary' : 'default'}
          onClick={() => setUnreadOnly(!unreadOnly)}
        >
          {unreadOnly ? 'Showing Unread Only' : 'Show Unread Only'}
        </Button>
        <Button onClick={load}>Refresh</Button>
      </Space>

      <Card>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
        ) : items.length === 0 ? (
          <Empty description="No notifications" />
        ) : (
          <List
            dataSource={items}
            renderItem={(item) => (
              <List.Item
                actions={!item.read ? [<Button size="small" onClick={() => markRead(item.notification_id)}>Mark Read</Button>] : []}
              >
                <List.Item.Meta
                  title={<Space>{!item.read && <Badge status="processing" />}<StatusBadge status={item.severity} />{item.title}</Space>}
                  description={item.message || item.created_at}
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}
