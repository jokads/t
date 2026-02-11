import { useState, useEffect } from 'react';
import FileExplorer from './components/FileExplorer';
import ModelManager from './components/ModelManager';
import PathConfig from './components/PathConfig';
import { checkBackendHealth } from '../../utils/api';

export default function FileManager() {
  const [activeTab, setActiveTab] = useState<'files' | 'models' | 'paths'>('files');
  const [backendOnline, setBackendOnline] = useState(true);

  useEffect(() => {
    // Verificar backend ao montar
    const checkBackend = async () => {
      const isOnline = await checkBackendHealth();
      setBackendOnline(isOnline);
    };
    
    checkBackend();
    
    // Verificar a cada 30 segundos
    const interval = setInterval(checkBackend, 30000);
    
    return () => clearInterval(interval);
  }, []);

  // ✅ Mostrar aviso se backend offline
  if (!backendOnline) {
    return (
      <div className="space-y-6 animate-slide-up">
        <div className="card p-8 text-center">
          <div className="w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <i className="ri-server-line text-4xl text-red-400"></i>
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Backend Offline</h2>
          <p className="text-purple-300 mb-6">
            O servidor backend não está acessível. Inicie o dashboard_server.py:
          </p>
          <div className="bg-black/30 rounded-lg p-4 font-mono text-sm text-left text-green-400 mb-6 max-w-2xl mx-auto">
            <div>cd C:\bot-mt5</div>
            <div>python -m backend.dashboard_server</div>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 bg-gradient-to-r from-orange-500 to-red-500 text-white rounded-lg hover:from-orange-600 hover:to-red-600 transition"
          >
            <i className="ri-refresh-line mr-2"></i>
            Tentar Novamente
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Gestor de Ficheiros</h1>
          <p className="text-sm text-purple-300 mt-1">Gerir ficheiros, modelos AI e configurações de caminhos</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="card p-2">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('files')}
            className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 whitespace-nowrap cursor-pointer ${
              activeTab === 'files'
                ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-lg'
                : 'text-purple-200 hover:bg-purple-800/50'
            }`}
          >
            <i className="ri-folder-line text-base w-5 h-5 flex items-center justify-center"></i>
            <span>Explorador</span>
          </button>
          <button
            onClick={() => setActiveTab('models')}
            className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 whitespace-nowrap cursor-pointer ${
              activeTab === 'models'
                ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-lg'
                : 'text-purple-200 hover:bg-purple-800/50'
            }`}
          >
            <i className="ri-brain-line text-base w-5 h-5 flex items-center justify-center"></i>
            <span>Modelos AI</span>
          </button>
          <button
            onClick={() => setActiveTab('paths')}
            className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 whitespace-nowrap cursor-pointer ${
              activeTab === 'paths'
                ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-lg'
                : 'text-purple-200 hover:bg-purple-800/50'
            }`}
          >
            <i className="ri-settings-3-line text-base w-5 h-5 flex items-center justify-center"></i>
            <span>Caminhos</span>
          </button>
        </div>
      </div>

      {/* Content */}
      {activeTab === 'files' && <FileExplorer />}
      {activeTab === 'models' && <ModelManager />}
      {activeTab === 'paths' && <PathConfig />}
    </div>
  );
}