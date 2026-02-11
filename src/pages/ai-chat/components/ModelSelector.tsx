
import React, { useState, useEffect } from 'react';

interface Model {
  name: string;
  size: string;
  type: string;
  performance: number;
  description: string;
}

interface ModelSelectorProps {
  selectedModel: string;
  onModelChange: (model: string) => void;
  availableModels: string[];
  modelsPath: string;
}

const ModelSelector: React.FC<ModelSelectorProps> = ({
  selectedModel,
  onModelChange,
  availableModels,
  modelsPath
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [modelDetails, setModelDetails] = useState<Model[]>([]);

  useEffect(() => {
    // Gerar detalhes dos modelos baseado nos modelos disponíveis
    const details = availableModels.map(model => ({
      name: model,
      size: model.includes('7B') ? '7B' : model.includes('3B') ? '3B' : '1B',
      type: model.includes('Llama') ? 'Meta' : model.includes('Mistral') ? 'Mistral AI' : 'GPT4All',
      performance: Math.floor(Math.random() * 20) + 80, // 80-100%
      description: model.includes('Llama') 
        ? 'Modelo avançado da Meta com alta performance'
        : model.includes('Mistral') 
        ? 'Modelo francês otimizado para conversas'
        : 'Modelo local otimizado para análises'
    }));
    setModelDetails(details);
  }, [availableModels]);

  const getModelIcon = (modelName: string) => {
    if (modelName.includes('Llama')) return 'ri-robot-line';
    if (modelName.includes('Mistral')) return 'ri-cpu-line';
    return 'ri-brain-line';
  };

  const getModelColor = (modelName: string) => {
    if (modelName.includes('Llama')) return 'text-blue-400';
    if (modelName.includes('Mistral')) return 'text-green-400';
    return 'text-purple-400';
  };

  const selectedModelDetail = modelDetails.find(m => m.name === selectedModel);

  return (
    <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-700/50 rounded-2xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 border border-purple-500/30">
            <i className="ri-cpu-line text-2xl text-purple-400"></i>
          </div>
          <div>
            <h3 className="text-xl font-black text-white">Seletor de Modelo IA</h3>
            <p className="text-sm text-gray-400">
              {availableModels.length} modelos disponíveis • <span className="font-mono text-purple-400">{modelsPath}</span>
            </p>
          </div>
        </div>

        {selectedModelDetail && (
          <div className="hidden md:flex items-center gap-2 px-4 py-2 rounded-xl bg-green-500/20 border border-green-500/30">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
            <span className="text-sm font-bold text-green-400">Performance: {selectedModelDetail.performance}%</span>
          </div>
        )}
      </div>

      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full px-6 py-4 rounded-xl bg-gradient-to-r from-gray-800/80 to-gray-700/80 border-2 border-gray-600/50 text-white font-bold hover:border-purple-500/60 hover:scale-[1.02] transition-all duration-300 shadow-xl flex items-center justify-between gap-4"
        >
          <div className="flex items-center gap-3">
            <i className={`${selectedModel ? getModelIcon(selectedModel) : 'ri-cpu-line'} text-xl ${selectedModel ? getModelColor(selectedModel) : 'text-gray-400'}`}></i>
            <div className="text-left">
              <div className="font-black text-lg">
                {selectedModel || 'Selecionar Modelo IA'}
              </div>
              {selectedModelDetail && (
                <div className="text-xs text-gray-400 font-normal">
                  {selectedModelDetail.type} • {selectedModelDetail.size} • {selectedModelDetail.performance}% Performance
                </div>
              )}
            </div>
          </div>
          <i className={`ri-arrow-${isOpen ? 'up' : 'down'}-s-line text-xl text-purple-400 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`}></i>
        </button>

        {isOpen && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-gray-900/95 backdrop-blur-sm border border-gray-700/50 rounded-xl shadow-2xl z-50 overflow-hidden">
            <div className="p-2 border-b border-gray-700/50 bg-gray-800/50">
              <div className="text-sm font-bold text-purple-400 px-3 py-2">
                📡 {availableModels.length} Modelos Detectados
              </div>
            </div>
            
            <div className="max-h-80 overflow-y-auto scrollbar-thin scrollbar-track-gray-800 scrollbar-thumb-purple-500">
              {modelDetails.map((model, index) => (
                <button
                  key={index}
                  onClick={() => {
                    onModelChange(model.name);
                    setIsOpen(false);
                  }}
                  className={`w-full px-4 py-4 text-left hover:bg-purple-500/10 transition-all duration-200 border-b border-gray-800/50 last:border-b-0 ${
                    selectedModel === model.name ? 'bg-purple-500/20 border-l-4 border-l-purple-500' : ''
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <i className={`${getModelIcon(model.name)} text-lg ${getModelColor(model.name)}`}></i>
                      <div>
                        <div className="font-bold text-white text-sm">
                          {model.name}
                        </div>
                        <div className="text-xs text-gray-400">
                          {model.description}
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <div className="px-2 py-1 rounded-lg bg-gray-800/80 border border-gray-600/50">
                        <span className="text-xs font-bold text-gray-300">{model.type}</span>
                      </div>
                      <div className="px-2 py-1 rounded-lg bg-blue-500/20 border border-blue-500/30">
                        <span className="text-xs font-bold text-blue-400">{model.size}</span>
                      </div>
                      <div className="px-2 py-1 rounded-lg bg-green-500/20 border border-green-500/30">
                        <span className="text-xs font-bold text-green-400">{model.performance}%</span>
                      </div>
                      
                      {selectedModel === model.name && (
                        <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse"></div>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {availableModels.length === 0 && (
              <div className="p-6 text-center">
                <i className="ri-error-warning-line text-3xl text-yellow-400 mb-2"></i>
                <div className="text-sm text-gray-400">Nenhum modelo detectado</div>
                <div className="text-xs text-gray-500 mt-1">Verifique o caminho: {modelsPath}</div>
              </div>
            )}
          </div>
        )}
      </div>

      {selectedModelDetail && (
        <div className="mt-4 p-4 rounded-xl bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <i className={`${getModelIcon(selectedModelDetail.name)} text-lg ${getModelColor(selectedModelDetail.name)}`}></i>
              <div>
                <div className="text-sm font-bold text-white">Modelo Ativo</div>
                <div className="text-xs text-gray-400">{selectedModelDetail.description}</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="px-3 py-1 rounded-lg bg-green-500/20 border border-green-500/30">
                <span className="text-xs font-bold text-green-400">PRONTO</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModelSelector;
