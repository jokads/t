import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const location = useLocation();

  const menuItems = [
    { icon: 'ri-dashboard-line', label: 'Dashboard', path: '/dashboard' },
    { icon: 'ri-line-chart-line', label: 'Estratégias', path: '/strategies' },
    { icon: 'ri-robot-line', label: 'Assistente IA', path: '/ai-chat' },
    { icon: 'ri-shield-check-line', label: 'Gestão de Risco', path: '/risk-manager' },
    { icon: 'ri-bug-line', label: 'Diagnóstico', path: '/diagnostics' },
    { icon: 'ri-code-box-line', label: 'Análise de Código', path: '/code-analysis' },
    { icon: 'ri-folder-open-line', label: 'Gestor de Ficheiros', path: '/file-manager' },
    { icon: 'ri-lock-line', label: 'Segurança', path: '/security' },
    { icon: 'ri-file-list-line', label: 'Auditoria', path: '/audit' },
    { icon: 'ri-links-line', label: 'Integrações', path: '/integrations' },
    { icon: 'ri-settings-3-line', label: 'Definições', path: '/settings' },
    { icon: 'ri-terminal-box-line', label: 'Controlo do Sistema', path: '/system-control' }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-950 via-red-950 to-purple-900">
      {/* Sidebar */}
      <aside className={`fixed left-0 top-0 h-full bg-black/40 backdrop-blur-xl border-r border-orange-500/20 transition-all duration-300 z-50 ${isSidebarOpen ? 'w-64' : 'w-20'}`}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-orange-500/20">
            <div className="flex items-center gap-3">
              <img 
                src="https://static.readdy.ai/image/d55f7533e2770f6cf984b3b0dd8016a8/0f4cef46158b860125e33f2644b930f5.png" 
                alt="JOKA Logo" 
                className="w-10 h-10 object-contain drop-shadow-[0_0_8px_rgba(251,146,60,0.5)]"
              />
              {isSidebarOpen && (
                <span className="text-xl font-bold gradient-text">JOKA</span>
              )}
            </div>
          </div>

          {/* Menu */}
          <nav className="flex-1 p-4 overflow-y-auto custom-scrollbar">
            <ul className="space-y-2">
              {menuItems.map((item) => (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all group ${
                      location.pathname === item.path
                        ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-lg shadow-orange-500/30'
                        : 'text-purple-200 hover:bg-purple-800/50'
                    }`}
                  >
                    <i className={`${item.icon} text-xl w-6 h-6 flex items-center justify-center`}></i>
                    {isSidebarOpen && <span className="text-sm font-medium whitespace-nowrap">{item.label}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          {/* Toggle Button */}
          <div className="p-4 border-t border-orange-500/20">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg transition-all cursor-pointer"
            >
              <i className={`${isSidebarOpen ? 'ri-arrow-left-s-line' : 'ri-arrow-right-s-line'} text-xl`}></i>
              {isSidebarOpen && <span className="text-sm font-medium whitespace-nowrap">Recolher</span>}
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className={`transition-all duration-300 ${isSidebarOpen ? 'ml-64' : 'ml-20'}`}>
        {/* Header */}
        <header className="sticky top-0 z-40 bg-black/40 backdrop-blur-xl border-b border-orange-500/20">
          <div className="px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <img 
                  src="https://static.readdy.ai/image/d55f7533e2770f6cf984b3b0dd8016a8/0f4cef46158b860125e33f2644b930f5.png" 
                  alt="JOKA" 
                  className="w-8 h-8 object-contain drop-shadow-[0_0_8px_rgba(251,146,60,0.5)]"
                />
                <div>
                  <h2 className="text-lg font-bold gradient-text">Trading Bot JOKA</h2>
                  <p className="text-xs text-purple-300">Dashboard Hardcore</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 px-4 py-2 bg-green-500/10 rounded-lg border border-green-500/30">
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  <span className="text-sm text-green-400 font-medium whitespace-nowrap">Sistema Ativo</span>
                </div>
                <Link
                  to="/settings"
                  className="w-10 h-10 flex items-center justify-center bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg transition-all cursor-pointer"
                >
                  <i className="ri-user-line text-xl"></i>
                </Link>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
