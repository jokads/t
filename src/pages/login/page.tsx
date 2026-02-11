import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { setAuthToken } from '../../utils/api';

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('damasclaudio2@gmail.com');
  const [password, setPassword] = useState('ThugParadise616#');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // ✅ GERADOR DE JWT OFFLINE (funciona SEMPRE, mesmo sem backend)
  const generateOfflineJWT = (email: string): string => {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const payload = btoa(JSON.stringify({
      email,
      username: email.split('@')[0],
      id: 1,
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60) // 24h
    }));
    // Signature simples para modo offline
    const signature = btoa(`JOKA-OFFLINE-${email}-${Date.now()}`);
    return `${header}.${payload}.${signature}`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // ✅ VALIDAÇÃO LOCAL DAS CREDENCIAIS HARDCORE
    const ADMIN_EMAIL = 'damasclaudio2@gmail.com';
    const ADMIN_PASSWORD = 'ThugParadise616#';

    if (email.trim() !== ADMIN_EMAIL || password !== ADMIN_PASSWORD) {
      setError('❌ Credenciais inválidas! Use as credenciais JOKA configuradas.');
      setLoading(false);
      return;
    }

    try {
      // ✅ TENTAR BACKEND PRIMEIRO (modo online preferido)
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (response.ok) {
        const data = await response.json();
        
        if (data?.token) {
          // ✅ LOGIN ONLINE BEM-SUCEDIDO
          setAuthToken(data.token);
          
          if (data.user) {
            localStorage.setItem('user_email', data.user.email);
            localStorage.setItem('username', data.user.username);
            localStorage.setItem('user_id', String(data.user.id));
          }
          
          localStorage.setItem('auth_mode', 'online');
          localStorage.setItem('last_login', new Date().toISOString());
          
          setTimeout(() => navigate('/dashboard'), 300);
          return;
        }
      }
    } catch (err) {
      // Backend offline - continuar para modo offline
      console.log('⚠️ Backend offline, usando modo JWT offline...');
    }

    // ✅ MODO OFFLINE - GERAR JWT LOCALMENTE (SEMPRE FUNCIONA!)
    const offlineToken = generateOfflineJWT(email);
    
    setAuthToken(offlineToken);
    localStorage.setItem('user_email', email);
    localStorage.setItem('username', email.split('@')[0]);
    localStorage.setItem('user_id', '1');
    localStorage.setItem('auth_mode', 'offline');
    localStorage.setItem('last_login', new Date().toISOString());
    
    setLoading(false);
    
    // ✅ REDIRECIONAR PARA DASHBOARD (SEMPRE!)
    setTimeout(() => navigate('/dashboard'), 300);
  };

  return (
    <div className="min-h-screen relative overflow-hidden flex items-center justify-center p-6">
      {/* ✅ WALLPAPER ANIMADO HARDCORE - Gradiente Vermelho/Laranja/Roxo Brilhante */}
      <div className="absolute inset-0 bg-gradient-to-br from-red-950 via-orange-950 to-purple-950"></div>
      
      {/* ✅ ANIMAÇÃO DE PARTÍCULAS BRILHANTES */}
      <div className="absolute inset-0 opacity-30">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-red-500 rounded-full mix-blend-multiply filter blur-3xl animate-pulse"></div>
        <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-orange-500 rounded-full mix-blend-multiply filter blur-3xl animate-pulse" style={{ animationDelay: '2s' }}></div>
        <div className="absolute bottom-1/4 left-1/3 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl animate-pulse" style={{ animationDelay: '4s' }}></div>
      </div>

      {/* ✅ GRID ANIMADO DE FUNDO */}
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0zNiAxOGMzLjMxNCAwIDYgMi42ODYgNiA2cy0yLjY4NiA2LTYgNi02LTIuNjg2LTYtNiAyLjY4Ni02IDYtNnoiIHN0cm9rZT0icmdiYSgyNTUsMTAwLDEwMCwwLjEpIiBzdHJva2Utd2lkdGg9IjIiLz48L2c+PC9zdmc+')] opacity-20"></div>

      <div className="w-full max-w-md relative z-10">
        {/* ✅ CARD PRINCIPAL COM GLASSMORPHISM */}
        <div className="bg-black/40 backdrop-blur-2xl rounded-3xl shadow-2xl border border-orange-500/30 overflow-hidden">
          {/* ✅ BORDA BRILHANTE ANIMADA */}
          <div className="absolute inset-0 rounded-3xl bg-gradient-to-r from-red-500 via-orange-500 to-purple-500 opacity-0 group-hover:opacity-20 transition-opacity duration-500 blur-xl"></div>
          
          <div className="relative p-10">
            {/* ✅ LOGO JOKA OFICIAL (Imagem que enviaste) */}
            <div className="text-center mb-8">
              <div className="relative inline-block group">
                {/* Glow effect */}
                <div className="absolute inset-0 bg-gradient-to-br from-orange-500 via-red-500 to-purple-500 rounded-full blur-2xl opacity-50 group-hover:opacity-75 transition-opacity duration-500 animate-pulse"></div>
                
                {/* Logo container */}
                <div className="relative w-32 h-32 mx-auto mb-6">
                  <img 
                    src="https://static.readdy.ai/image/d55f7533e2770f6cf984b3b0dd8016a8/0f4cef46158b860125e33f2644b930f5.png"
                    alt="JOKA Logo"
                    className="w-full h-full object-contain drop-shadow-2xl animate-float"
                  />
                </div>
              </div>
              
              <h1 className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-orange-400 via-red-400 to-purple-400 mb-3 tracking-wider animate-glow">
                JOKA TRADING
              </h1>
              <p className="text-orange-200/80 text-sm font-semibold tracking-wide">
                🔥 Ultra Hardcore Professional Dashboard 🔥
              </p>
            </div>

            {/* ✅ FORM */}
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Email */}
              <div>
                <label htmlFor="email" className="block text-sm font-bold text-orange-300 mb-2 tracking-wide">
                  📧 EMAIL ADMIN
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-5 py-3.5 bg-black/60 border-2 border-orange-500/50 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-400 focus:ring-4 focus:ring-orange-500/30 transition-all duration-300 font-medium backdrop-blur-sm"
                  placeholder="damasclaudio2@gmail.com"
                  required
                  autoComplete="email"
                  readOnly
                />
              </div>

              {/* Password */}
              <div>
                <label htmlFor="password" className="block text-sm font-bold text-purple-300 mb-2 tracking-wide">
                  🔐 PASSWORD HARDCORE
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-5 py-3.5 bg-black/60 border-2 border-purple-500/50 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-400 focus:ring-4 focus:ring-purple-500/30 transition-all duration-300 font-medium backdrop-blur-sm"
                  placeholder="••••••••••••••••"
                  required
                  autoComplete="current-password"
                />
              </div>

              {/* Error Message */}
              {error && (
                <div className="bg-red-500/20 border-2 border-red-500 rounded-xl p-4 flex items-start gap-3 animate-shake backdrop-blur-sm">
                  <i className="ri-error-warning-line text-red-400 text-2xl flex-shrink-0 mt-0.5 animate-pulse"></i>
                  <p className="text-red-300 text-sm font-bold">{error}</p>
                </div>
              )}

              {/* Submit Button ULTRA HARDCORE */}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-gradient-to-r from-red-600 via-orange-600 to-purple-600 text-white font-black text-lg rounded-xl hover:from-red-500 hover:via-orange-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 shadow-2xl shadow-orange-500/50 hover:shadow-orange-500/70 hover:scale-105 whitespace-nowrap flex items-center justify-center gap-3 border-2 border-orange-400/50 hover:border-orange-300 group relative overflow-hidden"
              >
                {/* Shimmer effect */}
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent translate-x-[-200%] group-hover:translate-x-[200%] transition-transform duration-1000"></div>
                
                <span className="relative flex items-center gap-3">
                  {loading ? (
                    <>
                      <i className="ri-loader-4-line animate-spin text-2xl"></i>
                      <span className="tracking-wider">CONECTANDO...</span>
                    </>
                  ) : (
                    <>
                      <i className="ri-login-box-fill text-2xl"></i>
                      <span className="tracking-wider">ENTRAR NO SISTEMA</span>
                      <i className="ri-arrow-right-line text-2xl group-hover:translate-x-1 transition-transform"></i>
                    </>
                  )}
                </span>
              </button>
            </form>

            {/* ✅ BADGES DE CONFIANÇA HARDCORE */}
            <div className="mt-8 grid grid-cols-3 gap-3">
              <div className="bg-gradient-to-br from-red-600/30 to-red-800/30 border border-red-500/50 rounded-xl p-3 text-center backdrop-blur-sm hover:scale-105 transition-transform duration-300">
                <i className="ri-shield-keyhole-fill text-red-400 text-3xl mb-1 animate-pulse"></i>
                <p className="text-red-300 text-xs font-bold">SEGURO</p>
              </div>
              <div className="bg-gradient-to-br from-orange-600/30 to-orange-800/30 border border-orange-500/50 rounded-xl p-3 text-center backdrop-blur-sm hover:scale-105 transition-transform duration-300">
                <i className="ri-flashlight-fill text-orange-400 text-3xl mb-1 animate-pulse" style={{ animationDelay: '0.3s' }}></i>
                <p className="text-orange-300 text-xs font-bold">RÁPIDO</p>
              </div>
              <div className="bg-gradient-to-br from-purple-600/30 to-purple-800/30 border border-purple-500/50 rounded-xl p-3 text-center backdrop-blur-sm hover:scale-105 transition-transform duration-300">
                <i className="ri-brain-fill text-purple-400 text-3xl mb-1 animate-pulse" style={{ animationDelay: '0.6s' }}></i>
                <p className="text-purple-300 text-xs font-bold">IA ELITE</p>
              </div>
            </div>

            {/* ✅ INFO JWT OFFLINE */}
            <div className="mt-6 bg-gradient-to-br from-green-600/20 to-emerald-800/20 border border-green-500/40 rounded-xl p-4 backdrop-blur-sm">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                <p className="text-green-300 text-sm font-bold">✅ JWT OFFLINE ATIVO</p>
              </div>
              <p className="text-green-200/70 text-xs leading-relaxed">
                Sistema autenticará <strong>SEMPRE</strong>, mesmo sem backend! Token JWT gerado localmente garante acesso total ao dashboard.
              </p>
            </div>

            {/* Footer */}
            <div className="mt-8 pt-6 border-t border-orange-500/30">
              <p className="text-center text-orange-200/60 text-xs font-semibold tracking-wide">
                © 2026 JOKA Trading Bot - Powered by AI 🤖
              </p>
              <p className="text-center text-orange-300/40 text-xs mt-1">
                Ultra Hardcore Professional System 💪🔥
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ✅ CSS ANIMATIONS */}
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px) rotate(0deg); }
          50% { transform: translateY(-20px) rotate(5deg); }
        }
        
        @keyframes glow {
          0%, 100% { text-shadow: 0 0 20px rgba(251, 146, 60, 0.8), 0 0 40px rgba(251, 146, 60, 0.5); }
          50% { text-shadow: 0 0 30px rgba(251, 146, 60, 1), 0 0 60px rgba(251, 146, 60, 0.8); }
        }
        
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-5px); }
          75% { transform: translateX(5px); }
        }
        
        .animate-float {
          animation: float 6s ease-in-out infinite;
        }
        
        .animate-glow {
          animation: glow 3s ease-in-out infinite;
        }
        
        .animate-shake {
          animation: shake 0.5s ease-in-out;
        }
      `}</style>
    </div>
  );
}
