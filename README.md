# 🤖 JOKA Trading Bot - Dashboard Full-Stack

Dashboard profissional para gestão de Trading Bot MT5 com integração Python (Flask + SocketIO) e frontend React/TypeScript.

![JOKA Logo](https://static.readdy.ai/image/d55f7533e2770f6cf984b3b0dd8016a8/0f4cef46158b860125e33f2644b930f5.png)

## 🎯 Funcionalidades

### 🔐 Autenticação & Segurança
- Login com JWT tokens
- Proteção contra brute-force (lockout após 5 tentativas)
- Sessões seguras com expiração
- Rate limiting em todas as rotas
- Audit logs completos

### 📊 Dashboard Principal
- **Resumo da Conta**: Balance, Equity, Margem, Profit/Loss, Drawdown
- **Gráfico de Equity**: Tempo real com zoom (1h, 24h, 7d, 30d)
- **Posições Abertas**: Tabela sortable com ações (fechar, modificar SL/TP)
- **Histórico de Trades**: Exportação CSV, filtros, paginação
- **Indicadores Técnicos**: RSI, MACD, EMA, SMA por símbolo
- **Envio de Sinais Manuais**: Interface para trading manual

### 🎯 Gestão de Estratégias
- Lista de estratégias com toggle on/off
- Editor de código Python (Monaco Editor)
- Deploy automático para diretório strategies/
- Logs em tempo real por estratégia
- Dry-run/backtest básico

### ⚠️ Gestão de Risco
- Configuração de limites (% risco, trades simultâneos, perda diária)
- Métricas visuais de risco atual
- Regras de auto-stop configuráveis
- Alertas em tempo real

### 🤖 Assistente AI
- Chat com modelos locais (GPT4All/Llama.cpp)
- Templates de prompts prontos
- Análise de código e geração de patches
- Geração automática de sinais
- Geração de estratégias a partir de descrição

### 🔧 Gestão de Modelos
- Upload de ficheiros .gguf
- Scan automático de modelos
- Carregar/descarregar modelos
- Visualização de tamanho e status

### 📡 Integrações
- **MT5**: Comunicação via Socket.IO
- **Telegram**: Envio de alertas e notificações
- **News API**: Integração com notícias de mercado

## 🚀 Instalação Rápida

### Pré-requisitos
- Python 3.8+
- Node.js 18+ (para frontend)
- Git

### 1️⃣ Clonar Repositório
```bash
git clone <seu-repo>
cd joka-trading-bot
```

### 2️⃣ Configurar Backend

#### Linux/Mac
```bash
chmod +x backend/start.sh
./backend/start.sh
```

#### Windows
```powershell
.\backend\start.ps1
```

#### Manual
```bash
# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r backend/requirements.txt

# Configurar .env
cp backend/.env.example backend/.env
# Editar backend/.env com suas configurações

# Criar diretórios
mkdir -p data models/gpt4all logs

# Iniciar servidor
cd backend
python dashboard_server.py
```

### 3️⃣ Configurar Frontend

```bash
# Instalar dependências
npm install

# Iniciar dev server
npm run dev
```

### 4️⃣ Testar Integração

Em outro terminal, execute o simulador de bot:

```bash
python backend/simulate_bot.py
```

## 🐳 Docker

### Build e Run
```bash
# Build
docker-compose build

# Iniciar
docker-compose up -d

# Ver logs
docker-compose logs -f dashboard

# Parar
docker-compose down
```

### Acessar
- Dashboard: http://localhost:5000
- Frontend: http://localhost:5173

## 🔑 Credenciais Padrão

**⚠️ ALTERE EM PRODUÇÃO!**

- **Utilizador**: `joka`
- **Password**: `ThugParadise616#`

## 📁 Estrutura do Projeto

```
joka-trading-bot/
├── backend/
│   ├── dashboard_server.py      # Servidor Flask + SocketIO
│   ├── mt5_connector.py          # Conector MT5 via Socket.IO
│   ├── ai_manager.py             # Gestor de modelos AI
│   ├── simulate_bot.py           # Simulador para testes
│   ├── requirements.txt          # Dependências Python
│   ├── .env.example              # Configurações de exemplo
│   ├── Dockerfile                # Docker image
│   ├── start.sh                  # Script Linux/Mac
│   └── start.ps1                 # Script Windows
├── src/
│   ├── pages/                    # Páginas React
│   ├── components/               # Componentes reutilizáveis
│   └── router/                   # Configuração de rotas
├── data/                         # Base de dados SQLite
├── models/gpt4all/              # Modelos AI (.gguf)
├── logs/                         # Logs do sistema
├── docker-compose.yml            # Orquestração Docker
└── README.md                     # Este ficheiro
```

## 🔌 API Endpoints

### Autenticação
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/verify` - Verificar token

### Dados de Trading
- `GET /api/account` - Informações da conta
- `GET /api/positions` - Posições abertas
- `GET /api/history?days=7` - Histórico de trades
- `GET /api/indicators` - Indicadores técnicos
- `GET /api/statistics` - Estatísticas gerais

### Estratégias
- `GET /api/strategies` - Lista de estratégias
- `POST /api/strategies/toggle` - Ativar/desativar estratégia

### Sinais
- `POST /api/send_signal` - Enviar sinal manual

### Bot Integration
- `POST /api/push` - Receber dados do bot (HTTP fallback)

### Admin
- `GET /api/audit_logs` - Logs de auditoria (admin only)
- `GET /api/sessions` - Sessões ativas (admin only)

### Health
- `GET /api/health` - Status do servidor

## 🔌 Socket.IO Events

### Namespace `/ui` (Frontend)
**Recebe:**
- `connection_status` - Status de conexão
- `bot_status` - Status do bot
- `account_update` - Atualização de conta
- `positions_update` - Atualização de posições
- `equity_update` - Atualização de equity
- `log` - Logs do bot
- `indicators_update` - Atualização de indicadores
- `strategies_update` - Atualização de estratégias

### Namespace `/bot` (Bot MT5)
**Envia:**
- `account_update` - Dados da conta
- `positions_update` - Posições abertas
- `equity_update` - Equity atual
- `log` - Mensagens de log
- `indicators_update` - Indicadores calculados
- `strategies_update` - Status das estratégias

**Recebe:**
- `manual_signal` - Sinal manual do dashboard
- `strategy_toggle` - Ativar/desativar estratégia

## 📊 Payloads de Exemplo

### Account Update
```json
{
  "balance": 10000.00,
  "equity": 9950.23,
  "free_margin": 8000.00,
  "profit": -49.77,
  "margin_level": 124.38,
  "connected": true,
  "timestamp": "2026-01-16T12:34:56Z"
}
```

### Positions Update
```json
[
  {
    "ticket": 12345,
    "symbol": "EURUSD",
    "type": "BUY",
    "volume": 0.1,
    "open_price": 1.0800,
    "current_price": 1.0815,
    "sl": 1.0700,
    "tp": 1.1000,
    "profit": 15.50,
    "time_open": "2026-01-16T11:00:00Z",
    "strategy": "adaptive_ml"
  }
]
```

### Equity Update
```json
{
  "equity": 9950.23,
  "timestamp": "2026-01-16T12:34:56Z"
}
```

### Log
```json
{
  "message": "Strategy X triggered buy EURUSD at 1.0800",
  "level": "info",
  "timestamp": "2026-01-16T12:34:56Z"
}
```

## 🤖 Integração com Bot MT5

### Exemplo Básico

```python
from mt5_connector import MT5DashboardConnector

# Criar conector
connector = MT5DashboardConnector(
    dashboard_url='http://localhost:5000',
    bot_token='joka-bot-token-616'
)

# Definir callbacks
def handle_manual_signal(signal):
    # Processar sinal manual
    print(f"Sinal recebido: {signal}")

connector.on_manual_signal = handle_manual_signal

# Conectar
connector.connect()

# Enviar dados
connector.send_account_update({
    'balance': 10000,
    'equity': 9950,
    'free_margin': 8000,
    'profit': -50
})

connector.send_positions_update([...])
connector.send_equity_update(9950.23)
connector.send_log("Sistema operacional")
```

## 🧠 AI Manager

### Adicionar Modelos

1. Fazer download de modelos .gguf (ex: GPT4All, Llama)
2. Colocar em `models/gpt4all/`
3. O dashboard irá detectar automaticamente

### Usar AI Manager

```python
from ai_manager import AIModelManager

# Criar manager
ai = AIModelManager()

# Escanear modelos
models = ai.scan_models()

# Carregar modelo
ai.load_model('model-name')

# Chat
response = ai.chat("Qual a melhor estratégia para mercado lateral?")

# Analisar código
analysis = ai.analyze_code(code, 'python')

# Gerar estratégia
strategy = ai.generate_strategy("Estratégia baseada em RSI e MACD")
```

## 🔒 Checklist de Segurança

### Desenvolvimento
- ✅ Tokens JWT com expiração
- ✅ Rate limiting
- ✅ Proteção brute-force
- ✅ Validação de inputs
- ✅ Audit logs

### Produção
- ⚠️ **ALTERAR** todas as secrets em `.env`
- ⚠️ **ATIVAR** HTTPS (`HTTPS_ENABLED=True`)
- ⚠️ **CONFIGURAR** CORS para domínios específicos
- ⚠️ **USAR** PostgreSQL em vez de SQLite
- ⚠️ **ATIVAR** Redis para rate limiting
- ⚠️ **CONFIGURAR** firewall e IP whitelist
- ⚠️ **FAZER** backups regulares da base de dados

## 🐛 Troubleshooting

### Backend não inicia
```bash
# Verificar logs
tail -f logs/dashboard.log

# Verificar porta
lsof -i :5000  # Linux/Mac
netstat -ano | findstr :5000  # Windows
```

### Bot não conecta
1. Verificar se dashboard está a correr
2. Verificar `BOT_PUSH_TOKEN` em `.env`
3. Verificar URL em `DASHBOARD_URL`
4. Ver logs do bot

### Frontend não conecta ao backend
1. Verificar CORS em `.env`
2. Verificar URL da API no frontend
3. Ver console do browser (F12)

## 📈 Melhorias Futuras

- [ ] Persistência com TimeSeries DB (InfluxDB)
- [ ] Alert Rules Engine avançado
- [ ] Role-Based Access Control (RBAC)
- [ ] Backtesting completo com dados históricos
- [ ] Otimização automática de parâmetros
- [ ] Machine Learning para previsões
- [ ] Mobile app (React Native)
- [ ] Multi-broker support
- [ ] Cloud deployment (AWS/GCP/Azure)

## 📝 Licença

Propriedade de JOKA Trading Systems. Todos os direitos reservados.

## 🤝 Suporte

Para questões e suporte:
- Email: support@joka-trading.com
- Discord: [JOKA Trading Community]
- Documentação: [docs.joka-trading.com]

---

**Desenvolvido por JOKA Trading Systems**

*"- Where Trading Meets AI"*
