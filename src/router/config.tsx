
import { RouteObject } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import DashboardLayout from '../components/feature/DashboardLayout';

const HomePage = lazy(() => import('../pages/home/page'));
const LoginPage = lazy(() => import('../pages/login/page'));
const DashboardPage = lazy(() => import('../pages/dashboard/page'));
const StrategiesPage = lazy(() => import('../pages/strategies/page'));
const AIChatPage = lazy(() => import('../pages/ai-chat/page'));
const RiskManagerPage = lazy(() => import('../pages/risk-manager/page'));
const IntegrationsPage = lazy(() => import('../pages/integrations/page'));
const SettingsPage = lazy(() => import('../pages/settings/page'));
const SystemControlPage = lazy(() => import('../pages/system-control/page'));
const DiagnosticsPage = lazy(() => import('../pages/diagnostics/page'));
const CodeAnalysisPage = lazy(() => import('../pages/code-analysis/page'));
const FileManagerPage = lazy(() => import('../pages/file-manager/page'));
const SecurityPage = lazy(() => import('../pages/security/page'));
const AuditPage = lazy(() => import('../pages/audit/page'));
const NotFoundPage = lazy(() => import('../pages/NotFound'));

// Componente de Loading JOKA
const LoadingSpinner = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-red-950 to-orange-900">
    <div className="text-center">
      <img 
        src="https://static.readdy.ai/image/d55f7533e2770f6cf984b3b0dd8016a8/0f4cef46158b860125e33f2644b930f5.png" 
        alt="JOKA" 
        className="w-20 h-20 object-contain mx-auto mb-6 animate-bounce drop-shadow-2xl"
      />
      <div className="w-12 h-12 border-4 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
      <p className="text-orange-300 text-sm font-bold tracking-wide">
        🔥 JOKA SYSTEM LOADING... 🔥
      </p>
    </div>
  </div>
);

// Wrapper para rotas protegidas com DashboardLayout
const DashboardRoute = ({ children }: { children: React.ReactNode }) => (
  <Suspense fallback={<LoadingSpinner />}>
    <DashboardLayout>
      {children}
    </DashboardLayout>
  </Suspense>
);

// Wrapper para rotas públicas
const PublicRoute = ({ children }: { children: React.ReactNode }) => (
  <Suspense fallback={<LoadingSpinner />}>
    {children}
  </Suspense>
);

const routes: RouteObject[] = [
  // 🏠 HOMEPAGE (Redireciona para dashboard automaticamente)
  { 
    path: '/', 
    element: <PublicRoute><HomePage /></PublicRoute>
  },
  
  // 🔐 LOGIN (Independente)
  { 
    path: '/login', 
    element: <PublicRoute><LoginPage /></PublicRoute>
  },
  
  // 📊 DASHBOARD (Principal - COM sidebar)
  { 
    path: '/dashboard', 
    element: <DashboardRoute><DashboardPage /></DashboardRoute>
  },
  
  // 🎯 ESTRATÉGIAS (COM sidebar)
  { 
    path: '/strategies', 
    element: <DashboardRoute><StrategiesPage /></DashboardRoute>
  },
  
  // 🤖 IA CHAT (COM sidebar)
  { 
    path: '/ai-chat', 
    element: <DashboardRoute><AIChatPage /></DashboardRoute>
  },
  
  // ⚠️ GESTÃO DE RISCO (COM sidebar)
  { 
    path: '/risk-manager', 
    element: <DashboardRoute><RiskManagerPage /></DashboardRoute>
  },
  
  // 🔗 INTEGRAÇÕES (COM sidebar)
  { 
    path: '/integrations', 
    element: <DashboardRoute><IntegrationsPage /></DashboardRoute>
  },
  
  // ⚙️ DEFINIÇÕES (COM sidebar)
  { 
    path: '/settings', 
    element: <DashboardRoute><SettingsPage /></DashboardRoute>
  },
  
  // 🖥️ CONTROLO DO SISTEMA (COM sidebar)
  { 
    path: '/system-control', 
    element: <DashboardRoute><SystemControlPage /></DashboardRoute>
  },
  
  // 🔍 DIAGNÓSTICOS (COM sidebar)
  { 
    path: '/diagnostics', 
    element: <DashboardRoute><DiagnosticsPage /></DashboardRoute>
  },
  
  // 💻 ANÁLISE DE CÓDIGO (COM sidebar)
  { 
    path: '/code-analysis', 
    element: <DashboardRoute><CodeAnalysisPage /></DashboardRoute>
  },
  
  // 📁 GESTOR DE FICHEIROS (COM sidebar)
  { 
    path: '/file-manager', 
    element: <DashboardRoute><FileManagerPage /></DashboardRoute>
  },
  
  // 🔐 SEGURANÇA (COM sidebar)
  { 
    path: '/security', 
    element: <DashboardRoute><SecurityPage /></DashboardRoute>
  },
  
  // 📋 AUDITORIA (COM sidebar)
  { 
    path: '/audit', 
    element: <DashboardRoute><AuditPage /></DashboardRoute>
  },
  
  // 404 - NOT FOUND
  { 
    path: '*', 
    element: <PublicRoute><NotFoundPage /></PublicRoute>
  }
];

export default routes;
