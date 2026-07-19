import { createBrowserRouter, Navigate } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import Login from './pages/Login';
import MissionControl from './pages/MissionControl';
import Organization from './pages/Organization';
import Assets from './pages/Assets';
import Jobs from './pages/Jobs';
import ModelServing from './pages/ModelServing';
import Services from './pages/Services';
import Configuration from './pages/Configuration';
import Security from './pages/Security';
import Operations from './pages/Operations';
import Audit from './pages/Audit';
import Steward from './pages/Steward';
import Search from './pages/Search';
import Notifications from './pages/Notifications';
import RouteGuard from './components/RouteGuard';

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { path: '/', element: <Navigate to="/mission-control" /> },
      { path: '/mission-control', element: <MissionControl /> },
      { path: '/organization', element: <Organization /> },
      { path: '/assets', element: <RouteGuard capability="asset:view"><Assets /></RouteGuard> },
      { path: '/jobs', element: <RouteGuard capability="job:view"><Jobs /></RouteGuard> },
      { path: '/models', element: <RouteGuard capability="model:view"><ModelServing /></RouteGuard> },
      { path: '/services', element: <RouteGuard capability="obs:view"><Services /></RouteGuard> },
      { path: '/configuration', element: <RouteGuard capability="config:view"><Configuration /></RouteGuard> },
      { path: '/security', element: <RouteGuard capability="operation:view"><Security /></RouteGuard> },
      { path: '/operations', element: <RouteGuard capability="operation:view"><Operations /></RouteGuard> },
      { path: '/audit', element: <RouteGuard capability="audit:view"><Audit /></RouteGuard> },
      { path: '/steward', element: <RouteGuard capability="steward:chat"><Steward /></RouteGuard> },
      { path: '/search', element: <Search /> },
      { path: '/notifications', element: <Notifications /> },
      { path: '/overview', element: <Navigate to="/mission-control" /> },
    ],
  },
]);
