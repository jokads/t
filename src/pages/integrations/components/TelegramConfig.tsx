import React, { useState } from 'react';
import { apiPost } from '../../../utils/api';

interface TelegramConfigProps {
  config: {
    enabled: boolean;
    botToken: string;
    chatIds: string[];
    notifications: {
      trades: boolean;
      dailyReport: boolean;
      losses: boolean;
      gains: boolean;
    };
  };
  onSave: (config: any) => void;
  backendOnline: boolean;
}

const TelegramConfig: React.FC<TelegramConfigProps> = ({ config, onSave, backendOnline }) => {
  const [localConfig, setLocalConfig] = useState(config);
  const [newChatId, setNewChatId] = useState('');
  const [testMessage, setTestMessage] = useState('');
  const [isTesting, setIsTesting] = useState(false);
  const [isSending, setIsSending] = useState(false);

  // Testar conexão do Telegram
  const testTelegram = async () => {
    if (!localConfig.botToken) {
      alert('⚠️ Por favor, insira o Bot Token primeiro!');
      return;
    }

    setIsTesting(true);
    try {
      const response = await apiPost<any>('/api/integrations/telegram/test', {
        botToken: localConfig.botToken,
        chatIds: localConfig.chatIds,
      });

      if (response && !response.error) {
        alert(`✅ Teste bem-sucedido!\n\nBot: ${response.botName}\nStatus: ${response.status}\nMensagem enviada para ${response.chatIds?.length || 0} chat(s).`);
      } else {
        alert('❌ Teste falhou: ' + (response?.error || 'Erro desconhecido'));
      }
    } catch (error) {
      console.error('❌ Erro ao testar Telegram:', error);
      alert('❌ Erro ao testar. Verifique se o backend está ativo.');
    } finally {
      setIsTesting(false);
    }
  };

  // Enviar mensagem manual
  const sendManualMessage = async () => {
    if (!testMessage.trim()) {
      alert('⚠️ Por favor, escreva uma mensagem primeiro!');
      return;
    }

    if (!localConfig.botToken || localConfig.chatIds.length === 0) {
      alert('⚠️ Configure o Bot Token e adicione pelo menos 1 Chat ID!');
      return;
    }

    setIsSending(true);
    try {
      const response = await apiPost<any>('/api/integrations/telegram/send', {
        botToken: localConfig.botToken,
        chatIds: localConfig.chatIds,
        message: testMessage,
      });

      if (response && !response.error) {
        alert(`✅ Mensagem enviada com sucesso para ${response.sentTo || localConfig.chatIds.length} chat(s)!`);
        setTestMessage('');
      } else {
        alert('❌ Erro ao enviar: ' + (response?.error || 'Erro desconhecido'));
      }
    } catch (error) {
      console.error('❌ Erro ao enviar mensagem:', error);
      alert('❌ Erro ao enviar. Verifique se o backend está ativo.');
    } finally {
      setIsSending(false);
    }
  };

  // Adicionar Chat ID
  const addChatId = () => {
    if (!newChatId.trim()) return;
    if (localConfig.chatIds.includes(newChatId.trim())) {
      alert('⚠️ Este Chat ID já está na lista!');
      return;
    }
    setLocalConfig({
      ...localConfig,
      chatIds: [...localConfig.chatIds, newChatId.trim()],
    });
    setNewChatId('');
  };

  // Remover Chat ID
  const removeChatId = (chatId: string) => {
    setLocalConfig({
      ...localConfig,
      chatIds: localConfig.chatIds.filter((id) => id !== chatId),
    });
  };

  // Guardar configurações
  const handleSave = () => {
    if (localConfig.enabled && !localConfig.botToken) {
      alert('⚠️ Por favor, insira o Bot Token antes de ativar!');
      return;
    }
    if (localConfig.enabled && localConfig.chatIds.length === 0) {
      alert('⚠️ Adicione pelo menos 1 Chat ID antes de ativar!');
      return;
    }
    onSave(localConfig);
  };

  return (
    <div className="p-6 bg-black/40 backdrop-blur-sm rounded-xl border border-cyan-500/20">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-cyan-400 flex items-center gap-2">
            <i className="ri-telegram-line"></i>
            Telegram Bot
          </h2>
          <p className="text-xs text-cyan-300/70 mt-1">Notificações e alertas em tempo real</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={localConfig.enabled}
            onChange={(e) => setLocalConfig({ ...localConfig, enabled: e.target.checked })}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-cyan-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-500"></div>
        </label>
      </div>

      {/* Bot Token */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-cyan-300 mb-2">
          <i className="ri-key-line"></i> Bot Token
        </label>
        <input
          type="password"
          value={localConfig.botToken}
          onChange={(e) => setLocalConfig({ ...localConfig, botToken: e.target.value })}
          placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
          className="w-full px-4 py-2 bg-black/60 border border-cyan-500/30 rounded-lg text-cyan-100 text-sm focus:outline-none focus:border-cyan-500"
        />
        <p className="text-xs text-cyan-400/60 mt-1">
          Obtenha em: <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer" className="underline hover:text-cyan-400">@BotFather</a>
        </p>
      </div>

      {/* Chat IDs */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-cyan-300 mb-2">
          <i className="ri-chat-1-line"></i> Chat IDs ({localConfig.chatIds.length})
        </label>
        <div className="flex gap-2 mb-2">
          <input
            type="text"
            value={newChatId}
            onChange={(e) => setNewChatId(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && addChatId()}
            placeholder="123456789 ou @username"
            className="flex-1 px-4 py-2 bg-black/60 border border-cyan-500/30 rounded-lg text-cyan-100 text-sm focus:outline-none focus:border-cyan-500"
          />
          <button
            onClick={addChatId}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-all text-sm cursor-pointer whitespace-nowrap"
          >
            <i className="ri-add-line"></i> Adicionar
          </button>
        </div>
        {localConfig.chatIds.length > 0 ? (
          <div className="space-y-1 max-h-32 overflow-y-auto custom-scrollbar">
            {localConfig.chatIds.map((chatId, index) => (
              <div
                key={index}
                className="flex items-center justify-between px-3 py-2 bg-cyan-900/20 rounded-lg border border-cyan-500/20"
              >
                <span className="text-sm text-cyan-300 font-mono">{chatId}</span>
                <button
                  onClick={() => removeChatId(chatId)}
                  className="text-red-400 hover:text-red-300 transition-colors cursor-pointer"
                >
                  <i className="ri-close-line"></i>
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-cyan-400/60 italic">Nenhum Chat ID adicionado</p>
        )}
        <p className="text-xs text-cyan-400/60 mt-1">
          Para obter seu Chat ID: <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer" className="underline hover:text-cyan-400">@userinfobot</a>
        </p>
      </div>

      {/* Notificações */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-cyan-300 mb-2">
          <i className="ri-notification-line"></i> Notificações Automáticas
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="flex items-center gap-2 px-3 py-2 bg-black/40 rounded-lg border border-cyan-500/20 cursor-pointer hover:bg-cyan-900/20 transition-colors">
            <input
              type="checkbox"
              checked={localConfig.notifications.trades}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  notifications: { ...localConfig.notifications, trades: e.target.checked },
                })
              }
              className="w-4 h-4 text-cyan-500 border-cyan-500/30 rounded focus:ring-cyan-500"
            />
            <span className="text-sm text-cyan-300">Trades</span>
          </label>
          <label className="flex items-center gap-2 px-3 py-2 bg-black/40 rounded-lg border border-cyan-500/20 cursor-pointer hover:bg-cyan-900/20 transition-colors">
            <input
              type="checkbox"
              checked={localConfig.notifications.dailyReport}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  notifications: { ...localConfig.notifications, dailyReport: e.target.checked },
                })
              }
              className="w-4 h-4 text-cyan-500 border-cyan-500/30 rounded focus:ring-cyan-500"
            />
            <span className="text-sm text-cyan-300">Relatório Diário</span>
          </label>
          <label className="flex items-center gap-2 px-3 py-2 bg-black/40 rounded-lg border border-cyan-500/20 cursor-pointer hover:bg-cyan-900/20 transition-colors">
            <input
              type="checkbox"
              checked={localConfig.notifications.losses}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  notifications: { ...localConfig.notifications, losses: e.target.checked },
                })
              }
              className="w-4 h-4 text-cyan-500 border-cyan-500/30 rounded focus:ring-cyan-500"
            />
            <span className="text-sm text-cyan-300">Perdas</span>
          </label>
          <label className="flex items-center gap-2 px-3 py-2 bg-black/40 rounded-lg border border-cyan-500/20 cursor-pointer hover:bg-cyan-900/20 transition-colors">
            <input
              type="checkbox"
              checked={localConfig.notifications.gains}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  notifications: { ...localConfig.notifications, gains: e.target.checked },
                })
              }
              className="w-4 h-4 text-cyan-500 border-cyan-500/30 rounded focus:ring-cyan-500"
            />
            <span className="text-sm text-cyan-300">Ganhos</span>
          </label>
        </div>
      </div>

      {/* Enviar Mensagem Manual */}
      <div className="mb-4 p-4 bg-cyan-900/10 rounded-lg border border-cyan-500/20">
        <label className="block text-sm font-medium text-cyan-300 mb-2">
          <i className="ri-send-plane-line"></i> Enviar Mensagem Teste
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={testMessage}
            onChange={(e) => setTestMessage(e.target.value)}
            placeholder="Digite sua mensagem aqui..."
            className="flex-1 px-4 py-2 bg-black/60 border border-cyan-500/30 rounded-lg text-cyan-100 text-sm focus:outline-none focus:border-cyan-500"
            onKeyPress={(e) => e.key === 'Enter' && sendManualMessage()}
          />
          <button
            onClick={sendManualMessage}
            disabled={!backendOnline || isSending}
            className={`px-4 py-2 rounded-lg transition-all text-sm cursor-pointer whitespace-nowrap flex items-center gap-2 ${
              backendOnline && !isSending
                ? 'bg-cyan-600 hover:bg-cyan-500 text-white'
                : 'bg-gray-700 text-gray-400 cursor-not-allowed'
            }`}
          >
            {isSending ? (
              <>
                <i className="ri-loader-4-line animate-spin"></i>
                Enviando...
              </>
            ) : (
              <>
                <i className="ri-send-plane-fill"></i>
                Enviar
              </>
            )}
          </button>
        </div>
      </div>

      {/* Ações */}
      <div className="flex gap-3">
        <button
          onClick={testTelegram}
          disabled={!backendOnline || isTesting}
          className={`flex-1 py-2 rounded-lg transition-all text-sm cursor-pointer whitespace-nowrap flex items-center justify-center gap-2 ${
            backendOnline && !isTesting
              ? 'bg-cyan-900/50 hover:bg-cyan-800/50 text-cyan-300 border border-cyan-500/30'
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
              Testar Conexão
            </>
          )}
        </button>
        <button
          onClick={handleSave}
          disabled={!backendOnline}
          className={`flex-1 py-2 rounded-lg transition-all text-sm cursor-pointer whitespace-nowrap flex items-center justify-center gap-2 ${
            backendOnline
              ? 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white shadow-lg shadow-cyan-500/30'
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

export default TelegramConfig;
