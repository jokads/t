import { useEffect, useState } from 'react';

interface EnvironmentStatus {
  frontend: boolean;
  backend: boolean;
  pythonCore: boolean;
  basePath: string;
  modelsPath: string;
  availableModels: number;
}

interface SystemStatusProps {
  environment: EnvironmentStatus;
  showDetailedResources?: boolean;
}

interface SystemMetrics {
  cpu: {
    usage: number;
    cores: number;
    temperature: number;
  };
  memory: {
    used: number;
    total: number;
    percentage: number;
  };
  disk: {
    used: number;
    total: number;
    percentage: number;
  };
  network: {
    download: number;
    upload: number;
    connections: number;
  };
  uptime: number;
  hostname: string;
  platform: string;
  pythonVersion: string;
  nodeVersion: string;
}

export default function SystemStatus({ environment, showDetailedResources = false }: SystemStatusProps) {
  const [metrics, setMetrics] = useState<SystemMetrics>({
    cpu: { usage: 23, cores: 8, temperature: 56 },
    memory: { used: 4.2, total: 16, percentage: 26 },
    disk: { used: 245, total: 500, percentage: 49 },
    network: { download: 2.3, upload: 0.8, connections: 12 },
    uptime: 0,
    hostname: 'TRADING-SERVER-01',
    platform: 'Windows 11 Pro',
    pythonVersion: '3.11.5',
    nodeVersion: '20.10.0'
  });

  const [processes, setProcesses] = useState([
    { name: 'trading_bot_core.py', status: 'running', pid: 12345, cpu: 15.3, memory: 234 },
    { name: 'dashboard_server.py', status: 'running', pid: 12346, cpu: 8.7, memory: 156 },
    { name: 'ai_manager.py', status: 'running', pid: 12347, cpu: 23.1, memory: 512 },
    { name: 'mt5_communication.py', status: 'running', pid: 12348, cpu: 5.2, memory: 89 },
    { name: 'strategy_engine.py', status: 'running', pid: 12349, cpu: 12.4, memory: 178 },
    { name: 'risk_manager.py', status: 'running', pid: 12350, cpu: 3.8, memory: 67 }
  ]);

  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(prev => ({
        ...prev,
        cpu: {
          ...prev.cpu,
          usage: Math.floor(Math.random() * 30) + 15,
          temperature: Math.floor(Math.random() * 10) + 52
        },
        memory: {
          ...prev.memory,
          percentage: Math.floor(Math.random() * 20) + 20
        },
        network: {
          ...prev.network,
          download: parseFloat((Math.random() * 5).toFixed(1)),
          upload: parseFloat((Math.random() * 2).toFixed(1))
        },
        uptime: prev.uptime + 1
      }));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    return `${hours}h ${minutes}m ${secs}s`;
  };

  const formatBytes = (gb: number) => {
    return `${gb.toFixed(1)} GB`;
  };

  if (showDetailedResources) {
    return (
      <div className="space-y-6">
        {/* CPU Details */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold gradient-text mb-6 flex items-center gap-2">
            <i className="ri-cpu-line text-xl"></i>
            CPU - Processador
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Utilização</p>
              <p className="text-3xl font-bold text-white mb-3">{metrics.cpu.usage}%</p>
              <div className="w-full bg-purple-900/50 rounded-full h-2">
                <div 
                  className="bg-gradient-to-r from-orange-500 to-red-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${metrics.cpu.usage}%` }}
                ></div>
              </div>
            </div>
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Núcleos</p>
              <p className="text-3xl font-bold text-white mb-3">{metrics.cpu.cores}</p>
              <p className="text-xs text-purple-300">Threads Disponíveis</p>
            </div>
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Temperatura</p>
              <p className="text-3xl font-bold text-white mb-3">{metrics.cpu.temperature}°C</p>
              <div className={`text-xs font-medium ${metrics.cpu.temperature > 70 ? 'text-red-400' : metrics.cpu.temperature > 60 ? 'text-yellow-400' : 'text-green-400'}`}>
                {metrics.cpu.temperature > 70 ? '🔥 Alta' : metrics.cpu.temperature > 60 ? '⚠️ Normal' : '✅ Ótima'}
              </div>
            </div>
          </div>
        </div>

        {/* Memory Details */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold gradient-text mb-6 flex items-center gap-2">
            <i className="ri-database-2-line text-xl"></i>
            Memória RAM
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Utilização</p>
              <p className="text-3xl font-bold text-white mb-3">{metrics.memory.percentage}%</p>
              <div className="w-full bg-purple-900/50 rounded-full h-2">
                <div 
                  className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${metrics.memory.percentage}%` }}
                ></div>
              </div>
            </div>
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Usada</p>
              <p className="text-3xl font-bold text-white mb-3">{formatBytes(metrics.memory.used)}</p>
              <p className="text-xs text-purple-300">de {formatBytes(metrics.memory.total)}</p>
            </div>
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Disponível</p>
              <p className="text-3xl font-bold text-white mb-3">{formatBytes(metrics.memory.total - metrics.memory.used)}</p>
              <p className="text-xs text-green-400">Livre para uso</p>
            </div>
          </div>
        </div>

        {/* Disk Details */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold gradient-text mb-6 flex items-center gap-2">
            <i className="ri-hard-drive-line text-xl"></i>
            Armazenamento em Disco
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Utilização</p>
              <p className="text-3xl font-bold text-white mb-3">{metrics.disk.percentage}%</p>
              <div className="w-full bg-purple-900/50 rounded-full h-2">
                <div 
                  className="bg-gradient-to-r from-cyan-500 to-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${metrics.disk.percentage}%` }}
                ></div>
              </div>
            </div>
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Usado</p>
              <p className="text-3xl font-bold text-white mb-3">{formatBytes(metrics.disk.used)}</p>
              <p className="text-xs text-purple-300">de {formatBytes(metrics.disk.total)}</p>
            </div>
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Livre</p>
              <p className="text-3xl font-bold text-white mb-3">{formatBytes(metrics.disk.total - metrics.disk.used)}</p>
              <p className="text-xs text-green-400">Espaço disponível</p>
            </div>
          </div>
        </div>

        {/* Network Details */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold gradient-text mb-6 flex items-center gap-2">
            <i className="ri-global-line text-xl"></i>
            Rede & Conexões
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Download</p>
              <p className="text-3xl font-bold text-green-400 mb-3">{metrics.network.download}</p>
              <p className="text-xs text-purple-300">MB/s</p>
            </div>
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Upload</p>
              <p className="text-3xl font-bold text-orange-400 mb-3">{metrics.network.upload}</p>
              <p className="text-xs text-purple-300">MB/s</p>
            </div>
            <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
              <p className="text-xs text-purple-300 mb-2">Conexões Ativas</p>
              <p className="text-3xl font-bold text-cyan-400 mb-3">{metrics.network.connections}</p>
              <p className="text-xs text-purple-300">TCP/UDP</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold gradient-text mb-6">Visão Geral do Sistema</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Uptime */}
        <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center">
              <i className="ri-time-line text-white text-xl"></i>
            </div>
            <div>
              <p className="text-xs text-purple-300">Uptime</p>
              <p className="text-lg font-bold text-white">{formatUptime(metrics.uptime)}</p>
            </div>
          </div>
        </div>

        {/* CPU Usage */}
        <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center">
              <i className="ri-cpu-line text-white text-xl"></i>
            </div>
            <div>
              <p className="text-xs text-purple-300">CPU ({metrics.cpu.cores} cores)</p>
              <p className="text-lg font-bold text-white">{metrics.cpu.usage}%</p>
            </div>
          </div>
          <div className="w-full bg-purple-900/50 rounded-full h-2">
            <div 
              className="bg-gradient-to-r from-orange-500 to-red-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${metrics.cpu.usage}%` }}
            ></div>
          </div>
        </div>

        {/* Memory Usage */}
        <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <i className="ri-database-2-line text-white text-xl"></i>
            </div>
            <div>
              <p className="text-xs text-purple-300">Memória RAM</p>
              <p className="text-lg font-bold text-white">{metrics.memory.percentage}%</p>
            </div>
          </div>
          <div className="w-full bg-purple-900/50 rounded-full h-2">
            <div 
              className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${metrics.memory.percentage}%` }}
            ></div>
          </div>
          <p className="text-xs text-purple-300 mt-2">{formatBytes(metrics.memory.used)} / {formatBytes(metrics.memory.total)}</p>
        </div>

        {/* Disk Usage */}
        <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
              <i className="ri-hard-drive-line text-white text-xl"></i>
            </div>
            <div>
              <p className="text-xs text-purple-300">Disco</p>
              <p className="text-lg font-bold text-white">{metrics.disk.percentage}%</p>
            </div>
          </div>
          <div className="w-full bg-purple-900/50 rounded-full h-2">
            <div 
              className="bg-gradient-to-r from-cyan-500 to-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${metrics.disk.percentage}%` }}
            ></div>
          </div>
          <p className="text-xs text-purple-300 mt-2">{formatBytes(metrics.disk.used)} / {formatBytes(metrics.disk.total)}</p>
        </div>
      </div>

      {/* Network & System Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
          <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <i className="ri-global-line text-cyan-400"></i>
            Rede
          </h4>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-purple-300">Download:</span>
              <span className="text-sm text-green-400 font-bold">{metrics.network.download} MB/s</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-purple-300">Upload:</span>
              <span className="text-sm text-orange-400 font-bold">{metrics.network.upload} MB/s</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-purple-300">Conexões Ativas:</span>
              <span className="text-sm text-cyan-400 font-bold">{metrics.network.connections}</span>
            </div>
          </div>
        </div>

        <div className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/20">
          <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <i className="ri-server-line text-purple-400"></i>
            Informações do Servidor
          </h4>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-purple-300">Hostname:</span>
              <span className="text-sm text-white font-mono">{metrics.hostname}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-purple-300">Plataforma:</span>
              <span className="text-sm text-white">{metrics.platform}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-purple-300">Python:</span>
              <span className="text-sm text-white font-mono">{metrics.pythonVersion}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-purple-300">Node.js:</span>
              <span className="text-sm text-white font-mono">{metrics.nodeVersion}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Active Processes */}
      <div className="pt-6 border-t border-purple-500/20">
        <h4 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-play-circle-line text-green-400"></i>
          Processos Ativos ({processes.filter(p => p.status === 'running').length}/{processes.length})
        </h4>
        <div className="space-y-2">
          {processes.map((process) => (
            <div key={process.pid} className="flex items-center justify-between p-3 bg-purple-900/20 rounded-lg border border-purple-500/10 hover:bg-purple-900/30 transition-all">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${process.status === 'running' ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
                <span className="text-sm text-white font-medium">{process.name}</span>
              </div>
              <div className="flex items-center gap-4 text-xs text-purple-300">
                <span>PID: {process.pid}</span>
                <span>CPU: {process.cpu}%</span>
                <span>RAM: {process.memory} MB</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
