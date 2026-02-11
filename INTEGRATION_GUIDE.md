# 🔥 Guia de Integração JOKA Dashboard

## ⚠️ ATENÇÃO: Este é um guia de INTEGRAÇÃO REAL

Este dashboard foi projetado para integrar diretamente com o bot-mt5 existente.
**NÃO** é um projeto standalone genérico.

---

## 📁 Estrutura Real do Projeto

```
bot-mt5/
├── trading_bot_core.py          # ← ENTRYPOINT PRINCIPAL
├── mt5_communication.py         # ← Socket MT5 (NÃO HTTP)
├── ai_manager.py                # ← 6 GPT4All + 1 llama.cpp
├── models/
│   └── gpt4all/
│       ├── Llama-3.2-1B-Instruct-Q4_0.gguf
│       ├── Llama-3.2-3B-Instruct-Q4_0.gguf
│       ├── Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf
│       ├── orca-mini-3b-gguf2-q4_0.gguf
│       ├── Phi-3-mini-4k-instruct.Q4_0.gguf
│       └── qwen2-1_5b-instruct-q4_0.gguf
├── core/
│   ├── news_api_manager.py
│   └── telegram_handler.py
├── strategies/
│   ├── adaptive_ml.py
│   ├── deep_q_learning.py
│   ├── ema_crossover.py
│   ├── rsi_strategy.py
│   ├── supertrend_strategy.py
│   ├── ict_concepts.py
│   ├── strategy_engine.py
│   ├── risk_manager.py
│   └── technical_indicators.py
├── backend/                      # ← DASHBOARD BACKEND
│   ├── dashboard_server.py      # ← Flask + SocketIO
│   ├── requirements.txt
│   ├── .env.example
│   ├── run_all.py
│   ├── run_all.sh
│   └── run_all.ps1
└── src/                         # ← DASHBOARD FRONTEND
    └── pages/
        ├── dashboard/
        ├── strategies/
        ├── risk-manager/
        ├── ai-chat/
        ├── diagnostics/         # ← NOVO: Análise de código
        ├── system-control/
        ├── file-manager/
        ├── integrations/
        └── settings/
```

---

## 🔧 Passo 1: Integrar trading_bot_core.py

### Adicionar ao seu `trading_bot_core.py`:

```python
# No início do ficheiro
import subprocess
import webbrowser
from pathlib import Path

# Estado global
dashboard_process = None

def start_dashboard():
    """Iniciar dashboard automaticamente"""
    global dashboard_process
    
    dashboard_path = Path(__file__).parent / 'backend' / 'dashboard_server.py'
    
    if not dashboard_path.exists():
        print("❌ dashboard_server.py não encontrado")
        return
    
    try:
        dashboard_process = subprocess.Popen(
            [sys.executable, str(dashboard_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("✅ Dashboard iniciado")
        time.sleep(3)
        webbrowser.open('http://localhost:5000')
    except Exception as e:
        print(f"❌ Erro ao iniciar dashboard: {e}")

def stop_dashboard():
    """Parar dashboard"""
    global dashboard_process
    if dashboard_process:
        dashboard_process.terminate()
        dashboard_process.wait(timeout=5)

# No __main__
if __name__ == '__main__':
    # Iniciar dashboard
    start_dashboard()
    
    # Resto do código do bot...
```

---

## 🔧 Passo 2: Expor Funções de Controlo

### Adicionar ao `trading_bot_core.py`:

```python
# Estado do bot
bot_running = False

def get_status():
    """Status do bot para o dashboard"""
    return {
        'running': bot_running,
        'uptime': get_uptime(),
        'mt5_connected': mt5.initialize(),
        'strategies_loaded': len(loaded_strategies),
        'ai_models_loaded': len(ai_manager.loaded_models)
    }

def start_bot():
    """Iniciar bot"""
    global bot_running
    bot_running = True
    # Lógica de inicialização...

def stop_bot():
    """Parar bot"""
    global bot_running
    bot_running = False
    # Lógica de paragem...
```

