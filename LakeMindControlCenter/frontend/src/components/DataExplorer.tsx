import { Table, Input, Space, Button, Select, Empty, Spin, Card } from 'antd';
import { SearchOutlined, ReloadOutlined, DownloadOutlined } from '@ant-design/icons';
import { ReactNode, useState, useEffect } from 'react';

export interface ColumnDef {
  title: string;
  dataIndex: string;
  key: string;
  render?: (value: any, record: any) => ReactNode;
  width?: number;
  sorter?: boolean;
}

interface DataExplorerProps {
  columns: ColumnDef[];
  fetchData: (params: { page: number; page_size: number; search?: string; sort?: string }) => Promise<{ items: any[]; total: number }>;
  rowKey?: string;
  onRowClick?: (record: any) => void;
  title?: string;
  extra?: ReactNode[];
  pageSize?: number;
  searchPlaceholder?: string;
}

export default function DataExplorer({
  columns, fetchData, rowKey = 'id', onRowClick, title, extra, pageSize = 20, searchPlaceholder = 'Search...',
}: DataExplorerProps) {
  const [data, setData] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchData({ page, page_size: pageSize, search: search || undefined });
      setData(result.items || []);
      setTotal(result.total || 0);
    } catch (err: any) {
      setError(err?.message || 'Failed to load data');
      setData([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, search]);

  return (
    <Card title={title} extra={extra && <Space>{extra}</Space>}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          allowClear
          style={{ width: 300 }}
        />
        <Button icon={<ReloadOutlined />} onClick={load}>Refresh</Button>
      </Space>

      {error && (
        <Result status="error" title="Loading Failed" subTitle={error} />
      )}

      <Table
        columns={columns}
        dataSource={data}
        rowKey={rowKey}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: false,
          onChange: (p) => setPage(p),
        }}
        onRow={(record) => ({
          onClick: () => onRowClick?.(record),
          style: onRowClick ? { cursor: 'pointer' } : {},
        })}
        locale={{
          emptyText: loading ? <Spin /> : <Empty description="No data" />,
        }}
        scroll={{ x: 'max-content' }}
      />
    </Card>
  );
}
