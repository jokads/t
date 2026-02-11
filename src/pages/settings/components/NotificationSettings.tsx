import { useState, useEffect } from 'react';
import { apiGet, apiPost } from '../../../utils/api';

interface NotificationSettingsProps {
  environment: {
    frontend: boolean;
    backend: boolean;
    pythonCore: boolean;
    basePath: string;
    modelsPath: string;
  };
}

export default function NotificationSettings({ environment }: NotificationSettingsProps) {
  const [config, setConfig] = useState({
    positionsOpen: true,
    positionsClosed: true,
    stopLossTakeProfit: true,
    riskLimitReached: true,
    highDrawdown: true,
    strategyErrors: true,
    email: 'damasclaudio2@gmail.com',
    webhookUrl: ''
  });

  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);

  // ✅ Carregar configurações do backend
  useEffect(() => {
    if (environment.backend) {
      loadConfig();
    }
  }, [environment.backend]);

  const loadConfig = async () => {
    try {
      const response = await apiGet<any>('/api/settings/notifications');
      if (response && !response.error) {
        setConfig({ ...config, ...response });
      }
    } catch (error) {
      console.log('Usando configurações locais');
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      if (environment.backend) {
        const response = await apiPost<any>('/api/settings/notifications', config);
        if (response && !response.error) {
          setSaved(true);
          setTimeout(() => setSaved(false), 3000);
          alert('✅ Configurações de notificações guardadas com sucesso!');
        }
      } else {
        // Salvar localmente
        localStorage.setItem('notificationSettings', JSON.stringify(config));
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        alert('✅ Configurações guardadas localmente! Inicie o backend para persistir.');
      }
    } catch (error) {
      console.error('Erro ao salvar:', error);
      alert('❌ Erro ao guardar configurações.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Notificações de Trading */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-exchange-line text-cyan-400"></i>
          Notificações de Trading
        </h3>
        <div className="space-y-3">
          <label className="flex items-center justify-between p-4 glass-effect rounded-lg border border-purple-500/30 cursor-pointer hover:bg-purple-500/10 transition-all">
            <div>
              <p className="text-sm text-white font-medium">Posições Abertas</p>
              <p className="text-xs text-purple-400 mt-1">Notificar quando uma nova posição for aberta</p>
            </div>
            <input 
              type="checkbox" 
              checked={config.positionsOpen}
              onChange={(e) => setConfig({ ...config, positionsOpen: e.target.checked })}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-cyan-500 focus:ring-2 focus:ring-cyan-500 cursor-pointer" 
            />
          </label>

          <label className="flex items-center justify-between p-4 glass-effect rounded-lg border border-purple-500/30 cursor-pointer hover:bg-purple-500/10 transition-all">
            <div>
              <p className="text-sm text-white font-medium">Posições Fechadas</p>
              <p className="text-xs text-purple-400 mt-1">Notificar quando uma posição for fechada</p>
            </div>
            <input 
              type="checkbox" 
              checked={config.positionsClosed}
              onChange={(e) => setConfig({ ...config, positionsClosed: e.target.checked })}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-cyan-500 focus:ring-2 focus:ring-cyan-500 cursor-pointer" 
            />
          </label>

          <label className="flex items-center justify-between p-4 glass-effect rounded-lg border border-purple-500/30 cursor-pointer hover:bg-purple-500/10 transition-all">
            <div>
              <p className="text-sm text-white font-medium">Stop Loss / Take Profit</p>
              <p className="text-xs text-purple-400 mt-1">Notificar quando SL ou TP forem atingidos</p>
            </div>
            <input 
              type="checkbox" 
              checked={config.stopLossTakeProfit}
              onChange={(e) => setConfig({ ...config, stopLossTakeProfit: e.target.checked })}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-cyan-500 focus:ring-2 focus:ring-cyan-500 cursor-pointer" 
            />
          </label>
        </div>
      </div>

      {/* Alertas de Risco */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-alert-line text-orange-400"></i>
          Alertas de Risco
        </h3>
        <div className="space-y-3">
          <label className="flex items-center justify-between p-4 glass-effect rounded-lg border border-purple-500/30 cursor-pointer hover:bg-purple-500/10 transition-all">
            <div>
              <p className="text-sm text-white font-medium">Limite de Risco Atingido</p>
              <p className="text-xs text-purple-400 mt-1">Alerta quando limites de risco forem atingidos</p>
            </div>
            <input 
              type="checkbox" 
              checked={config.riskLimitReached}
              onChange={(e) => setConfig({ ...config, riskLimitReached: e.target.checked })}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-orange-500 focus:ring-2 focus:ring-orange-500 cursor-pointer" 
            />
          </label>

          <label className="flex items-center justify-between p-4 glass-effect rounded-lg border border-purple-500/30 cursor-pointer hover:bg-purple-500/10 transition-all">
            <div>
              <p className="text-sm text-white font-medium">Drawdown Elevado</p>
              <p className="text-xs text-purple-400 mt-1">Alerta quando drawdown ultrapassar limites</p>
            </div>
            <input 
              type="checkbox" 
              checked={config.highDrawdown}
              onChange={(e) => setConfig({ ...config, highDrawdown: e.target.checked })}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-orange-500 focus:ring-2 focus:ring-orange-500 cursor-pointer" 
            />
          </label>

          <label className="flex items-center justify-between p-4 glass-effect rounded-lg border border-purple-500/30 cursor-pointer hover:bg-purple-500/10 transition-all">
            <div>
              <p className="text-sm text-white font-medium">Erros de Estratégia</p>
              <p className="text-xs text-purple-400 mt-1">Notificar sobre erros nas estratégias</p>
            </div>
            <input 
              type="checkbox" 
              checked={config.strategyErrors}
              onChange={(e) => setConfig({ ...config, strategyErrors: e.target.checked })}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-red-500 focus:ring-2 focus:ring-red-500 cursor-pointer" 
            />
          </label>
        </div>
      </div>

      {/* Canais de Notificação */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-send-plane-line text-pink-400"></i>
          Canais de Notificação
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Email</label>
            <input
              type="email"
              value={config.email}
              onChange={(e) => setConfig({ ...config, email: e.target.value })}
              className="w-full px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
              placeholder="seu-email@exemplo.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Webhook URL (opcional)</label>
            <input
              type="url"
              value={config.webhookUrl}
              onChange={(e) => setConfig({ ...config, webhookUrl: e.target.value })}
              placeholder="https://seu-webhook.com/notify"
              className="w-full px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <p className="text-xs text-purple-500 mt-1">Para integração com Slack, Discord, etc.</p>
          </div>
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
          className="flex-1 px-6 py-2 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-700 hover:to-teal-700 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-cyan-500/30 whitespace-nowrap cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
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
                As notificações foram atualizadas.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