---

## 🔧 Passo 3: Configurar Backend

### 1. Instalar Dependências

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configurar .env

```bash
cp .env.example .env
```

Editar `.env`:
```env
DASHBOARD_USER=joka
DASHBOARD_PASS=ThugParadise616#
DASHBOARD_SECRET_KEY=seu-secret-key-aqui
BOT_PUSH_TOKEN=joka-bot-token-616
TELEGRAM_TOKEN=seu-telegram-token
NEWS_API_KEY=sua-news-api-key
PORT=5000
DEBUG=False
```

### 3. Atualizar dashboard_server.py

O ficheiro `backend/dashboard_server.py` já está configurado para importar:
- `trading_bot_core`
- `ai_manager`
- `strategy_engine`
- `risk_manager`
- `news_api_manager`
- `telegram_handler`

**Certifique-se** que o caminho está correto:
```python
BOT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(BOT_ROOT))
```

---

## 🚀 Passo 4: Iniciar Sistema

### Opção 1: Script Automático (Recomendado)

**Windows:**
```powershell
.\backend\run_all.ps1
```

**Linux/Mac:**
```bash
chmod +x backend/run_all.sh
./backend/run_all.sh
```

**Python:**
```bash
python backend/run_all.py
```

### Opção 2: Manual

```bash
# Terminal 1: Backend
python backend/dashboard_server.py

# Terminal 2: Frontend (dev)
npm run dev

# Terminal 3: Bot
python trading_bot_core.py
```

---

## 🔐 Credenciais

- **URL:** http://localhost:5000
- **Utilizador:** `joka`
- **Password:** `ThugParadise616#`

---

## 🎯 Funcionalidades Implementadas

### ✅ Controlo Total do Bot
- Start/Stop/Restart via dashboard
- Monitorização de processos Python
- Health checks em tempo real

### ✅ Gestão de Modelos AI
- Scan automático de modelos .gguf
- Carregar/descarregar modelos
- Upload de novos modelos
- Chat com múltiplos modelos

### ✅ Diagnóstico & Correção
- **NOVO:** Página `/diagnostics`
- Scan automático de erros Python
- Análise de código com IA
- Aplicação automática de patches
- Backup automático (.bak)

### ✅ Gestão de Ficheiros
- Explorador de ficheiros bot-mt5
- Editor de código integrado
- Permissões restritas (strategies/, core/)
- Versionamento simples

### ✅ Integrações
- Telegram Bot (tokens, templates, alertas)
- News API (categorias, notícias macro)
- Configuração dinâmica via UI

### ✅ Segurança
- Autenticação JWT
- Proteção brute-force
- Audit logs completos
- Sessões ativas
- Rate limiting

---

## 🔥 Funcionalidades Hardcore

### 1. Diagnóstico Automático

```
/diagnostics
```

- Escaneia TODOS os .py do bot-mt5
- Detecta erros de sintaxe
- Detecta imports quebrados
- Envia para IA analisar
- IA retorna diff de correção
- Botão "Aplicar Correção"

### 2. Análise de Código com IA

```python
# Via API
POST /api/ai/analyze_code
{
  "code": "seu código Python",
  "language": "python"
}

# Resposta
{
  "problems": ["lista de problemas"],
  "suggestions": ["sugestões"],
  "fixed_code": "código corrigido"
}
```

### 3. Aplicar Patches

```python
POST /api/diagnostics/apply_patch
{
  "file_path": "strategies/adaptive_ml.py",
  "fixed_code": "código corrigido"
}
```

**Segurança:**
- Backup automático (.bak)
- Apenas ficheiros em `strategies/` e `core/`
- Audit log de todas as alterações

---

## 📊 API Endpoints

