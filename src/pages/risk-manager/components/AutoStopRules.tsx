import { useState, useEffect } from 'react';
import { apiGet } from '../../../utils/api';

interface AutoStopRulesProps {
  backendConnected: boolean;
}

export default function AutoStopRules({ backendConnected }: AutoStopRulesProps) {
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRules();
    
    // Atualizar a cada 15 segundos se backend conectado
    if (backendConnected) {
      const interval = setInterval(loadRules, 15000);
      return () => clearInterval(interval);
    }
  }, [backendConnected]);

  const loadRules = async () => {
    try {
      setLoading(true);
      const data = await apiGet('/api/risk/auto-stop-rules');
      if (data && data.rules) {
        setRules(data.rules);
        console.log('✅ Regras de auto-stop carregadas:', data.rules);
      }
    } catch (error) {
      console.error('Erro ao carregar regras:', error);
      
      // ✅ Fallback: regras padrão se backend offline
      setRules([
        {
          id: 1,
          name: 'Stop por Perda Diária',
          description: 'Para trading quando perda diária atingir 5%',
          enabled: true,
          priority: 'high'
        },
        {
          id: 2,
          name: 'Stop por Drawdown',
          description: 'Para trading quando drawdown atingir 10%',
          enabled: true,
          priority: 'critical'
        },
        {
          id: 3,
          name: 'Limite de Trades',
          description: 'Máximo de 5 trades simultâneos',
          enabled: true,
          priority: 'medium'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'red';
      case 'high': return 'orange';
      case 'medium': return 'yellow';
      default: return 'blue';
    }
  };

  const getPriorityLabel = (priority: string) => {
    switch (priority) {
      case 'critical': return 'CRÍTICA';
      case 'high': return 'ALTA';
      case 'medium': return 'MÉDIA';
      default: return 'BAIXA';
    }
  };

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white">Regras de Auto-Stop</h2>
            {backendConnected && (
              <span className="px-2 py-1 bg-green-500/20 border border-green-500/30 rounded text-xs text-green-300 font-semibold flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></div>
                LIVE
              </span>
            )}
            {!backendConnected && (
              <span className="px-2 py-1 bg-cyan-500/20 border border-cyan-500/30 rounded text-xs text-cyan-300 font-semibold flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400"></div>
                PREPARADO
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-1">Sistema automático de proteção</p>
        </div>
        <button 
          className="btn btn-sm btn-primary flex items-center gap-2 whitespace-nowrap"
          onClick={() => alert('Funcionalidade de criar nova regra será implementada em breve')}
        >
          <i className="ri-add-line text-base w-4 h-4 flex items-center justify-center"></i>
          <span>Nova Regra</span>
        </button>
      </div>

      {loading ? (
        <div className="text-center py-8">
          <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-sm text-gray-400 mt-3">Carregando regras...</p>
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => {
            const color = getPriorityColor(rule.priority);
            
            return (
              <div 
                key={rule.id}
                className="p-4 rounded-lg bg-purple-900/30 border border-purple-500/20 hover:border-purple-500/40 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h4 className="text-sm font-semibold text-white">{rule.name}</h4>
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold bg-${color}-500/20 text-${color}-400`}>
                        {getPriorityLabel(rule.priority)}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400">{rule.description}</p>
                  </div>
                  
                  <label className="relative inline-flex items-center cursor-pointer ml-4">
                    <input 
                      type="checkbox" 
                      checked={rule.enabled}
                      onChange={() => alert('Toggle de regras será implementado em breve')}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                  </label>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-purple-500/10">
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span className="flex items-center gap-1">
                      <i className="ri-time-line"></i>
                      Tempo real
                    </span>
                    <span className="flex items-center gap-1">
                      <i className="ri-shield-check-line"></i>
                      Automático
                    </span>
                    {backendConnected && (
                      <span className="flex items-center gap-1 text-green-400">
                        <i className="ri-checkbox-circle-line"></i>
                        Ativa
                      </span>
                    )}
                  </div>
                  <button 
                    className="text-xs text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1"
                    onClick={() => alert('Configuração de regras será implementada em breve')}
                  >
                    <i className="ri-settings-3-line"></i>
                    Configurar
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Summary */}
      <div className="mt-6 pt-6 border-t border-purple-500/20">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold text-white">{rules.length}</p>
            <p className="text-xs text-gray-400 mt-1">Total de Regras</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green-400">
              {rules.filter(r => r.enabled).length}
            </p>
            <p className="text-xs text-gray-400 mt-1">Ativas</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-red-400">
              {rules.filter(r => r.priority === 'critical').length}
            </p>
            <p className="text-xs text-gray-400 mt-1">Críticas</p>
          </div>
        </div>
      </div>

      {/* Info Footer */}
      {!backendConnected && (
        <div className="mt-4 pt-4 border-t border-purple-500/20">
          <div className="flex items-start gap-2 text-xs text-gray-400">
            <i className="ri-information-line text-cyan-400 mt-0.5"></i>
            <p>
              Regras padrão carregadas. Execute <code className="px-1.5 py-0.5 bg-purple-900/50 rounded text-cyan-300">python trading_bot_core.py</code> para conectar ao sistema real.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
