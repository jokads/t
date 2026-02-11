import { useState, useEffect } from 'react';
import { apiGet, apiPost, checkBackendHealth } from '../../../utils/api';

interface FileItem {
  name: string;
  path: string;
  type: 'file' | 'folder';
  size?: number;
  modified: string;
}

interface SystemStatus {
  frontend: boolean;
  backend: boolean;
  bot: boolean;
  mt5Socket: boolean;
  basePath: string;
}

interface FileStats {
  total_files: number;
  total_folders: number;
  total_size_mb: number;
  by_extension: Record<string, number>;
}

type BackendStatus = 'checking' | 'connected' | 'offline';

export default function FileExplorer() {
  const [currentPath, setCurrentPath] = useState('');
  const [files, setFiles] = useState<FileItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [isViewingFile, setIsViewingFile] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    frontend: true,
    backend: false,
    bot: false,
    mt5Socket: false,
    basePath: 'C:/bot-mt5'
  });
  const [stats, setStats] = useState<FileStats | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking');
  const [logs, setLogs] = useState<string[]>([]);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);

  // Adicionar log
  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString('pt-PT');
    setLogs(prev => [`[${timestamp}] ${message}`, ...prev].slice(0, 50));
  };

  // Verificar backend e carregar dados
  const checkBackendAndLoad = async () => {
    console.log('🔍 Verificando backend...');
    setBackendStatus('checking');
    
    try {
      const isHealthy = await checkBackendHealth();
      
      if (isHealthy) {
        setBackendStatus('connected');
        addLog('✅ Backend conectado - Carregando dados...');
        
        // Carregar dados do sistema
        try {
          const healthData = await apiGet<any>('/api/health');
          if (healthData && !healthData.error) {
            setSystemStatus(prev => ({
              ...prev,
              backend: true,
              bot: healthData.bot_connected || false,
              mt5Socket: healthData.mt5_socket_connected || false
            }));
          }
        } catch (err) {
          console.log('⚠️ Erro ao obter health data');
        }
        
        // Carregar informações do projeto
        try {
          const projectInfo = await apiGet<any>('/api/diagnostics/project_info');
          if (projectInfo && !projectInfo.error) {
            const basePath = projectInfo.base_path || projectInfo.project_root || 'C:/bot-mt5';
            setSystemStatus(prev => ({ ...prev, basePath }));
            addLog(`📂 Base path detectado: ${basePath}`);
          }
        } catch (err) {
          console.log('⚠️ Erro ao obter project info');
        }
        
        // Carregar ficheiros e estatísticas
        await Promise.all([
          loadFiles(''),
          loadStats()
        ]);
        
        addLog('🟢 Sistema completamente carregado');
      } else {
        setBackendStatus('offline');
        setSystemStatus(prev => ({ ...prev, backend: false }));
        addLog('⚪ Backend offline - Execute python trading_bot_core.py');
      }
    } catch (error) {
      console.error('❌ Erro ao verificar backend:', error);
      setBackendStatus('offline');
      setSystemStatus(prev => ({ ...prev, backend: false }));
      addLog('❌ Erro ao conectar ao backend');
    }
  };

  // Carregar estatísticas
  const loadStats = async () => {
    try {
      const response = await apiGet<any>('/api/files/stats');
      
      if (response && !response.error) {
        const statsData = response.data?.stats || response.stats || response;
        if (statsData && statsData.total_files !== undefined) {
          setStats(statsData);
          addLog(`📊 Stats: ${statsData.total_files} ficheiros, ${statsData.total_folders} pastas`);
        }
      }
    } catch (error) {
      console.log('⚠️ Stats endpoint não disponível');
    }
  };

  // Carregar ficheiros
  const loadFiles = async (path: string = '') => {
    if (backendStatus !== 'connected') {
      console.log('⚠️ Backend não conectado, aguardando...');
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await apiGet<any>(`/api/files/list?path=${encodeURIComponent(path)}`);
      
      // Verificar se é HTML (erro 404)
      if (typeof response === 'string' && response.includes('<!doctype html>')) {
        throw new Error('Endpoint não disponível (404)');
      }
      
      if (response && response.error) {
        throw new Error(response.error);
      }
      
      // Extrair array de ficheiros
      let filesData: FileItem[] = [];
      if (Array.isArray(response)) {
        filesData = response;
      } else if (response.data && Array.isArray(response.data)) {
        filesData = response.data;
      } else if (response.files && Array.isArray(response.files)) {
        filesData = response.files;
      }
      
      setFiles(filesData);
      setCurrentPath(path);
      addLog(`📂 ${filesData.length} ficheiros carregados em: ${path || '/'}`);
      
      console.log(`✅ ${filesData.length} ficheiros carregados em: ${path || '/'}`);
    } catch (error) {
      console.error('❌ Erro ao carregar ficheiros:', error);
      addLog(`❌ Erro ao carregar ficheiros: ${error instanceof Error ? error.message : 'Desconhecido'}`);
      setFiles([]);
    } finally {
      setLoading(false);
    }
  };

  // Carregar conteúdo do ficheiro
  const loadFileContent = async (path: string) => {
    if (backendStatus !== 'connected') {
      addLog('❌ Backend offline - Não é possível ler ficheiro');
      return;
    }
    
    setLoading(true);
    addLog(`🔍 Carregando: ${path.split('/').pop()}`);
    
    try {
      const response = await apiGet<any>(`/api/files/read?path=${encodeURIComponent(path)}`);
      
      // Verificar se é HTML (erro 404)
      if (typeof response === 'string' && response.includes('<!doctype html>')) {
        throw new Error('Endpoint de leitura não disponível');
      }
      
      if (response && response.error) {
        throw new Error(response.error);
      }
      
      // Extrair conteúdo
      const data = response.data || response;
      const content = data.content !== undefined ? data.content : '';
      
      setFileContent(content);
      setSelectedFile(path);
      setIsViewingFile(true);
      
      const lines = content.split('\n').length;
      const chars = content.length;
      addLog(`✅ Ficheiro carregado: ${lines} linhas, ${chars} caracteres`);
      
      console.log(`✅ Ficheiro carregado: ${path} (${chars} bytes)`);
    } catch (error) {
      console.error('❌ Erro ao ler ficheiro:', error);
      addLog(`❌ Erro ao ler: ${error instanceof Error ? error.message : 'Desconhecido'}`);
      setFileContent(`// Erro ao carregar ficheiro\n// ${error instanceof Error ? error.message : 'Desconhecido'}`);
      setSelectedFile(path);
      setIsViewingFile(true);
    } finally {
      setLoading(false);
    }
  };

  // Guardar ficheiro
  const saveFile = async () => {
    if (!selectedFile || backendStatus !== 'connected') {
      addLog('❌ Não é possível guardar - Backend offline');
      return;
    }
    
    setSaving(true);
    addLog(`💾 Guardando: ${selectedFile.split('/').pop()}`);
    
    try {
      const response = await apiPost<any>('/api/files/write', {
        path: selectedFile,
        content: fileContent
      });
      
      if (typeof response === 'string' && response.includes('<!doctype html>')) {
        throw new Error('Endpoint de escrita não disponível');
      }
      
      if (response && response.error) {
        throw new Error(response.error);
      }
      
      const data = response.data || response;
      
      if (data && data.success) {
        const backupMsg = data.backup_created ? ' (backup criado)' : '';
        addLog(`✅ Ficheiro guardado com sucesso${backupMsg}`);
        await loadFiles(currentPath); // Refresh lista
      } else {
        throw new Error('Erro ao guardar');
      }
    } catch (error) {
      console.error('❌ Erro ao guardar:', error);
      addLog(`❌ Erro ao guardar: ${error instanceof Error ? error.message : 'Desconhecido'}`);
    } finally {
      setSaving(false);
    }
  };

  // Clicar em ficheiro/pasta
  const handleFileClick = (file: FileItem) => {
    if (file.type === 'folder') {
      addLog(`📂 Navegando para: ${file.name}`);
      loadFiles(file.path);
    } else {
      loadFileContent(file.path);
    }
  };

  // Voltar para pasta anterior
  const goBack = () => {
    const parts = currentPath.split('/').filter(Boolean);
    parts.pop();
    const newPath = parts.join('/');
    addLog(`⬅️ Voltando para: ${newPath || '/'}`);
    loadFiles(newPath);
  };

  // Voltar para raiz
  const goToRoot = () => {
    addLog('🏠 Voltando para raiz');
    loadFiles('');
  };

  // Fechar visualizador
  const closeViewer = () => {
    setIsViewingFile(false);
    setSelectedFile(null);
    setFileContent('');
    addLog('✖️ Editor fechado');
  };

  // Formatar tamanho
  const formatSize = (bytes?: number) => {
    if (!bytes) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  // Formatar data
  const formatDate = (date: string) => {
    return new Date(date).toLocaleString('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Inicialização
  useEffect(() => {
    addLog('🚀 Gestor de Ficheiros iniciado');
    checkBackendAndLoad();
  }, []);

  // Auto-refresh a cada 30s (se backend conectado)
  useEffect(() => {
    if (backendStatus === 'connected' && autoRefreshEnabled) {
      const interval = setInterval(() => {
        addLog('🔄 Auto-refresh de estatísticas...');
        loadStats();
      }, 30000);
      
      return () => clearInterval(interval);
    }
  }, [backendStatus, autoRefreshEnabled]);

  return (
    <div className="space-y-6">
      {/* Banner de Status */}
      {backendStatus === 'checking' && (
        <div className="bg-gradient-to-r from-yellow-900/40 to-orange-900/40 backdrop-blur-xl border border-yellow-500/40 rounded-2xl p-6 shadow-2xl">
          <div className="flex items-center gap-4">
            <i className="ri-loader-4-line animate-spin text-3xl text-yellow-400"></i>
            <div>
              <h3 className="text-lg font-bold text-white mb-1">⏳ Verificando Sistema...</h3>
              <p className="text-yellow-300 text-sm">Conectando ao backend e escaneando ambiente</p>
            </div>
          </div>
        </div>
      )}

      {backendStatus === 'offline' && (
        <div className="bg-gradient-to-r from-red-900/40 to-orange-900/40 backdrop-blur-xl border border-red-500/40 rounded-2xl p-6 shadow-2xl">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 flex items-center justify-center bg-red-500/20 rounded-xl flex-shrink-0">
              <i className="ri-alert-line text-2xl text-red-400"></i>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-white mb-2">✅ Sistema Preparado para Acesso Completo</h3>
              <p className="text-red-300 text-sm mb-4">Execute python trading_bot_core.py para conectar dados ao vivo</p>
              
              <div className="flex flex-wrap gap-2 mb-4">
                <span className="px-3 py-1 bg-purple-500/20 border border-purple-500/30 rounded-full text-purple-300 text-xs">
                  📂 Base: {systemStatus.basePath}
                </span>
                <span className="px-3 py-1 bg-cyan-500/20 border border-cyan-500/30 rounded-full text-cyan-300 text-xs">
                  🤖 6 modelos IA prontos
                </span>
                <span className="px-3 py-1 bg-orange-500/20 border border-orange-500/30 rounded-full text-orange-300 text-xs">
                  📊 Estratégias disponíveis
                </span>
              </div>
              
              <button
                onClick={checkBackendAndLoad}
                className="px-4 py-2 bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white font-semibold rounded-lg transition-all cursor-pointer whitespace-nowrap"
              >
                <i className="ri-refresh-line mr-2"></i>
                Verificar
              </button>
            </div>
          </div>
        </div>
      )}

      {backendStatus === 'connected' && (
        <div className="bg-gradient-to-r from-green-900/40 to-emerald-900/40 backdrop-blur-xl border border-green-500/40 rounded-2xl p-6 shadow-2xl">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
              <div>
                <h3 className="text-lg font-bold text-white mb-1">🟢 Sistema Completamente Conectado</h3>
                <p className="text-green-300 text-sm">Backend ativo • Dados em tempo real • Acesso total aos ficheiros</p>
              </div>
            </div>
            <button
              onClick={checkBackendAndLoad}
              className="px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30 border border-green-500/30 text-green-300 rounded-lg text-xs transition-all cursor-pointer whitespace-nowrap"
            >
              <i className="ri-refresh-line mr-1"></i>
              Atualizar
            </button>
          </div>
          
          <div className="flex flex-wrap gap-2 mt-4">
            <span className="px-3 py-1 bg-green-500/20 border border-green-500/30 rounded-full text-green-300 text-xs">
              ✅ Trading Bot Core: {systemStatus.bot ? 'ATIVO' : 'OFFLINE'}
            </span>
            <span className="px-3 py-1 bg-green-500/20 border border-green-500/30 rounded-full text-green-300 text-xs">
              ✅ Dashboard Server: ONLINE
            </span>
            {stats && (
              <span className="px-3 py-1 bg-cyan-500/20 border border-cyan-500/30 rounded-full text-cyan-300 text-xs">
                🤖 {stats.total_files} ficheiros detectados
              </span>
            )}
            <span className="px-3 py-1 bg-purple-500/20 border border-purple-500/30 rounded-full text-purple-300 text-xs">
              🔄 Atualização: 30s
            </span>
          </div>
        </div>
      )}

      {/* System Status Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gradient-to-br from-purple-900/40 to-red-900/40 backdrop-blur-xl border border-orange-500/20 rounded-2xl p-4 shadow-2xl hover:scale-105 transition-transform">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${systemStatus.frontend ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
            <div className="flex-1">
              <p className="text-xs text-purple-300">Frontend</p>
              <p className="text-sm font-bold text-white mt-0.5">React Dashboard</p>
              <span className={`inline-block mt-2 px-2 py-0.5 rounded-full text-xs ${systemStatus.frontend ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                {systemStatus.frontend ? 'ATIVO' : 'OFFLINE'}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-900/40 to-red-900/40 backdrop-blur-xl border border-orange-500/20 rounded-2xl p-4 shadow-2xl hover:scale-105 transition-transform">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${backendStatus === 'connected' ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
            <div className="flex-1">
              <p className="text-xs text-purple-300">Backend API</p>
              <p className="text-sm font-bold text-white mt-0.5">dashboard_server.py</p>
              <span className={`inline-block mt-2 px-2 py-0.5 rounded-full text-xs ${backendStatus === 'connected' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                {backendStatus === 'connected' ? 'CONECTADO' : backendStatus === 'checking' ? 'VERIFICANDO...' : 'OFFLINE'}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-900/40 to-red-900/40 backdrop-blur-xl border border-orange-500/20 rounded-2xl p-4 shadow-2xl hover:scale-105 transition-transform">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${systemStatus.bot ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
            <div className="flex-1">
              <p className="text-xs text-purple-300">Python Core</p>
              <p className="text-sm font-bold text-white mt-0.5">trading_bot_core.py</p>
              <span className={`inline-block mt-2 px-2 py-0.5 rounded-full text-xs ${systemStatus.bot ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'}`}>
                {systemStatus.bot ? 'ATIVO' : 'PREPARADO'}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-900/40 to-red-900/40 backdrop-blur-xl border border-orange-500/20 rounded-2xl p-4 shadow-2xl hover:scale-105 transition-transform">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${systemStatus.mt5Socket ? 'bg-green-400 animate-pulse' : 'bg-slate-400'}`}></div>
            <div className="flex-1">
              <p className="text-xs text-purple-300">MT5 Socket</p>
              <p className="text-sm font-bold text-white mt-0.5">Porta 9090</p>
              <span className={`inline-block mt-2 px-2 py-0.5 rounded-full text-xs ${systemStatus.mt5Socket ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'}`}>
                {systemStatus.mt5Socket ? 'CONECTADO' : 'AGUARDANDO'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Logs do Sistema */}
      <div className="bg-gradient-to-br from-purple-900/40 to-red-900/40 backdrop-blur-xl border border-orange-500/20 rounded-2xl overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-purple-500/20">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <i className="ri-terminal-box-line text-orange-400"></i>
            Logs do Sistema
          </h3>
          <div className="flex items-center gap-3">
            <span className={`px-2 py-1 rounded-full text-xs font-bold ${backendStatus === 'connected' ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'}`}>
              {backendStatus === 'connected' ? '🟢 LIVE' : '⚪ OFFLINE'}
            </span>
            <button
              onClick={() => setLogs([])}
              className="px-2 py-1 bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 text-red-400 rounded text-xs transition-all cursor-pointer"
            >
              Limpar
            </button>
          </div>
        </div>
        <div className="p-4 bg-black/40 h-32 overflow-y-auto custom-scrollbar font-mono text-xs text-green-400">
          {logs.length === 0 ? (
            <p className="text-purple-400">Aguardando atividade...</p>
          ) : (
            logs.map((log, index) => (
              <div key={index} className="mb-1">{log}</div>
            ))
          )}
        </div>
      </div>

      {/* Navegação & Estatísticas */}
      {backendStatus === 'connected' && (
        <>
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm">
            <button
              onClick={goToRoot}
              className="px-3 py-1.5 bg-purple-800/50 hover:bg-purple-700/50 text-orange-400 rounded-lg transition-all cursor-pointer flex items-center gap-1"
            >
              <i className="ri-folder-line"></i>
              <span>bot-mt5</span>
            </button>
            {currentPath.split('/').filter(Boolean).map((part, index, arr) => (
              <div key={index} className="flex items-center gap-2">
                <i className="ri-arrow-right-s-line text-purple-400"></i>
                <button
                  onClick={() => {
                    const path = arr.slice(0, index + 1).join('/');
                    loadFiles(path);
                  }}
                  className="px-3 py-1.5 bg-purple-800/50 hover:bg-purple-700/50 text-orange-400 rounded-lg transition-all cursor-pointer"
                >
                  {part}
                </button>
              </div>
            ))}
          </div>

          {/* Actions & Stats */}
          <div className="flex items-center gap-3 flex-wrap">
            {currentPath && (
              <button
                onClick={goBack}
                className="px-4 py-2 bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg transition-all cursor-pointer whitespace-nowrap flex items-center gap-2"
              >
                <i className="ri-arrow-left-line"></i>
                <span>Voltar</span>
              </button>
            )}
            <button
              onClick={goToRoot}
              disabled={!currentPath}
              className="px-4 py-2 bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg transition-all cursor-pointer whitespace-nowrap flex items-center gap-2 disabled:opacity-50"
            >
              <i className="ri-home-line"></i>
              <span>Raiz</span>
            </button>
            <button
              onClick={() => loadFiles(currentPath)}
              disabled={loading}
              className="px-4 py-2 bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg transition-all cursor-pointer whitespace-nowrap flex items-center gap-2 disabled:opacity-50"
            >
              <i className={`${loading ? 'ri-loader-4-line animate-spin' : 'ri-refresh-line'}`}></i>
              <span>{loading ? 'Carregando...' : 'Atualizar'}</span>
            </button>
            <div className="flex-1"></div>
            {stats && (
              <div className="flex items-center gap-4 text-sm">
                <span className="text-purple-300">
                  <i className="ri-file-line mr-1 text-cyan-400"></i>
                  {files.length} itens
                </span>
                <span className="text-purple-300">
                  <i className="ri-folder-line mr-1 text-orange-400"></i>
                  {stats.total_folders} pastas
                </span>
                <span className="text-purple-300">
                  <i className="ri-database-2-line mr-1 text-green-400"></i>
                  {stats.total_size_mb.toFixed(2)} MB
                </span>
              </div>
            )}
          </div>

          {/* File List */}
          <div className="bg-gradient-to-br from-purple-900/40 to-red-900/40 backdrop-blur-xl border border-orange-500/20 rounded-2xl overflow-hidden shadow-2xl">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-purple-500/20">
                    <th className="py-3 pl-6 text-left text-xs font-semibold text-purple-300 uppercase tracking-wider">Nome</th>
                    <th className="py-3 text-left text-xs font-semibold text-purple-300 uppercase tracking-wider">Tipo</th>
                    <th className="py-3 text-left text-xs font-semibold text-purple-300 uppercase tracking-wider">Tamanho</th>
                    <th className="py-3 text-left text-xs font-semibold text-purple-300 uppercase tracking-wider">Modificado</th>
                    <th className="py-3 pr-6 text-right text-xs font-semibold text-purple-300 uppercase tracking-wider">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center">
                        <i className="ri-loader-4-line animate-spin text-3xl text-orange-400"></i>
                        <p className="text-purple-300 text-sm mt-2">A carregar ficheiros...</p>
                      </td>
                    </tr>
                  ) : files.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center text-purple-300">
                        <i className="ri-folder-open-line text-4xl text-purple-400 mb-2"></i>
                        <p className="text-sm">Pasta vazia ou sem permissões</p>
                      </td>
                    </tr>
                  ) : (
                    files.map((file, index) => (
                      <tr 
                        key={index} 
                        className={`border-b border-purple-500/10 hover:bg-purple-900/20 transition-all cursor-pointer ${
                          selectedFile === file.path ? 'bg-orange-500/10' : ''
                        }`}
                        onClick={() => handleFileClick(file)}
                      >
                        <td className="py-3 pl-6">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 flex items-center justify-center rounded-lg ${
                              file.type === 'folder' ? 'bg-orange-500/20' : 'bg-cyan-500/20'
                            }`}>
                              <i className={`${
                                file.type === 'folder' ? 'ri-folder-fill text-orange-400' : 'ri-file-code-line text-cyan-400'
                              } text-xl`}></i>
                            </div>
                            <span className="text-sm text-white font-medium">{file.name}</span>
                          </div>
                        </td>
                        <td className="py-3">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            file.type === 'folder' ? 'bg-orange-500/20 text-orange-400' : 'bg-cyan-500/20 text-cyan-400'
                          }`}>
                            {file.type === 'folder' ? 'Pasta' : 'Ficheiro'}
                          </span>
                        </td>
                        <td className="py-3 text-sm text-purple-300">{formatSize(file.size)}</td>
                        <td className="py-3 text-sm text-purple-300">{formatDate(file.modified)}</td>
                        <td className="py-3 pr-6">
                          <div className="flex items-center justify-end gap-2">
                            {file.type === 'folder' ? (
                              <button 
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleFileClick(file);
                                }}
                                className="px-3 py-1.5 bg-orange-500/20 hover:bg-orange-500/30 border border-orange-500/30 text-orange-400 rounded-lg transition-all cursor-pointer text-xs font-medium whitespace-nowrap"
                                title="Abrir pasta"
                              >
                                <i className="ri-folder-open-line mr-1"></i>
                                Abrir
                              </button>
                            ) : (
                              <button 
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleFileClick(file);
                                }}
                                className="px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 text-cyan-400 rounded-lg transition-all cursor-pointer text-xs font-medium whitespace-nowrap"
                                title="Ver código"
                              >
                                <i className="ri-eye-line mr-1"></i>
                                Ver Código
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* File Viewer/Editor */}
      {isViewingFile && (
        <div className="bg-gradient-to-br from-purple-900/40 to-red-900/40 backdrop-blur-xl border border-orange-500/20 rounded-2xl overflow-hidden shadow-2xl animate-slide-up">
          <div className="flex items-center justify-between p-4 border-b border-purple-500/20 bg-black/40">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <i className="ri-file-code-line text-cyan-400"></i>
                {selectedFile?.split('/').pop()}
              </h3>
              <p className="text-xs text-purple-400 mt-1 font-mono">{selectedFile}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={saveFile}
                disabled={saving || backendStatus !== 'connected'}
                className="px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white font-semibold rounded-lg transition-all cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <i className={`${saving ? 'ri-loader-4-line animate-spin' : 'ri-save-line'}`}></i>
                <span>{saving ? 'Guardando...' : 'Guardar'}</span>
              </button>
              <button
                onClick={closeViewer}
                className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 text-red-400 rounded-lg transition-all cursor-pointer whitespace-nowrap flex items-center gap-2"
              >
                <i className="ri-close-line"></i>
                <span>Fechar</span>
              </button>
            </div>
          </div>
          
          {/* Editor */}
          <div className="p-4 bg-black/40">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-4 text-xs text-purple-400">
                <span>
                  <i className="ri-file-text-line mr-1 text-cyan-400"></i>
                  {fileContent.split('\n').length} linhas
                </span>
                <span>
                  <i className="ri-text mr-1 text-orange-400"></i>
                  {fileContent.length} caracteres
                </span>
              </div>
              {backendStatus === 'connected' && (
                <div className="flex items-center gap-2 text-xs text-green-400">
                  <i className="ri-shield-check-line"></i>
                  <span>Backup automático ao guardar</span>
                </div>
              )}
            </div>
            <textarea
              value={fileContent}
              onChange={(e) => setFileContent(e.target.value)}
              className="w-full h-[500px] bg-black/60 border border-purple-500/20 rounded-lg p-4 text-sm text-green-400 font-mono focus:outline-none focus:border-orange-500/40 resize-none custom-scrollbar"
              spellCheck={false}
              disabled={backendStatus !== 'connected'}
              placeholder="// Conteúdo do ficheiro aparecerá aqui..."
            />
          </div>
        </div>
      )}
    </div>
  );
}