### Bot Control
- `GET /api/bot/status` - Status do bot
- `POST /api/bot/start` - Iniciar bot
- `POST /api/bot/stop` - Parar bot
- `POST /api/bot/restart` - Reiniciar bot

### AI Manager
- `GET /api/ai/models` - Listar modelos
- `POST /api/ai/load` - Carregar modelo
- `POST /api/ai/unload` - Descarregar modelo
- `POST /api/ai/chat` - Chat com IA
- `POST /api/ai/analyze_code` - Analisar código

### Diagnostics
- `GET /api/diagnostics/scan` - Escanear projeto
- `POST /api/diagnostics/analyze_file` - Analisar ficheiro
- `POST /api/diagnostics/apply_patch` - Aplicar patch

### File Manager
- `GET /api/files/list` - Listar ficheiros
- `GET /api/files/read` - Ler ficheiro
- `POST /api/files/write` - Escrever ficheiro
- `POST /api/files/upload` - Upload .gguf

### Config
- `GET /api/config/paths` - Caminhos configurados
- `GET /api/config/env` - Ler .env
- `POST /api/config/env` - Atualizar .env

---

## 🛡️ Segurança

### Ficheiros Protegidos

**Permitido editar:**
- `strategies/*.py`
- `core/*.py`
- Configurações AI

**Bloqueado:**
- `trading_bot_core.py`
- `dashboard_server.py`
- Ficheiros do sistema
- `.env` (apenas via API específica)

### Backup Automático

Todos os ficheiros editados criam backup `.bak`:
```
strategies/adaptive_ml.py
strategies/adaptive_ml.py.bak  ← backup automático
```

---

## 🎨 Design

- **Tema:** Dark roxo → vermelho
- **Highlights:** Laranja noturno
- **Modo Night Aggression:** Laranja mais forte após 20h
- **Logs:** Vermelho pulsante para erros
- **Status OK:** Verde profundo

---

## 🔄 Próximos Passos

1. **Testar Integração**
   ```bash
   python trading_bot_core.py
   ```

2. **Verificar Dashboard**
   - Abrir http://localhost:5000
   - Login: joka / ThugParadise616#

3. **Testar Diagnóstico**
   - Ir para `/diagnostics`
   - Clicar "Escanear Projeto"
   - Analisar erros com IA
   - Aplicar correções

4. **Configurar Integrações**
   - Telegram token
   - News API key
   - Testar notificações

5. **Adicionar Modelos AI**
   - Upload .gguf via `/file-manager`
   - Carregar modelos via `/ai-chat`
   - Testar análise de código

---

## 🐛 Troubleshooting

### Dashboard não inicia
```bash
# Verificar porta
lsof -i :5000  # Linux/Mac
netstat -ano | findstr :5000  # Windows

# Matar processo
kill -9 <PID>  # Linux/Mac
taskkill /PID <PID> /F  # Windows
```

### Módulos não carregados
```bash
# Verificar imports
python -c "import trading_bot_core; import ai_manager"

# Adicionar ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/caminho/para/bot-mt5"
```

### Erros de permissão
```bash
# Verificar permissões
ls -la backend/dashboard_server.py

# Dar permissões
chmod +x backend/*.sh
```

---

## 📞 Suporte

Para problemas ou dúvidas:
1. Verificar logs: `backend/logs/`
2. Verificar audit logs: `/settings` → Audit Logs
3. Verificar health: `/system-control`

---

## 🎯 Checklist de Integração

- [ ] `trading_bot_core.py` atualizado com funções de controlo
- [ ] `backend/.env` configurado
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] Dashboard inicia automaticamente
- [ ] Login funcional (joka / ThugParadise616#)
- [ ] Modelos AI detectados
- [ ] Diagnóstico funcional
- [ ] File manager com permissões corretas
- [ ] Integrações configuradas (Telegram, News API)
- [ ] Backup automático testado

---

**🔥 JOKA Trading Bot - Thug Paradise 616 Edition 🔥**
