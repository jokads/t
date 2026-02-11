import { useState, useEffect } from 'react';
import RiskMetrics from './components/RiskMetrics';
import RiskSettings from './components/RiskSettings';
import AutoStopRules from './components/AutoStopRules';
import RiskAlerts from './components/RiskAlerts';
import { apiGet, apiPost } from '../../utils/api';

export default function RiskManagerPage() {
  const [settings, setSettings] = useState({
    maxRiskPerTrade: 2,
    maxConcurrentTrades: 5,
    maxDailyLoss: 5,
    maxDrawdown: 10,
    autoStopEnabled: true
  });

  const [metrics, setMetrics] = useState({
    currentRisk: 0,
    activeTrades: 0,
    dailyLoss: 0,
    currentDrawdown: 0
  });

  const [loading, setLoading] = useState(true);
  const [backendStatus, setBackendStatus] = useState<'connected' | 'offline' | 'checking'>('checking');
  const [aiAnalysis, setAiAnalysis] = useState<any>(null);

  // ✅ Verificar backend e carregar dados
  useEffect(() => {
    checkBackendAndLoad();
    
    // Atualizar a cada 10 segundos
    const interval = setInterval(() => {
      if (backendStatus === 'connected') {
        loadMetrics();
        loadAiAnalysis();
      }
    }, 10000);
    
    return () => clearInterval(interval);
  }, []);

  const checkBackendAndLoad = async () => {
    try {
      setLoading(true);
      
      // Tentar conectar ao backend
      const healthCheck = await apiGet('/api/health').catch(() => null);
      
      if (healthCheck && healthCheck.status === 'ok') {
        setBackendStatus('connected');
        console.log('✅ Backend conectado - Carregando dados reais');
        await loadRiskData();
      } else {
        setBackendStatus('offline');
        console.log('⚠️ Backend offline - Usando dados padrão');
        // Manter valores padrão
      }
    } catch (error) {
      console.error('Erro ao verificar backend:', error);
      setBackendStatus('offline');
    } finally {
      setLoading(false);
    }
  };

  const loadRiskData = async () => {
    try {
      await Promise.all([
        loadSettings(),
        loadMetrics(),
        loadAiAnalysis()
      ]);
    } catch (error) {
      console.error('Erro ao carregar dados de risco:', error);
    }
  };

  const loadSettings = async () => {
    try {
      const data = await apiGet('/api/risk/settings');
      if (data) {
        setSettings(data);
        console.log('✅ Configurações de risco carregadas:', data);
      }
    } catch (error) {
      console.error('Erro ao carregar configurações:', error);
    }
  };

  const loadMetrics = async () => {
    try {
      const data = await apiGet('/api/risk/metrics');
      if (data) {
        setMetrics(data);
        console.log('✅ Métricas de risco carregadas:', data);
      }
    } catch (error) {
      console.error('Erro ao carregar métricas:', error);
    }
  };

  const loadAiAnalysis = async () => {
    try {
      const data = await apiPost('/api/risk/ai-analysis', {});
      if (data) {
        setAiAnalysis(data);
        console.log('✅ Análise IA carregada:', data);
      }
    } catch (error) {
      console.error('Erro ao carregar análise IA:', error);
    }
  };

  const handleSettingsUpdate = async (newSettings: any) => {
    try {
      const response = await apiPost('/api/risk/settings', newSettings);
      
      if (response && response.success) {
        setSettings(newSettings);
        console.log('✅ Configurações atualizadas com sucesso');
        
        // Recarregar análise IA e métricas
        await Promise.all([loadAiAnalysis(), loadMetrics()]);
        
        alert('✅ Configurações atualizadas com sucesso!');
      } else {
        throw new Error(response?.message || 'Erro ao atualizar');
      }
    } catch (error: any) {
      console.error('Erro ao atualizar configurações:', error);
      alert(`❌ Erro: ${error.message || 'Não foi possível atualizar'}`);
    }
  };

  const handleReset = async () => {
    if (!confirm('Tem certeza que deseja resetar todos os limites para valores padrão?')) {
      return;
    }

    try {
      const response = await apiPost('/api/risk/reset', {});
      
      if (response && response.success) {
        await loadRiskData();
        alert('✅ Limites resetados com sucesso!');
      } else {
        throw new Error(response?.message || 'Erro ao resetar');
      }
    } catch (error: any) {
      console.error('Erro ao resetar limites:', error);
      alert(`❌ Erro: ${error.message || 'Não foi possível resetar'}`);
    }
  };

  // ✅ Status visual do sistema
  const getSystemStatusBanner = () => {
    if (backendStatus === 'checking') {
      return (
        <div className="glass-card p-4 mb-6 border-l-4 border-yellow-500">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 border-4 border-yellow-500 border-t-transparent rounded-full animate-spin"></div>
            <div>
              <h3 className="text-sm font-bold text-white">Verificando Sistema...</h3>
              <p className="text-xs text-gray-400">Conectando ao backend</p>
            </div>
          </div>
        </div>
      );
    }

    if (backendStatus === 'offline') {
      return (
        <div className="glass-card p-4 mb-6 border-l-4 border-cyan-500">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-cyan-500/20 flex items-center justify-center">
              <i className="ri-settings-3-line text-xl text-cyan-400"></i>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-bold text-white">✅ Sistema Preparado para Dados Reais</h3>
              <p className="text-xs text-gray-400 mt-1">
                Execute <code className="px-2 py-0.5 bg-purple-900/50 rounded text-cyan-300">python trading_bot_core.py</code> para conectar dados ao vivo
              </p>
            </div>
            <button
              onClick={checkBackendAndLoad}
              className="px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 rounded-lg text-xs text-cyan-300 transition-colors whitespace-nowrap"
            >
              <i className="ri-refresh-line mr-1"></i>
              Verificar
            </button>
          </div>
          <div className="flex items-center gap-4 mt-3 text-xs text-gray-400">
            <span className="flex items-center gap-1.5">
              <i className="ri-folder-line text-cyan-400"></i>
              C:/bot-mt5/strategies/risk_manager.py
            </span>
            <span className="flex items-center gap-1.5">
              <i className="ri-shield-check-line text-cyan-400"></i>
              Limites: 2% risco | 5 trades | 5% perda diária
            </span>
          </div>
        </div>
      );
    }

    // Backend conectado
    return (
      <div className="glass-card p-4 mb-6 border-l-4 border-green-500">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
              <i className="ri-shield-check-line text-xl text-green-400"></i>
            </div>
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-bold text-white">🟢 Sistema de Risco Conectado</h3>
            <p className="text-xs text-gray-400 mt-1">
              Backend ativo • Dados em tempo real do <code className="text-green-300">risk_manager.py</code>
            </p>
          </div>
          <button
            onClick={loadRiskData}
            className="px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30 border border-green-500/30 rounded-lg text-xs text-green-300 transition-colors whitespace-nowrap"
          >
            <i className="ri-refresh-line mr-1"></i>
            Atualizar
          </button>
        </div>
        <div className="flex items-center gap-4 mt-3 text-xs">
          <span className="px-2 py-1 bg-green-500/20 border border-green-500/30 rounded text-green-300 flex items-center gap-1">
            <i className="ri-cpu-line"></i>
            Python Core: ATIVO
          </span>
          <span className="px-2 py-1 bg-green-500/20 border border-green-500/30 rounded text-green-300 flex items-center gap-1">
            <i className="ri-database-line"></i>
            Risk Manager: OPERACIONAL
          </span>
          <span className="px-2 py-1 bg-green-500/20 border border-green-500/30 rounded text-green-300 flex items-center gap-1">
            <i className="ri-time-line"></i>
            Atualização: 10s
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Gestão de Risco</h1>
          <p className="text-sm text-purple-300 mt-1">Configure limites e regras de proteção de capital</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-4 py-2 bg-purple-900/50 rounded-lg border border-green-500/30">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
            <span className="text-sm text-green-300">Proteção Ativa</span>
          </div>
          <button 
            onClick={handleReset}
            className="btn btn-secondary flex items-center gap-2 whitespace-nowrap"
            disabled={loading}
          >
            <i className="ri-refresh-line text-base w-5 h-5 flex items-center justify-center"></i>
            <span>Resetar Limites</span>
          </button>
        </div>
      </div>

      {/* System Status Banner */}
      {getSystemStatusBanner()}

      {/* AI Analysis Panel */}
      {aiAnalysis && (
        <div className={`glass-card p-6 border-l-4 ${
          aiAnalysis.risk_level === 'CRITICAL' ? 'border-red-500' :
          aiAnalysis.risk_level === 'HIGH' ? 'border-orange-500' :
          aiAnalysis.risk_level === 'MEDIUM' ? 'border-yellow-500' :
          'border-green-500'
        }`}>
          <div className="flex items-start gap-4">
            <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
              aiAnalysis.risk_level === 'CRITICAL' ? 'bg-red-500/20' :
              aiAnalysis.risk_level === 'HIGH' ? 'bg-orange-500/20' :
              aiAnalysis.risk_level === 'MEDIUM' ? 'bg-yellow-500/20' :
              'bg-green-500/20'
            }`}>
              <i className={`ri-ai-generate text-2xl ${
                aiAnalysis.risk_level === 'CRITICAL' ? 'text-red-400' :
                aiAnalysis.risk_level === 'HIGH' ? 'text-orange-400' :
                aiAnalysis.risk_level === 'MEDIUM' ? 'text-yellow-400' :
                'text-green-400'
              }`}></i>
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-bold text-white">Análise IA de Risco</h3>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Score:</span>
                  <span className={`text-lg font-bold ${
                    aiAnalysis.score > 70 ? 'text-green-400' :
                    aiAnalysis.score > 40 ? 'text-yellow-400' :
                    'text-red-400'
                  }`}>{aiAnalysis.score}/100</span>
                </div>
              </div>
              
              {/* Warnings */}
              {aiAnalysis.warnings && aiAnalysis.warnings.length > 0 && (
                <div className="mb-3 space-y-2">
                  {aiAnalysis.warnings.map((warning: string, idx: number) => (
                    <div key={idx} className="flex items-center gap-2 text-orange-300">
                      <i className="ri-alert-fill"></i>
                      <span className="text-sm">{warning}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Recommendations */}
              {aiAnalysis.recommendations && aiAnalysis.recommendations.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-purple-300">Recomendações:</p>
                  {aiAnalysis.recommendations.map((rec: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2 text-gray-300">
                      <i className="ri-check-line text-green-400 mt-0.5"></i>
                      <span className="text-sm">{rec}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Risk Metrics Overview */}
      {!loading && (
        <RiskMetrics 
          settings={settings} 
          metrics={metrics}
          backendConnected={backendStatus === 'connected'}
        />
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          {!loading && (
            <RiskSettings 
              settings={settings} 
              onUpdate={handleSettingsUpdate}
              backendConnected={backendStatus === 'connected'}
            />
          )}
          <AutoStopRules backendConnected={backendStatus === 'connected'} />
        </div>
        <div>
          <RiskAlerts backendConnected={backendStatus === 'connected'} />
        </div>
      </div>
    </div>
  );
}
