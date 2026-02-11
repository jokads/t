interface AccountSummaryProps {
  data: {
    balance: number;
    equity: number;
    freeMargin: number;
    profit: number;
    drawdown: number;
    uptime: string;
    connected: boolean;
  };
}

export default function AccountSummary({ data }: AccountSummaryProps) {
  const cards = [
    {
      label: 'Balance',
      value: `$${data.balance.toFixed(2)}`,
      icon: 'ri-wallet-3-line',
      color: 'from-blue-500 to-blue-600',
      change: data.balance > 0 ? '+2.5%' : '0%'
    },
    {
      label: 'Equity',
      value: `$${data.equity.toFixed(2)}`,
      icon: 'ri-line-chart-line',
      color: 'from-cyan-500 to-teal-500',
      change: data.profit >= 0 ? `+$${data.profit.toFixed(2)}` : `$${data.profit.toFixed(2)}`
    },
    {
      label: 'Margem Livre',
      value: `$${data.freeMargin.toFixed(2)}`,
      icon: 'ri-funds-line',
      color: 'from-emerald-500 to-emerald-600',
      change: data.balance > 0 ? `${((data.freeMargin / data.balance) * 100).toFixed(0)}%` : '0%'
    },
    {
      label: 'Profit/Loss',
      value: `$${data.profit.toFixed(2)}`,
      icon: data.profit >= 0 ? 'ri-arrow-up-line' : 'ri-arrow-down-line',
      color: data.profit >= 0 ? 'from-green-500 to-green-600' : 'from-red-500 to-red-600',
      change: data.balance > 0 ? `${((data.profit / data.balance) * 100).toFixed(2)}%` : '0%'
    },
    {
      label: 'Drawdown',
      value: `${data.drawdown.toFixed(2)}%`,
      icon: 'ri-arrow-down-circle-line',
      color: 'from-orange-500 to-orange-600',
      change: data.drawdown < 10 ? 'Baixo' : data.drawdown < 20 ? 'Médio' : 'Alto'
    },
    {
      label: 'Uptime',
      value: data.uptime,
      icon: 'ri-time-line',
      color: 'from-purple-500 to-purple-600',
      change: '24/7'
    }
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 md:gap-4">
      {cards.map((card, index) => (
        <div
          key={index}
          className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-3 md:p-5 hover:border-slate-600 transition-all"
        >
          <div className="flex items-start justify-between mb-2 md:mb-3">
            <div className={`w-8 h-8 md:w-10 md:h-10 rounded-lg bg-gradient-to-br ${card.color} flex items-center justify-center shadow-lg`}>
              <i className={`${card.icon} text-white text-base md:text-lg`}></i>
            </div>
            <span className="text-xs text-slate-400">{card.change}</span>
          </div>
          <div>
            <p className="text-xs text-slate-400 mb-1">{card.label}</p>
            <p className="text-base md:text-xl font-bold text-white truncate">{card.value}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
