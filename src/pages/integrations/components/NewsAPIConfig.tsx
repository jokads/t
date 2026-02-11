import React, { useState } from 'react';
import { apiPost } from '../../../utils/api';

interface NewsAPIConfigProps {
  config: {
    enabled: boolean;
    apiKey: string;
    sources: string[];
    updateInterval: number;
  };
  onSave: (config: any) => void;
  backendOnline: boolean;
}

const NewsAPIConfig: React.FC<NewsAPIConfigProps> = ({ config, onSave, backendOnline }) => {
  const [localConfig, setLocalConfig] = useState(config);
  const [newSource, setNewSource] = useState('');
  const [isTesting, setIsTesting] = useState(false);

  const availableSources = [
    { id: 'bloomberg', name: 'Bloomberg', icon: '📈' },
    { id: 'reuters', name: 'Reuters', icon: '📰' },
    { id: 'forexlive', name: 'ForexLive', icon: '💱' },
    { id: 'investing', name: 'Investing.com', icon: '💼' },
    { id: 'cnbc', name: 'CNBC', icon: '📊' },
    { id: 'marketwatch', name: 'MarketWatch', icon: '🔍' },
  ];

  // Testar API
  const testNewsAPI = async () => {
    if (!localConfig.apiKey) {
      alert('⚠️ Por favor, insira a API Key primeiro!');
      return;
    }

    setIsTesting(true);
    try {
      const response = await apiPost<any>('/api/integrations/newsapi/test', {
        apiKey: localConfig.apiKey,
        sources: localConfig.sources,
      });

      if (response && !response.error) {
        alert(`✅ Teste bem-sucedido!\n\nNotícias encontradas: ${response.newsCount || 0}\nÚltima atualização: ${response.lastUpdate || 'N/A'}\nStatus: ${response.status}`);
      } else {
        alert('❌ Teste falhou: ' + (response?.error || 'Erro desconhecido'));
      }
    } catch (error) {
      console.error('❌ Erro ao testar News API:', error);
      alert('❌ Erro ao testar. Verifique se o backend está ativo.');
    } finally {
      setIsTesting(false);
    }
  };

  // Toggle fonte
  const toggleSource = (sourceId: string) => {
    if (localConfig.sources.includes(sourceId)) {
      setLocalConfig({
        ...localConfig,
        sources: localConfig.sources.filter((s) => s !== sourceId),
      });
    } else {
      setLocalConfig({
        ...localConfig,
        sources: [...localConfig.sources, sourceId],
      });
    }
  };

  // Adicionar fonte customizada
  const addCustomSource = () => {
    if (!newSource.trim()) return;
    if (localConfig.sources.includes(newSource.trim())) {
      alert('⚠️ Esta fonte já está na lista!');
      return;
    }
    setLocalConfig({
      ...localConfig,
      sources: [...localConfig.sources, newSource.trim()],
    });
    setNewSource('');
  };

  // Remover fonte customizada
  const removeCustomSource = (source: string) => {
    // Só remove se não estiver na lista de fontes conhecidas
    if (!availableSources.find((s) => s.id === source)) {
      setLocalConfig({
        ...localConfig,
        sources: localConfig.sources.filter((s) => s !== source),
      });
    }
  };

  // Guardar configurações
  const handleSave = () => {
    if (localConfig.enabled && !localConfig.apiKey) {
      alert('⚠️ Por favor, insira a API Key antes de ativar!');
      return;
    }
    if (localConfig.enabled && localConfig.sources.length === 0) {
      alert('⚠️ Selecione pelo menos 1 fonte de notícias!');
      return;
    }
    onSave(localConfig);
  };

  // Fontes customizadas (não estão na lista padrão)
  const customSources = localConfig.sources.filter(
    (source) => !availableSources.find((s) => s.id === source)
  );

  return (
    <div className="p-6 bg-black/40 backdrop-blur-sm rounded-xl border border-green-500/20">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-green-400 flex items-center gap-2">
            <i className="ri-newspaper-line"></i>
            News API
          </h2>
          <p className="text-xs text-green-300/70 mt-1">Análise de notícias em tempo real</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={localConfig.enabled}
            onChange={(e) => setLocalConfig({ ...localConfig, enabled: e.target.checked })}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-green-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
        </label>
      </div>

      {/* API Key */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-green-300 mb-2">
          <i className="ri-key-line"></i> API Key
        </label>
        <input
          type="password"
          value={localConfig.apiKey}
          onChange={(e) => setLocalConfig({ ...localConfig, apiKey: e.target.value })}
          placeholder="a1b2c3d4e5f6g7h8i9j0"
          className="w-full px-4 py-2 bg-black/60 border border-green-500/30 rounded-lg text-green-100 text-sm focus:outline-none focus:border-green-500"
        />
        <p className="text-xs text-green-400/60 mt-1">
          Obtenha gratuitamente em: <a href="https://newsapi.org/" target="_blank" rel="noopener noreferrer" className="underline hover:text-green-400">NewsAPI.org</a>
        </p>
      </div>

      {/* Fontes de Notícias */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-green-300 mb-2">
          <i className="ri-file-list-line"></i> Fontes de Notícias ({localConfig.sources.length})
        </label>
        <div className="grid grid-cols-2 gap-2 mb-3">
          {availableSources.map((source) => (
            <label
              key={source.id}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all ${
                localConfig.sources.includes(source.id)
                  ? 'bg-green-900/30 border-green-500/50 hover:bg-green-800/30'
                  : 'bg-black/40 border-green-500/20 hover:bg-green-900/20'
              }`}
            >
              <input
                type="checkbox"
                checked={localConfig.sources.includes(source.id)}
                onChange={() => toggleSource(source.id)}
                className="w-4 h-4 text-green-500 border-green-500/30 rounded focus:ring-green-500"
              />
              <span className="text-lg">{source.icon}</span>
              <span className="text-sm text-green-300">{source.name}</span>
            </label>
          ))}
        </div>

        {/* Adicionar Fonte Customizada */}
        <div className="flex gap-2 mb-2">
          <input
            type="text"
            value={newSource}
            onChange={(e) => setNewSource(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && addCustomSource()}
            placeholder="Adicionar fonte customizada..."
            className="flex-1 px-4 py-2 bg-black/60 border border-green-500/30 rounded-lg text-green-100 text-sm focus:outline-none focus:border-green-500"
          />
          <button
            onClick={addCustomSource}
            className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-all text-sm cursor-pointer whitespace-nowrap"
          >
            <i className="ri-add-line"></i> Adicionar
          </button>
        </div>

        {/* Fontes Customizadas */}
        {customSources.length > 0 && (
          <div className="space-y-1 max-h-24 overflow-y-auto custom-scrollbar">
            {customSources.map((source, index) => (
              <div
                key={index}
                className="flex items-center justify-between px-3 py-2 bg-green-900/20 rounded-lg border border-green-500/20"
              >
                <span className="text-sm text-green-300 font-mono">{source}</span>
                <button
                  onClick={() => removeCustomSource(source)}
                  className="text-red-400 hover:text-red-300 transition-colors cursor-pointer"
                >
                  <i className="ri-close-line"></i>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Intervalo de Atualização */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-green-300 mb-2">
          <i className="ri-time-line"></i> Intervalo de Atualização: {localConfig.updateInterval}s
        </label>
        <input
          type="range"
          min="60"
          max="3600"
          step="60"
          value={localConfig.updateInterval}
          onChange={(e) => setLocalConfig({ ...localConfig, updateInterval: parseInt(e.target.value) })}
          className="w-full h-2 bg-green-900/30 rounded-lg appearance-none cursor-pointer slider-green"
        />
        <div className="flex justify-between text-xs text-green-400/60 mt-1">
          <span>1 min</span>
          <span>{Math.floor(localConfig.updateInterval / 60)} min</span>
          <span>60 min</span>
        </div>
      </div>

      {/* Info */}
      <div className="mb-4 p-3 bg-green-900/10 rounded-lg border border-green-500/20">
        <p className="text-xs text-green-400 flex items-start gap-2">
          <i className="ri-information-line text-lg"></i>
          <span>
            O sistema vai analisar notícias das fontes selecionadas a cada <strong>{Math.floor(localConfig.updateInterval / 60)} minutos</strong> e usar IA para detectar impactos no mercado.
          </span>
        </p>
      </div>

      {/* Ações */}
      <div className="flex gap-3">
        <button
          onClick={testNewsAPI}
          disabled={!backendOnline || isTesting}
          className={`flex-1 py-2 rounded-lg transition-all text-sm cursor-pointer whitespace-nowrap flex items-center justify-center gap-2 ${
            backendOnline && !isTesting
              ? 'bg-green-900/50 hover:bg-green-800/50 text-green-300 border border-green-500/30'
              : 'bg-gray-700 text-gray-400 cursor-not-allowed'
          }`}
        >
          {isTesting ? (
            <>
              <i className="ri-loader-4-line animate-spin"></i>
              Testando...
            </>
          ) : (
            <>
              <i className="ri-test-tube-line"></i>
              Testar API
            </>
          )}
        </button>
        <button
          onClick={handleSave}
          disabled={!backendOnline}
          className={`flex-1 py-2 rounded-lg transition-all text-sm cursor-pointer whitespace-nowrap flex items-center justify-center gap-2 ${
            backendOnline
              ? 'bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white shadow-lg shadow-green-500/30'
              : 'bg-gray-700 text-gray-400 cursor-not-allowed'
          }`}
        >
          <i className="ri-save-line"></i>
          Guardar Configurações
        </button>
      </div>

      {!backendOnline && (
        <p className="text-xs text-orange-400 mt-2 text-center">
          ⚠️ Backend offline. As configurações não serão guardadas.
        </p>
      )}
    </div>
  );
};

export default NewsAPIConfig;
