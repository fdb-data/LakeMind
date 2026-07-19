import { Card, List, Input, Tag, Space, Empty, Spin, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useNavigate, useSearchParams } from 'react-router-dom';

const { Text } = Typography;

interface SearchResult {
  object_type: string;
  object_id: string;
  title: string;
  subtitle?: string;
  scope_type: string;
  scope_id?: string;
  updated_at?: string;
}

const TYPE_COLORS: Record<string, string> = {
  tenant: 'blue',
  asset: 'green',
  job: 'cyan',
  model: 'purple',
  service: 'orange',
  operation: 'gold',
  config: 'magenta',
};

const TYPE_HREF: Record<string, string> = {
  tenant: '/organization',
  asset: '/assets',
  job: '/jobs',
  model: '/models',
  service: '/services',
  operation: '/operations',
  config: '/configuration',
};

export default function Search() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [groups, setGroups] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  async function doSearch(q: string) {
    if (!q.trim()) {
      setResults([]);
      setGroups({});
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const resp = await api.get('/search', { params: { q, page_size: 50 } });
      setResults(resp.data.items || []);
      setGroups(resp.data.groups || {});
      setTotal(resp.data.total || 0);
    } catch {
      setResults([]);
      setGroups({});
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const q = searchParams.get('q') || '';
    setQuery(q);
    doSearch(q);
  }, [searchParams]);

  function handleSearch(value: string) {
    setSearchParams({ q: value });
  }

  return (
    <div>
      <h2>Global Search</h2>
      <Input.Search
        placeholder="Search by name or ID..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onSearch={handleSearch}
        enterButton
        style={{ maxWidth: 600, marginBottom: 16 }}
      />

      {Object.keys(groups).length > 0 && (
        <Space style={{ marginBottom: 16 }}>
          {Object.entries(groups).map(([type, count]) => (
            <Tag key={type} color={TYPE_COLORS[type] || 'default'}>
              {type}: {count}
            </Tag>
          ))}
          <Text type="secondary">{total} results</Text>
        </Space>
      )}

      <Card>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
        ) : results.length === 0 ? (
          <Empty description={query ? 'No results found' : 'Type to search'} />
        ) : (
          <List
            dataSource={results}
            renderItem={(item) => (
              <List.Item
                onClick={() => navigate(`${TYPE_HREF[item.object_type] || '/'}/${item.object_id}`)}
                style={{ cursor: 'pointer' }}
              >
                <List.Item.Meta
                  title={<Space><Tag color={TYPE_COLORS[item.object_type] || 'default'}>{item.object_type}</Tag>{item.title}</Space>}
                  description={item.subtitle || item.object_id}
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}
