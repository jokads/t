
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function HomePage() {
  const navigate = useNavigate();

  useEffect(() => {
    // ✅ REDIRECIONAMENTO AUTOMÁTICO PARA O DASHBOARD JOKA
    // Em vez de ir para o Readdy, vai direto para o dashboard do bot
    const timer = setTimeout(() => {
      navigate('/dashboard');
    }, 500); // Meio segundo de delay

    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-red-950 to-orange-900">
      <div className="text-center max-w-md mx-auto p-8">
        {/* ✅ LOGO JOKA OFICIAL */}
        <div className="relative mb-8">
          <div className="absolute inset-0 bg-gradient-to-br from-orange-500 via-red-500 to-purple-500 rounded-full blur-3xl opacity-60 animate-pulse"></div>
          <img 
            src="https://static.readdy.ai/image/d55f7533e2770f6cf984b3b0dd8016a8/0f4cef46158b860125e33f2644b930f5.png" 
            alt="JOKA Trading Bot" 
            className="relative w-32 h-32 object-contain mx-auto drop-shadow-2xl animate-float"
          />
        </div>

        {/* ✅ TÍTULO HARDCORE */}
        <h1 className="text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-orange-400 via-red-400 to-purple-400 mb-4 tracking-wider animate-glow">
          JOKA TRADING
        </h1>
        
        <p className="text-orange-200 text-lg font-bold mb-6 tracking-wide">
          🔥 Ultra Hardcore Professional Bot 🔥
        </p>

        {/* ✅ LOADING SPINNER */}
        <div className="flex items-center justify-center gap-4 mb-6">
          <div className="w-8 h-8 border-4 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-orange-300 font-semibold">
            A carregar dashboard...
          </p>
        </div>

        {/* ✅ BADGES DE SISTEMA */}
        <div className="grid grid-cols-3 gap-3 mb-8">
          <div className="bg-gradient-to-br from-red-600/30 to-red-800/30 border border-red-500/50 rounded-xl p-3 text-center backdrop-blur-sm">
            <i className="ri-robot-2-fill text-red-400 text-2xl mb-1 animate-pulse"></i>
            <p className="text-red-300 text-xs font-bold">BOT IA</p>
          </div>
          <div className="bg-gradient-to-br from-orange-600/30 to-orange-800/30 border border-orange-500/50 rounded-xl p-3 text-center backdrop-blur-sm">
            <i className="ri-stock-fill text-orange-400 text-2xl mb-1 animate-pulse" style={{ animationDelay: '0.3s' }}></i>
            <p className="text-orange-300 text-xs font-bold">MT5</p>
          </div>
          <div className="bg-gradient-to-br from-purple-600/30 to-purple-800/30 border border-purple-500/50 rounded-xl p-3 text-center backdrop-blur-sm">
            <i className="ri-line-chart-fill text-purple-400 text-2xl mb-1 animate-pulse" style={{ animationDelay: '0.6s' }}></i>
            <p className="text-purple-300 text-xs font-bold">TRADING</p>
          </div>
        </div>

        {/* ✅ BOTÃO DE ACESSO DIRETO */}
        <button
          onClick={() => navigate('/dashboard')}
          className="w-full py-3 bg-gradient-to-r from-red-600 via-orange-600 to-purple-600 text-white font-bold text-lg rounded-xl hover:from-red-500 hover:via-orange-500 hover:to-purple-500 transition-all duration-300 shadow-2xl shadow-orange-500/50 hover:shadow-orange-500/70 hover:scale-105 whitespace-nowrap flex items-center justify-center gap-3 border-2 border-orange-400/50 hover:border-orange-300"
        >
          <i className="ri-dashboard-3-fill text-xl"></i>
          <span>ACEDER AO DASHBOARD</span>
          <i className="ri-arrow-right-line text-xl"></i>
        </button>

        {/* ✅ FOOTER INFO */}
        <div className="mt-8 pt-6 border-t border-orange-500/30">
          <p className="text-orange-200/60 text-xs font-semibold tracking-wide">
            © 2026 JOKA Trading Bot - Sistema Profissional
          </p>
          <p className="text-orange-300/40 text-xs mt-1">
            Dashboard Ultra Hardcore com IA 🤖💪🔥
          </p>
        </div>
      </div>
    </div>
  );
}
