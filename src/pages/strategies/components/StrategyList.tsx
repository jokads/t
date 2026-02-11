import { useEffect } from 'react';
import { apiPost } from '../../../utils/api';

interface Strategy {
  id: string;
  name: string;
  file: string;
  enabled: boolean;
  priority: number;
  status: 'running' | 'stopped' | 'error';
  trades: number;
  profit?: number;  // ✅ Opcional para evitar undefined
  winRate?: number; // ✅ Opcional para evitar undefined
}

interface StrategyListProps {
  onSelectStrategy: (id: string) => void;
  strategies: Strategy[];
  setStrategies: (strategies: Strategy[]) => void;
  backendConnected: boolean;
}

export default function StrategyList({ onSelectStrategy, strategies, setStrategies, backendConnected }: StrategyListProps) {

  const toggleStrategy = async (id: string) => {
    const strategy = strategies.find(s => s.id === id);
    if (!strategy) return;

    // Atualizar localmente primeiro (otimista)
    setStrategies(strategies.map(s => 
      s.id === id ? { ...s, enabled: !s.enabled, status: !s.enabled ? 'running' : 'stopped' } : s
    ));

    // Tentar atualizar no backend
    try {
      if (!backendConnected) return;

      await apiPost('/api/strategies/toggle', {
        strategy_id: id,
        enabled: !strategy.enabled
      });
    } catch (error) {
      // Modo silencioso
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'stopped': return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
      case 'error': return 'bg-red-500/20 text-red-400 border-red-500/30';
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  return (
    <div className="bg-black/40 backdrop-blur-xl rounded-lg border border-orange-500/20 overflow-hidden">
      <div className="p-4 md:p-6 border-b border-orange-500/20">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base md:text-lg font-semibold text-white">Estratégias Ativas</h2>
          {!backendConnected && (
            <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded border border-yellow-500/30">
              Modo Offline
            </span>
          )}
        </div>
        <p className="text-xs md:text-sm text-purple-300">
          {strategies.filter(s => s.enabled).length} de {strategies.length} estratégias em execução
        </p>
      </div>

      <div className="p-3 md:p-4 space-y-3 max-h-[600px] overflow-y-auto custom-scrollbar">
        {strategies.length === 0 ? (
          <div className="text-center py-8 md:py-12">
            <i className="ri-folder-open-line text-4xl md:text-5xl text-purple-800 mb-3 md:mb-4"></i>
            <p className="text-purple-400 text-sm md:text-base font-semibold">Nenhuma estratégia encontrada</p>
            <p className="text-purple-500 text-xs md:text-sm mt-2">
              Verifique se o backend está rodando: <br className="md:hidden" />
              <code className="bg-purple-900/30 px-2 py-1 rounded mt-1 inline-block">
                python -m backend.dashboard_server
              </code>
            </p>
          </div>
        ) : (
          strategies.map((strategy) => {
            // ✅ PROTEÇÃO CONTRA undefined - Valores padrão
            const profit = strategy.profit ?? 0;
            const winRate = strategy.winRate ?? 0;
            
            return (
              <div
                key={strategy.id}
                onClick={() => onSelectStrategy(strategy.id)}
                className="bg-purple-900/30 rounded-lg p-3 md:p-4 border border-purple-500/20 hover:border-orange-500/40 transition-all cursor-pointer"
              >
                <div className="flex items-start justify-between mb-3 gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 md:gap-3 mb-2 flex-wrap">
                      <h3 className="text-sm md:text-base font-semibold text-white break-words">{strategy.name}</h3>
                      <span className={`px-2 py-0.5 md:py-1 rounded text-xs font-medium border ${getStatusColor(strategy.status)}`}>
                        {strategy.status === 'running' ? 'Ativo' : strategy.status === 'stopped' ? 'Parado' : 'Erro'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 md:gap-4 text-xs text-purple-400 flex-wrap">
                      <span>📄 {strategy.file}</span>
                      <span>•</span>
                      <span>Prioridade: {strategy.priority}</span>
                      <span>•</span>
                      <span>{strategy.trades} trades</span>
                    </div>
                  </div>

                  <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
                    <input
                      type="checkbox"
                      checked={strategy.enabled}
                      onChange={(e) => {
                        e.stopPropagation();
                        toggleStrategy(strategy.id);
                      }}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 md:w-11 md:h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-cyan-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 md:after:h-5 md:after:w-5 after:transition-all peer-checked:bg-cyan-500"></div>
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-3 md:gap-4">
                  <div>
                    <p className="text-xs text-purple-400 mb-1">Profit Total</p>
                    <p className={`text-sm md:text-base font-semibold ${profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {profit >= 0 ? '+' : ''}${profit.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-purple-400 mb-1">Win Rate</p>
                    <p className="text-sm md:text-base font-semibold text-white">{winRate.toFixed(1)}%</p>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-purple-500/20 flex gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleStrategy(strategy.id);
                    }}
                    className="flex-1 px-3 py-2 bg-purple-700/50 hover:bg-purple-700 text-purple-200 rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-2 whitespace-nowrap cursor-pointer"
                  >
                    <i className={`${strategy.enabled ? 'ri-pause-line' : 'ri-play-line'} text-sm`}></i>
                    <span className="hidden sm:inline">{strategy.enabled ? 'Pausar' : 'Iniciar'}</span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectStrategy(strategy.id);
                    }}
                    className="flex-1 px-3 py-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-300 rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-2 whitespace-nowrap cursor-pointer border border-orange-500/30"
                  >
                    <i className="ri-settings-3-line text-sm"></i>
                    <span className="hidden sm:inline">Config</span>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}