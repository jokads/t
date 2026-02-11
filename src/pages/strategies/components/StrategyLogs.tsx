import { useState } from 'react';

interface StrategyLogsProps {
  strategyId: string | null;
  logs: Array<{
    id: string;
    timestamp: string;
    level: string;
    strategy: string;
    message: string;
  }>;
}

export default function StrategyLogs({ strategyId, logs }: StrategyLogsProps) {
  const [autoScroll, setAutoScroll] = useState(true);

  // Filtrar logs pela estratégia selecionada
  const filteredLogs = strategyId 
    ? logs.filter(log => log.strategy.toLowerCase().includes(strategyId.toLowerCase().replace('_', ' ')))
    : logs;

  const getLevelColor = (level: string) => {
    const upperLevel = level.toUpperCase();
    switch (upperLevel) {
      case 'SUCCESS': return 'text-green-400';
      case 'INFO': return 'text-cyan-400';
      case 'WARNING': 
      case 'WARN': return 'text-orange-400';
      case 'ERROR': return 'text-red-400';
      case 'DEBUG': return 'text-gray-400';
      default: return 'text-slate-400';
    }
  };

  const getLevelIcon = (level: string) => {
    const upperLevel = level.toUpperCase();
    switch (upperLevel) {
      case 'SUCCESS': return 'ri-checkbox-circle-line';
      case 'INFO': return 'ri-information-line';
      case 'WARNING': 
      case 'WARN': return 'ri-error-warning-line';
      case 'ERROR': return 'ri-close-circle-line';
      case 'DEBUG': return 'ri-bug-line';
      default: return 'ri-record-circle-line';
    }
  };

  return (
    <div className="bg-black/40 backdrop-blur-xl rounded-lg border border-orange-500/20 overflow-hidden h-full">
      <div className="p-4 md:p-6 border-b border-orange-500/20">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-base md:text-lg font-semibold text-white">Logs da Estratégia</h2>
            <p className="text-xs md:text-sm text-purple-300 mt-1">
              {strategyId ? `Filtrando por: ${strategyId}` : 'Todas as estratégias'}
            </p>
          </div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="w-4 h-4 rounded border-slate-600 bg-slate-900/50 text-cyan-500 focus:ring-2 focus:ring-cyan-500 cursor-pointer"
          />
          <span className="text-xs md:text-sm text-purple-300">Auto-scroll</span>
        </label>
      </div>

      <div className="p-3 md:p-4 space-y-2 max-h-[400px] md:max-h-[600px] overflow-y-auto custom-scrollbar">
        {filteredLogs.length === 0 ? (
          <div className="text-center py-8 md:py-12">
            <i className="ri-file-list-3-line text-3xl md:text-4xl text-purple-800 mb-2 md:mb-3"></i>
            <p className="text-xs md:text-sm text-purple-400">Nenhum log disponível</p>
            {strategyId && (
              <p className="text-xs text-purple-500 mt-2">Selecione outra estratégia ou aguarde atividade</p>
            )}
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div
              key={log.id}
              className="bg-purple-900/30 rounded-lg p-3 border border-purple-500/20 hover:border-orange-500/30 transition-all"
            >
              <div className="flex items-start gap-2 md:gap-3">
                <i className={`${getLevelIcon(log.level)} ${getLevelColor(log.level)} text-base md:text-lg mt-0.5 flex-shrink-0`}></i>
                <div className="flex-1 min-w-0">
                  <p className="text-xs md:text-sm text-white break-words leading-relaxed">{log.message}</p>
                  <div className="flex items-center gap-2 md:gap-3 mt-2 flex-wrap">
                    <span className={`text-xs font-semibold ${getLevelColor(log.level)}`}>
                      [{log.level.toUpperCase()}]
                    </span>
                    <span className="text-xs text-purple-400">
                      {new Date(log.timestamp).toLocaleString('pt-PT', {
                        day: '2-digit',
                        month: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                      })}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}