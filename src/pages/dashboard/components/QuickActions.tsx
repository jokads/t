import { useState } from 'react';

export default function QuickActions() {
  const [showSignalForm, setShowSignalForm] = useState(false);
  const [signalData, setSignalData] = useState({
    symbol: 'EURUSD',
    type: 'BUY',
    volume: 0.1,
    sl: '',
    tp: '',
    note: ''
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Enviar sinal:', signalData);
    setShowSignalForm(false);
  };

  return (
    <>
      <div className="flex gap-3">
        <button
          onClick={() => setShowSignalForm(true)}
          className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-cyan-500/30 flex items-center gap-2 whitespace-nowrap cursor-pointer"
        >
          <i className="ri-send-plane-fill text-base"></i>
          <span>Enviar Sinal Manual</span>
        </button>
      </div>

      {showSignalForm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl border border-slate-700 max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-white">Enviar Sinal Manual</h3>
              <button
                onClick={() => setShowSignalForm(false)}
                className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-all cursor-pointer"
              >
                <i className="ri-close-line text-xl"></i>
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Símbolo</label>
                  <select
                    value={signalData.symbol}
                    onChange={(e) => setSignalData({...signalData, symbol: e.target.value})}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  >
                    <option>EURUSD</option>
                    <option>GBPUSD</option>
                    <option>USDJPY</option>
                    <option>AUDUSD</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Tipo</label>
                  <select
                    value={signalData.type}
                    onChange={(e) => setSignalData({...signalData, type: e.target.value})}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  >
                    <option>BUY</option>
                    <option>SELL</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Volume</label>
                <input
                  type="number"
                  step="0.01"
                  value={signalData.volume}
                  onChange={(e) => setSignalData({...signalData, volume: parseFloat(e.target.value)})}
                  className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  placeholder="0.1"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Stop Loss</label>
                  <input
                    type="number"
                    step="0.00001"
                    value={signalData.sl}
                    onChange={(e) => setSignalData({...signalData, sl: e.target.value})}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
                    placeholder="1.0700"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Take Profit</label>
                  <input
                    type="number"
                    step="0.00001"
                    value={signalData.tp}
                    onChange={(e) => setSignalData({...signalData, tp: e.target.value})}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
                    placeholder="1.1000"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Nota (opcional)</label>
                <textarea
                  value={signalData.note}
                  onChange={(e) => setSignalData({...signalData, note: e.target.value})}
                  className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 resize-none"
                  rows={3}
                  placeholder="Adicione uma nota sobre este sinal..."
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowSignalForm(false)}
                  className="flex-1 px-4 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-cyan-500/30 whitespace-nowrap cursor-pointer"
                >
                  Enviar Sinal
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}