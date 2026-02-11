
import React, { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'ai';
  timestamp: Date;
  model?: string;
  tokens?: number;
  processingTime?: number;
  isPersistent?: boolean;
}

interface ChatInterfaceProps {
  selectedModel: string;
  onSendMessage: (message: string) => Promise<string>;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ selectedModel, onSendMessage }) => {
  // 💾 PERSISTÊNCIA TOTAL DE MENSAGENS
  const [messages, setMessages] = useState<Message[]>(() => {
    try {
      const savedMessages = localStorage.getItem('joka_chat_messages');
      const parsed = savedMessages ? JSON.parse(savedMessages) : [];
      
      if (parsed.length === 0) {
        return [{
          id: '1',
          content: '🚀 **Sistema Multi-IA JOKA Inicializado!**\n\nOlá! Sou o sistema de inteligência artificial do JOKA Trading Bot. Estou completamente operacional e pronto para:\n\n**📊 Análises Avançadas:**\n• Estratégias de trading em tempo real\n• Gestão de risco profissional\n• Análise técnica de mercados\n• Otimização de código e sistema\n\n**🤖 Modelos IA Disponíveis:**\n• 6 modelos avançados carregados\n• Respostas contextuais inteligentes\n• Análises específicas para trading\n\n**Como posso ajudar hoje?** Digite qualquer pergunta sobre trading, estratégias, risco, mercados ou código!',
          sender: 'ai',
          timestamp: new Date(),
          model: 'Sistema JOKA',
          tokens: 145,
          processingTime: 0.1,
          isPersistent: true
        }];
      }
      
      return parsed.map((msg: any) => ({
        ...msg,
        timestamp: new Date(msg.timestamp),
        isPersistent: true
      }));
    } catch {
      return [{
        id: '1',
        content: '🚀 **Sistema Multi-IA JOKA Inicializado!**\n\nOlá! Sistema operacional e pronto para análises avançadas de trading!',
        sender: 'ai',
        timestamp: new Date(),
        model: 'Sistema JOKA',
        isPersistent: true
      }];
    }
  });

  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [typingDots, setTypingDots] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 💾 SALVAR MENSAGENS AUTOMATICAMENTE
  useEffect(() => {
    try {
      localStorage.setItem('joka_chat_messages', JSON.stringify(messages));
    } catch (error) {
      console.warn('Erro ao salvar mensagens:', error);
    }
  }, [messages]);

  // 📜 SCROLL INTELIGENTE
  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // ⌨️ EFEITO DE DIGITAÇÃO ANIMADO
  useEffect(() => {
    if (isTyping) {
      const interval = setInterval(() => {
        setTypingDots(prev => {
          if (prev === '...') return '.';
          return prev + '.';
        });
      }, 500);
      return () => clearInterval(interval);
    } else {
      setTypingDots('');
    }
  }, [isTyping]);

  // 🎯 LISTENER PARA PROMPTS EXTERNOS
  useEffect(() => {
    const handlePromptSelect = (event: any) => {
      if (event.detail && typeof event.detail === 'string') {
        setInputMessage(event.detail);
        inputRef.current?.focus();
      }
    };

    window.addEventListener('selectPrompt', handlePromptSelect);
    return () => window.removeEventListener('selectPrompt', handlePromptSelect);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 🚀 ENVIO DE MENSAGEM ULTRA ROBUSTO
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    if (!selectedModel) {
      // Adicionar mensagem de aviso
      const warningMessage: Message = {
        id: Date.now().toString(),
        content: '⚠️ **Modelo não selecionado!**\n\nPor favor, selecione um modelo IA no seletor acima antes de enviar mensagens. Todos os 6 modelos estão disponíveis e prontos para uso!',
        sender: 'ai',
        timestamp: new Date(),
        model: 'Sistema',
        isPersistent: true
      };
      setMessages(prev => [...prev, warningMessage]);
      return;
    }

    const userMessageText = inputMessage.trim();
    
    // 📤 CRIAR MENSAGEM DO UTILIZADOR
    const userMessage: Message = {
      id: Date.now().toString(),
      content: userMessageText,
      sender: 'user',
      timestamp: new Date(),
      isPersistent: true
    };

    // 📥 ADICIONAR MENSAGEM IMEDIATAMENTE (NUNCA DESAPARECE)
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setIsTyping(true);

    try {
      const startTime = Date.now();
      
      // 🤖 OBTER RESPOSTA DA IA
      const response = await onSendMessage(userMessageText);
      const processingTime = (Date.now() - startTime) / 1000;

      // ⏱️ SIMULAR TEMPO DE PROCESSAMENTO REALÍSTICO
      const minimumDelay = Math.max(1000, processingTime * 1000);
      await new Promise(resolve => setTimeout(resolve, minimumDelay));

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: response,
        sender: 'ai',
        timestamp: new Date(),
        model: selectedModel,
        tokens: Math.floor(response.length / 3.8), // Estimativa mais precisa
        processingTime,
        isPersistent: true
      };

      // 📝 ADICIONAR RESPOSTA (PERSISTENTE)
      setMessages(prev => [...prev, aiMessage]);
      
    } catch (error) {
      console.error('Erro ao enviar mensagem:', error);
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: `❌ **Erro de Comunicação**\n\nOcorreu um erro ao processar a mensagem com ${selectedModel}. O sistema continua funcional - pode tentar novamente ou usar outro modelo IA.\n\n**Modelos alternativos disponíveis:**\n• Llama 3.2 1B (ultra-rápido)\n• Mistral 7B (análise técnica)\n• GPT4All Falcon (commodities)\n• Nous Hermes 13B (análises complexas)`,
        sender: 'ai',
        timestamp: new Date(),
        model: selectedModel || 'Sistema',
        tokens: 0,
        processingTime: 0,
        isPersistent: true
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 🗑️ CLEAR CHAT COM CONFIRMAÇÃO
  const clearChat = () => {
    if (messages.length <= 1) return;
    
    if (confirm('Tem certeza que quer limpar todo o histórico do chat? Esta ação não pode ser desfeita.')) {
      const welcomeMessage: Message = {
        id: '1',
        content: '🔄 **Chat Reiniciado!**\n\nHistórico limpo com sucesso. Como posso ajudar agora?\n\n**Sugestões:**\n• "Analisar estratégias atuais"\n• "Status do trading bot"\n• "Análise de risco do portfólio"\n• "Otimizações de código"',
        sender: 'ai',
        timestamp: new Date(),
        model: selectedModel || 'Sistema JOKA',
        isPersistent: true
      };
      
      setMessages([welcomeMessage]);
      localStorage.removeItem('joka_chat_messages');
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('pt-PT', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const formatMessageContent = (content: string) => {
    // Suporte para markdown básico
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code class="bg-gray-700/50 px-1 py-0.5 rounded text-sm">$1</code>')
      .replace(/```([\s\S]*?)```/g, '<pre class="bg-gray-800/80 p-3 rounded-lg overflow-x-auto text-sm mt-2 mb-2"><code>$1</code></pre>');
  };

  return (
    <div className="bg-gradient-to-br from-gray-900/90 to-gray-800/90 backdrop-blur-sm border border-gray-700/50 rounded-2xl overflow-hidden h-full flex flex-col shadow-2xl">
      {/* Header Ultra Avançado */}
      <div className="px-6 py-4 bg-gradient-to-r from-gray-800/90 to-gray-700/90 border-b border-gray-700/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-gradient-to-br from-green-500/20 to-blue-500/20 border border-green-500/30 shadow-lg">
              <i className="ri-message-3-line text-xl text-green-400"></i>
            </div>
            <div>
              <h3 className="text-xl font-black text-white">Chat IA Ultra-Inteligente</h3>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  {isTyping ? (
                    <>
                      <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse"></div>
                      <span className="text-sm text-purple-400 font-bold">IA processando{typingDots}</span>
                    </>
                  ) : (
                    <>
                      <div className="w-2 h-2 rounded-full bg-green-400"></div>
                      <span className="text-sm text-gray-400">
                        {selectedModel ? `Usando ${selectedModel}` : 'Selecione um modelo IA'}
                      </span>
                    </>
                  )}
                </div>
                {selectedModel && (
                  <div className="px-2 py-1 rounded-lg bg-green-500/20 border border-green-500/30">
                    <span className="text-xs font-bold text-green-400">PRONTO</span>
                  </div>
                )}
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="px-3 py-1 rounded-lg bg-purple-500/20 border border-purple-500/30">
              <span className="text-xs font-bold text-purple-400">{messages.length} msgs</span>
            </div>
            <button
              onClick={clearChat}
              disabled={messages.length <= 1}
              className={`p-2 rounded-lg border transition-all duration-200 ${
                messages.length <= 1
                  ? 'bg-gray-700/50 border-gray-600/50 text-gray-500 cursor-not-allowed'
                  : 'bg-red-500/20 border-red-500/30 text-red-400 hover:bg-red-500/30 hover:scale-105'
              }`}
              title={messages.length <= 1 ? 'Nada para limpar' : 'Limpar chat completo'}
            >
              <i className="ri-delete-bin-line text-lg"></i>
            </button>
          </div>
        </div>
      </div>

      {/* Área de Mensagens Ultra Robusta */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-track-gray-800 scrollbar-thumb-purple-500">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'} group`}
          >
            <div className={`max-w-[85%] ${
              message.sender === 'user' 
                ? 'bg-gradient-to-r from-purple-600/90 to-blue-600/90 text-white rounded-l-2xl rounded-tr-2xl shadow-lg shadow-purple-500/20' 
                : 'bg-gradient-to-r from-gray-800/90 to-gray-700/90 text-gray-100 rounded-r-2xl rounded-tl-2xl border border-gray-600/50 shadow-lg'
            } p-4 backdrop-blur-sm`}>
              
              {/* Message Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    message.sender === 'user' 
                      ? 'bg-purple-400/20 border border-purple-300/30' 
                      : 'bg-green-500/20 border border-green-400/30'
                  }`}>
                    <i className={`${
                      message.sender === 'user' 
                        ? 'ri-user-line text-purple-200' 
                        : 'ri-robot-2-line text-green-400'
                    } text-sm`}></i>
                  </div>
                  <div>
                    <span className="text-sm font-bold opacity-90">
                      {message.sender === 'user' ? 'Você' : (message.model || 'IA Sistema')}
                    </span>
                    <div className="text-xs opacity-60">
                      {formatTime(message.timestamp)}
                    </div>
                  </div>
                </div>

                {/* Message Actions */}
                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                  <button
                    onClick={() => navigator.clipboard.writeText(message.content)}
                    className="p-1 rounded hover:bg-white/10 transition-colors"
                    title="Copiar mensagem"
                  >
                    <i className="ri-file-copy-line text-xs opacity-60"></i>
                  </button>
                </div>
              </div>

              {/* Message Content */}
              <div 
                className="text-sm leading-relaxed"
                dangerouslySetInnerHTML={{ __html: formatMessageContent(message.content) }}
              />

              {/* Message Stats para respostas IA */}
              {message.sender === 'ai' && (message.tokens || message.processingTime) && (
                <div className="flex items-center gap-4 mt-4 pt-3 border-t border-gray-600/30">
                  {message.tokens && (
                    <div className="flex items-center gap-1">
                      <i className="ri-cpu-line text-xs text-blue-400"></i>
                      <span className="text-xs text-gray-400 font-mono">{message.tokens} tokens</span>
                    </div>
                  )}
                  {message.processingTime && (
                    <div className="flex items-center gap-1">
                      <i className="ri-time-line text-xs text-green-400"></i>
                      <span className="text-xs text-gray-400 font-mono">{message.processingTime.toFixed(1)}s</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1">
                    <i className="ri-shield-check-line text-xs text-purple-400"></i>
                    <span className="text-xs text-purple-400 font-bold">PERSISTENTE</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Indicador de Digitação Ultra Avançado */}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-gradient-to-r from-gray-800/90 to-gray-700/90 border border-gray-600/50 rounded-r-2xl rounded-tl-2xl p-4 backdrop-blur-sm shadow-lg">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-purple-500/20 border border-purple-400/30 flex items-center justify-center">
                  <i className="ri-robot-2-line text-purple-400 text-sm"></i>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 rounded-full bg-purple-400 animate-bounce"></div>
                    <div className="w-2 h-2 rounded-full bg-purple-400 animate-bounce" style={{animationDelay: '0.1s'}}></div>
                    <div className="w-2 h-2 rounded-full bg-purple-400 animate-bounce" style={{animationDelay: '0.2s'}}></div>
                  </div>
                  <span className="text-sm text-purple-400 font-bold">
                    {selectedModel} está a analisar{typingDots}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area Ultra Avançada */}
      <div className="p-6 bg-gray-800/50 border-t border-gray-700/50">
        {/* Quick Actions Inteligentes */}
        <div className="mb-4 flex flex-wrap gap-2">
          {[
            { text: "Analisar estratégias atuais", icon: "ri-line-chart-line" },
            { text: "Status completo do trading bot", icon: "ri-robot-line" },
            { text: "Gestão de risco do portfólio", icon: "ri-shield-line" },
            { text: "Análise de mercado em tempo real", icon: "ri-bar-chart-line" },
            { text: "Otimizações de código Python", icon: "ri-code-line" },
            { text: "Configurações avançadas", icon: "ri-settings-line" }
          ].map((prompt) => (
            <button
              key={prompt.text}
              onClick={() => setInputMessage(prompt.text)}
              disabled={isLoading}
              className="px-3 py-2 text-xs bg-gray-700/50 border border-gray-600/50 rounded-lg text-gray-300 hover:bg-purple-500/20 hover:border-purple-500/30 hover:text-purple-300 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              <i className={`${prompt.icon} text-sm`}></i>
              <span className="hidden sm:inline">{prompt.text}</span>
            </button>
          ))}
        </div>

        <div className="flex items-end gap-4">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={selectedModel 
                ? `Mensagem para ${selectedModel}... (Enter para enviar, Shift+Enter para nova linha)` 
                : "⚠️ Selecione um modelo IA no seletor acima primeiro..."
              }
              disabled={!selectedModel || isLoading}
              className="w-full px-4 py-4 bg-gray-900/90 border border-gray-600/50 rounded-xl text-white placeholder-gray-400 resize-none focus:outline-none focus:border-purple-500/60 focus:ring-2 focus:ring-purple-500/20 transition-all duration-200 scrollbar-thin scrollbar-track-gray-800 scrollbar-thumb-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
              rows={3}
              maxLength={4000}
            />
            <div className="absolute bottom-3 right-3 flex items-center gap-3">
              <span className={`text-xs font-mono ${
                inputMessage.length > 3500 ? 'text-red-400' : 
                inputMessage.length > 3000 ? 'text-yellow-400' : 'text-gray-500'
              }`}>
                {inputMessage.length}/4000
              </span>
              {inputMessage.trim() && selectedModel && (
                <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
              )}
            </div>
          </div>
          
          <button
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || !selectedModel || isLoading}
            className={`p-4 rounded-xl font-bold transition-all duration-200 flex items-center gap-2 shadow-lg ${
              !inputMessage.trim() || !selectedModel || isLoading
                ? 'bg-gray-700/50 text-gray-500 cursor-not-allowed border border-gray-600/50'
                : 'bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:scale-105 shadow-purple-500/30 border border-purple-500/50 hover:shadow-xl'
            }`}
          >
            {isLoading ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                <span className="hidden sm:inline">Enviando...</span>
              </>
            ) : (
              <>
                <i className="ri-send-plane-2-line text-xl"></i>
                <span className="hidden sm:inline">Enviar</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
