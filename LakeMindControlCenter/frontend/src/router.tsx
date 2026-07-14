import { createBrowserRouter, Navigate } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import Login from './pages/Login';
import Overview from './pages/Overview';
import Assets from './pages/Assets';
import Jobs from './pages/Jobs';
import ModelServing from './pages/ModelServing';
import Services from './pages/Services';
import Configuration from './pages/Configuration';
import Security from './pages/Security';
import Operations from './pages/Operations';
import Audit from './pages/Audit';
import Steward from './pages/Steward';

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { path: '/', element: <Navigate to="/overview" /> },
      { path: '/overview', element: <Overview /> },
      { path: '/assets', element: <Assets /> },
      { path: '/jobs', element: <Jobs /> },
      { path: '/models', element: <ModelServing /> },
      { path: '/services', element: <Services /> },
      { path: '/configuration', element: <Configuration /> },
      { path: '/security', element: <Security /> },
      { path: '/operations', element: <Operations /> },
      { path: '/audit', element: <Audit /> },
      { path: '/steward', element: <Steward /> },
    ],
  },
]);
