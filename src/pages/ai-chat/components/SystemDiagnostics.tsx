interface SystemHealth {
  frontend: boolean;
  backend: boolean;
  pythonCore: boolean;
  modelsCount: number;
  basePath: string;
  modelsPath: string;
  availableModels: string[];
}

interface SystemDiagnosticsProps {
  systemHealth: SystemHealth;
}

export default function SystemDiagnostics({ systemHealth }: SystemDiagnosticsProps) {
  const components = [
    {
      name: 'Frontend React',
      status: systemHealth.frontend,
      icon: 'ri-reactjs-line',
      color: 'cyan',
      info: 'Dashboard web ativo'
    },
    {
      name: 'Backend API',
      status: systemHealth.backend,
      icon: 'ri-server-line',
      color: 'purple',
      info: 'dashboard_server.py'
    },
    {
      name: 'Python Core',
      status: systemHealth.pythonCore,
      icon: 'ri-code-s-slash-line',
      color: 'blue',
      info: 'trading_bot_core.py'
    },
    {
      name: `Modelos IA (${systemHealth.modelsCount})`,
      status: systemHealth.modelsCount > 0,
      icon: 'ri-brain-line',
      color: 'fuchsia',
      info: systemHealth.modelsPath
    }
  ];

  return (
    <div className="rounded-xl bg-gradient-to-br from-gray-900/90 to-gray-800/90 backdrop-blur-xl border-2 border-cyan-500/30 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-cyan-900/50 to-blue-900/50 border-b-2 border-cyan-500/30 p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center shadow-lg shadow-cyan-500/50">
            <i className="ri-dashboard-line text-xl text-white"></i>
          </div>
          <div>
            <h3 className="font-black text-white">Diagnóstico do Sistema</h3>
            <p className="text-xs text-cyan-400">Status de todos os componentes</p>
          </div>
        </div>
      </div>

      {/* Components */}
      <div className="p-4 space-y-3">
        {components.map((comp, idx) => (
          <div
            key={idx}
            className={`rounded-xl p-3 border-2 transition-all hover:scale-[1.02] ${
              comp.status
                ? 'bg-gradient-to-r from-green-900/30 to-emerald-900/30 border-green-500/60 shadow-lg shadow-green-500/10'
                : 'bg-gradient-to-r from-gray-800/50 to-gray-700/50 border-gray-600/40'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg bg-${comp.color}-500/20 flex items-center justify-center`}>
                  <i className={`${comp.icon} text-xl text-${comp.color}-400`}></i>
                </div>
                <div>
                  <h4 className="font-bold text-white text-sm">{comp.name}</h4>
                  <p className="text-xs text-gray-400 font-mono">{comp.info}</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${
                  comp.status ? 'bg-green-400 animate-pulse shadow-lg shadow-green-500/50' : 'bg-gray-600'
                }`}></div>
                <span className={`text-xs font-bold ${comp.status ? 'text-green-300' : 'text-gray-500'}`}>
                  {comp.status ? 'ATIVO' : 'OFFLINE'}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer Info */}
      <div className="border-t-2 border-cyan-500/30 p-3 bg-cyan-900/20">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <p className="text-gray-400">Base Path:</p>
            <p className="text-cyan-300 font-mono font-bold truncate">{systemHealth.basePath}</p>
          </div>
          <div>
            <p className="text-gray-400">Status Geral:</p>
            <p className={`font-bold ${
              systemHealth.backend && systemHealth.pythonCore ? 'text-green-300' : 
              systemHealth.modelsCount > 0 ? 'text-cyan-300' : 'text-orange-300'
            }`}>
              {systemHealth.backend && systemHealth.pythonCore ? '🟢 Operacional' : 
               systemHealth.modelsCount > 0 ? '○ Preparado' : '⚠️ Aguardando'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
