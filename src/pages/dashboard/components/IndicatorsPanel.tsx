import { useState } from 'react';

interface Indicator {
  symbol: string;
  rsi: number;
  macd: { value: number; signal: string };
  ema: number;
  sma: number;
  signal: 'BUY' | 'SELL' | 'NEUTRAL';
}

export default function IndicatorsPanel() {
  const [indicators] = useState<Indicator[]>([
    {
      symbol: 'EURUSD',
      rsi: 65.3,
      macd: { value: 0.0012, signal: 'Bullish' },
      ema: 1.0795,
      sma: 1.0780,
      signal: 'BUY'
    },
    {
      symbol: 'GBPUSD',
      rsi: 42.8,
      macd: { value: -0.0008, signal: 'Bearish' },
      ema: 1.2655,
      sma: 1.2670,
      signal: 'SELL'
    },
    {
      symbol: 'USDJPY',
      rsi: 55.1,
      macd: { value: 0.0003, signal: 'Neutral' },
      ema: 148.45,
      sma: 148.40,
      signal: 'NEUTRAL'
    }
  ]);

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'BUY': return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'SELL': return 'bg-red-500/20 text-red-400 border-red-500/30';
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  const getRSIColor = (rsi: number) => {
    if (rsi > 70) return 'text-red-400';
    if (rsi < 30) return 'text-green-400';
    return 'text-slate-300';
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
      <div className="p-6 border-b border-slate-700/50">
        <h2 className="text-lg font-semibold text-white">Indicadores Técnicos</h2>
        <p className="text-sm text-slate-400 mt-1">Análise em tempo real</p>
      </div>

      <div className="p-4 space-y-4">
        {indicators.map((indicator) => (
          <div
            key={indicator.symbol}
            className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 hover:border-slate-600 transition-all"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white">{indicator.symbol}</h3>
              <span className={`px-2 py-1 rounded text-xs font-medium border ${getSignalColor(indicator.signal)}`}>
                {indicator.signal}
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">RSI (14)</span>
                <span className={`text-sm font-medium ${getRSIColor(indicator.rsi)}`}>
                  {indicator.rsi.toFixed(1)}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">MACD</span>
                <div className="text-right">
                  <span className="text-sm font-medium text-slate-300">{indicator.macd.value.toFixed(4)}</span>
                  <span className="text-xs text-slate-500 ml-2">({indicator.macd.signal})</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">EMA (20)</span>
                <span className="text-sm font-medium text-slate-300">{indicator.ema.toFixed(5)}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">SMA (50)</span>
                <span className="text-sm font-medium text-slate-300">{indicator.sma.toFixed(5)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 border-t border-slate-700/50">
        <button className="w-full py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 whitespace-nowrap cursor-pointer">
          <i className="ri-refresh-line text-base"></i>
          <span>Atualizar Indicadores</span>
        </button>
      </div>
    </div>
  );
}