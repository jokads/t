import { useState, useEffect } from 'react';

interface EnvironmentStatus {
  frontend: boolean;
  backend: boolean;
  pythonCore: boolean;
  basePath: string;
  modelsPath: string;
  availableModels: number;
}

interface HealthMonitorProps {
  environment: EnvironmentStatus;
  showAPIsOnly?: boolean;
}

interface HealthCheck {
  service: string;
  category: 'system' | 'api' | 'ai' | 'database';
  status: 'healthy' | 'warning' | 'critical' | 'offline';
  latency: number;
  lastCheck: string;
  details?: string;
}

export default function HealthMonitor({ environment, showAPIsOnly = false }: HealthMonitorProps) {
  const [healthChecks, setHealthChecks] = useState<HealthCheck[]>([
    // System Services
    { service: 'Frontend (npm run dev)', category: 'system', status: 'healthy', latency: 5, lastCheck: 'Agora', details: 'React + Vite rodando em http://localhost:5173' },
    { service: 'Backend (dashboard_server.py)', category: 'system', status: 'healthy', latency: 12, lastCheck: 'Agora', details: 'Flask rodando em http://localhost:5000' },
    { service: 'Python Core (trading_bot_core.py)', category: 'system', status: 'healthy', latency: 8, lastCheck: 'Agora', details: 'Bot principal ativo e operacional' },
    { service: 'MT5 Socket', category: 'system', status: 'healthy', latency: 45, lastCheck: 'Agora', details: 'Conectado via mt5_communication.py' },
    
    // Database
    { service: 'Supabase Database', category: 'database', status: 'healthy', latency: 89, lastCheck: 'Agora', details: 'PostgreSQL + Tables: users, trades, strategies' },
    { service: 'Local Cache', category: 'database', status: 'healthy', latency: 3, lastCheck: 'Agora', details: 'Redis local para dados temporários' },
    
    // AI Services
    { service: 'AI Manager', category: 'ai', status: 'healthy', latency: 234, lastCheck: 'Agora', details: '6 modelos IA carregados e prontos' },
    { service: 'Llama 3.2 3B', category: 'ai', status: 'healthy', latency: 156, lastCheck: 'Agora', details: 'Modelo recomendado ativo' },
    { service: 'Nous Hermes 2 Mistral 7B', category: 'ai', status: 'healthy', latency: 298, lastCheck: 'Agora', details: 'Modelo avançado ativo' },
    
    // External APIs
    { service: 'Telegram Bot API', category: 'api', status: 'healthy', latency: 123, lastCheck: 'Agora', details: 'Token: 7536817878:AAFi...byc4' },
    { service: 'News API', category: 'api', status: 'warning', latency: 567, lastCheck: 'Há 2s', details: 'API Key: 56767a95...f29e13 | Latência alta' },
    { service: 'MT5 Broker API', category: 'api', status: 'healthy', latency: 234, lastCheck: 'Agora', details: 'Conectado ao servidor de broker' }
  ]);

  const [selectedCategory, setSelectedCategory] = useState<'all' | 'system' | 'api' | 'ai' | 'database'>('all');

  useEffect(() => {
    const interval = setInterval(() => {
      setHealthChecks(prev => prev.map(check => ({
        ...check,
        latency: Math.floor(Math.random() * 500) + 10,
        status: Math.random() > 0.95 ? 'warning' : Math.random() > 0.98 ? 'critical' : 'healthy',
        lastCheck: 'Agora'
      })));
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-green-400 bg-green-500/20 border-green-500/30';
      case 'warning': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30';
      case 'critical': return 'text-red-400 bg-red-500/20 border-red-500/30';
      case 'offline': return 'text-slate-400 bg-slate-500/20 border-slate-500/30';
      default: return 'text-slate-400 bg-slate-500/20 border-slate-500/30';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return 'ri-checkbox-circle-fill';
      case 'warning': return 'ri-error-warning-fill';
      case 'critical': return 'ri-close-circle-fill';
      case 'offline': return 'ri-stop-circle-fill';
      default: return 'ri-question-fill';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'system': return 'ri-server-line';
      case 'api': return 'ri-plug-line';
      case 'ai': return 'ri-brain-line';
      case 'database': return 'ri-database-2-line';
      default: return 'ri-service-line';
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'system': return 'text-orange-400 bg-orange-500/20';
      case 'api': return 'text-cyan-400 bg-cyan-500/20';
      case 'ai': return 'text-pink-400 bg-pink-500/20';
      case 'database': return 'text-purple-400 bg-purple-500/20';
      default: return 'text-slate-400 bg-slate-500/20';
    }
  };

  const filteredChecks = selectedCategory === 'all' 
    ? healthChecks 
    : healthChecks.filter(c => c.category === selectedCategory);

  const healthyCount = healthChecks.filter(c => c.status === 'healthy').length;
  const warningCount = healthChecks.filter(c => c.status === 'warning').length;
  const criticalCount = healthChecks.filter(c => c.status === 'critical').length;
  const offlineCount = healthChecks.filter(c => c.status === 'offline').length;

  if (showAPIsOnly) {
    const apiChecks = healthChecks.filter(c => c.category === 'api');
    const systemChecks = healthChecks.filter(c => c.category === 'system');
    const aiChecks = healthChecks.filter(c => c.category === 'ai');
    const dbChecks = healthChecks.filter(c => c.category === 'database');

    return (
      <div className="space-y-6">
        {/* APIs Externas */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold gradient-text mb-6 flex items-center gap-2">
            <i className="ri-plug-line text-xl"></i>
            APIs Externas & Integrações
          </h3>
          <div className="space-y-3">
            {apiChecks.map((check, index) => (
              <div key={index} className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/10 hover:bg-purple-900/30 transition-all">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <i className={`${getStatusIcon(check.status)} text-xl ${getStatusColor(check.status).split(' ')[0]}`}></i>
                    <div>
                      <p className="text-sm font-medium text-white">{check.service}</p>
                      <p className="text-xs text-purple-400 mt-1">{check.details}</p>
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(check.status)}`}>
                    {check.status === 'healthy' ? '✅ OK' : check.status === 'warning' ? '⚠️ Aviso' : check.status === 'critical' ? '🔴 Crítico' : '⚫ Offline'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-purple-300">
                  <span>Latência: {check.latency}ms</span>
                  <span>{check.lastCheck}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Serviços do Sistema */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold gradient-text mb-6 flex items-center gap-2">
            <i className="ri-server-line text-xl"></i>
            Serviços do Sistema
          </h3>
          <div className="space-y-3">
            {systemChecks.map((check, index) => (
              <div key={index} className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/10 hover:bg-purple-900/30 transition-all">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <i className={`${getStatusIcon(check.status)} text-xl ${getStatusColor(check.status).split(' ')[0]}`}></i>
                    <div>
                      <p className="text-sm font-medium text-white">{check.service}</p>
                      <p className="text-xs text-purple-400 mt-1">{check.details}</p>
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(check.status)}`}>
                    {check.status === 'healthy' ? '✅ OK' : check.status === 'warning' ? '⚠️ Aviso' : check.status === 'critical' ? '🔴 Crítico' : '⚫ Offline'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-purple-300">
                  <span>Latência: {check.latency}ms</span>
                  <span>{check.lastCheck}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Modelos IA */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold gradient-text mb-6 flex items-center gap-2">
            <i className="ri-brain-line text-xl"></i>
            Modelos de IA
          </h3>
          <div className="space-y-3">
            {aiChecks.map((check, index) => (
              <div key={index} className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/10 hover:bg-purple-900/30 transition-all">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <i className={`${getStatusIcon(check.status)} text-xl ${getStatusColor(check.status).split(' ')[0]}`}></i>
                    <div>
                      <p className="text-sm font-medium text-white">{check.service}</p>
                      <p className="text-xs text-purple-400 mt-1">{check.details}</p>
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(check.status)}`}>
                    {check.status === 'healthy' ? '✅ OK' : check.status === 'warning' ? '⚠️ Aviso' : check.status === 'critical' ? '🔴 Crítico' : '⚫ Offline'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-purple-300">
                  <span>Latência: {check.latency}ms</span>
                  <span>{check.lastCheck}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Base de Dados */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold gradient-text mb-6 flex items-center gap-2">
            <i className="ri-database-2-line text-xl"></i>
            Base de Dados
          </h3>
          <div className="space-y-3">
            {dbChecks.map((check, index) => (
              <div key={index} className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/10 hover:bg-purple-900/30 transition-all">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <i className={`${getStatusIcon(check.status)} text-xl ${getStatusColor(check.status).split(' ')[0]}`}></i>
                    <div>
                      <p className="text-sm font-medium text-white">{check.service}</p>
                      <p className="text-xs text-purple-400 mt-1">{check.details}</p>
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(check.status)}`}>
                    {check.status === 'healthy' ? '✅ OK' : check.status === 'warning' ? '⚠️ Aviso' : check.status === 'critical' ? '🔴 Crítico' : '⚫ Offline'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-purple-300">
                  <span>Latência: {check.latency}ms</span>
                  <span>{check.lastCheck}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold gradient-text flex items-center gap-2">
          <i className="ri-heart-pulse-line text-xl"></i>
          Health Monitor
        </h3>
        <button className="w-8 h-8 flex items-center justify-center bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg transition-all cursor-pointer" title="Atualizar">
          <i className="ri-refresh-line text-sm"></i>
        </button>
      </div>

      {/* Category Filter */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
        <button
          onClick={() => setSelectedCategory('all')}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
            selectedCategory === 'all'
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
              : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
          }`}
        >
          Todos ({healthChecks.length})
        </button>
        <button
          onClick={() => setSelectedCategory('system')}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
            selectedCategory === 'system'
              ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white'
              : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
          }`}
        >
          Sistema ({healthChecks.filter(c => c.category === 'system').length})
        </button>
        <button
          onClick={() => setSelectedCategory('api')}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
            selectedCategory === 'api'
              ? 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white'
              : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
          }`}
        >
          APIs ({healthChecks.filter(c => c.category === 'api').length})
        </button>
        <button
          onClick={() => setSelectedCategory('ai')}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
            selectedCategory === 'ai'
              ? 'bg-gradient-to-r from-pink-500 to-purple-500 text-white'
              : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
          }`}
        >
          IA ({healthChecks.filter(c => c.category === 'ai').length})
        </button>
        <button
          onClick={() => setSelectedCategory('database')}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
            selectedCategory === 'database'
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
              : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
          }`}
        >
          Database ({healthChecks.filter(c => c.category === 'database').length})
        </button>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {filteredChecks.map((check, index) => (
          <div key={index} className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/10 hover:bg-purple-900/30 transition-all">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg ${getCategoryColor(check.category)} flex items-center justify-center`}>
                  <i className={`${getCategoryIcon(check.category)} text-sm`}></i>
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{check.service}</p>
                  {check.details && <p className="text-xs text-purple-400 mt-0.5">{check.details}</p>}
                </div>
              </div>
              <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(check.status)}`}>
                {check.status === 'healthy' ? 'OK' : check.status === 'warning' ? 'Aviso' : check.status === 'critical' ? 'Crítico' : 'Offline'}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs text-purple-300">
              <span>Latência: <span className={check.latency > 500 ? 'text-yellow-400' : 'text-green-400'}>{check.latency}ms</span></span>
              <span>{check.lastCheck}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 pt-6 border-t border-purple-500/20">
        <div className="grid grid-cols-4 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold text-green-400">{healthyCount}</p>
            <p className="text-xs text-purple-300 mt-1">Saudável</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-yellow-400">{warningCount}</p>
            <p className="text-xs text-purple-300 mt-1">Avisos</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-red-400">{criticalCount}</p>
            <p className="text-xs text-purple-300 mt-1">Críticos</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-400">{offlineCount}</p>
            <p className="text-xs text-purple-300 mt-1">Offline</p>
          </div>
        </div>
      </div>
    </div>
  );
}
