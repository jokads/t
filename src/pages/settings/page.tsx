import { useState, useEffect } from 'react';
import GeneralSettings from './components/GeneralSettings';
import SecuritySettings from './components/SecuritySettings';
import NotificationSettings from './components/NotificationSettings';
import APISettings from './components/APISettings';
import AuditLogs from './components/AuditLogs';
import { apiGet } from '../../utils/api';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('general');
  const [environment, setEnvironment] = useState({
    frontend: true,
    backend: false,
    pythonCore: false,
    basePath: 'C:/bot-mt5',
    modelsPath: 'C:/bot-mt5/models/gpt4all'
  });
  const [aiModels, setAiModels] = useState<any[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // ✅ Detecção automática do ambiente a cada 10s
  useEffect(() => {
    const detectEnvironment = async () => {
      try {
        // ✅ Usar endpoint CORRETO que existe no backend
        const response = await apiGet<any>('/api/diagnostics/project_info');
        
        if (response && !response.error) {
          console.log('🔍 Ambiente detectado:', response);
          
          // ✅ Atualizar estado do ambiente
          setEnvironment({
            frontend: true,
            backend: response.dashboard_api?.active || false,
            pythonCore: response.bot_connected || false,
            basePath: response.base_path || 'C:/bot-mt5',
            modelsPath: response.models_path || 'C:/bot-mt5/models/gpt4all'
          });
          
          // ✅ Carregar modelos IA REAIS
          if (response.ai_models && response.ai_models.length > 0) {
            setAiModels(response.ai_models);
            
            // ✅ Auto-selecionar 2 primeiros modelos se nenhum selecionado
            if (selectedModels.length === 0) {
              const firstTwo = response.ai_models.slice(0, 2).map((m: any) => m.name || m.id);
              setSelectedModels(firstTwo);
            }
          }
        }
      } catch (error) {
        console.log('⚠️ Backend offline, usando modo fallback');
        // ✅ Modo fallback: Frontend sempre ativo
        setEnvironment({
          frontend: true,
          backend: false,
          pythonCore: false,
          basePath: 'C:/bot-mt5',
          modelsPath: 'C:/bot-mt5/models/gpt4all'
        });
      }
    };

    detectEnvironment();
    
    // ✅ Auto-refresh apenas se ativado
    if (autoRefresh) {
      const interval = setInterval(detectEnvironment, 10000);
      return () => clearInterval(interval);
    }
  }, [selectedModels.length, autoRefresh]);

  const tabs = [
    { id: 'general', label: 'Geral', icon: 'ri-settings-3-line' },
    { id: 'security', label: 'Segurança', icon: 'ri-shield-check-line' },
    { id: 'notifications', label: 'Notificações', icon: 'ri-notification-3-line' },
    { id: 'api', label: 'API & Integração', icon: 'ri-code-s-slash-line' },
    { id: 'audit', label: 'Logs de Auditoria', icon: 'ri-file-list-3-line' }
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'general':
        return <GeneralSettings environment={environment} aiModels={aiModels} />;
      case 'security':
        return (
          <SecuritySettings
            environment={environment}
            aiModels={aiModels}
            selectedModels={selectedModels}
            setSelectedModels={setSelectedModels}
          />
        );
      case 'notifications':
        return <NotificationSettings environment={environment} />;
      case 'api':
        return <APISettings environment={environment} aiModels={aiModels} />;
      case 'audit':
        return (
          <AuditLogs
            environment={environment}
            aiModels={aiModels}
            selectedModels={selectedModels}
            setSelectedModels={setSelectedModels}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Configurações</h1>
          <p className="text-sm text-purple-300 mt-1">Gerir preferências e configurações do sistema</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 px-3 py-2 glass-effect rounded-lg border border-purple-500/30 cursor-pointer hover:bg-purple-500/10 transition-all">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-purple-500 focus:ring-2 focus:ring-purple-500 cursor-pointer"
            />
            <i className="ri-refresh-line text-purple-400"></i>
            <span className="text-xs text-purple-300 whitespace-nowrap">Auto-refresh (10s)</span>
          </label>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg text-sm font-medium transition-all border border-purple-500/30 whitespace-nowrap cursor-pointer flex items-center gap-2"
          >
            <i className="ri-refresh-line"></i>
            Atualizar
          </button>
        </div>
      </div>

      {/* Estado do Ambiente */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-purple-300">📊 Estado do Ambiente</h3>
          <div className="text-xs text-purple-400">{autoRefresh ? 'Atualiza a cada 10s' : 'Auto-refresh desativado'}</div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {/* Frontend */}
          <div className="glass-effect p-4 rounded-lg text-center border border-purple-500/30 hover:border-purple-500/50 transition-all">
            <div className="text-3xl mb-2">
              {environment.frontend ? (
                <div className="relative inline-block">
                  <span className="text-green-400">🟢</span>
                  <span className="absolute inset-0 animate-ping text-green-400 opacity-50">🟢</span>
                </div>
              ) : (
                <span className="text-red-400">🔴</span>
              )}
            </div>
            <div className="text-sm font-medium text-white">Frontend React</div>
            <div className="text-xs text-purple-300 mt-1">
              {environment.frontend ? 'Online' : 'Offline'}
            </div>
          </div>

          {/* Backend */}
          <div className="glass-effect p-4 rounded-lg text-center border border-purple-500/30 hover:border-purple-500/50 transition-all">
            <div className="text-3xl mb-2">
              {environment.backend ? (
                <div className="relative inline-block">
                  <span className="text-cyan-400">🟢</span>
                  <span className="absolute inset-0 animate-ping text-cyan-400 opacity-50">🟢</span>
                </div>
              ) : (
                <span className="text-red-400">🔴</span>
              )}
            </div>
            <div className="text-sm font-medium text-white">Backend API</div>
            <div className="text-xs text-purple-300 mt-1">
              {environment.backend ? 'dashboard_server.py' : 'Offline'}
            </div>
          </div>

          {/* Python Core */}
          <div className="glass-effect p-4 rounded-lg text-center border border-purple-500/30 hover:border-purple-500/50 transition-all">
            <div className="text-3xl mb-2">
              {environment.pythonCore ? (
                <div className="relative inline-block">
                  <span className="text-orange-400">🟢</span>
                  <span className="absolute inset-0 animate-ping text-orange-400 opacity-50">🟢</span>
                </div>
              ) : (
                <span className="text-gray-400">⚪</span>
              )}
            </div>
            <div className="text-sm font-medium text-white">Python Core</div>
            <div className="text-xs text-purple-300 mt-1">
              {environment.pythonCore ? 'trading_bot_core.py' : 'Offline'}
            </div>
          </div>

          {/* Modelos IA */}
          <div className="glass-effect p-4 rounded-lg text-center border border-purple-500/30 hover:border-purple-500/50 transition-all">
            <div className="text-3xl mb-2 text-cyan-400">🤖</div>
            <div className="text-sm font-medium text-white">Modelos IA</div>
            <div className="text-xs text-purple-300 mt-1">
              {aiModels.length} disponíveis
            </div>
          </div>
        </div>

        {/* Info de Caminhos */}
        {environment.basePath && (
          <div className="mt-4 space-y-2 text-xs">
            <div className="flex items-center gap-2 text-purple-300">
              <i className="ri-folder-line"></i>
              <span className="font-mono">Base: {environment.basePath}</span>
            </div>
            {environment.modelsPath && (
              <div className="flex items-center gap-2 text-purple-300">
                <i className="ri-robot-line"></i>
                <span className="font-mono">Models: {environment.modelsPath}</span>
              </div>
            )}
          </div>
        )}

        {/* Banner de Backend Offline */}
        {!environment.backend && (
          <div className="mt-4 bg-orange-500/10 border border-orange-500/30 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <i className="ri-alert-line text-orange-400 text-xl"></i>
              <div className="flex-1">
                <div className="text-sm font-medium text-orange-300 mb-1">Backend Offline</div>
                <div className="text-xs text-orange-200/70 mb-2">
                  Algumas funcionalidades estão limitadas. Inicie o backend para acesso completo.
                </div>
                <div className="text-xs text-orange-200/50 space-y-1 font-mono">
                  <div>Terminal 1: cd C:\bot-mt5\backend && python dashboard_server.py</div>
                  <div>Terminal 2: cd C:\bot-mt5 && npm run dev</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="card p-2">
        <div className="flex gap-2 overflow-x-auto custom-scrollbar">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg whitespace-nowrap transition-all cursor-pointer ${
                activeTab === tab.id
                  ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg shadow-purple-500/30'
                  : 'text-purple-300 hover:bg-purple-500/10'
              }`}
            >
              <i className={tab.icon}></i>
              <span className="text-sm font-medium">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      {renderTabContent()}
    </div>
  );
}
