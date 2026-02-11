import { useState, useEffect } from 'react';

interface EnvironmentStatus {
  frontend: boolean;
  backend: boolean;
  pythonCore: boolean;
  basePath: string;
  modelsPath: string;
  availableModels: number;
}

interface Process {
  pid: number;
  name: string;
  path: string;
  cpu: number;
  memory: number;
  status: 'running' | 'stopped' | 'error';
  uptime: string;
  type: 'core' | 'service' | 'ai' | 'integration';
  autoStart: boolean;
}

interface ProcessManagerProps {
  environment: EnvironmentStatus;
  selectedProcesses: number[];
  setSelectedProcesses: (pids: number[]) => void;
  onSelectAll: () => void;
  onStopSelected: () => void;
  onStartSelected: () => void;
  onRestartSelected: () => void;
}

export default function ProcessManager({ 
  environment,
  selectedProcesses, 
  setSelectedProcesses,
  onSelectAll,
  onStopSelected,
  onStartSelected,
  onRestartSelected
}: ProcessManagerProps) {
  const [processes, setProcesses] = useState<Process[]>([
    { pid: 12345, name: 'trading_bot_core.py', path: 'C:/bot-mt5/trading_bot_core.py', cpu: 15.3, memory: 234, status: 'running', uptime: '2h 34m', type: 'core', autoStart: true },
    { pid: 12346, name: 'dashboard_server.py', path: 'C:/bot-mt5/backend/dashboard_server.py', cpu: 8.7, memory: 156, status: 'running', uptime: '2h 34m', type: 'core', autoStart: true },
    { pid: 12347, name: 'ai_manager.py', path: 'C:/bot-mt5/core/local_ai_manager.py', cpu: 23.1, memory: 512, status: 'running', uptime: '2h 33m', type: 'ai', autoStart: true },
    { pid: 12348, name: 'mt5_communication.py', path: 'C:/bot-mt5/mt5_communication.py', cpu: 5.2, memory: 89, status: 'running', uptime: '2h 34m', type: 'service', autoStart: true },
    { pid: 12349, name: 'strategy_engine.py', path: 'C:/bot-mt5/strategies/strategy_engine.py', cpu: 12.4, memory: 178, status: 'running', uptime: '2h 32m', type: 'service', autoStart: true },
    { pid: 12350, name: 'risk_manager.py', path: 'C:/bot-mt5/strategies/risk_manager.py', cpu: 3.8, memory: 67, status: 'running', uptime: '2h 34m', type: 'service', autoStart: true },
    { pid: 12351, name: 'telegram_handler.py', path: 'C:/bot-mt5/core/telegram_handler.py', cpu: 2.1, memory: 45, status: 'stopped', uptime: '0m', type: 'integration', autoStart: false },
    { pid: 12352, name: 'news_api_manager.py', path: 'C:/bot-mt5/core/news_api_manager.py', cpu: 1.8, memory: 38, status: 'stopped', uptime: '0m', type: 'integration', autoStart: false },
    { pid: 12353, name: 'adaptive_ml.py', path: 'C:/bot-mt5/strategies/adaptive_ml.py', cpu: 18.5, memory: 423, status: 'running', uptime: '2h 31m', type: 'ai', autoStart: true },
    { pid: 12354, name: 'deep_q_learning.py', path: 'C:/bot-mt5/strategies/deep_q_learning.py', cpu: 0, memory: 0, status: 'stopped', uptime: '0m', type: 'ai', autoStart: false }
  ]);

  const [sortBy, setSortBy] = useState<'cpu' | 'memory' | 'name' | 'status'>('cpu');
  const [filterType, setFilterType] = useState<'all' | 'core' | 'service' | 'ai' | 'integration'>('all');
  const [filterStatus, setFilterStatus] = useState<'all' | 'running' | 'stopped' | 'error'>('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Update CPU/Memory randomly for demo
  useEffect(() => {
    const interval = setInterval(() => {
      setProcesses(prev => prev.map(p => 
        p.status === 'running' 
          ? { ...p, cpu: parseFloat((Math.random() * 25 + 5).toFixed(1)), memory: Math.floor(Math.random() * 100 + p.memory * 0.8) }
          : p
      ));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const filteredProcesses = processes.filter(p => {
    if (filterType !== 'all' && p.type !== filterType) return false;
    if (filterStatus !== 'all' && p.status !== filterStatus) return false;
    if (searchTerm && !p.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  const sortedProcesses = [...filteredProcesses].sort((a, b) => {
    if (sortBy === 'cpu') return b.cpu - a.cpu;
    if (sortBy === 'memory') return b.memory - a.memory;
    if (sortBy === 'name') return a.name.localeCompare(b.name);
    if (sortBy === 'status') return a.status.localeCompare(b.status);
    return 0;
  });

  const handleSelectProcess = (pid: number) => {
    if (selectedProcesses.includes(pid)) {
      setSelectedProcesses(selectedProcesses.filter(p => p !== pid));
    } else {
      setSelectedProcesses([...selectedProcesses, pid]);
    }
  };

  const handleSelectAllVisible = () => {
    const allPids = sortedProcesses.map(p => p.pid);
    if (selectedProcesses.length === allPids.length) {
      setSelectedProcesses([]);
    } else {
      setSelectedProcesses(allPids);
    }
  };

  const handleStartProcess = (pid: number) => {
    setProcesses(prev => prev.map(p => 
      p.pid === pid ? { ...p, status: 'running', uptime: '0m' } : p
    ));
  };

  const handleStopProcess = (pid: number) => {
    setProcesses(prev => prev.map(p => 
      p.pid === pid ? { ...p, status: 'stopped', uptime: '0m', cpu: 0, memory: 0 } : p
    ));
  };

  const handleRestartProcess = (pid: number) => {
    setProcesses(prev => prev.map(p => 
      p.pid === pid ? { ...p, status: 'running', uptime: '0m' } : p
    ));
  };

  const handleToggleAutoStart = (pid: number) => {
    setProcesses(prev => prev.map(p => 
      p.pid === pid ? { ...p, autoStart: !p.autoStart } : p
    ));
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'core': return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
      case 'service': return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      case 'ai': return 'bg-pink-500/20 text-pink-400 border-pink-500/30';
      case 'integration': return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30';
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'core': return 'Core';
      case 'service': return 'Serviço';
      case 'ai': return 'IA';
      case 'integration': return 'Integração';
      default: return 'Outro';
    }
  };

  const runningCount = processes.filter(p => p.status === 'running').length;
  const stoppedCount = processes.filter(p => p.status === 'stopped').length;
  const errorCount = processes.filter(p => p.status === 'error').length;

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold gradient-text flex items-center gap-2">
            <i className="ri-list-check text-xl"></i>
            Gestor de Processos Ultra-Hardcore
          </h3>
          <p className="text-xs text-purple-300 mt-1">
            Total: {processes.length} | Ativos: {runningCount} | Parados: {stoppedCount} | Erros: {errorCount}
          </p>
        </div>
        
        {/* Bulk Actions */}
        {selectedProcesses.length > 0 && (
          <div className="flex gap-2">
            <button
              onClick={onStartSelected}
              className="px-4 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-400 rounded-lg text-sm font-medium transition-all border border-green-500/30 whitespace-nowrap cursor-pointer"
            >
              <i className="ri-play-circle-line mr-2"></i>
              Iniciar ({selectedProcesses.length})
            </button>
            <button
              onClick={onRestartSelected}
              className="px-4 py-2 bg-orange-500/10 hover:bg-orange-500/20 text-orange-400 rounded-lg text-sm font-medium transition-all border border-orange-500/30 whitespace-nowrap cursor-pointer"
            >
              <i className="ri-restart-line mr-2"></i>
              Reiniciar ({selectedProcesses.length})
            </button>
            <button
              onClick={onStopSelected}
              className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-sm font-medium transition-all border border-red-500/30 whitespace-nowrap cursor-pointer"
            >
              <i className="ri-stop-circle-line mr-2"></i>
              Parar ({selectedProcesses.length})
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="text-xs text-purple-300 mb-2 block">Pesquisar</label>
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Nome do processo..."
            className="w-full px-3 py-2 bg-purple-900/50 border border-purple-500/20 rounded-lg text-sm text-white placeholder-purple-400 focus:outline-none focus:border-purple-500/50"
          />
        </div>

        <div>
          <label className="text-xs text-purple-300 mb-2 block">Tipo</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as any)}
            className="w-full px-3 py-2 bg-purple-900/50 border border-purple-500/20 rounded-lg text-sm text-white focus:outline-none focus:border-purple-500/50 cursor-pointer"
          >
            <option value="all">Todos</option>
            <option value="core">Core</option>
            <option value="service">Serviços</option>
            <option value="ai">IA</option>
            <option value="integration">Integrações</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-purple-300 mb-2 block">Status</label>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as any)}
            className="w-full px-3 py-2 bg-purple-900/50 border border-purple-500/20 rounded-lg text-sm text-white focus:outline-none focus:border-purple-500/50 cursor-pointer"
          >
            <option value="all">Todos</option>
            <option value="running">Ativos</option>
            <option value="stopped">Parados</option>
            <option value="error">Erros</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-purple-300 mb-2 block">Ordenar por</label>
          <div className="flex gap-2">
            <button
              onClick={() => setSortBy('cpu')}
              className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
                sortBy === 'cpu'
                  ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white'
                  : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
              }`}
            >
              CPU
            </button>
            <button
              onClick={() => setSortBy('memory')}
              className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
                sortBy === 'memory'
                  ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white'
                  : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
              }`}
            >
              RAM
            </button>
            <button
              onClick={() => setSortBy('name')}
              className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
                sortBy === 'name'
                  ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white'
                  : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
              }`}
            >
              Nome
            </button>
          </div>
        </div>
      </div>

      {/* Process Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-purple-500/20">
              <th className="text-left text-xs font-medium text-purple-300 pb-3 pl-3">
                <input
                  type="checkbox"
                  checked={selectedProcesses.length === sortedProcesses.length && sortedProcesses.length > 0}
                  onChange={handleSelectAllVisible}
                  className="w-4 h-4 rounded bg-purple-900/50 border-purple-500/30 text-purple-500 focus:ring-purple-500 cursor-pointer"
                />
              </th>
              <th className="text-left text-xs font-medium text-purple-300 pb-3">PID</th>
              <th className="text-left text-xs font-medium text-purple-300 pb-3">Processo</th>
              <th className="text-left text-xs font-medium text-purple-300 pb-3">Tipo</th>
              <th className="text-left text-xs font-medium text-purple-300 pb-3">CPU</th>
              <th className="text-left text-xs font-medium text-purple-300 pb-3">Memória</th>
              <th className="text-left text-xs font-medium text-purple-300 pb-3">Status</th>
              <th className="text-left text-xs font-medium text-purple-300 pb-3">Uptime</th>
              <th className="text-left text-xs font-medium text-purple-300 pb-3">Auto-Start</th>
              <th className="text-right text-xs font-medium text-purple-300 pb-3 pr-3">Ações</th>
            </tr>
          </thead>
          <tbody>
            {sortedProcesses.map((process) => (
              <tr key={process.pid} className="border-b border-purple-500/10 hover:bg-purple-900/20 transition-colors">
                <td className="py-3 pl-3">
                  <input
                    type="checkbox"
                    checked={selectedProcesses.includes(process.pid)}
                    onChange={() => handleSelectProcess(process.pid)}
                    className="w-4 h-4 rounded bg-purple-900/50 border-purple-500/30 text-purple-500 focus:ring-purple-500 cursor-pointer"
                  />
                </td>
                <td className="py-3 text-sm text-purple-300 font-mono">{process.pid}</td>
                <td className="py-3">
                  <div>
                    <p className="text-sm text-white font-medium">{process.name}</p>
                    <p className="text-xs text-purple-400 font-mono truncate max-w-xs">{process.path}</p>
                  </div>
                </td>
                <td className="py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getTypeColor(process.type)}`}>
                    {getTypeLabel(process.type)}
                  </span>
                </td>
                <td className="py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-16 bg-purple-900/50 rounded-full h-1.5">
                      <div 
                        className="bg-gradient-to-r from-orange-500 to-red-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(process.cpu, 100)}%` }}
                      ></div>
                    </div>
                    <span className="text-xs text-white font-mono">{process.cpu}%</span>
                  </div>
                </td>
                <td className="py-3 text-sm text-white font-mono">{process.memory} MB</td>
                <td className="py-3">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${
                      process.status === 'running' ? 'bg-green-400 animate-pulse' :
                      process.status === 'error' ? 'bg-red-400 animate-pulse' :
                      'bg-slate-400'
                    }`}></div>
                    <span className={`text-xs font-medium ${
                      process.status === 'running' ? 'text-green-400' :
                      process.status === 'error' ? 'text-red-400' :
                      'text-slate-400'
                    }`}>
                      {process.status === 'running' ? 'Ativo' : process.status === 'error' ? 'Erro' : 'Parado'}
                    </span>
                  </div>
                </td>
                <td className="py-3 text-sm text-purple-300">{process.uptime}</td>
                <td className="py-3">
                  <button
                    onClick={() => handleToggleAutoStart(process.pid)}
                    className={`w-10 h-5 rounded-full transition-all cursor-pointer ${
                      process.autoStart ? 'bg-green-500' : 'bg-slate-600'
                    }`}
                  >
                    <div className={`w-4 h-4 bg-white rounded-full transition-transform ${
                      process.autoStart ? 'translate-x-5' : 'translate-x-0.5'
                    }`}></div>
                  </button>
                </td>
                <td className="py-3 text-right pr-3">
                  <div className="flex items-center justify-end gap-2">
                    {process.status === 'stopped' || process.status === 'error' ? (
                      <button 
                        onClick={() => handleStartProcess(process.pid)}
                        className="w-8 h-8 flex items-center justify-center bg-green-500/10 hover:bg-green-500/20 text-green-400 rounded-lg transition-all cursor-pointer" 
                        title="Iniciar"
                      >
                        <i className="ri-play-circle-line text-sm"></i>
                      </button>
                    ) : (
                      <>
                        <button 
                          onClick={() => handleRestartProcess(process.pid)}
                          className="w-8 h-8 flex items-center justify-center bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg transition-all cursor-pointer" 
                          title="Reiniciar"
                        >
                          <i className="ri-restart-line text-sm"></i>
                        </button>
                        <button 
                          onClick={() => handleStopProcess(process.pid)}
                          className="w-8 h-8 flex items-center justify-center bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg transition-all cursor-pointer" 
                          title="Parar"
                        >
                          <i className="ri-stop-circle-line text-sm"></i>
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sortedProcesses.length === 0 && (
        <div className="text-center py-12">
          <i className="ri-file-search-line text-6xl text-purple-500/30 mb-4"></i>
          <p className="text-purple-300">Nenhum processo encontrado com os filtros aplicados.</p>
        </div>
      )}
    </div>
  );
}
