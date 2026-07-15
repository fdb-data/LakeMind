import { Layout, Menu, theme } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined, DatabaseOutlined, CloudOutlined,
  ExperimentOutlined, AppstoreOutlined, SettingOutlined,
  SafetyOutlined, AuditOutlined, FileSearchOutlined, RobotOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { logout, api } from '../api/client';

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: '/overview', icon: <DashboardOutlined />, label: 'Overview' },
  { key: '/assets', icon: <DatabaseOutlined />, label: 'Assets' },
  { key: '/jobs', icon: <CloudOutlined />, label: 'Jobs' },
  { key: '/models', icon: <ExperimentOutlined />, label: 'Models' },
  { key: '/services', icon: <AppstoreOutlined />, label: 'Services' },
  { key: '/configuration', icon: <SettingOutlined />, label: 'Configuration' },
  { key: '/security', icon: <SafetyOutlined />, label: 'Security' },
  { key: '/operations', icon: <AuditOutlined />, label: 'Operations' },
  { key: '/audit', icon: <FileSearchOutlined />, label: 'Audit' },
  { key: '/steward', icon: <RobotOutlined />, label: 'Steward' },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { token: themeToken } = theme.useToken();

  useEffect(() => {
    if (location.pathname === '/login') return;
    apiCheck();
  }, [location.pathname]);

  async function apiCheck() {
    try {
      await api.get('/overview');
    } catch (err: any) {
      if (err?.response?.status === 401) {
        navigate('/login');
      }
    }
  }

  async function handleLogout() {
    try { await logout(); } catch {}
    navigate('/login');
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ height: 48, margin: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ color: '#fff', fontSize: collapsed ? 14 : 18, fontWeight: 'bold' }}>
            {collapsed ? 'LM' : 'LakeMind'}
          </span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: '0 16px', background: themeToken.colorBgContainer, display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
          <span onClick={handleLogout} style={{ cursor: 'pointer', color: themeToken.colorPrimary }}>
            <LogoutOutlined /> Logout
          </span>
        </Header>
        <Content style={{ margin: 16, padding: 24, background: themeToken.colorBgContainer, borderRadius: 8, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
