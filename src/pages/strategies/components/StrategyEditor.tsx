import { useState, useRef, useEffect } from 'react';

export default function StrategyEditor() {
  const [code, setCode] = useState(`# Exemplo de Estratégia de Trading
# Esta é uma estratégia básica usando RSI

def initialize():
    """Inicializar parâmetros da estratégia"""
    self.rsi_period = 14
    self.rsi_oversold = 30
    self.rsi_overbought = 70
    self.position_size = 0.1

def on_tick(symbol, price, indicators):
    """Executado a cada tick de preço"""
    rsi = indicators['rsi'][symbol]
    
    # Sinal de compra: RSI abaixo de 30
    if rsi < self.rsi_oversold and not self.has_position(symbol):
        self.open_position(
            symbol=symbol,
            type='BUY',
            volume=self.position_size,
            sl=price * 0.98,  # Stop loss 2%
            tp=price * 1.04   # Take profit 4%
        )
        self.log(f"Sinal de COMPRA em {symbol} - RSI: {rsi}")
    
    # Sinal de venda: RSI acima de 70
    elif rsi > self.rsi_overbought and self.has_position(symbol):
        self.close_position(symbol)
        self.log(f"Fechando posição em {symbol} - RSI: {rsi}")

def on_bar_close(symbol, timeframe, bar):
    """Executado quando uma barra fecha"""
    pass

def calculate_risk():
    """Calcular risco da posição"""
    return self.position_size * 100  # Risco em percentagem
`);

  const [fileName, setFileName] = useState('rsi_strategy.py');
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [code]);

  const handleSave = () => {
    console.log('Guardar estratégia:', fileName, code);
    setShowSaveDialog(false);
  };

  const handleRunDryRun = () => {
    console.log('Executar dry-run da estratégia');
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
      <div className="p-6 border-b border-slate-700/50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">Editor de Estratégias</h2>
            <p className="text-sm text-slate-400 mt-1">Edite e teste as suas estratégias Python</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setShowSaveDialog(true)}
              className="px-4 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap cursor-pointer"
            >
              <i className="ri-save-line text-base"></i>
              <span>Guardar</span>
            </button>
            <button
              onClick={handleRunDryRun}
              className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-cyan-500/30 flex items-center gap-2 whitespace-nowrap cursor-pointer"
            >
              <i className="ri-play-line text-base"></i>
              <span>Executar Dry-Run</span>
            </button>
          </div>
        </div>
      </div>

      <div className="p-6">
        <div className="bg-slate-900 rounded-lg border border-slate-700 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-slate-800/50 border-b border-slate-700">
            <div className="flex items-center gap-2">
              <i className="ri-file-code-line text-cyan-400"></i>
              <span className="text-sm text-slate-300">{fileName}</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span>Python</span>
              <span>•</span>
              <span>{code.split('\n').length} linhas</span>
            </div>
          </div>

          <div className="relative">
            <textarea
              ref={textareaRef}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full p-4 bg-slate-900 text-slate-300 font-mono text-sm focus:outline-none resize-none"
              style={{ minHeight: '500px' }}
              spellCheck={false}
            />
            <div className="absolute top-0 left-0 p-4 pointer-events-none select-none">
              <div className="flex flex-col gap-0 text-slate-600 font-mono text-sm">
                {code.split('\n').map((_, i) => (
                  <div key={i} className="text-right pr-4" style={{ minWidth: '40px' }}>
                    {i + 1}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
            <div className="flex items-center gap-2 mb-2">
              <i className="ri-information-line text-cyan-400"></i>
              <h3 className="text-sm font-semibold text-white">Sintaxe</h3>
            </div>
            <p className="text-xs text-slate-400">Código Python válido sem erros de sintaxe</p>
          </div>

          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
            <div className="flex items-center gap-2 mb-2">
              <i className="ri-shield-check-line text-green-400"></i>
              <h3 className="text-sm font-semibold text-white">Validação</h3>
            </div>
            <p className="text-xs text-slate-400">Funções obrigatórias implementadas</p>
          </div>

          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
            <div className="flex items-center gap-2 mb-2">
              <i className="ri-test-tube-line text-orange-400"></i>
              <h3 className="text-sm font-semibold text-white">Testes</h3>
            </div>
            <p className="text-xs text-slate-400">Execute dry-run antes de ativar</p>
          </div>
        </div>
      </div>

      {showSaveDialog && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl border border-slate-700 max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-white">Guardar Estratégia</h3>
              <button
                onClick={() => setShowSaveDialog(false)}
                className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-all cursor-pointer"
              >
                <i className="ri-close-line text-xl"></i>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Nome do Ficheiro</label>
                <input
                  type="text"
                  value={fileName}
                  onChange={(e) => setFileName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  placeholder="strategy.py"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setShowSaveDialog(false)}
                  className="flex-1 px-4 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-all whitespace-nowrap cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleSave}
                  className="flex-1 px-4 py-2 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-cyan-500/30 whitespace-nowrap cursor-pointer"
                >
                  Guardar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}