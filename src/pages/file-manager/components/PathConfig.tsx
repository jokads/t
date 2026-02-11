import { useState } from 'react';

interface PathConfig {
  name: string;
  path: string;
  description: string;
  icon: string;
}

export default function PathConfig() {
  const [paths, setPaths] = useState<PathConfig[]>([
    { name: 'Strategies', path: '/bot-mt5/strategies/', description: 'Diretório de estratégias de trading', icon: 'ri-lightbulb-line' },
    { name: 'Models', path: '/bot-mt5/models/gpt4all/', description: 'Modelos AI (.gguf)', icon: 'ri-brain-line' },
    { name: 'Core', path: '/bot-mt5/core/', description: 'Módulos principais do sistema', icon: 'ri-code-box-line' },
    { name: 'Dashboard', path: '/bot-mt5/dashboard/', description: 'Ficheiros do dashboard', icon: 'ri-dashboard-line' },
    { name: 'Logs', path: '/bot-mt5/logs/', description: 'Logs do sistema', icon: 'ri-file-list-line' }
  ]);

  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  const handleEdit = (index: number) => {
    setEditingIndex(index);
    setEditValue(paths[index].path);
  };

  const handleSave = (index: number) => {
    setPaths(prev => prev.map((p, i) => i === index ? { ...p, path: editValue } : p));
    setEditingIndex(null);
  };

  const handleCancel = () => {
    setEditingIndex(null);
    setEditValue('');
  };

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold gradient-text">Configuração de Caminhos</h3>
        <button className="px-4 py-2 bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap cursor-pointer">
          <i className="ri-add-line text-base w-5 h-5 flex items-center justify-center"></i>
          <span>Adicionar</span>
        </button>
      </div>

      <div className="space-y-4">
        {paths.map((pathConfig, index) => (
          <div key={index} className="bg-purple-900/20 rounded-lg p-4 border border-purple-500/10">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center flex-shrink-0">
                <i className={`${pathConfig.icon} text-white text-xl`}></i>
              </div>
              <div className="flex-1">
                <h4 className="text-sm font-semibold text-white mb-1">{pathConfig.name}</h4>
                <p className="text-xs text-purple-300 mb-3">{pathConfig.description}</p>
                
                {editingIndex === index ? (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="flex-1 px-3 py-2 bg-purple-900/50 border border-purple-500/30 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                    <button
                      onClick={() => handleSave(index)}
                      className="px-4 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-400 rounded-lg text-sm font-medium transition-all border border-green-500/30 whitespace-nowrap cursor-pointer"
                    >
                      <i className="ri-check-line"></i>
                    </button>
                    <button
                      onClick={handleCancel}
                      className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-sm font-medium transition-all border border-red-500/30 whitespace-nowrap cursor-pointer"
                    >
                      <i className="ri-close-line"></i>
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center justify-between">
                    <code className="text-xs text-cyan-400 bg-black/30 px-3 py-1.5 rounded border border-purple-500/20 font-mono">
                      {pathConfig.path}
                    </code>
                    <button
                      onClick={() => handleEdit(index)}
                      className="px-3 py-1.5 bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg text-sm transition-all whitespace-nowrap cursor-pointer"
                    >
                      <i className="ri-edit-line mr-1"></i>
                      Editar
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 pt-6 border-t border-purple-500/20">
        <div className="flex items-start gap-3 p-4 bg-orange-500/10 rounded-lg border border-orange-500/30">
          <i className="ri-information-line text-orange-400 text-xl mt-0.5"></i>
          <div>
            <p className="text-sm text-orange-400 font-medium mb-1">Atenção</p>
            <p className="text-xs text-orange-300">Alterar caminhos requer reiniciar o AI Manager e o Trading Bot para aplicar as mudanças.</p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex gap-3">
        <button className="flex-1 px-6 py-2 bg-purple-800/50 hover:bg-purple-700/50 text-purple-200 rounded-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer">
          Cancelar
        </button>
        <button className="flex-1 px-6 py-2 bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-orange-500/30 whitespace-nowrap cursor-pointer">
          Guardar e Reiniciar
        </button>
      </div>
    </div>
  );
}
