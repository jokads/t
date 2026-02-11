import { useState, useEffect } from 'react';
import { apiGet } from '../../../utils/api';

interface RiskAlertsProps {
  backendConnected: boolean;
}

export default function RiskAlerts({ backendConnected }: RiskAlertsProps) {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAlerts();
    
    // Atualizar a cada 15 segundos se backend conectado
    if (backendConnected) {
      const interval = setInterval(loadAlerts, 15000);
      return () => clearInterval(interval);
    }
  }, [backendConnected]);

  const loadAlerts = async () => {
    try {
      setLoading(true);
      const data = await apiGet('/api/risk/alerts');
      if (data && data.alerts) {
        setAlerts(data.alerts);
        console.log('✅ Alertas de risco carregados:', data.alerts);
      }
    } catch (error) {
      console.error('Erro ao carregar alertas:', error);
      // Manter lista vazia se erro
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'red';
      case 'high': return 'orange';
      case 'medium': return 'yellow';
      default: return 'blue';
    }
  };

  const getPriorityIcon = (priority: string) => {
    switch (priority) {
      case 'critical': return 'ri-error-warning-fill';
      case 'high': return 'ri-alert-fill';
      case 'medium': return 'ri-information-fill';
      default: return 'ri-notification-3-line';
    }
  };

  return (
    <div className="glass-card p-6 h-full">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-white">Alertas de Risco</h2>
        <div className="flex items-center gap-2">
          {loading ? (
            <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse"></div>
          ) : backendConnected ? (
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
          ) : (
            <div className="w-2 h-2 rounded-full bg-cyan-400"></div>
          )}
          <span className="text-xs text-gray-400">
            {alerts.length} {alerts.length === 1 ? 'alerta' : 'alertas'}
          </span>
        </div>
      </div>

      <div className="space-y-3">
        {alerts.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
              <i className="ri-shield-check-line text-3xl text-green-400"></i>
            </div>
            <p className="text-sm text-gray-400">Nenhum alerta ativo</p>
            <p className="text-xs text-gray-500 mt-1">
              {backendConnected 
                ? 'Sistema operando dentro dos limites'
                : 'Sistema preparado para monitoramento'
              }
            </p>
          </div>
        ) : (
          alerts.map((alert: any) => {
            const color = getPriorityColor(alert.priority);
            const icon = getPriorityIcon(alert.priority);
            
            return (
              <div 
                key={alert.id}
                className={`p-4 rounded-lg bg-${color}-500/10 border border-${color}-500/30 hover:bg-${color}-500/20 transition-colors`}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-8 h-8 rounded-full bg-${color}-500/20 flex items-center justify-center flex-shrink-0`}>
                    <i className={`${icon} text-${color}-400`}></i>
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-semibold text-white mb-1">{alert.title}</h4>
                    <p className="text-xs text-gray-400">{alert.message}</p>
                    {alert.timestamp && (
                      <p className="text-xs text-gray-500 mt-2">
                        {new Date(alert.timestamp).toLocaleString('pt-PT')}
                      </p>
                    )}
                  </div>
                  <button 
                    className="text-gray-400 hover:text-white transition-colors"
                    onClick={() => alert('Dismiss de alertas será implementado em breve')}
                  >
                    <i className="ri-close-line"></i>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Quick Stats */}
      <div className="mt-6 pt-6 border-t border-purple-500/20">
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-white">
              {alerts.filter(a => a.priority === 'critical' || a.priority === 'high').length}
            </p>
            <p className="text-xs text-gray-400 mt-1">Alta Prioridade</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-white">
              {alerts.filter(a => a.priority === 'medium' || a.priority === 'low').length}
            </p>
            <p className="text-xs text-gray-400 mt-1">Média/Baixa</p>
          </div>
        </div>
      </div>

      {/* Status Footer */}
      <div className="mt-4 pt-4 border-t border-purple-500/20">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-400">
            {backendConnected ? (
              <span className="flex items-center gap-1.5 text-green-400">
                <i className="ri-radio-button-line text-green-400 animate-pulse"></i>
                Monitoramento ativo
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-cyan-400">
                <i className="ri-settings-3-line"></i>
                Aguardando backend
              </span>
            )}
          </span>
          <button
            onClick={loadAlerts}
            className="text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1"
          >
            <i className="ri-refresh-line"></i>
            Atualizar
          </button>
        </div>
      </div>
    </div>
  );
}
