import React, { useState, useEffect } from 'react';
import { apiGet, apiPost } from '../../utils/api';
import TelegramConfig from './components/TelegramConfig';
import NewsAPIConfig from './components/NewsAPIConfig';

interface EnvironmentStatus {
  frontend: { status: string };
  backend: { status: string; port?: number };
  pythonCore: { status: string; pid?: number };
  mt5Socket: { status: string; host?: string; port?: number };
  basePath: string;
  modelsPath: string;
  aiModelsCount: number;
}

interface IntegrationConfig {
  telegram: {
    enabled: boolean;
    botToken: string;
    chatIds: string[];
    notifications: {
      trades: boolean;
      dailyReport: boolean;
      losses: boolean;
      gains: boolean;
    };
  };
  newsApi: {
    enabled: boolean;
    apiKey: string;
    sources: string[];
    updateInterval: number;
  };
}

const IntegrationsPage: React.FC = () => {
  const [envStatus, setEnvStatus] = useState<EnvironmentStatus | null>(null);
  const [config, setConfig] = useState<IntegrationConfig>({
    telegram: {
      enabled: false,
      botToken: '',
      chatIds: [],
      notifications: {
        trades: true,
        dailyReport: true,
        losses: true,
        gains: true,
      },
    },
    newsApi: {
      enabled: false,
      apiKey: '',
      sources: ['bloomberg', 'reuters', 'forexlive'],
      updateInterval: 300,
    },
  });
  const [loading, setLoading] = useState(true);

  // Carregar estado do ambiente
  const loadEnvironmentStatus = async () => {
    try {
      const response = await apiGet<any>('/api/environment/status');
      if (response && !response.error) {
        setEnvStatus(response);
      }
    } catch (error) {
      console.error('❌ Erro ao carregar status do ambiente:', error);
    }
  };

  // Carregar configurações das integrações
  const loadIntegrationConfig = async () => {
    try {
      const response = await apiGet<IntegrationConfig>('/api/integrations/config');
      if (response && !response.error) {
        setConfig(response);
      }
    } catch (error) {
      console.error('❌ Erro ao carregar configurações:', error);
    } finally {
      setLoading(false);
    }
  };

  // Salvar configurações
  const saveConfig = async (updatedConfig: IntegrationConfig) => {
    try {
      const response = await apiPost<any>('/api/integrations/config', updatedConfig);
      if (response && !response.error) {
        setConfig(updatedConfig);
        alert('✅ Configurações guardadas com sucesso!');
      } else {
        alert('❌ Erro ao guardar configurações: ' + (response?.error || 'Erro desconhecido'));
      }
    } catch (error) {
      console.error('❌ Erro ao guardar configurações:', error);
      alert('❌ Erro ao guardar configurações. Backend pode estar offline.');
    }
  };

  useEffect(() => {
    loadEnvironmentStatus();
    loadIntegrationConfig();

    // Auto-refresh a cada 10s
    const interval = setInterval(() => {
      loadEnvironmentStatus();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  const backendOnline = envStatus?.backend?.status === 'online';

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text flex items-center gap-3">
            <i className="ri-links-line"></i>
            Integrações
          </h1>
          <p className="text-purple-300 mt-2">Configure Telegram, News API e automação inteligente</p>
        </div>
        <button
          onClick={loadIntegrationConfig}
          className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-all flex items-center gap-2 cursor-pointer"
        >
          <i className="ri-refresh-line"></i>
          Atualizar
        </button>
      </div>

      {/* Status do Ambiente */}
      <div className="p-6 bg-black/40 backdrop-blur-sm rounded-xl border border-orange-500/20">
        <h2 className="text-lg font-bold text-orange-400 mb-4 flex items-center gap-2">
          <i className="ri-server-line"></i>
          Estado do Ambiente em Tempo Real
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Frontend */}
          <div className="p-4 bg-gradient-to-br from-green-900/40 to-emerald-900/40 rounded-lg border border-green-500/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-green-300 font-medium">Frontend React</span>
              <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
            </div>
            <p className="text-xs text-green-400 font-bold">ONLINE</p>
            <p className="text-xs text-green-300/70 mt-1">Dashboard Ativo</p>
          </div>

          {/* Backend */}
          <div className={`p-4 rounded-lg border ${
            backendOnline
              ? 'bg-gradient-to-br from-green-900/40 to-emerald-900/40 border-green-500/30'
              : 'bg-gradient-to-br from-red-900/40 to-pink-900/40 border-red-500/30'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-green-300 font-medium">Backend API</span>
              <div className={`w-3 h-3 rounded-full ${backendOnline ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
            </div>
            <p className={`text-xs font-bold ${backendOnline ? 'text-green-400' : 'text-red-400'}`}>
              {backendOnline ? 'ONLINE' : 'OFFLINE'}
            </p>
            <p className="text-xs text-green-300/70 mt-1">
              {backendOnline ? `Porta ${envStatus?.backend?.port || 5000}` : 'Execute o backend'}
            </p>
          </div>

          {/* Python Core */}
          <div className={`p-4 rounded-lg border ${
            envStatus?.pythonCore?.status === 'active'
              ? 'bg-gradient-to-br from-green-900/40 to-emerald-900/40 border-green-500/30'
              : 'bg-gradient-to-br from-gray-900/40 to-slate-900/40 border-gray-500/30'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-green-300 font-medium">Python Core</span>
              <div className={`w-3 h-3 rounded-full ${
                envStatus?.pythonCore?.status === 'active' ? 'bg-green-400 animate-pulse' : 'bg-gray-400'
              }`}></div>
            </div>
            <p className={`text-xs font-bold ${
              envStatus?.pythonCore?.status === 'active' ? 'text-green-400' : 'text-gray-400'
            }`}>
              {envStatus?.pythonCore?.status === 'active' ? 'ATIVO' : 'OFFLINE'}
            </p>
            <p className="text-xs text-green-300/70 mt-1">
              {envStatus?.pythonCore?.pid ? `PID ${envStatus.pythonCore.pid}` : 'trading_bot_core.py'}
            </p>
          </div>

          {/* MT5 Socket */}
          <div className={`p-4 rounded-lg border ${
            envStatus?.mt5Socket?.status === 'connected'
              ? 'bg-gradient-to-br from-green-900/40 to-emerald-900/40 border-green-500/30'
              : 'bg-gradient-to-br from-gray-900/40 to-slate-900/40 border-gray-500/30'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-green-300 font-medium">MT5 Socket</span>
              <div className={`w-3 h-3 rounded-full ${
                envStatus?.mt5Socket?.status === 'connected' ? 'bg-green-400 animate-pulse' : 'bg-gray-400'
              }`}></div>
            </div>
            <p className={`text-xs font-bold ${
              envStatus?.mt5Socket?.status === 'connected' ? 'text-green-400' : 'text-gray-400'
            }`}>
              {envStatus?.mt5Socket?.status === 'connected' ? 'CONECTADO' : 'OFFLINE'}
            </p>
            <p className="text-xs text-green-300/70 mt-1">
              {envStatus?.mt5Socket?.port ? `Porta ${envStatus.mt5Socket.port}` : 'Aguardando'}
            </p>
          </div>
        </div>

        {/* Info Adicional */}
        {envStatus && (
          <div className="mt-4 pt-4 border-t border-orange-500/20">
            <div className="flex flex-wrap items-center gap-4 text-xs text-purple-300">
              <span className="flex items-center gap-1">
                <i className="ri-folder-line text-orange-400"></i>
                Base: {envStatus.basePath}
              </span>
              <span className="flex items-center gap-1">
                <i className="ri-folder-open-line text-orange-400"></i>
                Models: {envStatus.modelsPath}
              </span>
              <span className="flex items-center gap-1">
                <i className="ri-robot-line text-orange-400"></i>
                {envStatus.aiModelsCount} modelos IA
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Banner de Fallback */}
      {!backendOnline && (
        <div className="p-6 bg-gradient-to-r from-orange-900/40 to-red-900/40 rounded-xl border border-orange-500/30">
          <div className="flex items-start gap-4">
            <i className="ri-information-line text-3xl text-orange-400"></i>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-orange-400 mb-2">Modo Fallback Ativo</h3>
              <p className="text-sm text-orange-300 mb-3">
                Backend offline. As configurações podem não ser carregadas ou guardadas corretamente.
              </p>
              <p className="text-xs text-orange-400 mb-2 font-mono">
                Para ativar as integrações localmente, execute:
              </p>
              <div className="space-y-2">
                <p className="text-xs text-orange-300 font-mono bg-black/30 px-3 py-2 rounded">
                  python -m backend.dashboard_server
                </p>
                <p className="text-xs text-orange-300 font-mono bg-black/30 px-3 py-2 rounded">
                  python trading_bot_core.py
                </p>
              </div>
            </div>
            <button
              onClick={loadEnvironmentStatus}
              className="px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-lg transition-all text-sm cursor-pointer whitespace-nowrap"
            >
              Verificar Novamente
            </button>
          </div>
        </div>
      )}

      {/* Componentes de Configuração */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TelegramConfig
          config={config.telegram}
          onSave={(telegramConfig) => saveConfig({ ...config, telegram: telegramConfig })}
          backendOnline={backendOnline}
        />
        <NewsAPIConfig
          config={config.newsApi}
          onSave={(newsApiConfig) => saveConfig({ ...config, newsApi: newsApiConfig })}
          backendOnline={backendOnline}
        />
      </div>
    </div>
  );
};

export default IntegrationsPage;
