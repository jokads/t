import { useState } from 'react';

interface AIModel {
  name: string;
  size: string;
  status: 'loaded' | 'unloaded' | 'loading';
  path: string;
  type: string;
}

export default function ModelManager() {
  const [models, setModels] = useState<AIModel[]>([
    { name: 'Llama-3.2-1B-Instruct-Q4_0.gguf', size: '1.2 GB', status: 'loaded', path: '/bot-mt5/models/gpt4all/', type: 'GPT4All' },
    { name: 'Llama-3.2-3B-Instruct-Q4_0.gguf', size: '2.8 GB', status: 'loaded', path: '/bot-mt5/models/gpt4all/', type: 'GPT4All' },
    { name: 'Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf', size: '4.1 GB', status: 'loaded', path: '/bot-mt5/models/gpt4all/', type: 'GPT4All' },
    { name: 'orca-mini-3b-gguf2-q4_0.gguf', size: '1.9 GB', status: 'unloaded', path: '/bot-mt5/models/gpt4all/', type: 'GPT4All' },
    { name: 'Phi-3-mini-4k-instruct.Q4_0.gguf', size: '2.3 GB', status: 'loaded', path: '/bot-mt5/models/gpt4all/', type: 'GPT4All' },
    { name: 'qwen2-1_5b-instruct-q4_0.gguf', size: '1.5 GB', status: 'loaded', path: '/bot-mt5/models/gpt4all/', type: 'GPT4All' }
  ]);

  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

  const handleToggleModel = (index: number) => {
    setModels(prev => prev.map((model, i) => {
      if (i === index) {
        return {
          ...model,
          status: model.status === 'loaded' ? 'unloaded' : 'loading'
        };
      }
      return model;
    }));

    setTimeout(() => {
      setModels(prev => prev.map((model, i) => {
        if (i === index) {
          return {
            ...model,
            status: model.status === 'loading' ? 'loaded' : 'unloaded'
          };
        }
        return model;
      }));
    }, 2000);
  };

  const handleUpload = () => {
    setIsUploading(true);
    setUploadProgress(0);
    const interval = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsUploading(false);
          return 100;
        }
        return prev + 10;
      });
    }, 300);
  };

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold gradient-text">Gestor de Modelos AI</h3>
        <button 
          onClick={handleUpload}
          disabled={isUploading}
          className="px-4 py-2 bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <i className="ri-upload-cloud-line text-base w-5 h-5 flex items-center justify-center"></i>
          <span>Upload .gguf</span>
        </button>
      </div>

      {isUploading && (
        <div className="mb-6 p-4 bg-purple-900/20 rounded-lg border border-purple-500/20">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-white">A fazer upload...</span>
            <span className="text-sm text-purple-300">{uploadProgress}%</span>
          </div>
          <div className="w-full bg-purple-900/50 rounded-full h-2">
            <div 
              className="bg-gradient-to-r from-orange-500 to-red-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {models.map((model, index) => (
          <div key={index} className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/10">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <i className="ri-brain-line text-orange-400 text-xl"></i>
                  <div>
                    <h4 className="text-sm font-semibold text-white">{model.name}</h4>
                    <p className="text-xs text-purple-300 mt-1">{model.path}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 mt-3">
                  <span className="text-xs text-purple-300">
                    <i className="ri-file-line mr-1"></i>
                    {model.size}
                  </span>
                  <span className="text-xs text-purple-300">
                    <i className="ri-price-tag-3-line mr-1"></i>
                    {model.type}
                  </span>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    model.status === 'loaded' ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
                    model.status === 'loading' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
                    'bg-slate-500/20 text-slate-400 border border-slate-500/30'
                  }`}>
                    {model.status === 'loaded' ? 'Carregado' : model.status === 'loading' ? 'A carregar...' : 'Descarregado'}
                  </span>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleToggleModel(index)}
                  disabled={model.status === 'loading'}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer ${
                    model.status === 'loaded' 
                      ? 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30'
                      : 'bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/30'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {model.status === 'loaded' ? 'Descarregar' : model.status === 'loading' ? 'A carregar...' : 'Carregar'}
                </button>
                <button className="w-10 h-10 flex items-center justify-center bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg transition-all cursor-pointer">
                  <i className="ri-more-2-fill text-base"></i>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 pt-6 border-t border-purple-500/20">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold text-white">{models.length}</p>
            <p className="text-xs text-purple-300 mt-1">Total Modelos</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green-400">{models.filter(m => m.status === 'loaded').length}</p>
            <p className="text-xs text-purple-300 mt-1">Carregados</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-orange-400">13.8 GB</p>
            <p className="text-xs text-purple-300 mt-1">Espaço Usado</p>
          </div>
        </div>
      </div>
    </div>
  );
}
