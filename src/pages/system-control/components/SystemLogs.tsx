import { useState, useEffect, useRef } from 'react';

interface EnvironmentStatus {
  frontend: boolean;
  backend: boolean;
  pythonCore: boolean;
  basePath: string;
  modelsPath: string;
  availableModels: number;
}

interface SystemLogsProps {
  environment: EnvironmentStatus;
}

interface LogEntry {
  id: number;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success' | 'critical';
  category: 'system' | 'trading' | 'api' | 'ai' | 'security';
  source: string;
  message: string;
  details?: string;
  aiAnalysis?: {
    summary: string;
    confidence: number;
    recommendations: string[];
  };
}

export default function SystemLogs({ environment }: SystemLogsProps) {
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: 1, timestamp: '14:32:45', level: 'success', category: 'system', source: 'trading_bot_core.py', message: 'Trading bot iniciado com sucesso', details: 'Sistema operacional e conectado' },
    { id: 2, timestamp: '14:32:46', level: 'info', category: 'system', source: 'mt5_communication.py', message: 'Conectado ao MT5 via socket', details: 'Socket.IO estabelecido na porta 8765' },
    { id: 3, timestamp: '14:32:47', level: 'success', category: 'ai', source: 'ai_manager.py', message: 'AI Manager carregou 6 modelos', details: 'Llama 3.2 3B, Nous Hermes 2 Mistral 7B, e mais 4 modelos' },
    { id: 4, timestamp: '14:32:48', level: 'success', category: 'system', source: 'dashboard_server.py', message: 'Dashboard server ativo na porta 5000', details: 'Flask rodando em modo produção' },
    { id: 5, timestamp: '14:33:12', level: 'warning', category: 'api', source: 'news_api_manager.py', message: 'News API latência alta: 567ms', details: 'Timeout em 3 tentativas, usando cache', aiAnalysis: { summary: 'API respondendo lentamente mas funcional', confidence: 85, recommendations: ['Verificar conexão de rede', 'Considerar cache local'] } },
    { id: 6, timestamp: '14:33:45', level: 'info', category: 'trading', source: 'strategy_engine.py', message: 'Nova posição aberta: EURUSD BUY 0.5 lotes', details: 'Entry: 1.0950, SL: 1.0900, TP: 1.1000' },
    { id: 7, timestamp: '14:34:12', level: 'success', category: 'api', source: 'telegram_handler.py', message: 'Mensagem enviada ao Telegram com sucesso', details: 'Notificação de trade enviada ao chat 7343664374' },
    { id: 8, timestamp: '14:35:23', level: 'warning', category: 'security', source: 'risk_manager.py', message: 'Drawdown atingiu 65% do limite', details: 'Perda atual: $650 de $1000 limite diário', aiAnalysis: { summary: 'Risco elevado mas ainda controlado', confidence: 92, recommendations: ['Reduzir tamanho de posições', 'Revisar estratégias ativas', 'Monitorar próximo trade'] } },
    { id: 9, timestamp: '14:36:01', level: 'error', category: 'system', source: 'mt5_communication.py', message: 'Conexão MT5 perdida temporariamente', details: 'Tentando reconectar... (tentativa 1/5)', aiAnalysis: { summary: 'Problema de rede temporário', confidence: 78, recommendations: ['Verificar terminal MT5', 'Checar conexão de internet', 'Reiniciar socket se persistir'] } },
    { id: 10, timestamp: '14:36:03', level: 'success', category: 'system', source: 'mt5_communication.py', message: 'Reconectado ao MT5 com sucesso', details: 'Conexão restabelecida, sincronizando posições' },
    { id: 11, timestamp: '14:37:15', level: 'critical', category: 'security', source: 'risk_manager.py', message: 'Emergency Stop ativado!', details: 'Drawdown atingiu 80% - Trading interrompido', aiAnalysis: { summary: 'Proteção de capital ativada automaticamente', confidence: 98, recommendations: ['Analisar trades perdedores antes de reativar', 'Revisar todas as estratégias', 'Verificar condições de mercado'] } },
    { id: 12, timestamp: '14:38:22', level: 'info', category: 'ai', source: 'adaptive_ml.py', message: 'Modelo ML retreinado com novos dados', details: '250 trades analisados, acurácia: 68%' },
    { id: 13, timestamp: '14:39:01', level: 'success', category: 'trading', source: 'strategy_engine.py', message: 'Posição fechada: EURUSD BUY - Lucro +25 USD', details: 'Duração: 5min 16s, ROI: +0.25%' },
    { id: 14, timestamp: '14:40:15', level: 'warning', category: 'ai', source: 'ai_manager.py', message: 'Modelo Orca Mini 3B com alta utilização de RAM', details: 'Usando 1.2GB de 1.8GB limite', aiAnalysis: { summary: 'Modelo próximo do limite de memória', confidence: 88, recommendations: ['Monitorar uso de RAM', 'Considerar descarregar se não usado', 'Limpar cache do modelo'] } },
    { id: 15, timestamp: '14:41:33', level: 'info', category: 'system', source: 'trading_bot_core.py', message: 'Uptime: 2h 30m - Sistema estável', details: 'CPU: 18%, RAM: 24%, Trades: 12' }
  ]);

  const [autoScroll, setAutoScroll] = useState(true);
  const [filterLevel, setFilterLevel] = useState<'all' | 'info' | 'warning' | 'error' | 'success' | 'critical'>('all');
  const [filterCategory, setFilterCategory] = useState<'all' | 'system' | 'trading' | 'api' | 'ai' | 'security'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [showAIAnalysis, setShowAIAnalysis] = useState(true);
  const [selectedAIModels, setSelectedAIModels] = useState<string[]>(['llama-3.2-3b', 'nous-hermes-2-mistral-7b']);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const aiModels = [
    { id: 'llama-3.2-1b', name: 'Llama 3.2 1B', size: '1.2GB', recommended: false },
    { id: 'llama-3.2-3b', name: 'Llama 3.2 3B', size: '2.0GB', recommended: true },
    { id: 'nous-hermes-2-mistral-7b', name: 'Nous Hermes 2 Mistral 7B', size: '4.1GB', recommended: true },
    { id: 'orca-mini-3b', name: 'Orca Mini 3B', size: '1.8GB', recommended: false },
    { id: 'phi-3-mini-4k', name: 'Phi-3 Mini 4K', size: '2.3GB', recommended: false },
    { id: 'qwen2-1.5b', name: 'Qwen2 1.5B', size: '1.0GB', recommended: false }
  ];

  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Simulate new logs
  useEffect(() => {
    const interval = setInterval(() => {
      const newLog: LogEntry = {
        id: logs.length + 1,
        timestamp: new Date().toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        level: ['info', 'success', 'warning'][Math.floor(Math.random() * 3)] as any,
        category: ['system', 'trading', 'api'][Math.floor(Math.random() * 3)] as any,
        source: 'trading_bot_core.py',
        message: 'Sistema operacional - Monitoramento ativo',
        details: `CPU: ${Math.floor(Math.random() * 30 + 10)}%, RAM: ${Math.floor(Math.random() * 20 + 15)}%`
      };
      setLogs(prev => [...prev, newLog]);
    }, 15000);
    return () => clearInterval(interval);
  }, [logs.length]);

  const filteredLogs = logs.filter(log => {
    if (filterLevel !== 'all' && log.level !== filterLevel) return false;
    if (filterCategory !== 'all' && log.category !== filterCategory) return false;
    if (searchTerm && !log.message.toLowerCase().includes(searchTerm.toLowerCase()) && !log.source.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'success': return 'text-green-400 bg-green-500/20 border-green-500/30';
      case 'info': return 'text-cyan-400 bg-cyan-500/20 border-cyan-500/30';
      case 'warning': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30';
      case 'error': return 'text-red-400 bg-red-500/20 border-red-500/30';
      case 'critical': return 'text-red-500 bg-red-500/30 border-red-500/50';
      default: return 'text-purple-300 bg-purple-500/20 border-purple-500/30';
    }
  };

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'success': return 'ri-checkbox-circle-line';
      case 'info': return 'ri-information-line';
      case 'warning': return 'ri-error-warning-line';
      case 'error': return 'ri-close-circle-line';
      case 'critical': return 'ri-alert-line';
      default: return 'ri-record-circle-line';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'system': return 'ri-server-line';
      case 'trading': return 'ri-line-chart-line';
      case 'api': return 'ri-plug-line';
      case 'ai': return 'ri-brain-line';
      case 'security': return 'ri-shield-line';
      default: return 'ri-file-line';
    }
  };

  const handleAnalyzeWithAI = async (logId: number) => {
    // TODO: Integrar com backend para análise IA real
    const mockAnalysis = {
      summary: 'Análise automática gerada por múltiplos modelos IA',
      confidence: Math.floor(Math.random() * 30 + 70),
      recommendations: [
        'Recomendação 1 baseada no contexto do log',
        'Recomendação 2 para prevenção de problemas futuros',
        'Recomendação 3 para otimização do sistema'
      ]
    };

    setLogs(prev => prev.map(log => 
      log.id === logId ? { ...log, aiAnalysis: mockAnalysis } : log
    ));
  };

  const handleExportLogs = () => {
    const dataStr = JSON.stringify(filteredLogs, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const exportFileDefaultName = `system-logs-${new Date().toISOString().split('T')[0]}.json`;
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const handleClearLogs = () => {
    if (confirm('Tem certeza que deseja limpar todos os logs? Esta ação não pode ser desfeita.')) {
      setLogs([]);
    }
  };

  const toggleAIModel = (modelId: string) => {
    if (selectedAIModels.includes(modelId)) {
      setSelectedAIModels(selectedAIModels.filter(id => id !== modelId));
    } else {
      setSelectedAIModels([...selectedAIModels, modelId]);
    }
  };

  const infoCount = logs.filter(l => l.level === 'info').length;
  const successCount = logs.filter(l => l.level === 'success').length;
  const warningCount = logs.filter(l => l.level === 'warning').length;
  const errorCount = logs.filter(l => l.level === 'error').length;
  const criticalCount = logs.filter(l => l.level === 'critical').length;

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold gradient-text flex items-center gap-2">
            <i className="ri-file-list-line text-xl"></i>
            Logs do Sistema em Tempo Real
          </h3>
          <div className="flex items-center gap-4 mt-2 text-xs">
            <span className="text-cyan-400">Info: {infoCount}</span>
            <span className="text-green-400">Success: {successCount}</span>
            <span className="text-yellow-400">Warning: {warningCount}</span>
            <span className="text-red-400">Error: {errorCount}</span>
            <span className="text-red-500">Critical: {criticalCount}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAIAnalysis(!showAIAnalysis)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer flex items-center gap-2 ${
              showAIAnalysis 
                ? 'bg-gradient-to-r from-pink-500 to-purple-500 text-white' 
                : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
            }`}
          >
            <i className="ri-brain-line"></i>
            Análise IA
          </button>
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`w-10 h-10 flex items-center justify-center rounded-lg transition-all cursor-pointer ${
              autoScroll ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white' : 'bg-purple-800/50 text-purple-200'
            }`}
            title={autoScroll ? 'Auto-scroll ativo' : 'Auto-scroll desativado'}
          >
            <i className="ri-arrow-down-line text-sm"></i>
          </button>
          <button 
            onClick={handleClearLogs}
            className="w-10 h-10 flex items-center justify-center bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg transition-all cursor-pointer" 
            title="Limpar logs"
          >
            <i className="ri-delete-bin-line text-sm"></i>
          </button>
        </div>
      </div>

      {/* AI Configuration */}
      {showAIAnalysis && (
        <div className="mb-6 p-4 bg-purple-900/30 rounded-lg border border-purple-500/30">
          <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <i className="ri-brain-line text-pink-400"></i>
            Configuração de IA para Análise de Logs
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {aiModels.map(model => (
              <button
                key={model.id}
                onClick={() => toggleAIModel(model.id)}
                disabled={!environment.backend}
                className={`p-3 rounded-lg border-2 transition-all cursor-pointer text-left ${
                  selectedAIModels.includes(model.id)
                    ? 'bg-pink-500/20 border-pink-500/50'
                    : 'bg-purple-900/20 border-purple-500/20 hover:border-purple-500/40'
                } ${!environment.backend ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-white">{model.name}</span>
                  {model.recommended && <span className="text-xs">✨</span>}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-purple-300">{model.size}</span>
                  {selectedAIModels.includes(model.id) && (
                    <i className="ri-checkbox-circle-fill text-pink-400"></i>
                  )}
                </div>
              </button>
            ))}
          </div>
          <p className="text-xs text-purple-400 mt-3">
            {selectedAIModels.length} modelo(s) selecionado(s) • Os modelos marcados com ✨ são recomendados
          </p>
        </div>
      )}

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div>
          <label className="text-xs text-purple-300 mb-2 block">Pesquisar</label>
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Pesquisar logs..."
            className="w-full px-3 py-2 bg-purple-900/50 border border-purple-500/20 rounded-lg text-sm text-white placeholder-purple-400 focus:outline-none focus:border-purple-500/50"
          />
        </div>

        <div>
          <label className="text-xs text-purple-300 mb-2 block">Nível</label>
          <select
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value as any)}
            className="w-full px-3 py-2 bg-purple-900/50 border border-purple-500/20 rounded-lg text-sm text-white focus:outline-none focus:border-purple-500/50 cursor-pointer"
          >
            <option value="all">Todos os níveis</option>
            <option value="info">Info</option>
            <option value="success">Success</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="critical">Critical</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-purple-300 mb-2 block">Categoria</label>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value as any)}
            className="w-full px-3 py-2 bg-purple-900/50 border border-purple-500/20 rounded-lg text-sm text-white focus:outline-none focus:border-purple-500/50 cursor-pointer"
          >
            <option value="all">Todas as categorias</option>
            <option value="system">Sistema</option>
            <option value="trading">Trading</option>
            <option value="api">API</option>
            <option value="ai">IA</option>
            <option value="security">Segurança</option>
          </select>
        </div>
      </div>

      {/* Logs Display */}
      <div className="bg-black/40 rounded-lg p-4 h-96 overflow-y-auto font-mono text-xs border border-purple-500/20">
        {filteredLogs.map((log) => (
          <div key={log.id} className="mb-4 hover:bg-purple-900/20 p-2 rounded transition-all">
            <div className="flex items-start gap-3">
              <span className="text-purple-400 whitespace-nowrap">[{log.timestamp}]</span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium border whitespace-nowrap ${getLevelColor(log.level)}`}>
                {log.level.toUpperCase()}
              </span>
              <div className="flex items-center gap-2">
                <i className={`${getCategoryIcon(log.category)} text-purple-400`}></i>
                <span className="text-purple-300">{log.source}</span>
              </div>
            </div>
            <div className="ml-32 mt-1">
              <p className="text-white">{log.message}</p>
              {log.details && (
                <p className="text-purple-400 text-xs mt-1">{log.details}</p>
              )}
              
              {showAIAnalysis && log.aiAnalysis && (
                <div className="mt-2 p-3 bg-pink-500/10 border border-pink-500/30 rounded">
                  <div className="flex items-center gap-2 mb-2">
                    <i className="ri-brain-line text-pink-400"></i>
                    <span className="text-xs font-semibold text-pink-400">Análise IA (Confiança: {log.aiAnalysis.confidence}%)</span>
                  </div>
                  <p className="text-white text-xs mb-2">{log.aiAnalysis.summary}</p>
                  {log.aiAnalysis.recommendations.length > 0 && (
                    <div>
                      <p className="text-xs text-purple-300 mb-1">💡 Recomendações:</p>
                      <ul className="text-xs text-purple-200 space-y-1">
                        {log.aiAnalysis.recommendations.map((rec, i) => (
                          <li key={i} className="ml-3">• {rec}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {showAIAnalysis && !log.aiAnalysis && selectedAIModels.length > 0 && (
                <button
                  onClick={() => handleAnalyzeWithAI(log.id)}
                  disabled={!environment.backend}
                  className="mt-2 px-3 py-1 bg-pink-500/10 hover:bg-pink-500/20 text-pink-400 rounded text-xs border border-pink-500/30 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <i className="ri-brain-line mr-1"></i>
                  Analisar com IA
                </button>
              )}
            </div>
          </div>
        ))}
        <div ref={logsEndRef} />
      </div>

      {filteredLogs.length === 0 && (
        <div className="text-center py-8">
          <i className="ri-file-search-line text-4xl text-purple-500/30 mb-2"></i>
          <p className="text-purple-300 text-sm">Nenhum log encontrado com os filtros aplicados.</p>
        </div>
      )}

      <div className="mt-4 flex gap-2">
        <button 
          onClick={handleExportLogs}
          className="flex-1 px-4 py-2 bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer"
        >
          <i className="ri-download-line mr-2"></i>
          Exportar Logs ({filteredLogs.length})
        </button>
      </div>

      {!environment.backend && (
        <div className="mt-4 p-4 bg-orange-500/10 border border-orange-500/30 rounded-lg">
          <div className="flex items-start gap-3">
            <i className="ri-error-warning-line text-orange-400 text-xl"></i>
            <div>
              <p className="text-sm text-orange-400 font-semibold mb-1">Backend Offline</p>
              <p className="text-xs text-orange-300">
                A análise IA de logs requer o backend ativo. Inicie o dashboard_server.py para usar esta funcionalidade.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
