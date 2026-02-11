import { useState, useEffect } from 'react';

interface GeneralSettingsProps {
  environment: {
    frontend: boolean;
    backend: boolean;
    pythonCore: boolean;
    basePath: string;
    modelsPath: string;
  };
  aiModels: any[];
}

export default function GeneralSettings({ environment, aiModels }: GeneralSettingsProps) {
  const [config, setConfig] = useState({
    botName: 'Trading Bot Pro',
    timezone: 'UTC+0',
    language: 'pt',
    currency: 'USD',
    darkMode: true,
    animations: true,
    sounds: false
  });

  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);

  // Carregar configurações do backend
  useEffect(() => {
    if (environment.backend) {
      loadConfig();
    }
  }, [environment.backend]);

  const loadConfig = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/settings/general');
      if (response.ok) {
        const data = await response.json();
        setConfig({ ...config, ...data });
      }
    } catch (error) {
      console.log('Usando configurações locais');
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      if (environment.backend) {
        const response = await fetch('http://localhost:8000/api/settings/general', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config)
        });
        if (response.ok) {
          setSaved(true);
          setTimeout(() => setSaved(false), 3000);
        }
      } else {
        // Salvar localmente
        localStorage.setItem('generalSettings', JSON.stringify(config));
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      }
    } catch (error) {
      console.error('Erro ao salvar:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Informações do Sistema */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-information-line text-cyan-400"></i>
          Informações do Sistema
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="glass-effect p-4 rounded-lg">
            <div className="text-xs text-purple-400 mb-1">Base Path</div>
            <div className="text-sm text-white font-mono break-all">
              {environment.basePath || 'C:/bot-mt5'}
            </div>
          </div>
          <div className="glass-effect p-4 rounded-lg">
            <div className="text-xs text-purple-400 mb-1">Models Path</div>
            <div className="text-sm text-white font-mono break-all">
              {environment.modelsPath || 'C:/bot-mt5/models/gpt4all'}
            </div>
          </div>
          <div className="glass-effect p-4 rounded-lg">
            <div className="text-xs text-purple-400 mb-1">Modelos IA Disponíveis</div>
            <div className="text-2xl font-bold text-cyan-400">
              {aiModels.length}
            </div>
            <div className="text-xs text-purple-300 mt-1">
              {aiModels.filter(m => m.recommended).length} recomendados
            </div>
          </div>
          <div className="glass-effect p-4 rounded-lg">
            <div className="text-xs text-purple-400 mb-1">Status dos Serviços</div>
            <div className="flex gap-2 mt-2">
              <span className={`px-2 py-1 rounded text-xs ${environment.frontend ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                Frontend
              </span>
              <span className={`px-2 py-1 rounded text-xs ${environment.backend ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                Backend
              </span>
              <span className={`px-2 py-1 rounded text-xs ${environment.pythonCore ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                Core
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Preferências Gerais */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-settings-3-line text-purple-400"></i>
          Preferências Gerais
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Nome do Bot</label>
            <input
              type="text"
              value={config.botName}
              onChange={(e) => setConfig({ ...config, botName: e.target.value })}
              className="w-full px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Timezone</label>
            <select 
              value={config.timezone}
              onChange={(e) => setConfig({ ...config, timezone: e.target.value })}
              className="w-full px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              <option value="UTC+0">UTC+0 (Lisboa)</option>
              <option value="UTC+1">UTC+1 (Europa Central)</option>
              <option value="UTC-3">UTC-3 (Brasil)</option>
              <option value="UTC-5">UTC-5 (Nova York)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Idioma</label>
            <select 
              value={config.language}
              onChange={(e) => setConfig({ ...config, language: e.target.value })}
              className="w-full px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              <option value="pt">Português</option>
              <option value="en">English</option>
              <option value="es">Español</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Moeda de Exibição</label>
            <select 
              value={config.currency}
              onChange={(e) => setConfig({ ...config, currency: e.target.value })}
              className="w-full px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Preferências de Interface */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-palette-line text-pink-400"></i>
          Preferências de Interface
        </h3>
        <div className="space-y-3">
          <label className="flex items-center justify-between p-3 glass-effect rounded-lg cursor-pointer hover:bg-purple-500/10 transition-all">
            <div className="flex items-center gap-3">
              <i className="ri-moon-line text-purple-400"></i>
              <span className="text-sm text-white">Modo Escuro</span>
            </div>
            <input 
              type="checkbox" 
              checked={config.darkMode}
              onChange={(e) => setConfig({ ...config, darkMode: e.target.checked })}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-purple-500 focus:ring-2 focus:ring-purple-500 cursor-pointer" 
            />
          </label>
          <label className="flex items-center justify-between p-3 glass-effect rounded-lg cursor-pointer hover:bg-purple-500/10 transition-all">
            <div className="flex items-center gap-3">
              <i className="ri-speed-line text-cyan-400"></i>
              <span className="text-sm text-white">Animações</span>
            </div>
            <input 
              type="checkbox" 
              checked={config.animations}
              onChange={(e) => setConfig({ ...config, animations: e.target.checked })}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-cyan-500 focus:ring-2 focus:ring-cyan-500 cursor-pointer" 
            />
          </label>
          <label className="flex items-center justify-between p-3 glass-effect rounded-lg cursor-pointer hover:bg-purple-500/10 transition-all">
            <div className="flex items-center gap-3">
              <i className="ri-volume-up-line text-pink-400"></i>
              <span className="text-sm text-white">Sons de Notificação</span>
            </div>
            <input 
              type="checkbox" 
              checked={config.sounds}
              onChange={(e) => setConfig({ ...config, sounds: e.target.checked })}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-pink-500 focus:ring-2 focus:ring-pink-500 cursor-pointer" 
            />
          </label>
        </div>
      </div>

      {/* Botões de Ação */}
      <div className="flex gap-3">
        <button 
          onClick={loadConfig}
          className="px-6 py-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg text-sm font-medium transition-all border border-purple-500/30 whitespace-nowrap cursor-pointer"
          disabled={loading || !environment.backend}
        >
          Recarregar
        </button>
        <button 
          onClick={handleSave}
          className="flex-1 px-6 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-purple-500/30 whitespace-nowrap cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={loading}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <i className="ri-loader-4-line animate-spin"></i>
              Guardando...
            </span>
          ) : saved ? (
            <span className="flex items-center justify-center gap-2">
              <i className="ri-check-line"></i>
              Guardado!
            </span>
          ) : (
            'Guardar Alterações'
          )}
        </button>
      </div>

      {saved && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <i className="ri-checkbox-circle-line text-green-400 text-xl"></i>
            <div>
              <div className="text-sm font-medium text-green-300">Configurações guardadas com sucesso!</div>
              <div className="text-xs text-green-200/70 mt-1">
                As alterações foram aplicadas ao sistema.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
