interface RiskSettingsProps {
  settings: {
    maxRiskPerTrade: number;
    maxConcurrentTrades: number;
    maxDailyLoss: number;
    maxDrawdown: number;
    autoStopEnabled: boolean;
  };
  onUpdate: (settings: any) => void;
  backendConnected: boolean;
}

export default function RiskSettings({ settings, onUpdate, backendConnected }: RiskSettingsProps) {
  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">Configurações de Risco</h2>
            <p className="text-sm text-slate-400 mt-1">Defina os limites de proteção de capital</p>
          </div>
          {backendConnected && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-green-500/20 border border-green-500/30 rounded-lg">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
              <span className="text-xs text-green-300 font-semibold">CONECTADO</span>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-6">
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="text-sm font-medium text-slate-300">Risco Máximo por Trade</label>
            <span className="text-lg font-bold text-cyan-400">{settings.maxRiskPerTrade}%</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="10"
            step="0.5"
            value={settings.maxRiskPerTrade}
            onChange={(e) => onUpdate({ ...settings, maxRiskPerTrade: parseFloat(e.target.value) })}
            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
          />
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>0.5%</span>
            <span>10%</span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="text-sm font-medium text-slate-300">Trades Simultâneos Máximos</label>
            <span className="text-lg font-bold text-cyan-400">{settings.maxConcurrentTrades}</span>
          </div>
          <input
            type="range"
            min="1"
            max="20"
            step="1"
            value={settings.maxConcurrentTrades}
            onChange={(e) => onUpdate({ ...settings, maxConcurrentTrades: parseInt(e.target.value) })}
            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
          />
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>1</span>
            <span>20</span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="text-sm font-medium text-slate-300">Perda Diária Máxima</label>
            <span className="text-lg font-bold text-red-400">{settings.maxDailyLoss}%</span>
          </div>
          <input
            type="range"
            min="1"
            max="20"
            step="1"
            value={settings.maxDailyLoss}
            onChange={(e) => onUpdate({ ...settings, maxDailyLoss: parseInt(e.target.value) })}
            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-red-500"
          />
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>1%</span>
            <span>20%</span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="text-sm font-medium text-slate-300">Drawdown Máximo</label>
            <span className="text-lg font-bold text-orange-400">{settings.maxDrawdown}%</span>
          </div>
          <input
            type="range"
            min="5"
            max="50"
            step="5"
            value={settings.maxDrawdown}
            onChange={(e) => onUpdate({ ...settings, maxDrawdown: parseInt(e.target.value) })}
            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
          />
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>5%</span>
            <span>50%</span>
          </div>
        </div>

        <div className="pt-4 border-t border-slate-700/50">
          <label className="flex items-center justify-between cursor-pointer">
            <div>
              <span className="text-sm font-medium text-slate-300">Auto-Stop em Emergência</span>
              <p className="text-xs text-slate-500 mt-1">Parar automaticamente quando limites forem atingidos</p>
            </div>
            <div className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.autoStopEnabled}
                onChange={(e) => onUpdate({ ...settings, autoStopEnabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-cyan-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-500"></div>
            </div>
          </label>
        </div>

        {/* Info Footer */}
        <div className="pt-4 border-t border-slate-700/50">
          <div className="flex items-start gap-2 text-xs text-slate-400">
            <i className="ri-information-line text-cyan-400 mt-0.5"></i>
            <p>
              {backendConnected ? (
                <span>As configurações são aplicadas imediatamente ao <code className="px-1.5 py-0.5 bg-slate-700 rounded text-cyan-300">risk_manager.py</code></span>
              ) : (
                <span>Configure os limites. Serão aplicados quando o backend conectar.</span>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
