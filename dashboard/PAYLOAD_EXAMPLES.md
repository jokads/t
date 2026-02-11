# Exemplos de Payloads - MT5 Trading Dashboard

Este documento contém exemplos reais de payloads JSON que o frontend React envia para o backend Flask.

---

## 🔐 Autenticação

### POST /api/login

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200 OK):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwiZXhwIjoxNzA0MDcwODAwLCJpYXQiOjE3MDQwNjcyMDB9.abc123...",
  "expires_in": 3600,
  "user": {
    "username": "admin",
    "role": "admin"
  }
}
```

**Response (401 Unauthorized):**
```json
{
  "error": "Credenciais inválidas"
}
```

---

## 📊 Conta

### GET /api/account

**Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200 OK):**
```json
{
  "balance": 10000.00,
  "equity": 10250.50,
  "margin": 500.00,
  "free_margin": 9750.50,
  "margin_level": 2050.10,
  "profit": 250.50,
  "currency": "USD",
  "leverage": 100,
  "server": "MetaQuotes-Demo",
  "name": "John Doe",
  "number": 12345678
}
```

---

## 📈 Trading

### GET /api/positions

**Response (200 OK):**
```json
[
  {
    "ticket": 123456789,
    "symbol": "EURUSD",
    "type": "buy",
    "volume": 0.10,
    "price_open": 1.08500,
    "price_current": 1.08550,
    "sl": 1.08200,
    "tp": 1.09000,
    "profit": 50.00,
    "swap": -0.50,
    "commission": -2.00,
    "time": "2024-01-01T10:00:00Z",
    "comment": "RSI_Strategy"
  },
  {
    "ticket": 987654321,
    "symbol": "GBPUSD",
    "type": "sell",
    "volume": 0.05,
    "price_open": 1.27500,
    "price_current": 1.27450,
    "sl": 1.27800,
    "tp": 1.27000,
    "profit": 25.00,
    "swap": 0.00,
    "commission": -1.00,
    "time": "2024-01-01T11:30:00Z",
    "comment": "Manual order"
  }
]
```

---

### POST /api/place

**Request (Ordem Manual Simples):**
```json
{
  "symbol": "EURUSD",
  "side": "buy",
  "volume": 0.01,
  "tp": 50,
  "sl": 30,
  "source": "manual_dashboard",
  "confidence": 1.0,
  "uuid": "manual_1704067200",
  "force": false,
  "dry_run": false,
  "audit_note": "Teste de ordem manual"
}
```

**Request (Ordem com Force Send):**
```json
{
  "symbol": "GBPUSD",
  "side": "sell",
  "volume": 0.02,
  "tp": 40,
  "sl": 25,
  "source": "manual_dashboard",
  "confidence": 1.0,
  "uuid": "manual_1704067300",
  "force": true,
  "dry_run": false,
  "audit_note": "Ordem forçada - ignorar validadores"
}
```

**Request (Dry Run - Simulação):**
```json
{
  "symbol": "USDJPY",
  "side": "buy",
  "volume": 0.05,
  "tp": 60,
  "sl": 35,
  "source": "manual_dashboard",
  "confidence": 1.0,
  "uuid": "manual_1704067400",
  "force": false,
  "dry_run": true,
  "audit_note": "Teste de simulação"
}
```

**Request (Ordem sem TP/SL):**
```json
{
  "symbol": "AUDUSD",
  "side": "buy",
  "volume": 0.01,
  "source": "manual_dashboard",
  "confidence": 1.0,
  "uuid": "manual_1704067500",
  "force": false,
  "dry_run": false,
  "audit_note": "Ordem sem TP/SL"
}
```

**Response (200 OK - Sucesso):**
```json
{
  "success": true,
  "ticket": 123456789,
  "message": "Ordem enviada com sucesso",
  "dry_run": false
}
```

**Response (200 OK - Dry Run):**
```json
{
  "success": true,
  "ticket": null,
  "message": "Ordem simulada com sucesso (dry run)",
  "dry_run": true
}
```

**Response (400 Bad Request - Validação Falhou):**
```json
{
  "success": false,
  "error": "Ordem rejeitada pelos validadores",
  "validators": [
    {
      "name": "AI_Validator",
      "type": "ai",
      "approved": false,
      "confidence": 0.35,
      "reason": "Baixa confiança - padrão não identificado",
      "timestamp": "2024-01-01T12:00:01Z"
    },
    {
      "name": "RSI_Strategy",
      "type": "strategy",
      "approved": true,
      "confidence": 0.75,
      "reason": "RSI em zona de sobrevenda",
      "timestamp": "2024-01-01T12:00:01Z"
    }
  ]
}
```

**Response (400 Bad Request - Erro MT5):**
```json
{
  "success": false,
  "error": "Margem insuficiente"
}
```

---

### POST /api/close

**Request:**
```json
{
  "order_id": "123456789",
  "audit_note": "Fechado manualmente via dashboard - lucro atingido"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Ordem fechada com sucesso"
}
```

**Response (400 Bad Request):**
```json
{
  "success": false,
  "error": "Posição não encontrada"
}
```

---

## 🎯 Estratégias

### GET /api/strategies

**Response (200 OK):**
```json
[
  {
    "name": "RSI_Strategy",
    "enabled": true,
    "description": "Estratégia baseada em RSI com confirmação de tendência",
    "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
    "timeframe": "M15",
    "parameters": {
      "rsi_period": 14,
      "rsi_overbought": 70,
      "rsi_oversold": 30,
      "min_confidence": 0.7
    },
    "performance": {
      "total_trades": 150,
      "winning_trades": 95,
      "losing_trades": 55,
      "win_rate": 63.33,
      "profit": 1250.50
    }
  },
  {
    "name": "MACD_Crossover",
    "enabled": false,
    "description": "Cruzamento de MACD com filtro de volatilidade",
    "symbols": ["EURUSD", "AUDUSD"],
    "timeframe": "H1",
    "parameters": {
      "fast_ema": 12,
      "slow_ema": 26,
      "signal_period": 9
    },
    "performance": {
      "total_trades": 80,
      "winning_trades": 48,
      "losing_trades": 32,
      "win_rate": 60.00,
      "profit": 850.00
    }
  }
]
```

---

### POST /api/strategies/toggle

**Request:**
```json
{
  "strategy": "RSI_Strategy",
  "enabled": false
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "strategy": "RSI_Strategy",
  "enabled": false
}
```

---

## 🔔 Webhooks

### POST /hooks/signal

**Request (Sinal do TradingView):**
```json
{
  "symbol": "EURUSD",
  "side": "buy",
  "volume": 0.01,
  "tp": 50,
  "sl": 30,
  "source": "tradingview",
  "confidence": 0.85,
  "uuid": "tv_signal_1704067600"
}
```

**Request (Sinal do Telegram):**
```json
{
  "symbol": "GBPUSD",
  "side": "sell",
  "volume": 0.02,
  "tp": 40,
  "sl": 25,
  "source": "telegram_channel",
  "confidence": 0.75,
  "uuid": "tg_signal_1704067700"
}
```

**Request (Sinal de API Externa):**
```json
{
  "symbol": "USDJPY",
  "side": "buy",
  "volume": 0.05,
  "tp": 60,
  "sl": 35,
  "source": "external_api",
  "confidence": 0.90,
  "uuid": "ext_signal_1704067800",
  "metadata": {
    "provider": "SignalProvider XYZ",
    "signal_id": "abc123",
    "timestamp": "2024-01-01T12:30:00Z"
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Sinal recebido e processado",
  "signal_uuid": "tv_signal_1704067600"
}
```

---

## 📝 Logs

### GET /api/logs?level=ERROR&limit=10

**Response (200 OK):**
```json
[
  {
    "timestamp": "2024-01-01T12:00:00Z",
    "level": "ERROR",
    "message": "Failed to place order: Insufficient margin",
    "module": "mt5_communication",
    "extra": {
      "symbol": "EURUSD",
      "volume": 1.0,
      "required_margin": 1000.0,
      "available_margin": 500.0
    }
  },
  {
    "timestamp": "2024-01-01T11:45:00Z",
    "level": "ERROR",
    "message": "MT5 connection lost",
    "module": "trading_bot_core",
    "extra": {
      "error_code": "CONNECTION_TIMEOUT",
      "retry_attempt": 3
    }
  }
]
```

---

## 🔍 Auditoria

### GET /api/audit?limit=5

**Response (200 OK):**
```json
[
  {
    "timestamp": "2024-01-01T12:00:00Z",
    "user": "admin",
    "action": "place_order",
    "details": {
      "symbol": "EURUSD",
      "side": "buy",
      "volume": 0.01,
      "tp": 50,
      "sl": 30,
      "dry_run": false,
      "audit_note": "Ordem manual de teste"
    },
    "ip_address": "192.168.1.100"
  },
  {
    "timestamp": "2024-01-01T11:55:00Z",
    "user": "admin",
    "action": "close_order",
    "details": {
      "order_id": "123456789",
      "note": "Fechado manualmente - lucro atingido"
    },
    "ip_address": "192.168.1.100"
  },
  {
    "timestamp": "2024-01-01T11:50:00Z",
    "user": "admin",
    "action": "toggle_strategy",
    "details": {
      "strategy": "RSI_Strategy",
      "enabled": false
    },
    "ip_address": "192.168.1.100"
  }
]
```

---

## 🌐 WebSocket

### Cliente → Servidor

**Subscribe:**
```json
{
  "event": "subscribe",
  "data": {
    "channels": ["quotes", "positions", "orders", "logs"]
  }
}
```

**Unsubscribe:**
```json
{
  "event": "unsubscribe",
  "data": {
    "channels": ["logs"]
  }
}
```

**Heartbeat:**
```json
{
  "event": "heartbeat",
  "data": {
    "timestamp": 1704067200000
  }
}
```

---

### Servidor → Cliente

**Quotes:**
```json
{
  "event": "quotes",
  "data": {
    "symbol": "EURUSD",
    "bid": 1.08500,
    "ask": 1.08520,
    "spread": 20,
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

**Positions Update:**
```json
{
  "event": "positions_update",
  "data": [
    {
      "ticket": 123456789,
      "symbol": "EURUSD",
      "type": "buy",
      "volume": 0.10,
      "price_open": 1.08500,
      "price_current": 1.08550,
      "profit": 50.00
    }
  ]
}
```

**Logs Update:**
```json
{
  "event": "logs_update",
  "data": {
    "timestamp": "2024-01-01T12:00:00Z",
    "level": "INFO",
    "message": "Order placed successfully: EURUSD BUY 0.01",
    "module": "mt5_communication"
  }
}
```

**Signals Update:**
```json
{
  "event": "signals_update",
  "data": {
    "uuid": "signal_1704067200",
    "symbol": "EURUSD",
    "side": "buy",
    "volume": 0.01,
    "source": "RSI_Strategy",
    "confidence": 0.85,
    "validators": [
      {
        "name": "AI_Validator",
        "type": "ai",
        "approved": true,
        "confidence": 0.92,
        "reason": "Strong bullish pattern detected"
      }
    ],
    "status": "approved"
  }
}
```

**Error:**
```json
{
  "event": "error",
  "data": {
    "error": "Failed to fetch positions",
    "details": "MT5 connection timeout",
    "code": "MT5_TIMEOUT"
  }
}
```

---

## 🧪 Exemplos curl

### Login
```bash
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### Get Account
```bash
curl http://localhost:5000/api/account \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Place Order
```bash
curl -X POST http://localhost:5000/api/place \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "side": "buy",
    "volume": 0.01,
    "tp": 50,
    "sl": 30,
    "source": "manual_dashboard",
    "confidence": 1.0,
    "uuid": "manual_1704067200",
    "force": false,
    "dry_run": false,
    "audit_note": "Teste via curl"
  }'
```

### Close Order
```bash
curl -X POST http://localhost:5000/api/close \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "123456789",
    "audit_note": "Fechado via curl"
  }'
```

### Toggle Strategy
```bash
curl -X POST http://localhost:5000/api/strategies/toggle \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "RSI_Strategy",
    "enabled": false
  }'
```

### Send Signal (Webhook)
```bash
curl -X POST http://localhost:5000/hooks/signal \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "side": "buy",
    "volume": 0.01,
    "tp": 50,
    "sl": 30,
    "source": "tradingview",
    "confidence": 0.85,
    "uuid": "tv_signal_1704067600"
  }'
```

---

## 🧪 Exemplos wscat

### Conectar
```bash
wscat -c ws://127.0.0.1:9090
```

### Subscribe
```
> {"event":"subscribe","data":{"channels":["quotes","positions"]}}
```

### Heartbeat
```
> {"event":"heartbeat","data":{"timestamp":1704067200000}}
```

---

## 📌 Notas Importantes

1. **UUIDs**: Sempre únicos por sinal. Frontend gera automaticamente se não fornecido.
2. **Timestamps**: Formato ISO 8601 (UTC): `2024-01-01T12:00:00Z`
3. **Volumes**: Sempre em lotes (0.01 = 1 micro lote)
4. **TP/SL**: Podem ser em pips ou preço absoluto (backend decide)
5. **Confidence**: Valor entre 0.0 e 1.0
6. **Force**: Se `true`, ignora validadores AI/estratégias
7. **Dry Run**: Se `true`, apenas simula sem executar no MT5
8. **Audit Note**: Máximo 500 caracteres

---

## 🔗 Integração com mt5_communication.py

O backend Flask deve chamar:

```python
from mt5_communication import MT5Communication

mt5_comm = MT5Communication()

# Processar sinal
result = mt5_comm._process_signal_payload({
    "symbol": "EURUSD",
    "side": "buy",
    "volume": 0.01,
    "tp": 50,
    "sl": 30,
    "source": "manual_dashboard",
    "confidence": 1.0,
    "uuid": "manual_1704067200",
    "force": False,
    "dry_run": False
})

# result = {'success': True, 'ticket': 123456789}
# ou
# result = {'success': False, 'error': 'Margem insuficiente'}
```

---

**Todos os payloads acima são exemplos reais que o frontend React produz e espera receber do backend Flask.**
