
import React, { useState } from 'react';

interface PromptTemplate {
  id: string;
  title: string;
  description: string;
  prompt: string;
  category: 'trading' | 'analysis' | 'strategy' | 'risk' | 'general';
  icon: string;
  color: string;
  variables?: string[];
}

interface PromptTemplatesProps {
  onSelectPrompt: (prompt: string) => void;
  selectedModel: string;
}

const PromptTemplates: React.FC<PromptTemplatesProps> = ({ onSelectPrompt, selectedModel }) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [customPrompt, setCustomPrompt] = useState('');
  const [showCustomEditor, setShowCustomEditor] = useState(false);

  const templates: PromptTemplate[] = [
    {
      id: '1',
      title: 'Análise de Estratégia',
      description: 'Analisa performance e sugere otimizações para estratégias de trading',
      prompt: 'Analise a performance da minha estratégia de trading atual. Considere os seguintes fatores: drawdown máximo, taxa de acerto, profit factor e Sharpe ratio. Forneça sugestões específicas de otimização baseadas nos dados históricos.',
      category: 'strategy',
      icon: 'ri-line-chart-line',
      color: 'from-blue-500 to-cyan-500'
    },
    {
      id: '2',
      title: 'Gestão de Risco',
      description: 'Avalia e otimiza configurações de gestão de risco',
      prompt: 'Reveja as minhas configurações atuais de gestão de risco. Analise o position sizing, stop loss, take profit e correlação entre posições. Sugira melhorias para reduzir o risco total do portfólio mantendo a rentabilidade.',
      category: 'risk',
      icon: 'ri-shield-check-line',
      color: 'from-red-500 to-pink-500'
    },
    {
      id: '3',
      title: 'Análise de Mercado',
      description: 'Análise técnica e fundamental do mercado atual',
      prompt: 'Faça uma análise completa do mercado atual. Inclua análise técnica dos principais pares de moedas, análise de sentimento, eventos económicos importantes e previsões de curto/médio prazo. Destaque oportunidades e riscos.',
      category: 'analysis',
      icon: 'ri-global-line',
      color: 'from-green-500 to-emerald-500'
    },
    {
      id: '4',
      title: 'Otimização de Parâmetros',
      description: 'Otimiza parâmetros de indicadores técnicos',
      prompt: 'Ajude-me a otimizar os parâmetros dos meus indicadores técnicos (RSI, MACD, EMA, Bollinger Bands). Baseie-se no timeframe que uso, volatilidade do mercado e estilo de trading. Explique o raciocínio por trás de cada sugestão.',
      category: 'strategy',
      icon: 'ri-settings-3-line',
      color: 'from-purple-500 to-violet-500'
    },
    {
      id: '5',
      title: 'Diagnóstico de Performance',
      description: 'Diagnóstica problemas na performance do bot',
      prompt: 'Analise os logs e métricas do meu trading bot. Identifique possíveis problemas de performance, latência, execução de ordens ou bugs no código. Sugira soluções técnicas específicas para melhorar a eficiência.',
      category: 'analysis',
      icon: 'ri-bug-line',
      color: 'from-yellow-500 to-orange-500'
    },
    {
      id: '6',
      title: 'Backtesting Avançado',
      description: 'Configura e interpreta resultados de backtesting',
      prompt: 'Configure um backtesting robusto para a minha estratégia. Defina o período de teste, métricas de avaliação, análise de walk-forward e validação cruzada. Interprete os resultados e identifique possível overfitting.',
      category: 'strategy',
      icon: 'ri-history-line',
      color: 'from-indigo-500 to-blue-500'
    },
    {
      id: '7',
      title: 'Correlação de Ativos',
      description: 'Analisa correlação entre diferentes ativos e timeframes',
      prompt: 'Analise a correlação entre os ativos que estou a tradear. Identifique redundâncias no portfólio, diversificação insuficiente e oportunidades de hedging. Sugira ajustes para melhor distribuição de risco.',
      category: 'risk',
      icon: 'ri-links-line',
      color: 'from-teal-500 to-green-500'
    },
    {
      id: '8',
      title: 'Automação e Scripts',
      description: 'Ajuda na criação de scripts e automações',
      prompt: 'Preciso de ajuda para criar um script de automação. Descreva a funcionalidade desejada, linguagem de programação preferida e integração necessária. Forneça código limpo, comentado e com tratamento de erros.',
      category: 'general',
      icon: 'ri-code-s-slash-line',
      color: 'from-gray-500 to-slate-500'
    }
  ];

  const categories = [
    { id: 'all', name: 'Todos', icon: 'ri-apps-line', count: templates.length },
    { id: 'trading', name: 'Trading', icon: 'ri-stock-line', count: templates.filter(t => t.category === 'trading').length },
    { id: 'analysis', name: 'Análise', icon: 'ri-bar-chart-line', count: templates.filter(t => t.category === 'analysis').length },
    { id: 'strategy', name: 'Estratégia', icon: 'ri-route-line', count: templates.filter(t => t.category === 'strategy').length },
    { id: 'risk', name: 'Risco', icon: 'ri-shield-line', count: templates.filter(t => t.category === 'risk').length },
    { id: 'general', name: 'Geral', icon: 'ri-tools-line', count: templates.filter(t => t.category === 'general').length }
  ];

  const filteredTemplates = selectedCategory === 'all' 
    ? templates 
    : templates.filter(template => template.category === selectedCategory);

  const handleUseTemplate = (template: PromptTemplate) => {
    onSelectPrompt(template.prompt);
  };

  const handleCustomPrompt = () => {
    if (customPrompt.trim()) {
      onSelectPrompt(customPrompt);
      setCustomPrompt('');
      setShowCustomEditor(false);
    }
  };

  return (
    <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-700/50 rounded-2xl p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-gradient-to-br from-orange-500/20 to-red-500/20 border border-orange-500/30">
            <i className="ri-magic-line text-2xl text-orange-400"></i>
          </div>
          <div>
            <h3 className="text-xl font-black text-white">Templates de Prompts</h3>
            <p className="text-sm text-gray-400">
              Prompts otimizados para {selectedModel || 'IA'} • {filteredTemplates.length} disponíveis
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowCustomEditor(!showCustomEditor)}
          className={`px-4 py-2 rounded-xl font-bold transition-all duration-300 flex items-center gap-2 ${
            showCustomEditor
              ? 'bg-red-500/20 border border-red-500/30 text-red-400'
              : 'bg-green-500/20 border border-green-500/30 text-green-400'
          }`}
        >
          <i className={`ri-${showCustomEditor ? 'close' : 'add'}-line`}></i>
          <span className="hidden sm:inline">
            {showCustomEditor ? 'Fechar' : 'Criar Prompt'}
          </span>
        </button>
      </div>

      {/* Custom Prompt Editor */}
      {showCustomEditor && (
        <div className="mb-6 p-4 rounded-xl bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/20">
          <div className="flex items-center gap-2 mb-3">
            <i className="ri-edit-line text-purple-400"></i>
            <span className="font-bold text-white">Criar Prompt Personalizado</span>
          </div>
          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder="Escreva o seu prompt personalizado aqui. Seja específico sobre o que pretende analisar ou o tipo de ajuda que precisa..."
            className="w-full px-4 py-3 bg-gray-900/80 border border-gray-600/50 rounded-xl text-white placeholder-gray-400 resize-none focus:outline-none focus:border-purple-500/60 transition-all duration-200 scrollbar-thin scrollbar-track-gray-800 scrollbar-thumb-purple-500"
            rows={4}
          />
          <div className="flex items-center justify-between mt-3">
            <span className="text-xs text-gray-500">{customPrompt.length}/2000 caracteres</span>
            <button
              onClick={handleCustomPrompt}
              disabled={!customPrompt.trim()}
              className={`px-4 py-2 rounded-lg font-bold transition-all duration-200 ${
                customPrompt.trim()
                  ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:scale-105'
                  : 'bg-gray-700/50 text-gray-500 cursor-not-allowed'
              }`}
            >
              <i className="ri-send-plane-line mr-2"></i>
              Usar Prompt
            </button>
          </div>
        </div>
      )}

      {/* Category Filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        {categories.map((category) => (
          <button
            key={category.id}
            onClick={() => setSelectedCategory(category.id)}
            className={`px-4 py-2 rounded-xl font-bold transition-all duration-200 flex items-center gap-2 ${
              selectedCategory === category.id
                ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white scale-105'
                : 'bg-gray-800/50 border border-gray-600/50 text-gray-300 hover:bg-purple-500/20 hover:border-purple-500/30'
            }`}
          >
            <i className={`${category.icon} text-sm`}></i>
            <span>{category.name}</span>
            <div className="px-2 py-0.5 rounded-lg bg-white/10 text-xs">
              {category.count}
            </div>
          </button>
        ))}
      </div>

      {/* Templates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredTemplates.map((template) => (
          <div
            key={template.id}
            className="bg-gradient-to-br from-gray-800/80 to-gray-700/80 border border-gray-600/50 rounded-xl p-4 hover:border-purple-500/40 hover:scale-[1.02] transition-all duration-300 group cursor-pointer"
            onClick={() => handleUseTemplate(template)}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg bg-gradient-to-r ${template.color}/20 border border-current/30 text-transparent bg-clip-text bg-gradient-to-r ${template.color}`}>
                  <i className={`${template.icon} text-lg`} style={{
                    background: `linear-gradient(to right, ${template.color.split(' ')[1]}, ${template.color.split(' ')[3]})`,
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent'
                  }}></i>
                </div>
                <div>
                  <h4 className="font-bold text-white group-hover:text-purple-300 transition-colors">
                    {template.title}
                  </h4>
                  <span className="text-xs px-2 py-1 rounded-lg bg-gray-700/50 text-gray-400 capitalize">
                    {template.category}
                  </span>
                </div>
              </div>
              <i className="ri-arrow-right-line text-gray-400 group-hover:text-purple-400 group-hover:translate-x-1 transition-all duration-300"></i>
            </div>

            <p className="text-sm text-gray-400 mb-4 leading-relaxed">
              {template.description}
            </p>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <i className="ri-character-recognition-line text-xs text-blue-400"></i>
                <span className="text-xs text-gray-500">
                  {template.prompt.length} caracteres
                </span>
              </div>
              <button className="px-3 py-1 rounded-lg bg-purple-500/20 border border-purple-500/30 text-purple-400 text-xs font-bold hover:bg-purple-500/30 transition-all duration-200">
                Usar Template
              </button>
            </div>

            {/* Preview do prompt (primeiras palavras) */}
            <div className="mt-3 p-2 rounded-lg bg-gray-900/50 border border-gray-700/30">
              <p className="text-xs text-gray-500 italic">
                "{template.prompt.substring(0, 100)}..."
              </p>
            </div>
          </div>
        ))}
      </div>

      {filteredTemplates.length === 0 && (
        <div className="text-center py-12">
          <i className="ri-search-line text-4xl text-gray-500 mb-4"></i>
          <h4 className="text-lg font-bold text-gray-400 mb-2">Nenhum template encontrado</h4>
          <p className="text-sm text-gray-500">
            Tente selecionar uma categoria diferente ou criar um prompt personalizado.
          </p>
        </div>
      )}

      {/* Quick Stats */}
      <div className="mt-6 p-4 rounded-xl bg-gradient-to-r from-gray-800/50 to-gray-700/50 border border-gray-600/30">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-black text-purple-400">{templates.length}</div>
            <div className="text-xs text-gray-400">Templates</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-black text-blue-400">{categories.length - 1}</div>
            <div className="text-xs text-gray-400">Categorias</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-black text-green-400">
              {Math.floor(templates.reduce((acc, t) => acc + t.prompt.length, 0) / templates.length)}
            </div>
            <div className="text-xs text-gray-400">Chars Médio</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-black text-orange-400">
              {selectedModel ? 'ON' : 'OFF'}
            </div>
            <div className="text-xs text-gray-400">Modelo IA</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PromptTemplates;
