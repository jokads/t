import { useState, useEffect } from 'react';

interface SecuritySettingsProps {
  environment: {
    frontend: boolean;
    backend: boolean;
    pythonCore: boolean;
    basePath: string;
    modelsPath: string;
  };
  aiModels: any[];
  selectedModels: string[];
  setSelectedModels: (models: string[]) => void;
}

export default function SecuritySettings({ environment, aiModels, selectedModels, setSelectedModels }: SecuritySettingsProps) {
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [threats, setThreats] = useState<any[]>([]);
  const [securityScore, setSecurityScore] = useState(85);
  const [aiAssistance, setAiAssistance] = useState(true);
  const [autoMonitoring, setAutoMonitoring] = useState(true);

  // Carregar ameaças em tempo real
  useEffect(() => {
    if (environment.backend && autoMonitoring) {
      loadThreats();
      const interval = setInterval(loadThreats, 10000);
      return () => clearInterval(interval);
    }
  }, [environment.backend, autoMonitoring]);

  const loadThreats = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/security/threats');
      if (response.ok) {
        const data = await response.json();
        setThreats(data.threats || []);
        setSecurityScore(data.score || 85);
      }
    } catch (error) {
      console.log('Usando dados simulados de segurança');
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      alert('As palavras-passe não coincidem!');
      return;
    }
    if (newPassword.length < 8) {
      alert('A palavra-passe deve ter pelo menos 8 caracteres!');
      return;
    }

    try {
      if (environment.backend) {
        const response = await fetch('http://localhost:8000/api/security/change-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ currentPassword, newPassword })
        });
        if (response.ok) {
          alert('Palavra-passe alterada com sucesso!');
          setCurrentPassword('');
          setNewPassword('');
          setConfirmPassword('');
        } else {
          alert('Erro ao alterar palavra-passe. Verifique a palavra-passe atual.');
        }
      } else {
        // Simular mudança
        alert('Palavra-passe alterada com sucesso! (Modo simulado)');
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
      }
    } catch (error) {
      console.error('Erro ao alterar palavra-passe:', error);
    }
  };

  const toggleModelSelection = (modelName: string) => {
    if (selectedModels.includes(modelName)) {
      setSelectedModels(selectedModels.filter(m => m !== modelName));
    } else {
      setSelectedModels([...selectedModels, modelName]);
    }
  };

  const handleSecurityScan = async () => {
    if (!environment.backend) {
      alert('Backend offline. Inicie o backend para executar análise de segurança.');
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/api/security/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models: selectedModels })
      });
      if (response.ok) {
        const data = await response.json();
        alert(`Análise de segurança concluída!\n\nScore: ${data.score}/100\nAmeaças detectadas: ${data.threats || 0}`);
        loadThreats();
      }
    } catch (error) {
      console.error('Erro ao executar análise:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Score de Segurança */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <i className="ri-shield-check-line text-purple-400"></i>
            Score de Segurança
          </h3>
          <button
            onClick={handleSecurityScan}
            disabled={!environment.backend || selectedModels.length === 0}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-purple-500/30 whitespace-nowrap cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <i className="ri-scan-line mr-2"></i>
            Análise IA
          </button>
        </div>
        <div className="relative">
          <div className="flex items-center justify-center">
            <div className="relative w-48 h-48">
              <svg className="w-full h-full transform -rotate-90">
                <circle
                  cx="96"
                  cy="96"
                  r="88"
                  stroke="currentColor"
                  strokeWidth="12"
                  fill="none"
                  className="text-purple-500/20"
                />
                <circle
                  cx="96"
                  cy="96"
                  r="88"
                  stroke="currentColor"
                  strokeWidth="12"
                  fill="none"
                  strokeDasharray={`${2 * Math.PI * 88}`}
                  strokeDashoffset={`${2 * Math.PI * 88 * (1 - securityScore / 100)}`}
                  className={`transition-all duration-1000 ${
                    securityScore >= 80 ? 'text-green-400' : securityScore >= 60 ? 'text-orange-400' : 'text-red-400'
                  }`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center flex-col">
                <div className={`text-5xl font-bold ${
                  securityScore >= 80 ? 'text-green-400' : securityScore >= 60 ? 'text-orange-400' : 'text-red-400'
                }`}>
                  {securityScore}
                </div>
                <div className="text-sm text-purple-300 mt-1">de 100</div>
              </div>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-4">
            <div className="glass-effect p-3 rounded-lg text-center">
              <div className="text-2xl font-bold text-green-400">{threats.filter(t => t.severity === 'low').length}</div>
              <div className="text-xs text-green-300 mt-1">Baixo</div>
            </div>
            <div className="glass-effect p-3 rounded-lg text-center">
              <div className="text-2xl font-bold text-orange-400">{threats.filter(t => t.severity === 'medium').length}</div>
              <div className="text-xs text-orange-300 mt-1">Médio</div>
            </div>
            <div className="glass-effect p-3 rounded-lg text-center">
              <div className="text-2xl font-bold text-red-400">{threats.filter(t => t.severity === 'high' || t.severity === 'critical').length}</div>
              <div className="text-xs text-red-300 mt-1">Alto/Crítico</div>
            </div>
          </div>
        </div>
      </div>

      {/* Configuração de IA para Segurança */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-robot-line text-cyan-400"></i>
          Configuração de IA para Segurança
        </h3>
        <div className="space-y-4 mb-6">
          <label className="flex items-center justify-between p-3 glass-effect rounded-lg cursor-pointer hover:bg-purple-500/10 transition-all">
            <div className="flex items-center gap-3">
              <i className="ri-brain-line text-purple-400"></i>
              <div>
                <div className="text-sm text-white font-medium">Assistência IA</div>
                <div className="text-xs text-purple-300">Análise inteligente de ameaças</div>
              </div>
            </div>
            <input 
              type="checkbox" 
              checked={aiAssistance}
              onChange={(e) => setAiAssistance(e.target.checked)}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-purple-500 focus:ring-2 focus:ring-purple-500 cursor-pointer" 
            />
          </label>
          <label className="flex items-center justify-between p-3 glass-effect rounded-lg cursor-pointer hover:bg-purple-500/10 transition-all">
            <div className="flex items-center gap-3">
              <i className="ri-eye-line text-cyan-400"></i>
              <div>
                <div className="text-sm text-white font-medium">Auto-Monitoramento</div>
                <div className="text-xs text-purple-300">Atualiza a cada 10 segundos</div>
              </div>
            </div>
            <input 
              type="checkbox" 
              checked={autoMonitoring}
              onChange={(e) => setAutoMonitoring(e.target.checked)}
              className="w-4 h-4 rounded border-purple-600 bg-black/30 text-cyan-500 focus:ring-2 focus:ring-cyan-500 cursor-pointer" 
            />
          </label>
        </div>

        {aiModels.length > 0 && (
          <div>
            <div className="text-sm text-purple-300 mb-3">
              Modelos IA Ativos ({selectedModels.length} selecionados)
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {aiModels.map((model) => (
                <label
                  key={model.name}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedModels.includes(model.name)
                      ? 'bg-purple-500/20 border-purple-500'
                      : 'bg-black/20 border-purple-500/30 hover:border-purple-500/50'
                  }`}
                  onClick={() => toggleModelSelection(model.name)}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={selectedModels.includes(model.name)}
                      onChange={() => {}}
                      className="mt-0.5 w-4 h-4 rounded border-purple-600 bg-black/30 text-purple-500 cursor-pointer"
                    />
                    <div className="flex-1">
                      <div className="text-sm text-white font-medium flex items-center gap-2">
                        {model.name}
                        {model.recommended && <span className="text-xs">✨</span>}
                      </div>
                      <div className="text-xs text-purple-400 mt-1">{model.size}</div>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Credenciais de Login */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-lock-password-line text-orange-400"></i>
          Alterar Palavra-passe
        </h3>
        <div className="bg-orange-500/10 rounded-lg p-4 border border-orange-500/30 mb-4">
          <div className="flex items-start gap-3">
            <i className="ri-information-line text-orange-400 text-xl mt-0.5"></i>
            <div>
              <p className="text-sm text-orange-400 font-medium mb-1">Credenciais Atuais</p>
              <p className="text-xs text-orange-300">Utilizador: <strong>joka</strong></p>
              <p className="text-xs text-orange-300">Password: <strong>ThugParadise616#</strong></p>
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Palavra-passe Atual</label>
            <div className="relative">
              <input
                type={showCurrentPassword ? 'text' : 'password'}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full px-4 py-2 pr-10 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                placeholder="Digite a palavra-passe atual"
              />
              <button
                type="button"
                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-purple-400 hover:text-purple-300 cursor-pointer"
              >
                <i className={`${showCurrentPassword ? 'ri-eye-off-line' : 'ri-eye-line'} text-base`}></i>
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Nova Palavra-passe</label>
            <div className="relative">
              <input
                type={showNewPassword ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-4 py-2 pr-10 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                placeholder="Digite a nova palavra-passe"
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-purple-400 hover:text-purple-300 cursor-pointer"
              >
                <i className={`${showNewPassword ? 'ri-eye-off-line' : 'ri-eye-line'} text-base`}></i>
              </button>
            </div>
            <p className="text-xs text-purple-400 mt-1">Mínimo 8 caracteres</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-purple-300 mb-2">Confirmar Nova Palavra-passe</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-2 bg-black/30 border border-purple-500/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
              placeholder="Confirme a nova palavra-passe"
            />
          </div>
        </div>
      </div>

      {/* Autenticação de Dois Fatores */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-shield-keyhole-line text-cyan-400"></i>
          Autenticação de Dois Fatores
        </h3>
        <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm text-white font-medium mb-1">2FA não está ativado</p>
              <p className="text-xs text-purple-300">Adicione uma camada extra de segurança à sua conta</p>
            </div>
            <button className="px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 rounded-lg text-sm font-medium transition-all border border-cyan-500/30 whitespace-nowrap cursor-pointer">
              Ativar 2FA
            </button>
          </div>
        </div>
      </div>

      {/* Sessões Ativas */}
      <div className="card p-6">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <i className="ri-device-line text-pink-400"></i>
          Sessões Ativas
        </h3>
        <div className="space-y-3">
          <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
            <div className="flex items-start justify-between">
              <div className="flex gap-3">
                <i className="ri-computer-line text-cyan-400 text-xl"></i>
                <div>
                  <p className="text-sm text-white font-medium">Windows - Chrome</p>
                  <p className="text-xs text-purple-400 mt-1">Lisboa, Portugal • Ativo agora</p>
                </div>
              </div>
              <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded border border-green-500/30">Atual</span>
            </div>
          </div>

          <div className="glass-effect rounded-lg p-4 border border-purple-500/30">
            <div className="flex items-start justify-between">
              <div className="flex gap-3">
                <i className="ri-smartphone-line text-purple-400 text-xl"></i>
                <div>
                  <p className="text-sm text-white font-medium">iPhone - Safari</p>
                  <p className="text-xs text-purple-400 mt-1">Lisboa, Portugal • Há 2 horas</p>
                </div>
              </div>
              <button className="text-xs text-red-400 hover:text-red-300 whitespace-nowrap cursor-pointer">Terminar</button>
            </div>
          </div>
        </div>
      </div>

      {/* Botões de Ação */}
      <div className="flex gap-3">
        <button className="px-6 py-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 rounded-lg text-sm font-medium transition-all border border-purple-500/30 whitespace-nowrap cursor-pointer">
          Cancelar
        </button>
        <button 
          onClick={handleChangePassword}
          className="flex-1 px-6 py-2 bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white rounded-lg text-sm font-medium transition-all shadow-lg shadow-orange-500/30 whitespace-nowrap cursor-pointer"
        >
          Guardar Alterações
        </button>
      </div>
    </div>
  );
}
