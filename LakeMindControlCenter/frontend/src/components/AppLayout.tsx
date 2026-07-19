import { Layout, Menu, theme, Spin } from 'antd';
import { Outlet, useNavigate, useLocation, Navigate } from 'react-router-dom';
import {
  DashboardOutlined, DatabaseOutlined, CloudOutlined,
  ExperimentOutlined, AppstoreOutlined, SettingOutlined,
  SafetyOutlined, AuditOutlined, RobotOutlined,
  LogoutOutlined, TeamOutlined,
} from '@ant-design/icons';
import { useState, useEffect, ReactNode } from 'react';
import { logout, api } from '../api/client';
import { CapabilityProvider, useCapabilities } from '../CapabilityContext';
import ContextBar from './ContextBar';

const { Sider, Content, Header } = Layout;

interface NavItem {
  key: string;
  icon: ReactNode;
  label: string;
  capability?: string;
}

const navItems: NavItem[] = [
  { key: '/mission-control', icon: <DashboardOutlined />, label: 'Mission Control', capability: 'obs:view' },
  { key: '/organization', icon: <TeamOutlined />, label: 'Organization', capability: 'tenant:view' },
  { key: '/assets', icon: <DatabaseOutlined />, label: 'Assets', capability: 'asset:view' },
  { key: '/jobs', icon: <CloudOutlined />, label: 'Jobs', capability: 'job:view' },
  { key: '/models', icon: <ExperimentOutlined />, label: 'Models', capability: 'model:view' },
  { key: '/services', icon: <AppstoreOutlined />, label: 'Services', capability: 'obs:view' },
  { key: '/configuration', icon: <SettingOutlined />, label: 'Configuration', capability: 'config:view' },
  { key: '/security', icon: <SafetyOutlined />, label: 'Security', capability: 'operation:view' },
];

const secondaryItems: NavItem[] = [
  { key: '/operations', icon: <AuditOutlined />, label: 'Operations', capability: 'operation:view' },
  { key: '/audit', icon: <SafetyOutlined />, label: 'Audit', capability: 'audit:view' },
  { key: '/steward', icon: <RobotOutlined />, label: 'Steward', capability: 'steward:chat' },
];

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { token: themeToken } = theme.useToken();
  const { me, loading, hasCapability } = useCapabilities();

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

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!me) {
    return <Navigate to="/login" replace />;
  }

  const visibleNav = navItems.filter(item => !item.capability || hasCapability(item.capability));
  const visibleSecondary = secondaryItems.filter(item => !item.capability || hasCapability(item.capability));

  const allMenuItems = [
    ...visibleNav.map(item => ({ key: item.key, icon: item.icon, label: item.label })),
    { type: 'divider' as const, key: 'divider' },
    ...visibleSecondary.map(item => ({ key: item.key, icon: item.icon, label: item.label })),
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} width={220}>
        <div style={{ height: 48, margin: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ color: '#fff', fontSize: collapsed ? 14 : 18, fontWeight: 'bold' }}>
            {collapsed ? 'LM' : 'LakeMind'}
          </span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={allMenuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: 0, background: themeToken.colorBgContainer, display: 'flex', alignItems: 'center' }}>
          <ContextBar onLogout={handleLogout} />
        </Header>
        <Content style={{ margin: 16, padding: 24, background: themeToken.colorBgContainer, borderRadius: 8, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

export default function AppLayout() {
  return (
    <CapabilityProvider>
      <AppShell />
    </CapabilityProvider>
  );
}
