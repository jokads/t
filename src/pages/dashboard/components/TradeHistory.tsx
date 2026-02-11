interface Trade {
  ticket: number;
  symbol: string;
  type: 'BUY' | 'SELL';
  volume: number;
  openPrice: number;
  closePrice: number;
  profit: number;
  openTime: string;
  closeTime: string;
}

interface TradeHistoryProps {
  trades: Trade[];
}

export default function TradeHistory({ trades }: TradeHistoryProps) {
  // ✅ SEM DADOS MOCK - Apenas dados reais do MT5

  const exportCSV = () => {
    if (trades.length === 0) return;
    
    const headers = ['Ticket', 'Símbolo', 'Tipo', 'Volume', 'Preço Abertura', 'Preço Fecho', 'Profit', 'Hora Abertura', 'Hora Fecho'];
    const rows = trades.map(t => [
      t.ticket,
      t.symbol,
      t.type,
      t.volume,
      t.openPrice,
      t.closePrice,
      t.profit,
      t.openTime,
      t.closeTime
    ]);
    
    const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trade_history_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  const calculateDuration = (openTime: string, closeTime: string) => {
    const diff = new Date(closeTime).getTime() - new Date(openTime).getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}h ${minutes}m`;
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
      <div className="p-4 md:p-6 border-b border-slate-700/50">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base md:text-lg font-semibold text-white">Histórico de Trades</h2>
            <p className="text-xs md:text-sm text-slate-400 mt-1">
              {trades.length > 0 ? `${trades.length} operações fechadas` : 'Nenhuma operação fechada'}
            </p>
          </div>
          {trades.length > 0 && (
            <button
              onClick={exportCSV}
              className="px-3 md:px-4 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded-lg text-xs md:text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap cursor-pointer"
            >
              <i className="ri-download-line text-base"></i>
              <span>Exportar CSV</span>
            </button>
          )}
        </div>
      </div>

      {trades.length === 0 ? (
        <div className="p-8 md:p-12 text-center">
          <div className="w-16 h-16 md:w-20 md:h-20 mx-auto mb-4 rounded-full bg-slate-700/50 flex items-center justify-center">
            <i className="ri-history-line text-3xl md:text-4xl text-slate-500"></i>
          </div>
          <h3 className="text-base md:text-lg font-semibold text-white mb-2">Nenhum Histórico</h3>
          <p className="text-xs md:text-sm text-slate-400">
            O histórico de trades fechados aparecerá aqui
          </p>
        </div>
      ) : (
        <>
          {/* Mobile Cards */}
          <div className="block lg:hidden divide-y divide-slate-700/50 max-h-96 overflow-y-auto">
            {trades.map((trade) => (
              <div key={trade.ticket} className="p-4 hover:bg-slate-700/20 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-bold text-white">{trade.symbol}</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        trade.type === 'BUY' 
                          ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                          : 'bg-red-500/20 text-red-400 border border-red-500/30'
                      }`}>
                        {trade.type}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">Ticket: #{trade.ticket}</p>
                  </div>
                  <span className={`text-sm font-bold ${
                    trade.profit >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    ${trade.profit.toFixed(2)}
                  </span>
                </div>
                
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400">Volume:</span>
                    <span className="text-white ml-2">{trade.volume}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Abertura:</span>
                    <span className="text-white ml-2">{trade.openPrice.toFixed(5)}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Fecho:</span>
                    <span className="text-white ml-2">{trade.closePrice.toFixed(5)}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Duração:</span>
                    <span className="text-white ml-2">{calculateDuration(trade.openTime, trade.closeTime)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop Table */}
          <div className="hidden lg:block overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-900/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Ticket</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Símbolo</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Tipo</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Volume</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Abertura</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Fecho</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Profit</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Duração</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {trades.map((trade) => (
                  <tr key={trade.ticket} className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-4 py-4 text-sm text-slate-300">#{trade.ticket}</td>
                    <td className="px-4 py-4 text-sm font-medium text-white">{trade.symbol}</td>
                    <td className="px-4 py-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        trade.type === 'BUY' 
                          ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                          : 'bg-red-500/20 text-red-400 border border-red-500/30'
                      }`}>
                        {trade.type}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-300">{trade.volume}</td>
                    <td className="px-4 py-4 text-sm text-slate-300">{trade.openPrice.toFixed(5)}</td>
                    <td className="px-4 py-4 text-sm text-slate-300">{trade.closePrice.toFixed(5)}</td>
                    <td className="px-4 py-4">
                      <span className={`text-sm font-medium ${
                        trade.profit >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        ${trade.profit.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-400">
                      {calculateDuration(trade.openTime, trade.closeTime)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
