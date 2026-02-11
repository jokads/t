import { useState, useEffect } from 'react';

interface APISettingsProps {
  environment: {
    frontend: boolean;
    backend: boolean;
    pythonCore: boolean;
    basePath: string;
    modelsPath: string;
  };
  aiModels: any[];
}

export default function APISettings({ environment, aiModels }: APISettingsProps) {
  const [showBotToken, setShowBotToken] = useState(false);
  const [showTelegramToken, setShowTelegramToken] = useState(false);
  const [showNewsApiKey, setShowNewsApiKey] = useState(false);

  // Suas APIs reais já configuradas
  const [telegramBotToken, setTelegramBotToken] = useState('7536817878:AAFiJY7VXzRW86oEk_o2b988X1bM859byc4');
  const [telegramChatId, setTelegramChatId] = useState('7343664374');
  const [newsApiKey, setNewsApiKey] = useState('56767a95-502d-4686-90f7-4d0d2df29e13');
  const [botToken, setBotToken] = useState('bot_tk_a1b2c3d4e5f6g7h8i9j0');
  
  const [telegramStatus, setTelegramStatus] = useState<'connected' | 'disconnected' | 'testing'>('disconnected');
  const [newsApiStatus, setNewsApiStatus] = useState<'connected' | 'disconnected' | 'testing'>('disconnected');
  const [saved, setSaved] = useState(false);

  // Verificar conexões a cada 30s
  useEffect(() => {
    if (environment.backend) {
      checkConnections();
      const interval = setInterval(checkConnections, 30000);
      return () => clearInterval(interval);
    }
  }, [environment.backend]);

  const checkConnections = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/integrations/status');
      if (response.ok) {
        const data = await response.json();
        setTelegramStatus(data.telegram?.connected ? 'connected' : 'disconnected');
        setNewsApiStatus(data.news_api?.connected ? 'connected' : 'disconnected');
      }
    } catch (error) {
      console.log('Backend offline, usando status local');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Token copiado para a área de transferência!');
  };

  const regenerateToken = () => {
    const newToken = 'bot_tk_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    setBotToken(newToken);
    alert('Token regenerado com sucesso!');
  };

  const testTelegram = async () => {
    setTelegramStatus('testing');
    try {
      const response = await fetch('http://localhost:8000/api/telegram/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: telegramBotToken, chatId: telegramChatId })
      });
      if (response.ok) {
        setTelegramStatus('connected');
        alert('✅ Telegram conectado com sucesso! Verifique seu celular.');
      } else {
        setTelegramStatus('disconnected');
        alert('❌ Erro ao conectar ao Telegram. Verifique as credenciais.');
      }
    } catch (error) {
      setTelegramStatus('disconnected');
      alert('❌ Erro ao conectar ao Telegram. Backend offline.');
    }
  };

  const testNewsApi = async () => {
    setNewsApiStatus('testing');
    try {
      const response = await fetch('http://localhost:8000/api/news/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apiKey: newsApiKey })
      });
      if (response.ok) {
        setNewsApiStatus('connected');
        alert('✅ News API conectada com sucesso!');
      } else {
        setNewsApiStatus('disconnected');
        alert('❌ Erro ao conectar à News API. Verifique a chave.');
      }
    } catch (error) {
      setNewsApiStatus('disconnected');
      alert('❌ Erro ao conectar à News API. Backend offline.');
    }
  };

  const handleSave = async () => {
    try {
      if (environment.backend) {
        const response = await fetch('http://localhost:8000/api/settings/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            telegramBotToken,
            telegramChatId,
            newsApiKey,
            botToken
          })
        });
        if (response.ok) {
          setSaved(true);
          setTimeout(() => setSaved(false), 3000);
          // Salvar também no .env
          await fetch('http://localhost:8000/api/settings/save-env', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              TELEGRAM_BOT_TOKEN: telegramBotToken,
              TELEGRAM_CHAT_ID: telegramChatId,
              NEWS_API_KEY: newsApiKey
            })
          });
          alert('✅ Configurações guardadas com sucesso!\n\nAs APIs foram salvas no .env para uso em produção.');
        }
      } else {
        localStorage.setItem('apiSettings', JSON.stringify({
          telegramBotToken,
          telegramChatId,
          newsApiKey,
          botToken
        }));
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        alert('✅ Configurações guardadas localmente! Inicie o backend para salvar no .env.');
      }
    } catch (error) {
      console.error('Erro ao salvar:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Telegram Bot */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <i className="ri-telegram-line text-cyan-400"></i>
            Telegram Bot
          </h3>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              telegramStatus === 'connected' ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
              telegramStatus === 'testing' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
              'bg-red-500/20 text-red-400 border border-red-500/30'
            }`}>
              {telegramStatus === 'connected' ? '🟢 Conectado' : 
               telegramStatus === 'testing' ? '🟡 Testando...' : 
               '🔴 Desconectado'}
            </span>
          </div>
        </div>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Bot Token</label>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <input
                  type={showTelegramToken ? 'text' : 'password'}
                  value={telegramBotToken}
                  onChange={(e) => setTelegramBotToken(e.target.value)}
                  className="w-full px-4 py-2 pr-10 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowTelegramToken(!showTelegramToken)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-purple-400 hover:text-purple-300 cursor-pointer"
                >
                  <i className={`${showTelegramToken ? 'ri-eye-off-line' : 'ri-eye-line'} text-base`}></i>
                </button>
              </div>
              <button
                onClick={() => copyToClipboard(telegramBotToken)}
                className="w-10 h-10 flex items-center justify-center bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg transition-all border border-purple-500/30 cursor-pointer"
                title="Copiar"
              >
                <i className="ri-file-copy-line text-base"></i>
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Chat ID</label>
            <input
              type="text"
              value={telegramChatId}
              onChange={(e) => setTelegramChatId(e.target.value)}
              className="w-full px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
            />
          </div>

          <button
            onClick={testTelegram}
            disabled={!environment.backend || telegramStatus === 'testing'}
            className="w-full px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-cyan-500/30 whitespace-nowrap cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {telegramStatus === 'testing' ? (
              <span className="flex items-center justify-center gap-2">
                <i className="ri-loader-4-line animate-spin"></i>
                Testando...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <i className="ri-send-plane-line"></i>
                Enviar Mensagem de Teste
              </span>
            )}
          </button>
        </div>
      </div>

      {/* News API */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <i className="ri-newspaper-line text-orange-400"></i>
            News API
          </h3>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              newsApiStatus === 'connected' ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
              newsApiStatus === 'testing' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
              'bg-red-500/20 text-red-400 border border-red-500/30'
            }`}>
              {newsApiStatus === 'connected' ? '🟢 Conectado' : 
               newsApiStatus === 'testing' ? '🟡 Testando...' : 
               '🔴 Desconectado'}
            </span>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">API Key</label>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <input
                  type={showNewsApiKey ? 'text' : 'password'}
                  value={newsApiKey}
                  onChange={(e) => setNewsApiKey(e.target.value)}
                  className="w-full px-4 py-2 pr-10 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowNewsApiKey(!showNewsApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-purple-400 hover:text-purple-300 cursor-pointer"
                >
                  <i className={`${showNewsApiKey ? 'ri-eye-off-line' : 'ri-eye-line'} text-base`}></i>
                </button>
              </div>
              <button
                onClick={() => copyToClipboard(newsApiKey)}
                className="w-10 h-10 flex items-center justify-center bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg transition-all border border-purple-500/30 cursor-pointer"
                title="Copiar"
              >
                <i className="ri-file-copy-line text-base"></i>
              </button>
            </div>
          </div>

          <button
            onClick={testNewsApi}
            disabled={!environment.backend || newsApiStatus === 'testing'}
            className="w-full px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-orange-500/30 whitespace-nowrap cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {newsApiStatus === 'testing' ? (
              <span className="flex items-center justify-center gap-2">
                <i className="ri-loader-4-line animate-spin"></i>
                Testando...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <i className="ri-checkbox-circle-line"></i>
                Testar Conexão
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Token de Autenticação do Bot */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-key-line text-pink-400"></i>
          Token de Autenticação do Bot
        </h3>
        <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
          <p className="text-xs text-purple-400 mb-3">Use este token para autenticar o bot ao enviar dados para o dashboard</p>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <input
                type={showBotToken ? 'text' : 'password'}
                value={botToken}
                readOnly
                className="w-full px-4 py-2 pr-10 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm font-mono"
              />
              <button
                type="button"
                onClick={() => setShowBotToken(!showBotToken)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-purple-400 hover:text-purple-300 cursor-pointer"
              >
                <i className={`${showBotToken ? 'ri-eye-off-line' : 'ri-eye-line'} text-base`}></i>
              </button>
            </div>
            <button
              onClick={() => copyToClipboard(botToken)}
              className="w-10 h-10 flex items-center justify-center bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg transition-all border border-purple-500/30 cursor-pointer"
              title="Copiar"
            >
              <i className="ri-file-copy-line text-base"></i>
            </button>
          </div>
          <button 
            onClick={regenerateToken}
            className="mt-3 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-sm font-medium transition-all border border-red-500/30 whitespace-nowrap cursor-pointer"
          >
            <i className="ri-refresh-line mr-2"></i>
            Regenerar Token
          </button>
        </div>
      </div>

      {/* Endpoints da API */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-links-line text-cyan-400"></i>
          Endpoints da API
        </h3>
        <div className="space-y-3">
          <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">Push de Dados do Bot</span>
              <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded border border-green-500/30">POST</span>
            </div>
            <code className="text-xs text-purple-400 break-all">http://localhost:8000/api/push</code>
          </div>

          <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">Enviar Sinal Manual</span>
              <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded border border-green-500/30">POST</span>
            </div>
            <code className="text-xs text-purple-400 break-all">http://localhost:8000/api/send_signal</code>
          </div>

          <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">Obter Dados da Conta</span>
              <span className="px-2 py-1 bg-cyan-500/20 text-cyan-400 text-xs rounded border border-cyan-500/30">GET</span>
            </div>
            <code className="text-xs text-purple-400 break-all">http://localhost:8000/api/account</code>
          </div>

          <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">Telegram - Enviar Mensagem</span>
              <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded border border-green-500/30">POST</span>
            </div>
            <code className="text-xs text-purple-400 break-all">http://localhost:8000/api/telegram/send</code>
          </div>

          <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">News API - Obter Notícias</span>
              <span className="px-2 py-1 bg-cyan-500/20 text-cyan-400 text-xs rounded border border-cyan-500/30">GET</span>
            </div>
            <code className="text-xs text-purple-400 break-all">http://localhost:8000/api/news/latest</code>
          </div>
        </div>
      </div>

      {/* Exemplo de Payload */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-code-s-slash-line text-orange-400"></i>
          Exemplo de Payload
        </h3>
        <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
          <pre className="text-xs text-purple-300 overflow-x-auto">
{`{
  "kind": "account",
  "data": {
    "balance": 10000,
    "equity": 9950,
    "free_margin": 8000,
    "profit": -50,
    "connected": true,
    "timestamp": "2026-01-16T12:34:56Z"
  },
  "token": "${botToken}"
}`}
          </pre>
        </div>
      </div>

      {/* Botões de Ação */}
      <div className="flex gap-3">
        <button className="px-6 py-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg text-sm font-medium transition-all border border-purple-500/30 whitespace-nowrap cursor-pointer">
          Cancelar
        </button>
        <button 
          onClick={handleSave}
          className="flex-1 px-6 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-purple-500/30 whitespace-nowrap cursor-pointer"
        >
          {saved ? (
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
                Telegram: {telegramBotToken.substring(0, 15)}...
                <br />
                News API: {newsApiKey.substring(0, 15)}...
                <br />
                APIs salvas no .env para produção! ✅
              </div>
            </div>
          </div>
        </div>
      )}

      {!environment.backend && (
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <i className="ri-alert-line text-orange-400 text-xl"></i>
            <div>
              <div className="text-sm font-medium text-orange-300 mb-1">Backend Offline</div>
              <div className="text-xs text-orange-200/70">
                Inicie o backend para testar as conexões e salvar no .env:
                <br />
                <code className="text-orange-300 mt-2 block">cd C:\bot-mt5\backend && python dashboard_server.py</code>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
