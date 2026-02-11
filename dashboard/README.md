# MT5 Trading Dashboard - Frontend

Dashboard profissional em React + TypeScript para gerenciamento de bot de trading MT5 com monitoramento em tempo real.

## 🚀 Funcionalidades

- ✅ **Painel de Conta**: Saldo, patrimônio, lucro/prejuízo em tempo real
- ✅ **Posições Abertas**: Visualização e fechamento de posições
- ✅ **Ordens Pendentes**: Gerenciamento de ordens
- ✅ **Estratégias**: Ativar/desativar estratégias de trading
- ✅ **Envio Manual de Ordens**: Formulário completo com validação
- ✅ **Gráficos em Tempo Real**: Chart.js com cotações ao vivo
- ✅ **Logs do Sistema**: Visualizador com filtros por nível
- ✅ **WebSocket**: Atualizações em tempo real via Socket.IO
- ✅ **Autenticação**: Login admin com token Bearer

## 📋 Pré-requisitos

- Node.js 18+ e npm/yarn
- Backend Flask rodando (veja `BACKEND_INTEGRATION_GUIDE.md`)

## 🔧 Instalação

### 1. Clone e instale dependências

```bash
cd C:\bot-mt5\dashboard
npm install
```

### 2. Configure variáveis de ambiente

Copie `.env.example` para `.env` e configure:

```env
VITE_API_URL=http://localhost:5000
VITE_WS_URL=ws://127.0.0.1:9090
VITE_ADMIN_TOKEN=your_token_here
```

### 3. Execute em modo desenvolvimento

```bash
npm run dev
```

Acesse: `http://localhost:5173`

### 4. Build para produção

```bash
npm run build
npm run preview
```

## 📁 Estrutura do Projeto

```
src/
├── config/
│   └── api.config.ts          # Configuração de endpoints e WebSocket
├── services/
│   ├── api.service.ts         # Cliente HTTP (Axios)
│   └── websocket.service.ts   # Cliente WebSocket (Socket.IO)
├── types/
│   └── trading.types.ts       # Interfaces TypeScript
├── pages/
│   ├── dashboard/
│   │   ├── page.tsx           # Página principal
│   │   └── components/        # Widgets do dashboard
│   └── login/
│       └── page.tsx           # Página de login
└── router/
    └── config.tsx             # Configuração de rotas
```

## 🔌 Integração com Backend

### Endpoints REST Esperados

O frontend espera que o backend Flask exponha:

```
POST   /api/login              # Autenticação
GET    /api/health             # Health check
GET    /api/account            # Informações da conta
GET    /api/symbols            # Lista de símbolos
GET    /api/orders             # Ordens (abertas/fechadas)
GET    /api/positions          # Posições abertas
GET    /api/history            # Histórico de trades
POST   /api/place              # Enviar ordem
POST   /api/close              # Fechar ordem
GET    /api/strategies         # Lista de estratégias
POST   /api/strategies/toggle  # Ativar/desativar estratégia
GET    /api/config             # Configurações
POST   /api/config/update      # Atualizar configurações
GET    /api/logs               # Logs do sistema
POST   /hooks/signal           # Webhook para sinais externos
GET    /api/audit              # Auditoria
```

### WebSocket Events

**Cliente → Servidor:**
- `subscribe`: `{ channels: ['quotes', 'positions', 'orders', 'logs'] }`
- `unsubscribe`: `{ channels: [...] }`
- `heartbeat`: `{ timestamp: 1234567890 }`

**Servidor → Cliente:**
- `quotes`: `{ symbol: 'EURUSD', bid: 1.0850, ask: 1.0852, timestamp: '...' }`
- `positions_update`: `[{ ticket, symbol, type, volume, profit, ... }]`
- `orders_update`: `[{ ticket, symbol, type, state, ... }]`
- `logs_update`: `{ timestamp, level, message, module }`
- `account_update`: `{ balance, equity, profit, ... }`
- `error`: `{ error: 'message' }`

## 📝 Exemplo de Payload de Ordem

```json
{
  "symbol": "EURUSD",
  "side": "buy",
  "volume": 0.01,
  "tp": 50,
  "sl": 30,
  "source": "manual_dashboard",
  "confidence": 1.0,
  "uuid": "manual_1234567890",
  "force": false,
  "dry_run": false,
  "audit_note": "Ordem manual de teste"
}
```

## 🔐 Autenticação

1. Usuário faz login em `/login`
2. Backend retorna `{ token: 'xxx' }`
3. Frontend armazena token em `localStorage`
4. Todas as requisições incluem header: `Authorization: Bearer <token>`

## 🛠️ Desenvolvimento

### Adicionar novo widget

1. Crie componente em `src/pages/dashboard/components/`
2. Importe e use em `src/pages/dashboard/page.tsx`
3. Conecte ao WebSocket se precisar de dados em tempo real

### Adicionar novo endpoint

1. Adicione endpoint em `src/config/api.config.ts`
2. Crie método em `src/services/api.service.ts`
3. Use no componente: `await apiService.newMethod()`

## 📚 Documentação Adicional

- **API Contract**: Veja `API_CONTRACT.yaml` (OpenAPI v3)
- **WebSocket Spec**: Veja `WEBSOCKET_SPEC.md`
- **Backend Integration**: Veja `BACKEND_INTEGRATION_GUIDE.md`
- **Payload Examples**: Veja `PAYLOAD_EXAMPLES.md`

## 🐛 Troubleshooting

### WebSocket não conecta

1. Verifique se backend Flask-SocketIO está rodando
2. Confirme URL em `.env` (VITE_WS_URL)
3. Verifique firewall/porta 9090

### Erro 401 Unauthorized

1. Faça login novamente
2. Verifique token em localStorage
3. Confirme que backend aceita o token

### Dados não atualizam

1. Verifique conexão WebSocket (indicador no header)
2. Confirme que backend está emitindo eventos
3. Veja console do navegador para erros

## 📞 Suporte

Para implementação do backend Flask, consulte:
- `BACKEND_INTEGRATION_GUIDE.md` - Guia passo-a-passo
- `API_CONTRACT.yaml` - Contrato completo de API
- `PAYLOAD_EXAMPLES.md` - Exemplos de payloads reais

## 📄 Licença

Proprietary - Uso interno apenas
