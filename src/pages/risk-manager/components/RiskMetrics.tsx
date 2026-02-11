interface RiskMetricsProps {
  settings: {
    maxRiskPerTrade: number;
    maxConcurrentTrades: number;
    maxDailyLoss: number;
    maxDrawdown: number;
  };
  metrics: {
    currentRisk: number;
    activeTrades: number;
    dailyLoss: number;
    currentDrawdown: number;
  };
  backendConnected: boolean;
}

export default function RiskMetrics({ settings, metrics, backendConnected }: RiskMetricsProps) {
  const calculatePercentage = (current: number, max: number) => {
    if (max === 0) return 0;
    return (current / max) * 100;
  };

  const getStatusColor = (percentage: number) => {
    if (percentage >= 80) return 'red';
    if (percentage >= 60) return 'orange';
    if (percentage >= 40) return 'yellow';
    return 'green';
  };

  // ✅ Validação defensiva - garante que os valores existam
  const safeMetrics = {
    currentRisk: metrics?.currentRisk ?? 0,
    activeTrades: metrics?.activeTrades ?? 0,
    dailyLoss: metrics?.dailyLoss ?? 0,
    currentDrawdown: metrics?.currentDrawdown ?? 0
  };

  const safeSettings = {
    maxRiskPerTrade: settings?.maxRiskPerTrade ?? 2,
    maxConcurrentTrades: settings?.maxConcurrentTrades ?? 5,
    maxDailyLoss: settings?.maxDailyLoss ?? 5,
    maxDrawdown: settings?.maxDrawdown ?? 10
  };

  const metrics_data = [
    {
      label: 'Risco Atual',
      current: safeMetrics.currentRisk,
      max: safeSettings.maxRiskPerTrade,
      unit: '%',
      icon: 'ri-pie-chart-line'
    },
    {
      label: 'Trades Ativos',
      current: safeMetrics.activeTrades,
      max: safeSettings.maxConcurrentTrades,
      unit: '',
      icon: 'ri-line-chart-line'
    },
    {
      label: 'Perda Diária',
      current: safeMetrics.dailyLoss,
      max: safeSettings.maxDailyLoss,
      unit: '%',
      icon: 'ri-arrow-down-line'
    },
    {
      label: 'Drawdown',
      current: safeMetrics.currentDrawdown,
      max: safeSettings.maxDrawdown,
      unit: '%',
      icon: 'ri-bar-chart-box-line'
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      {metrics_data.map((metric, index) => {
        // ✅ Garantir que current é um número válido
        const currentValue = typeof metric.current === 'number' ? metric.current : 0;
        const maxValue = typeof metric.max === 'number' ? metric.max : 1;
        
        const percentage = calculatePercentage(currentValue, maxValue);
        const statusColor = getStatusColor(percentage);
        
        return (
          <div key={index} className="glass-card p-6 hover:scale-105 transition-transform">
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="text-xs text-gray-400 mb-1">Máx: {maxValue}{metric.unit}</p>
                <h3 className="text-sm font-semibold text-white">{metric.label}</h3>
              </div>
              <div className={`w-10 h-10 rounded-lg bg-${statusColor}-500/20 flex items-center justify-center`}>
                <i className={`${metric.icon} text-xl text-${statusColor}-400`}></i>
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex items-end justify-between">
                <span className="text-3xl font-bold text-white">
                  {metric.unit === '' ? currentValue : currentValue.toFixed(1)}
                  {metric.unit}
                </span>
                <span className={`text-sm font-semibold text-${statusColor}-400`}>
                  {percentage.toFixed(1)}% do limite
                </span>
              </div>
              
              {/* Progress Bar */}
              <div className="w-full h-2 bg-purple-900/30 rounded-full overflow-hidden">
                <div 
                  className={`h-full bg-gradient-to-r from-${statusColor}-500 to-${statusColor}-400 transition-all duration-500`}
                  style={{ width: `${Math.min(percentage, 100)}%` }}
                ></div>
              </div>

              {/* Status Badge */}
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-gray-500">
                  {backendConnected ? (
                    <span className="flex items-center gap-1 text-green-400">
                      <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></div>
                      Dados reais
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-cyan-400">
                      <div className="w-1.5 h-1.5 rounded-full bg-cyan-400"></div>
                      Preparado
                    </span>
                  )}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
