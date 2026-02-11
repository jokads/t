import { useState, useEffect } from 'react';

interface AuditLog {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  details: string;
  ip: string;
  category: string;
  severity: string;
  aiAnalysis?: {
    summary: string;
    confidence: number;
    recommendations: string[];
  };
}

interface AuditLogsProps {
  environment: {
    frontend: boolean;
    backend: boolean;
    pythonCore: boolean;
    basePath: string;
    modelsPath: string;
  };
  aiModels: any[];
  selectedModels: string[];
  setSelectedModels: (models: string[]) => void;
}

export default function AuditLogs({ environment, aiModels, selectedModels, setSelectedModels }: AuditLogsProps) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [filteredLogs, setFilteredLogs] = useState<AuditLog[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [aiAssistance, setAiAssistance] = useState(true);
  const [autoMonitoring, setAutoMonitoring] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [stats, setStats] = useState({
    total: 0,
    success: 0,
    info: 0,
    warning: 0,
    error: 0
  });

  // Carregar logs em tempo real a cada 10s
  useEffect(() => {
    loadLogs();
    if (autoMonitoring) {
      const interval = setInterval(loadLogs, 10000);
      return () => clearInterval(interval);
    }
  }, [autoMonitoring, environment.backend]);

  // Filtrar logs quando mudar pesquisa ou filtros
  useEffect(() => {
    filterLogs();
  }, [logs, searchTerm, categoryFilter, severityFilter]);

  const loadLogs = async () => {
    try {
      if (environment.backend) {
        const response = await fetch('http://localhost:8000/api/audit/logs');
        if (response.ok) {
          const data = await response.json();
          setLogs(data.logs || []);
          setStats(data.stats || stats);
        }
      } else {
        // Dados mock quando backend offline
        const mockLogs: AuditLog[] = [
          {
            id: 'log-1',
            timestamp: new Date().toISOString(),
            user: 'damasclaudio2@gmail.com',
            action: 'Posição Aberta',
            details: 'EURUSD BUY 0.1 lotes @ 1.0950',
            ip: '192.168.1.100',
            category: 'trading',
            severity: 'info',
            aiAnalysis: {
              summary: 'Trade aberto em zona de suporte. Confluência positiva de indicadores.',
              confidence: 92,
              recommendations: ['Monitorar resistência em 1.1000', 'Considerar mover SL após +20 pips']
            }
          },
          {
            id: 'log-2',
            timestamp: new Date(Date.now() - 300000).toISOString(),
            user: 'damasclaudio2@gmail.com',
            action: 'Emergency Stop Ativado',
            details: 'Drawdown atingiu 70%. Trading interrompido.',
            ip: '192.168.1.100',
            category: 'security',
            severity: 'critical',
            aiAnalysis: {
              summary: 'Ação crítica. Sistema protegeu capital automaticamente.',
              confidence: 98,
              recommendations: ['Revisar estratégias antes de reativar', 'Analisar trades perdedores', 'Verificar condições de mercado']
            }
          },
          {
            id: 'log-3',
            timestamp: new Date(Date.now() - 600000).toISOString(),
            user: 'damasclaudio2@gmail.com',
            action: 'Estratégia Ativada',
            details: 'RSI Reversal Strategy iniciada',
            ip: '192.168.1.100',
            category: 'system',
            severity: 'info'
          },
          {
            id: 'log-4',
            timestamp: new Date(Date.now() - 900000).toISOString(),
            user: 'damasclaudio2@gmail.com',
            action: 'Configuração Alterada',
            details: 'Risco máximo por trade: 2% → 2.5%',
            ip: '192.168.1.100',
            category: 'config',
            severity: 'warning'
          },
          {
            id: 'log-5',
            timestamp: new Date(Date.now() - 1200000).toISOString(),
            user: 'damasclaudio2@gmail.com',
            action: 'Login',
            details: 'Login bem-sucedido',
            ip: '192.168.1.100',
            category: 'user',
            severity: 'success'
          }
        ];
        setLogs(mockLogs);
        setStats({
          total: 215,
          success: 142,
          info: 58,
          warning: 12,
          error: 3
        });
      }
    } catch (error) {
      console.log('Erro ao carregar logs:', error);
    }
  };

  const filterLogs = () => {
    let filtered = [...logs];

    // Filtro de pesquisa
    if (searchTerm) {
      filtered = filtered.filter(log => 
        log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.details.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.user.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Filtro de categoria
    if (categoryFilter !== 'all') {
      filtered = filtered.filter(log => log.category === categoryFilter);
    }

    // Filtro de severidade
    if (severityFilter !== 'all') {
      filtered = filtered.filter(log => log.severity === severityFilter);
    }

    setFilteredLogs(filtered);
  };

  const toggleModelSelection = (modelName: string) => {
    if (selectedModels.includes(modelName)) {
      setSelectedModels(selectedModels.filter(m => m !== modelName));
    } else {
      setSelectedModels([...selectedModels, modelName]);
    }
  };

  const analyzeAllLogs = async () => {
    if (!environment.backend) {
      alert('Backend offline. Inicie o backend para análise IA.');
      return;
    }
    if (selectedModels.length === 0) {
      alert('Selecione pelo menos um modelo IA para análise.');
      return;
    }

    setAnalyzing(true);
    try {
      const response = await fetch('http://localhost:8000/api/audit/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          models: selectedModels,
          logIds: filteredLogs.map(l => l.id)
        })
      });
      if (response.ok) {
        const data = await response.json();
        alert(`✅ Análise IA concluída!\n\n${data.analyzed} logs analisados\nModelos usados: ${selectedModels.length}`);
        loadLogs();
      }
    } catch (error) {
      console.error('Erro ao analisar:', error);
    } finally {
      setAnalyzing(false);
    }
  };

  const exportLogs = () => {
    const data = {
      timestamp: new Date().toISOString(),
      environment,
      stats,
      logs: filteredLogs,
      filters: { searchTerm, categoryFilter, severityFilter }
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-logs-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'success': return 'text-green-400 bg-green-500/20 border-green-500/30';
      case 'info': return 'text-cyan-400 bg-cyan-500/20 border-cyan-500/30';
      case 'warning': return 'text-orange-400 bg-orange-500/20 border-orange-500/30';
      case 'error': return 'text-red-400 bg-red-500/20 border-red-500/30';
      case 'critical': return 'text-red-400 bg-red-500/30 border-red-500/50';
      default: return 'text-purple-400 bg-purple-500/20 border-purple-500/30';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'success': return 'ri-checkbox-circle-line';
      case 'info': return 'ri-information-line';
      case 'warning': return 'ri-alert-line';
      case 'error': return 'ri-error-warning-line';
      case 'critical': return 'ri-alarm-warning-line';
      default: return 'ri-record-circle-line';
    }
  };

  const getTimeAgo = (timestamp: string) => {
    const seconds = Math.floor((new Date().getTime() - new Date(timestamp).getTime()) / 1000);
    if (seconds < 60) return 'Agora';
    if (seconds < 3600) return `Há ${Math.floor(seconds / 60)} min`;
    if (seconds < 86400) return `Há ${Math.floor(seconds / 3600)} horas`;
    return `Há ${Math.floor(seconds / 86400)} dias`;
  };

  return (
    <div className="space-y-6">
      {/* Estatísticas */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <i className="ri-file-list-line text-purple-400 text-xl"></i>
            <span className="text-2xl font-bold text-white">{stats.total}</span>
          </div>
          <div className="text-xs text-purple-300">Total</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <i className="ri-checkbox-circle-line text-green-400 text-xl"></i>
            <span className="text-2xl font-bold text-green-400">{stats.success}</span>
          </div>
          <div className="text-xs text-green-300">Sucessos</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <i className="ri-information-line text-cyan-400 text-xl"></i>
            <span className="text-2xl font-bold text-cyan-400">{stats.info}</span>
          </div>
          <div className="text-xs text-cyan-300">Infos</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <i className="ri-alert-line text-orange-400 text-xl"></i>
            <span className="text-2xl font-bold text-orange-400">{stats.warning}</span>
          </div>
          <div className="text-xs text-orange-300">Avisos</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <i className="ri-error-warning-line text-red-400 text-xl"></i>
            <span className="text-2xl font-bold text-red-400">{stats.error}</span>
          </div>
          <div className="text-xs text-red-300">Erros</div>
        </div>
      </div>

      {/* Configuração de IA */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-robot-line text-cyan-400"></i>
          Configuração de IA para Auditoria
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <label className="flex items-center justify-between p-3 glass-effect rounded-lg cursor-pointer hover:bg-purple-500/10 transition-all">
            <div className="flex items-center gap-3">
              <i className="ri-brain-line text-purple-400"></i>
              <div>
                <div className="text-sm text-white font-medium">Assistência IA</div>
                <div className="text-xs text-purple-300">Análise automática de logs</div>
              </div>
            </div>
            <input 
              type="checkbox" 
              checked={aiAssistance}
              onChange={(e) => setAiAssistance(e.target.checked)}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-purple-500 focus:ring-2 focus:ring-purple-500 cursor-pointer" 
            />
          </label>
          <label className="flex items-center justify-between p-3 glass-effect rounded-lg cursor-pointer hover:bg-purple-500/10 transition-all">
            <div className="flex items-center gap-3">
              <i className="ri-eye-line text-cyan-400"></i>
              <div>
                <div className="text-sm text-white font-medium">Auto-Monitoramento</div>
                <div className="text-xs text-purple-300">Atualiza a cada 10 segundos</div>
              </div>
            </div>
            <input 
              type="checkbox" 
              checked={autoMonitoring}
              onChange={(e) => setAutoMonitoring(e.target.checked)}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-cyan-500 focus:ring-2 focus:ring-cyan-500 cursor-pointer" 
            />
          </label>
        </div>

        {aiModels.length > 0 && (
          <div>
            <div className="text-sm text-purple-300 mb-3 flex items-center justify-between">
              <span>Modelos IA Ativos ({selectedModels.length} selecionados)</span>
              <button
                onClick={analyzeAllLogs}
                disabled={!environment.backend || selectedModels.length === 0 || analyzing}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-purple-500/30 whitespace-nowrap cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {analyzing ? (
                  <span className="flex items-center gap-2">
                    <i className="ri-loader-4-line animate-spin"></i>
                    Analisando...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <i className="ri-magic-line"></i>
                    Analisar Todos
                  </span>
                )}
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {aiModels.map((model) => (
                <label
                  key={model.name}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedModels.includes(model.name)
                      ? 'bg-purple-500/20 border-purple-500'
                      : 'bg-black/20 border-purple-500/30 hover:border-purple-500/50'
                  }`}
                  onClick={() => toggleModelSelection(model.name)}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={selectedModels.includes(model.name)}
                      onChange={() => {}}
                      className="mt-0.5 w-4 h-4 rounded border-purple-600 bg-black/30 text-purple-500 cursor-pointer"
                    />
                    <div className="flex-1">
                      <div className="text-sm text-white font-medium flex items-center gap-2">
                        {model.name}
                        {model.recommended && <span className="text-xs">✨</span>}
                      </div>
                      <div className="text-xs text-purple-400 mt-1">{model.size}</div>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Filtros e Pesquisa */}
      <div className="card p-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Pesquisar logs..."
                className="w-full px-4 py-2 pl-10 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
              <i className="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-purple-400"></i>
            </div>
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          >
            <option value="all">Todas Categorias</option>
            <option value="trading">Trading</option>
            <option value="system">Sistema</option>
            <option value="security">Segurança</option>
            <option value="user">Utilizador</option>
            <option value="config">Configuração</option>
          </select>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          >
            <option value="all">Todas Severidades</option>
            <option value="success">Sucesso</option>
            <option value="info">Info</option>
            <option value="warning">Aviso</option>
            <option value="error">Erro</option>
            <option value="critical">Crítico</option>
          </select>
          <button
            onClick={exportLogs}
            className="px-4 py-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg text-sm font-medium transition-all border border-purple-500/30 whitespace-nowrap cursor-pointer flex items-center gap-2"
          >
            <i className="ri-download-line"></i>
            Exportar
          </button>
        </div>
      </div>

      {/* Lista de Logs */}
      <div className="space-y-3">
        {filteredLogs.length === 0 ? (
          <div className="card p-8 text-center">
            <i className="ri-file-list-line text-purple-400 text-4xl mb-3"></i>
            <p className="text-purple-300">Nenhum log encontrado</p>
            <p className="text-xs text-purple-400 mt-1">Ajuste os filtros ou aguarde novos logs</p>
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} className="card p-4 hover:bg-purple-500/5 transition-all">
              <div className="flex items-start gap-4">
                <div className={`p-2 rounded-lg ${getSeverityColor(log.severity)}`}>
                  <i className={`${getSeverityIcon(log.severity)} text-lg`}></i>
                </div>
                <div className="flex-1">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <span className="text-sm font-semibold text-white">{log.action}</span>
                        <span className="text-xs text-purple-400">{getTimeAgo(log.timestamp)}</span>
                      </div>
                      <p className="text-sm text-purple-200">{log.details}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-purple-400">
                        <span className="flex items-center gap-1">
                          <i className="ri-user-line"></i>
                          {log.user}
                        </span>
                        <span className="flex items-center gap-1">
                          <i className="ri-map-pin-line"></i>
                          {log.ip}
                        </span>
                        <span className={`px-2 py-0.5 rounded ${getSeverityColor(log.severity)}`}>
                          {log.category}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  {log.aiAnalysis && aiAssistance && (
                    <div className="mt-3 bg-purple-500/10 border border-purple-500/30 rounded-lg p-3">
                      <div className="flex items-start gap-2 mb-2">
                        <i className="ri-robot-line text-purple-400 text-lg"></i>
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-purple-300">Análise IA</span>
                            <span className="text-xs text-purple-400">Confiança: {log.aiAnalysis.confidence}%</span>
                          </div>
                          <p className="text-sm text-purple-200 mb-2">{log.aiAnalysis.summary}</p>
                          {log.aiAnalysis.recommendations.length > 0 && (
                            <div>
                              <div className="text-xs font-medium text-purple-300 mb-1">💡 Recomendações:</div>
                              <ul className="space-y-1">
                                {log.aiAnalysis.recommendations.map((rec, idx) => (
                                  <li key={idx} className="text-xs text-purple-200 flex items-start gap-2">
                                    <span className="text-purple-400">•</span>
                                    <span>{rec}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Paginação */}
      {filteredLogs.length > 10 && (
        <div className="card p-4 flex items-center justify-between">
          <span className="text-sm text-purple-400">
            Mostrando {Math.min(currentPage * 10, filteredLogs.length)} de {filteredLogs.length} logs
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="px-3 py-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg text-sm transition-all border border-purple-500/30 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              Anterior
            </button>
            <button
              onClick={() => setCurrentPage(currentPage + 1)}
              disabled={currentPage * 10 >= filteredLogs.length}
              className="px-3 py-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg text-sm transition-all border border-purple-500/30 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              Próxima
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
