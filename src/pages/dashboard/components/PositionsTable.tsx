interface Position {
  ticket: number;
  symbol: string;
  type: 'BUY' | 'SELL';
  volume: number;
  openPrice: number;
  sl: number;
  tp: number;
  profit: number;
  timeOpen: string;
}

interface PositionsTableProps {
  positions: Position[];
}

export default function PositionsTable({ positions }: PositionsTableProps) {
  // ✅ SEM DADOS MOCK - Apenas dados reais do MT5

  const handleClosePosition = async (ticket: number) => {
    // TODO: Integrar com API real
    console.log('Fechando posição:', ticket);
  };

  const handleModifyPosition = async (ticket: number) => {
    // TODO: Integrar com API real
    console.log('Modificando posição:', ticket);
  };

  const handleCloseAll = async () => {
    // TODO: Integrar com API real
    console.log('Fechando todas as posições');
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
      <div className="p-4 md:p-6 border-b border-slate-700/50">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base md:text-lg font-semibold text-white">Posições Abertas</h2>
            <p className="text-xs md:text-sm text-slate-400 mt-1">{positions.length} posições ativas</p>
          </div>
          {positions.length > 0 && (
            <button 
              onClick={handleCloseAll}
              className="px-3 md:px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-xs md:text-sm font-medium transition-all flex items-center gap-2 border border-red-500/30 whitespace-nowrap cursor-pointer"
            >
              <i className="ri-close-circle-line text-base"></i>
              <span>Fechar Todas</span>
            </button>
          )}
        </div>
      </div>

      {positions.length === 0 ? (
        <div className="p-8 md:p-12 text-center">
          <div className="w-16 h-16 md:w-20 md:h-20 mx-auto mb-4 rounded-full bg-slate-700/50 flex items-center justify-center">
            <i className="ri-inbox-line text-3xl md:text-4xl text-slate-500"></i>
          </div>
          <h3 className="text-base md:text-lg font-semibold text-white mb-2">Nenhuma Posição Aberta</h3>
          <p className="text-xs md:text-sm text-slate-400">
            Aguardando sinais de trading das estratégias ativas
          </p>
        </div>
      ) : (
        <>
          {/* Mobile Cards */}
          <div className="block lg:hidden divide-y divide-slate-700/50">
            {positions.map((position) => (
              <div key={position.ticket} className="p-4 hover:bg-slate-700/20 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-bold text-white">{position.symbol}</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        position.type === 'BUY' 
                          ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                          : 'bg-red-500/20 text-red-400 border border-red-500/30'
                      }`}>
                        {position.type}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">Ticket: #{position.ticket}</p>
                  </div>
                  <span className={`text-sm font-bold ${
                    position.profit >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    ${position.profit.toFixed(2)}
                  </span>
                </div>
                
                <div className="grid grid-cols-2 gap-3 mb-3 text-xs">
                  <div>
                    <span className="text-slate-400">Volume:</span>
                    <span className="text-white ml-2">{position.volume}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Abertura:</span>
                    <span className="text-white ml-2">{position.openPrice.toFixed(5)}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">SL:</span>
                    <span className="text-white ml-2">{position.sl.toFixed(5)}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">TP:</span>
                    <span className="text-white ml-2">{position.tp.toFixed(5)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button 
                    onClick={() => handleModifyPosition(position.ticket)}
                    className="flex-1 px-3 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-all cursor-pointer"
                  >
                    <i className="ri-edit-line mr-1"></i>
                    Modificar
                  </button>
                  <button 
                    onClick={() => handleClosePosition(position.ticket)}
                    className="flex-1 px-3 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-xs font-medium transition-all border border-red-500/30 cursor-pointer"
                  >
                    <i className="ri-close-line mr-1"></i>
                    Fechar
                  </button>
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">SL</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">TP</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Profit</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Hora</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {positions.map((position) => (
                  <tr key={position.ticket} className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-4 py-4 text-sm text-slate-300">#{position.ticket}</td>
                    <td className="px-4 py-4 text-sm font-medium text-white">{position.symbol}</td>
                    <td className="px-4 py-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        position.type === 'BUY' 
                          ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                          : 'bg-red-500/20 text-red-400 border border-red-500/30'
                      }`}>
                        {position.type}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-300">{position.volume}</td>
                    <td className="px-4 py-4 text-sm text-slate-300">{position.openPrice.toFixed(5)}</td>
                    <td className="px-4 py-4 text-sm text-slate-300">{position.sl.toFixed(5)}</td>
                    <td className="px-4 py-4 text-sm text-slate-300">{position.tp.toFixed(5)}</td>
                    <td className="px-4 py-4">
                      <span className={`text-sm font-medium ${
                        position.profit >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        ${position.profit.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-400">
                      {new Date(position.timeOpen).toLocaleTimeString('pt-PT')}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <button 
                          onClick={() => handleModifyPosition(position.ticket)}
                          className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-cyan-400 hover:bg-slate-700 rounded transition-all cursor-pointer" 
                          title="Modificar"
                        >
                          <i className="ri-edit-line text-base"></i>
                        </button>
                        <button 
                          onClick={() => handleClosePosition(position.ticket)}
                          className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-red-400 hover:bg-slate-700 rounded transition-all cursor-pointer" 
                          title="Fechar"
                        >
                          <i className="ri-close-line text-base"></i>
                        </button>
                      </div>
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
