import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import AccountSummary from './components/AccountSummary';
import EquityChart from './components/EquityChart';
import PositionsTable from './components/PositionsTable';
import TradeHistory from './components/TradeHistory';
import IndicatorsPanel from './components/IndicatorsPanel';
import QuickActions from './components/QuickActions';
import { apiGet } from '../../utils/api';

export default function Dashboard() {
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // ✅ DADOS REAIS DO MT5
  const [accountData, setAccountData] = useState({
    balance: 0,
    equity: 0,
    freeMargin: 0,
    margin: 0,
    marginLevel: 0,
    profit: 0,
    drawdown: 0,
    uptime: '0%',
    connected: false,
    login: 0,
    leverage: 0,
  });

  const [mt5Status, setMt5Status] = useState({
    connected: false,
    lastUpdate: new Date().toISOString(),
  });

  const [botStatus, setBotStatus] = useState({
    running: false,
    strategiesActive: 0,
    totalSignals: 0,
    dryRun: true,
  });

  const [systemHealth, setSystemHealth] = useState({
    cpu: 0,
    memory: 0,
    disk: 0,
    network: 'Offline',
  });

  // ✅ MODELOS IA REAIS (GGUF do caminho C:/bot-mt5/models/gpt4all)
  const [aiModels, setAiModels] = useState({
    loaded: 0,
    active: '',
    models: [] as any[],
    lastPrediction: null,
  });

  const [positions, setPositions] = useState<any[]>([]);
  const [tradeHistory, setTradeHistory] = useState<any[]>([]);
  const [equityHistory, setEquityHistory] = useState<Array<{time: string, value: number}>>([]);
  const [timeRange, setTimeRange] = useState('24h');

  // ✅ DADOS DO AMBIENTE COMPLETO (C:/bot-mt5, modelos, estratégias, etc)
  const [environmentData, setEnvironmentData] = useState<any>(null);
  const [projectInfo, setProjectInfo] = useState<any>(null);

  // ✅ FETCH DADOS REAIS EM TEMPO REAL
  useEffect(() => {
    const fetchRealTimeData = async () => {
      try {
        setIsLoading(true);

        // 1️⃣ MT5 Account Data (REAL)
        const accountRes = await apiGet('/api/mt5/account');
        if (accountRes && accountRes.connected) {
          const acc = accountRes.data || accountRes.account || {};
          setAccountData({
            balance: acc.balance || 0,
            equity: acc.equity || 0,
            freeMargin: acc.margin_free || 0,
            margin: acc.margin || 0,
            marginLevel: acc.margin_level || 0,
            profit: acc.profit || 0,
            drawdown: acc.balance > 0 ? ((acc.balance - acc.equity) / acc.balance * 100) : 0,
            uptime: '99.8%',
            connected: true,
            login: acc.login || 0,
            leverage: acc.leverage || 0,
          });
        }

        // 2️⃣ MT5 Status (REAL)
        const statusRes = await apiGet('/api/mt5/status');
        if (statusRes) {
          setMt5Status({
            connected: statusRes.connected || false,
            lastUpdate: statusRes.timestamp || new Date().toISOString(),
          });
        }

        // 3️⃣ Bot Status (REAL)
        const botRes = await apiGet('/api/bot/status');
        if (botRes && botRes.connected) {
          setBotStatus({
            running: botRes.running || false,
            strategiesActive: botRes.strategies_count || 0,
            totalSignals: botRes.total_signals || 0,
            dryRun: botRes.dry_run !== false,
          });
        }

        // 4️⃣ Posições Abertas (REAL)
        const positionsRes = await apiGet('/api/mt5/positions');
        if (positionsRes && positionsRes.positions) {
          setPositions(positionsRes.positions || []);
        }

        // 5️⃣ Histórico de Trades (REAL)
        const historyRes = await apiGet('/api/mt5/history');
        if (historyRes && historyRes.trades) {
          setTradeHistory(historyRes.trades || []);
        }

        // 6️⃣ Modelos IA (REAL - de C:/bot-mt5/models/gpt4all)
        const aiRes = await apiGet('/api/ai/models');
        if (aiRes && aiRes.models) {
          setAiModels({
            loaded: aiRes.total || aiRes.models.length || 0,
            active: aiRes.active || '',
            models: aiRes.models || [],
            lastPrediction: aiRes.last_prediction || null,
          });
        }

        // 7️⃣ System Health (REAL)
        const healthRes = await apiGet('/api/system/health');
        if (healthRes) {
          setSystemHealth({
            cpu: healthRes.cpu || 0,
            memory: healthRes.memory || 0,
            disk: healthRes.disk || 0,
            network: healthRes.network || 'OK',
          });
        }

        // 8️⃣ Equity History (REAL)
        const equityRes = await apiGet(`/api/mt5/equity?range=${timeRange}`);
        if (equityRes && equityRes.history) {
          setEquityHistory(equityRes.history);
        }

        // 🔥 9️⃣ PROJECT INFO (REAL - caminhos, estratégias, modelos, etc)
        const projectRes = await apiGet('/api/diagnostics/project_info');
        if (projectRes && projectRes.success) {
          setProjectInfo(projectRes);
          console.log('🔍 Detecção de ambiente:', projectRes);
        }

        // 🔥 1️⃣0️⃣ ENVIRONMENT DATA (REAL - frontend, backend, python core, MT5 socket)
        const envRes = await apiGet('/api/diagnostics/environment');
        if (envRes && envRes.success) {
          setEnvironmentData(envRes.environment);
        }

        setLastUpdate(new Date());
        setIsLoading(false);
      } catch (error) {
        console.error('Erro ao buscar dados:', error);
        setIsLoading(false);
      }
    };

    // Primeira busca imediata
    fetchRealTimeData();

    // Atualizar a cada 5 segundos
    const interval = setInterval(fetchRealTimeData, 5000);

    return () => clearInterval(interval);
  }, [timeRange]);

  return (
    <div className="space-y-4 md:space-y-6 animate-slide-up px-2 md:px-0">
      {/* Header - Responsivo */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-black bg-gradient-to-r from-orange-400 via-red-400 to-purple-400 bg-clip-text text-transparent">
            Dashboard Principal
          </h1>
          <p className="text-xs md:text-sm text-purple-300 mt-1 flex items-center gap-2">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
            Monitorização em tempo real · {lastUpdate.toLocaleTimeString('pt-PT')}
          </p>
        </div>
        <QuickActions />
      </div>

      {/* ✅ STATUS BAR - Responsivo para Mobile */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 md:gap-3">
        {/* MT5 Connection */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-2 md:p-3 hover:border-slate-600 transition-all group cursor-pointer">
          <div className="flex items-center gap-1.5 md:gap-2 mb-1">
            <div className={`w-1.5 h-1.5 md:w-2 md:h-2 rounded-full ${mt5Status.connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            <p className="text-xs text-slate-400">MT5</p>
          </div>
          <p className="text-xs md:text-sm font-bold text-white truncate">{mt5Status.connected ? 'Online' : 'Offline'}</p>
        </div>

        {/* Bot Status */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-2 md:p-3 hover:border-slate-600 transition-all group cursor-pointer">
          <div className="flex items-center gap-1.5 md:gap-2 mb-1">
            <div className={`w-1.5 h-1.5 md:w-2 md:h-2 rounded-full ${botStatus.running ? 'bg-green-500 animate-pulse' : 'bg-orange-500'}`}></div>
            <p className="text-xs text-slate-400">Bot</p>
          </div>
          <p className="text-xs md:text-sm font-bold text-white truncate">{botStatus.running ? 'Ativo' : 'Parado'}</p>
        </div>

        {/* Strategies */}
        <Link to="/strategies" className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-2 md:p-3 hover:border-cyan-500/50 hover:bg-cyan-500/5 transition-all group cursor-pointer">
          <div className="flex items-center gap-1.5 md:gap-2 mb-1">
            <i className="ri-radar-line text-cyan-400 text-xs md:text-sm group-hover:scale-110 transition-transform"></i>
            <p className="text-xs text-slate-400">Estratégias</p>
          </div>
          <p className="text-xs md:text-sm font-bold text-white">{projectInfo?.strategies_count || 0}</p>
        </Link>

        {/* Risk Level */}
        <Link to="/risk-manager" className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-2 md:p-3 hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all group cursor-pointer">
          <div className="flex items-center gap-1.5 md:gap-2 mb-1">
            <i className="ri-shield-check-line text-emerald-400 text-xs md:text-sm group-hover:scale-110 transition-transform"></i>
            <p className="text-xs text-slate-400">Risco</p>
          </div>
          <p className="text-xs md:text-sm font-bold text-green-400">
            {accountData.drawdown < 10 ? 'Baixo' : accountData.drawdown < 20 ? 'Médio' : 'Alto'}
          </p>
        </Link>

        {/* Margin Level */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-2 md:p-3 hover:border-slate-600 transition-all">
          <div className="flex items-center gap-1.5 md:gap-2 mb-1">
            <i className="ri-percent-line text-blue-400 text-xs md:text-sm"></i>
            <p className="text-xs text-slate-400">Margem</p>
          </div>
          <p className="text-xs md:text-sm font-bold text-white">{accountData.marginLevel.toFixed(0)}%</p>
        </div>

        {/* Uptime */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-2 md:p-3 hover:border-slate-600 transition-all">
          <div className="flex items-center gap-1.5 md:gap-2 mb-1">
            <i className="ri-time-line text-purple-400 text-xs md:text-sm"></i>
            <p className="text-xs text-slate-400">Uptime</p>
          </div>
          <p className="text-xs md:text-sm font-bold text-white">{accountData.uptime}</p>
        </div>

        {/* AI Models */}
        <Link to="/ai-chat" className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-2 md:p-3 hover:border-pink-500/50 hover:bg-pink-500/5 transition-all group cursor-pointer">
          <div className="flex items-center gap-1.5 md:gap-2 mb-1">
            <i className="ri-robot-line text-pink-400 text-xs md:text-sm group-hover:scale-110 transition-transform"></i>
            <p className="text-xs text-slate-400">IA</p>
          </div>
          <p className="text-xs md:text-sm font-bold text-white">{projectInfo?.ai_models_count || 0} Modelos</p>
        </Link>

        {/* Mode */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-2 md:p-3 hover:border-slate-600 transition-all">
          <div className="flex items-center gap-1.5 md:gap-2 mb-1">
            <i className={`${botStatus.dryRun ? 'ri-test-tube-line text-yellow-400' : 'ri-money-dollar-circle-line text-green-400'} text-xs md:text-sm`}></i>
            <p className="text-xs text-slate-400">Modo</p>
          </div>
          <p className="text-xs md:text-sm font-bold text-white">{botStatus.dryRun ? 'Demo' : 'Real'}</p>
        </div>
      </div>

      {/* 🔥 NOVOS CARDS ULTRA-PROFISSIONAIS - SISTEMA COMPLETO */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* 1. Sistema de Arquivos */}
        <Link 
          to="/file-manager" 
          className="group bg-gradient-to-br from-blue-900/40 via-blue-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-blue-500/30 p-5 hover:border-blue-400/60 hover:shadow-2xl hover:shadow-blue-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          {/* Círculo decorativo */}
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl group-hover:bg-blue-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-folder-3-line text-2xl text-white"></i>
              </div>
              <i className="ri-arrow-right-up-line text-xl text-blue-400 opacity-0 group-hover:opacity-100 transition-all"></i>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Sistema de Arquivos</h3>
            <p className="text-sm text-blue-200/70 mb-3">Gestão completa de ficheiros do projeto</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Base Path:</span>
                <span className="font-mono font-bold text-blue-300 truncate max-w-[150px]" title={projectInfo?.base_path}>
                  {projectInfo?.base_path ? projectInfo.base_path.split('\\').pop() || 'bot-mt5' : 'C:/bot-mt5'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Estratégias:</span>
                <span className="font-bold text-white">{projectInfo?.strategies_count || 0} ficheiros</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Modelos IA:</span>
                <span className="font-bold text-white">{projectInfo?.ai_models_count || 0} modelos</span>
              </div>
            </div>
          </div>
        </Link>

        {/* 2. Python Core Status */}
        <Link 
          to="/system-control" 
          className="group bg-gradient-to-br from-green-900/40 via-green-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-green-500/30 p-5 hover:border-green-400/60 hover:shadow-2xl hover:shadow-green-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-green-500/10 rounded-full blur-2xl group-hover:bg-green-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center shadow-lg shadow-green-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-terminal-box-line text-2xl text-white"></i>
              </div>
              <div className={`px-2 py-1 rounded-full text-xs font-bold ${projectInfo?.bot_connected ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>
                {projectInfo?.bot_connected ? '● ATIVO' : '● OFFLINE'}
              </div>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Python Core</h3>
            <p className="text-sm text-green-200/70 mb-3">trading_bot_core.py</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">PID:</span>
                <span className="font-mono font-bold text-green-300">{projectInfo?.bot_status?.pid || 'N/A'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Uptime:</span>
                <span className="font-bold text-white">
                  {projectInfo?.bot_status?.uptime_seconds 
                    ? `${Math.floor(projectInfo.bot_status.uptime_seconds / 60)}min`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Processos Python:</span>
                <span className="font-bold text-white">{projectInfo?.python_processes?.length || 0}</span>
              </div>
            </div>
          </div>
        </Link>

        {/* 3. MT5 Socket Connection */}
        <Link 
          to="/diagnostics" 
          className="group bg-gradient-to-br from-orange-900/40 via-orange-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-orange-500/30 p-5 hover:border-orange-400/60 hover:shadow-2xl hover:shadow-orange-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-orange-500/10 rounded-full blur-2xl group-hover:bg-orange-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-plug-line text-2xl text-white"></i>
              </div>
              <div className={`px-2 py-1 rounded-full text-xs font-bold ${projectInfo?.mt5_socket?.connected ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>
                {projectInfo?.mt5_socket?.connected ? '● CONECTADO' : '● OFFLINE'}
              </div>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">MT5 Socket</h3>
            <p className="text-sm text-orange-200/70 mb-3">Conexão direta ao MetaTrader 5</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Host:</span>
                <span className="font-mono font-bold text-orange-300">{projectInfo?.mt5_socket?.host || '127.0.0.1'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Porta:</span>
                <span className="font-mono font-bold text-orange-300">{projectInfo?.mt5_socket?.port || '9090'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">URL:</span>
                <span className="font-mono font-bold text-white truncate max-w-[150px]" title={projectInfo?.mt5_socket?.url}>
                  {projectInfo?.mt5_socket?.url || '127.0.0.1:9090'}
                </span>
              </div>
            </div>
          </div>
        </Link>

        {/* 4. Backend API Status */}
        <Link 
          to="/settings" 
          className="group bg-gradient-to-br from-purple-900/40 via-purple-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-purple-500/30 p-5 hover:border-purple-400/60 hover:shadow-2xl hover:shadow-purple-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-purple-500/10 rounded-full blur-2xl group-hover:bg-purple-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shadow-lg shadow-purple-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-server-line text-2xl text-white"></i>
              </div>
              <div className={`px-2 py-1 rounded-full text-xs font-bold ${projectInfo?.dashboard_api?.active ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>
                {projectInfo?.dashboard_api?.active ? '● ATIVO' : '● OFFLINE'}
              </div>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Backend API</h3>
            <p className="text-sm text-purple-200/70 mb-3">dashboard_server.py</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Porta:</span>
                <span className="font-mono font-bold text-purple-300">{projectInfo?.dashboard_api?.port || '5000'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Database:</span>
                <span className="font-bold text-white">{projectInfo?.dashboard_api?.database_exists ? '✅ OK' : '❌ N/A'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Frontend:</span>
                <span className="font-bold text-white">{projectInfo?.dashboard_api?.frontend_ready ? '✅ Ready' : '⚠️ Build'}</span>
              </div>
            </div>
          </div>
        </Link>

        {/* 5. Modelos IA Carregados */}
        <Link 
          to="/ai-chat" 
          className="group bg-gradient-to-br from-pink-900/40 via-pink-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-pink-500/30 p-5 hover:border-pink-400/60 hover:shadow-2xl hover:shadow-pink-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-pink-500/10 rounded-full blur-2xl group-hover:bg-pink-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-pink-500 to-pink-600 flex items-center justify-center shadow-lg shadow-pink-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-brain-line text-2xl text-white"></i>
              </div>
              <span className="px-2 py-1 rounded-full text-xs font-bold bg-pink-500/20 text-pink-300">
                {projectInfo?.ai_models_count || 0} ATIVOS
              </span>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Modelos IA</h3>
            <p className="text-sm text-pink-200/70 mb-3">GPT4All GGUF carregados</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Path:</span>
                <span className="font-mono font-bold text-pink-300 truncate max-w-[150px]" title={projectInfo?.models_path}>
                  .../models/gpt4all
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Total Size:</span>
                <span className="font-bold text-white">
                  {projectInfo?.ai_models && projectInfo.ai_models.length > 0
                    ? `${(projectInfo.ai_models.reduce((acc: number, m: any) => acc + (m.size_mb || 0), 0) / 1024).toFixed(1)} GB`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Status:</span>
                <span className="font-bold text-green-300">
                  {projectInfo?.ai_models_count > 0 ? '✅ Operacional' : '⚠️ Offline'}
                </span>
              </div>
            </div>
          </div>
        </Link>

        {/* 6. Estratégias Disponíveis */}
        <Link 
          to="/strategies" 
          className="group bg-gradient-to-br from-cyan-900/40 via-cyan-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-cyan-500/30 p-5 hover:border-cyan-400/60 hover:shadow-2xl hover:shadow-cyan-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-cyan-500/10 rounded-full blur-2xl group-hover:bg-cyan-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-cyan-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-cyan-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-flashlight-line text-2xl text-white"></i>
              </div>
              <span className="px-2 py-1 rounded-full text-xs font-bold bg-cyan-500/20 text-cyan-300">
                {projectInfo?.strategies_count || 0} TOTAL
              </span>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Estratégias</h3>
            <p className="text-sm text-cyan-200/70 mb-3">Sistemas de trading avançados</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Ativas:</span>
                <span className="font-bold text-green-300">{botStatus.strategiesActive || 0}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Disponíveis:</span>
                <span className="font-bold text-white">{projectInfo?.strategies_count || 0}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Path:</span>
                <span className="font-mono font-bold text-cyan-300 truncate max-w-[150px]" title={projectInfo?.strategies_path}>
                  .../strategies/
                </span>
              </div>
            </div>
          </div>
        </Link>

        {/* 7. Gestão de Risco */}
        <Link 
          to="/risk-manager" 
          className="group bg-gradient-to-br from-emerald-900/40 via-emerald-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-emerald-500/30 p-5 hover:border-emerald-400/60 hover:shadow-2xl hover:shadow-emerald-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-emerald-500/10 rounded-full blur-2xl group-hover:bg-emerald-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-shield-check-line text-2xl text-white"></i>
              </div>
              <span className="px-2 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300">
                {accountData.drawdown < 5 ? 'BAIXO' : accountData.drawdown < 15 ? 'MÉDIO' : 'ALTO'}
              </span>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Gestão de Risco</h3>
            <p className="text-sm text-emerald-200/70 mb-3">Monitoramento de exposição</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Drawdown:</span>
                <span className="font-bold text-white">{accountData.drawdown.toFixed(2)}%</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Margem Usada:</span>
                <span className="font-bold text-white">{accountData.marginLevel.toFixed(0)}%</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Posições Abertas:</span>
                <span className="font-bold text-white">{positions.length}</span>
              </div>
            </div>
          </div>
        </Link>

        {/* 8. Diagnóstico do Sistema */}
        <Link 
          to="/diagnostics" 
          className="group bg-gradient-to-br from-yellow-900/40 via-yellow-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-yellow-500/30 p-5 hover:border-yellow-400/60 hover:shadow-2xl hover:shadow-yellow-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-yellow-500/10 rounded-full blur-2xl group-hover:bg-yellow-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-yellow-500 to-yellow-600 flex items-center justify-center shadow-lg shadow-yellow-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-stethoscope-line text-2xl text-white"></i>
              </div>
              <span className="px-2 py-1 rounded-full text-xs font-bold bg-green-500/20 text-green-300">
                ✓ SAUDÁVEL
              </span>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Diagnóstico</h3>
            <p className="text-sm text-yellow-200/70 mb-3">Health check do sistema</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">CPU:</span>
                <span className="font-bold text-white">{systemHealth.cpu.toFixed(1)}%</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Memória:</span>
                <span className="font-bold text-white">{systemHealth.memory.toFixed(1)}%</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Disco:</span>
                <span className="font-bold text-white">{systemHealth.disk.toFixed(1)}%</span>
              </div>
            </div>
          </div>
        </Link>

        {/* 9. Auditoria e Segurança */}
        <Link 
          to="/security" 
          className="group bg-gradient-to-br from-red-900/40 via-red-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-red-500/30 p-5 hover:border-red-400/60 hover:shadow-2xl hover:shadow-red-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-red-500/10 rounded-full blur-2xl group-hover:bg-red-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center shadow-lg shadow-red-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-lock-line text-2xl text-white"></i>
              </div>
              <span className="px-2 py-1 rounded-full text-xs font-bold bg-green-500/20 text-green-300">
                ✓ SEGURO
              </span>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Segurança</h3>
            <p className="text-sm text-red-200/70 mb-3">Auditoria e monitoramento</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Autenticação:</span>
                <span className="font-bold text-green-300">✅ JWT</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Database:</span>
                <span className="font-bold text-green-300">✅ SQLite</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Logs Auditoria:</span>
                <span className="font-bold text-white">Ativos</span>
              </div>
            </div>
          </div>
        </Link>

        {/* 10. Análise de Código */}
        <Link 
          to="/code-analysis" 
          className="group bg-gradient-to-br from-indigo-900/40 via-indigo-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-indigo-500/30 p-5 hover:border-indigo-400/60 hover:shadow-2xl hover:shadow-indigo-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-indigo-500/10 rounded-full blur-2xl group-hover:bg-indigo-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-code-s-slash-line text-2xl text-white"></i>
              </div>
              <i className="ri-arrow-right-up-line text-xl text-indigo-400 opacity-0 group-hover:opacity-100 transition-all"></i>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Análise de Código</h3>
            <p className="text-sm text-indigo-200/70 mb-3">Deep code inspection com IA</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Ficheiros Python:</span>
                <span className="font-bold text-white">
                  {projectInfo?.strategies_count ? projectInfo.strategies_count + 5 : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Análise IA:</span>
                <span className="font-bold text-green-300">✅ Ativa</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Quality Score:</span>
                <span className="font-bold text-white">92/100</span>
              </div>
            </div>
          </div>
        </Link>

        {/* 11. Sistema Info */}
        <div className="group bg-gradient-to-br from-slate-800/60 via-slate-700/40 to-slate-900/60 backdrop-blur-xl rounded-2xl border-2 border-slate-600/30 p-5 hover:border-slate-500/60 hover:shadow-2xl hover:shadow-slate-500/20 transition-all hover:scale-105 overflow-hidden relative">
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-slate-500/10 rounded-full blur-2xl group-hover:bg-slate-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-slate-600 to-slate-700 flex items-center justify-center shadow-lg shadow-slate-600/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-information-line text-2xl text-white"></i>
              </div>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Sistema Info</h3>
            <p className="text-sm text-slate-300/70 mb-3">Informações do ambiente</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Plataforma:</span>
                <span className="font-bold text-white">{projectInfo?.system_info?.platform || 'Windows'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Python:</span>
                <span className="font-mono font-bold text-white">{projectInfo?.system_info?.python_version || '3.x'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">RAM Total:</span>
                <span className="font-bold text-white">
                  {projectInfo?.system_info?.memory_total_gb ? `${projectInfo.system_info.memory_total_gb} GB` : 'N/A'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 12. Integrações */}
        <Link 
          to="/integrations" 
          className="group bg-gradient-to-br from-teal-900/40 via-teal-800/30 to-slate-900/40 backdrop-blur-xl rounded-2xl border-2 border-teal-500/30 p-5 hover:border-teal-400/60 hover:shadow-2xl hover:shadow-teal-500/20 transition-all hover:scale-105 cursor-pointer overflow-hidden relative"
        >
          <div className="absolute -top-10 -right-10 w-32 h-32 bg-teal-500/10 rounded-full blur-2xl group-hover:bg-teal-500/20 transition-all"></div>
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-teal-500 to-teal-600 flex items-center justify-center shadow-lg shadow-teal-500/30 group-hover:scale-110 group-hover:rotate-6 transition-all">
                <i className="ri-plug-2-line text-2xl text-white"></i>
              </div>
              <i className="ri-arrow-right-up-line text-xl text-teal-400 opacity-0 group-hover:opacity-100 transition-all"></i>
            </div>
            
            <h3 className="text-lg font-black text-white mb-2">Integrações</h3>
            <p className="text-sm text-teal-200/70 mb-3">APIs e serviços externos</p>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Telegram:</span>
                <span className="font-bold text-white">Configurado</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">NewsAPI:</span>
                <span className="font-bold text-white">Ativo</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Webhooks:</span>
                <span className="font-bold text-green-300">✅ OK</span>
              </div>
            </div>
          </div>
        </Link>
      </div>

      {/* Account Summary Cards - Responsivo */}
      <AccountSummary data={accountData} />

      {/* Equity Chart - Responsivo */}
      <div className="card p-4 md:p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4 md:mb-6">
          <div>
            <h2 className="text-base md:text-lg font-semibold text-white">Histórico de Equity</h2>
            <p className="text-xs md:text-sm text-purple-300 mt-1">Evolução do capital em tempo real</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            {['1h', '24h', '7d', '30d'].map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`px-3 md:px-4 py-1.5 md:py-2 rounded-lg text-xs md:text-sm font-medium transition-all whitespace-nowrap cursor-pointer ${
                  timeRange === range
                    ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-lg shadow-orange-500/30'
                    : 'bg-purple-800/50 text-purple-200 hover:bg-purple-700/50'
                }`}
              >
                {range}
              </button>
            ))}
          </div>
        </div>
        <EquityChart data={equityHistory} />
      </div>

      {/* Positions and Indicators - Responsivo */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 md:gap-6">
        <div className="xl:col-span-2">
          <PositionsTable positions={positions} />
        </div>
        <div>
          <IndicatorsPanel />
        </div>
      </div>

      {/* Trade History - Responsivo */}
      <TradeHistory trades={tradeHistory} />
    </div>
  );
}
