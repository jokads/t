import { useState, useEffect } from 'react';
import SystemStatus from './components/SystemStatus';
import ProcessManager from './components/ProcessManager';
import HealthMonitor from './components/HealthMonitor';
import SystemLogs from './components/SystemLogs';
import { apiGet, getAuthToken } from '../../utils/api';

interface EnvironmentStatus {
  frontend: boolean;
  backend: boolean;
  pythonCore: boolean;
  mt5Socket: boolean;
  basePath: string;
  modelsPath: string;
  availableModels: number;
}

interface ProjectInfo {
  base_path: string;
  frontend_active: boolean;
  backend_active: boolean;
  bot_connected: boolean;
  mt5_socket?: {
    connected: boolean;
    host: string;
    port: number;
  };
  ai_models?: any[];
  ai_models_count?: number;
  models_path?: string;
  error?: string;
  status?: number;
}

export default function SystemControl() {
  // Environment Detection
  const [environment, setEnvironment] = useState<EnvironmentStatus>({
    frontend: true,
    backend: false,
    pythonCore: false,
    mt5Socket: false,
    basePath: 'C:/bot-mt5',
    modelsPath: 'C:/bot-mt5/models/gpt4all',
    availableModels: 0
  });

  const [activeTab, setActiveTab] = useState<'overview' | 'processes' | 'resources' | 'logs' | 'apis'>('overview');
  const [selectedProcesses, setSelectedProcesses] = useState<number[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [backendOfflineMode, setBackendOfflineMode] = useState(false);

  // 🔥 DETECÇÃO REAL DE AMBIENTE (100% CORRIGIDA - ENDPOINT CORRETO!)
  useEffect(() => {
    // ✅ Verificar autenticação ANTES de fazer requests
    const token = getAuthToken();
    if (!token) {
      console.log('⚠️ Usuário não autenticado, redirecionando...');
      window.location.href = '/login';
      return;
    }

    detectEnvironment();
    const interval = autoRefresh ? setInterval(detectEnvironment, 10000) : null;
    return () => { if (interval) clearInterval(interval); };
  }, [autoRefresh]);

  const detectEnvironment = async () => {
    try {
      // ✅ USAR O ENDPOINT CORRETO DO BACKEND!
      const projectData = await apiGet<ProjectInfo>('/api/diagnostics/project_info');
      
      // ✅ Verificar se retornou dados válidos
      if (projectData && !projectData.error) {
        // Backend ONLINE e dados recebidos
        setBackendOfflineMode(false);
        
        setEnvironment({
          frontend: true, // Se a página carregou, frontend está ativo
          backend: true,
          pythonCore: projectData.bot_connected || false,
          mt5Socket: projectData.mt5_socket?.connected || false,
          basePath: projectData.base_path || 'C:/bot-mt5',
          modelsPath: projectData.models_path || 'C:/bot-mt5/models/gpt4all',
          availableModels: projectData.ai_models_count || 0
        });
      } else {
        // Backend retornou erro (ex: 401, 403, 500)
        throw new Error(projectData?.error || 'Backend retornou erro');
      }
    } catch (error: any) {
      // ✅ MODO FALLBACK SILENCIOSO - Backend offline OU erro de autenticação
      
      // Se erro de autenticação, redirecionar
      if (error?.message?.includes('401') || error?.message?.includes('Token') || error?.message?.includes('inválido')) {
        console.log('⚠️ Token inválido/expirado, redirecionando para login...');
        window.location.href = '/login';
        return;
      }
      
      // Backend offline - modo fallback
      setBackendOfflineMode(true);
      setEnvironment(prev => ({
        ...prev,
        frontend: true,
        backend: false,
        pythonCore: false,
        mt5Socket: false,
        availableModels: 0
      }));
    }
  };

  const handleSelectAll = () => {
    // Implementar seleção de todos os processos visíveis
    alert('💡 Funcionalidade de seleção em massa ainda não implementada no backend.');
  };

  const handleStopSelected = () => {
    if (selectedProcesses.length === 0) {
      alert('⚠️ Nenhum processo selecionado!');
      return;
    }
    
    if (!environment.backend) {
      alert('❌ Backend offline! Não é possível parar processos.\n\n💡 Inicie o backend primeiro:\npython -m backend.dashboard_server');
      return;
    }
    
    if (confirm(`Tem certeza que deseja PARAR ${selectedProcesses.length} processo(s)?`)) {
      // TODO: Implementar chamada ao backend
      alert(`🛑 Parando ${selectedProcesses.length} processo(s)...\n\n⚠️ Esta funcionalidade requer integração com o backend.`);
      setSelectedProcesses([]);
    }
  };

  const handleStartSelected = () => {
    if (selectedProcesses.length === 0) {
      alert('⚠️ Nenhum processo selecionado!');
      return;
    }
    
    if (!environment.backend) {
      alert('❌ Backend offline! Não é possível iniciar processos.\n\n💡 Inicie o backend primeiro:\npython -m backend.dashboard_server');
      return;
    }
    
    // TODO: Implementar chamada ao backend
    alert(`▶️ Iniciando ${selectedProcesses.length} processo(s)...\n\n⚠️ Esta funcionalidade requer integração com o backend.`);
    setSelectedProcesses([]);
  };

  const handleRestartSelected = () => {
    if (selectedProcesses.length === 0) {
      alert('⚠️ Nenhum processo selecionado!');
      return;
    }
    
    if (!environment.backend) {
      alert('❌ Backend offline! Não é possível reiniciar processos.\n\n💡 Inicie o backend primeiro:\npython -m backend.dashboard_server');
      return;
    }
    
    if (confirm(`Tem certeza que deseja REINICIAR ${selectedProcesses.length} processo(s)?`)) {
      // TODO: Implementar chamada ao backend
      alert(`🔄 Reiniciando ${selectedProcesses.length} processo(s)...\n\n⚠️ Esta funcionalidade requer integração com o backend.`);
      setSelectedProcesses([]);
    }
  };

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Controlo do Sistema</h1>
          <p className="text-sm text-purple-300 mt-1">Gestão completa ultra-hardcore com monitoramento em tempo real</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap cursor-pointer ${
              autoRefresh 
                ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white' 
                : 'bg-purple-800/50 hover:bg-purple-700/50 text-purple-200'
            }`}
          >
            <i className={`${autoRefresh ? 'ri-refresh-line animate-spin' : 'ri-refresh-line'} text-base w-5 h-5 flex items-center justify-center`}></i>
            <span>{autoRefresh ? 'Auto-Refresh ON' : 'Auto-Refresh OFF'}</span>
          </button>
          
          {backendOfflineMode && (
            <button
              onClick={detectEnvironment}
              className="px-4 py-2 bg-orange-500/20 hover:bg-orange-500/30 border border-orange-500/50 text-orange-300 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap cursor-pointer"
            >
              <i className="ri-refresh-line text-base w-5 h-5 flex items-center justify-center"></i>
              <span>Verificar Novamente</span>
            </button>
          )}
        </div>
      </div>

      {/* 🔥 AVISO BACKEND OFFLINE */}
      {backendOfflineMode && (
        <div className="bg-gradient-to-br from-orange-900/40 to-red-900/40 border-2 border-orange-500/50 rounded-2xl p-6 shadow-2xl">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 flex items-center justify-center bg-orange-500/20 rounded-xl flex-shrink-0">
              <i className="ri-alert-line text-2xl text-orange-400"></i>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-orange-300 mb-2">⚠️ Modo Fallback Ativo - Backend Offline</h3>
              <p className="text-orange-200/80 text-sm mb-4">
                O backend não está disponível. Sistema funcionando em modo limitado com dados simulados.
              </p>
              
              <div className="bg-black/30 border border-orange-500/20 rounded-lg p-4 mb-4">
                <p className="text-orange-300 font-semibold mb-3 text-sm">📍 Para ativar controlo completo:</p>
                
                <div className="space-y-3">
                  <div>
                    <p className="text-orange-200 text-xs font-semibold mb-1">1️⃣ Iniciar Backend (Dashboard):</p>
                    <div className="bg-black/40 border border-orange-500/20 rounded px-3 py-2">
                      <code className="text-orange-300 text-xs font-mono">
                        cd C:/bot-mt5<br/>
                        python -m backend.dashboard_server
                      </code>
                    </div>
                  </div>
                  
                  <div>
                    <p className="text-orange-200 text-xs font-semibold mb-1">2️⃣ Iniciar Python Core (Trading Bot):</p>
                    <div className="bg-black/40 border border-orange-500/20 rounded px-3 py-2">
                      <code className="text-orange-300 text-xs font-mono">
                        cd C:/bot-mt5<br/>
                        python trading_bot_core.py
                      </code>
                    </div>
                  </div>
                  
                  <div>
                    <p className="text-orange-200 text-xs font-semibold mb-1">💡 Ou use o script automático:</p>
                    <div className="bg-black/40 border border-orange-500/20 rounded px-3 py-2">
                      <code className="text-orange-300 text-xs font-mono">
                        .\backend\run_all.ps1  # Windows<br/>
                        ./backend/run_all.sh   # Linux/Mac
                      </code>
                    </div>
                  </div>
                </div>
              </div>

              <button
                onClick={detectEnvironment}
                className="px-6 py-2 bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white font-semibold rounded-lg transition-all shadow-lg hover:shadow-orange-500/50 flex items-center gap-2 whitespace-nowrap cursor-pointer"
              >
                <i className="ri-refresh-line text-base w-5 h-5 flex items-center justify-center"></i>
                <span>Verificar Novamente</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Environment Status Panel */}
      <div className="card p-6 bg-gradient-to-br from-purple-900/40 to-pink-900/40 border-purple-500/30">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold gradient-text flex items-center gap-2">
            <i className="ri-server-line text-xl w-6 h-6 flex items-center justify-center"></i>
            Estado do Ambiente em Tempo Real
          </h3>
          <span className="text-xs text-purple-300">Atualiza a cada 10s</span>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Frontend */}
          <div className={`p-4 rounded-lg border-2 transition-all ${
            environment.frontend 
              ? 'bg-green-500/10 border-green-500/50' 
              : 'bg-red-500/10 border-red-500/50'
          }`}>
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${environment.frontend ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
              <div>
                <p className="text-xs text-purple-300">Frontend</p>
                <p className={`text-sm font-bold ${environment.frontend ? 'text-green-400' : 'text-red-400'}`}>
                  {environment.frontend ? '🟢 React Dashboard' : '🔴 Offline'}
                </p>
              </div>
            </div>
          </div>

          {/* Backend */}
          <div className={`p-4 rounded-lg border-2 transition-all ${
            environment.backend 
              ? 'bg-green-500/10 border-green-500/50' 
              : 'bg-red-500/10 border-red-500/50'
          }`}>
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${environment.backend ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
              <div>
                <p className="text-xs text-purple-300">Backend API</p>
                <p className={`text-sm font-bold ${environment.backend ? 'text-green-400' : 'text-red-400'}`}>
                  {environment.backend ? '🟢 dashboard_server.py' : '🔴 Offline'}
                </p>
              </div>
            </div>
          </div>

          {/* Python Core */}
          <div className={`p-4 rounded-lg border-2 transition-all ${
            environment.pythonCore 
              ? 'bg-green-500/10 border-green-500/50' 
              : 'bg-orange-500/10 border-orange-500/50'
          }`}>
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${environment.pythonCore ? 'bg-green-400 animate-pulse' : 'bg-orange-400'}`}></div>
              <div>
                <p className="text-xs text-purple-300">Python Core</p>
                <p className={`text-sm font-bold ${environment.pythonCore ? 'text-green-400' : 'text-orange-400'}`}>
                  {environment.pythonCore ? '🟢 trading_bot_core.py' : '🟠 Offline'}
                </p>
              </div>
            </div>
          </div>

          {/* MT5 Socket */}
          <div className={`p-4 rounded-lg border-2 transition-all ${
            environment.mt5Socket 
              ? 'bg-green-500/10 border-green-500/50' 
              : 'bg-orange-500/10 border-orange-500/50'
          }`}>
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${environment.mt5Socket ? 'bg-green-400 animate-pulse' : 'bg-orange-400'}`}></div>
              <div>
                <p className="text-xs text-purple-300">MT5 Socket</p>
                <p className={`text-sm font-bold ${environment.mt5Socket ? 'text-green-400' : 'text-orange-400'}`}>
                  {environment.mt5Socket ? '🟢 Conectado' : '🟠 Offline'}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-purple-500/20 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="flex items-center gap-2 text-sm">
            <i className="ri-folder-line text-cyan-400 w-5 h-5 flex items-center justify-center"></i>
            <span className="text-purple-300">Base Path:</span>
            <span className="text-white font-mono">{environment.basePath}</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <i className="ri-brain-line text-purple-400 w-5 h-5 flex items-center justify-center"></i>
            <span className="text-purple-300">Models Path:</span>
            <span className="text-white font-mono">{environment.modelsPath}</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <i className="ri-robot-line text-orange-400 w-5 h-5 flex items-center justify-center"></i>
            <span className="text-purple-300">Modelos IA:</span>
            <span className={`font-semibold ${environment.availableModels > 0 ? 'text-green-400' : 'text-orange-400'}`}>
              {environment.availableModels > 0 ? `🤖 ${environment.availableModels} disponíveis` : '⚠️ 0 disponíveis'}
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-purple-500/20 overflow-x-auto pb-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'overview'
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
              : 'text-purple-300 hover:text-white hover:bg-purple-800/50'
          }`}
        >
          <i className="ri-dashboard-line mr-2 w-5 h-5 inline-flex items-center justify-center"></i>
          Visão Geral
        </button>
        <button
          onClick={() => setActiveTab('processes')}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'processes'
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
              : 'text-purple-300 hover:text-white hover:bg-purple-800/50'
          }`}
        >
          <i className="ri-list-check mr-2 w-5 h-5 inline-flex items-center justify-center"></i>
          Gestor de Processos
        </button>
        <button
          onClick={() => setActiveTab('resources')}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'resources'
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
              : 'text-purple-300 hover:text-white hover:bg-purple-800/50'
          }`}
        >
          <i className="ri-cpu-line mr-2 w-5 h-5 inline-flex items-center justify-center"></i>
          Recursos do Sistema
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'logs'
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
              : 'text-purple-300 hover:text-white hover:bg-purple-800/50'
          }`}
        >
          <i className="ri-file-list-line mr-2 w-5 h-5 inline-flex items-center justify-center"></i>
          Logs do Sistema
        </button>
        <button
          onClick={() => setActiveTab('apis')}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'apis'
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
              : 'text-purple-300 hover:text-white hover:bg-purple-800/50'
          }`}
        >
          <i className="ri-plug-line mr-2 w-5 h-5 inline-flex items-center justify-center"></i>
          APIs & Conexões
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2">
            <SystemStatus environment={environment} />
          </div>
          <div>
            <HealthMonitor environment={environment} />
          </div>
        </div>
      )}

      {activeTab === 'processes' && (
        <div>
          <ProcessManager 
            environment={environment}
            selectedProcesses={selectedProcesses}
            setSelectedProcesses={setSelectedProcesses}
            onSelectAll={handleSelectAll}
            onStopSelected={handleStopSelected}
            onStartSelected={handleStartSelected}
            onRestartSelected={handleRestartSelected}
          />
        </div>
      )}

      {activeTab === 'resources' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <SystemStatus environment={environment} showDetailedResources />
        </div>
      )}

      {activeTab === 'logs' && (
        <div>
          <SystemLogs environment={environment} />
        </div>
      )}

      {activeTab === 'apis' && (
        <div>
          <HealthMonitor environment={environment} showAPIsOnly />
        </div>
      )}
    </div>
  );
}
