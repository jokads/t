# Especificação WebSocket - MT5 Trading Dashboard

## Visão Geral

O dashboard utiliza **Socket.IO** para comunicação em tempo real com o backend Flask.

**URL de Conexão:** `ws://127.0.0.1:9090` (configurável via `.env`)

**Biblioteca:** `socket.io-client` (frontend) + `Flask-SocketIO` (backend)

---

## Autenticação

### Conexão Inicial

O cliente envia o token JWT durante a conexão:

```javascript
import { io } from 'socket.io-client';

const socket = io('ws://127.0.0.1:9090', {
  auth: {
    token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
  },
  transports: ['websocket', 'polling']
});
```

### Backend Flask-SocketIO

```python
from flask_socketio import SocketIO, emit, disconnect
from functools import wraps

socketio = SocketIO(app, cors_allowed_origins="*")

def authenticated_only(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = request.args.get('token') or \
                (hasattr(request, 'auth') and request.auth.get('token'))
        if not token or not verify_token(token):
            disconnect()
            return
        return f(*args, **kwargs)
    return wrapped
```

---

## Eventos Cliente → Servidor

### 1. `subscribe`

Inscreve-se em canais de dados em tempo real.

**Payload:**
```json
{
  "channels": ["quotes", "positions", "orders", "logs", "account"]
}
```

**Canais Disponíveis:**
- `quotes` - Cotações em tempo real
- `positions` - Atualizações de posições
- `orders` - Atualizações de ordens
- `logs` - Logs do sistema
- `signals` - Sinais de trading
- `account` - Informações da conta

**Exemplo (JavaScript):**
```javascript
socket.emit('subscribe', {
  channels: ['quotes', 'positions', 'orders']
});
```

**Backend Flask:**
```python
@socketio.on('subscribe')
@authenticated_only
def handle_subscribe(data):
    channels = data.get('channels', [])
    for channel in channels:
        join_room(channel)
    emit('subscribed', {'channels': channels})
```

---

### 2. `unsubscribe`

Cancela inscrição em canais.

**Payload:**
```json
{
  "channels": ["logs"]
}
```

**Backend Flask:**
```python
@socketio.on('unsubscribe')
@authenticated_only
def handle_unsubscribe(data):
    channels = data.get('channels', [])
    for channel in channels:
        leave_room(channel)
    emit('unsubscribed', {'channels': channels})
```

---

### 3. `heartbeat`

Mantém conexão ativa (enviado a cada 30 segundos pelo cliente).

**Payload:**
```json
{
  "timestamp": 1704067200000
}
```

**Backend Flask:**
```python
@socketio.on('heartbeat')
def handle_heartbeat(data):
    emit('heartbeat_ack', {'timestamp': time.time()})
```

---

## Eventos Servidor → Cliente

### 1. `quotes`

Cotações em tempo real de símbolos.

**Payload:**
```json
{
  "symbol": "EURUSD",
  "bid": 1.08500,
  "ask": 1.08520,
  "spread": 20,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Backend Flask (emitir):**
```python
def broadcast_quote(symbol, bid, ask):
    socketio.emit('quotes', {
        'symbol': symbol,
        'bid': bid,
        'ask': ask,
        'spread': int((ask - bid) / point),
        'timestamp': datetime.utcnow().isoformat()
    }, room='quotes')
```

**Frontend (receber):**
```javascript
socket.on('quotes', (data) => {
  console.log(`${data.symbol}: Bid=${data.bid}, Ask=${data.ask}`);
  updateChart(data);
});
```

---

### 2. `positions_update`

Atualização de posições abertas.

**Payload:**
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
  }
]
```

**Backend Flask:**
```python
def broadcast_positions():
    positions = get_open_positions()  # Sua função
    socketio.emit('positions_update', positions, room='positions')
```

---

### 3. `orders_update`

Atualização de ordens pendentes.

**Payload:**
```json
[
  {
    "ticket": 987654321,
    "symbol": "GBPUSD",
    "type": "buy_limit",
    "volume": 0.05,
    "price_open": 1.27000,
    "sl": 1.26500,
    "tp": 1.28000,
    "time_setup": "2024-01-01T11:00:00Z",
    "state": "pending",
    "comment": "Manual order"
  }
]
```

---

### 4. `logs_update`

Novo log do sistema.

**Payload:**
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "message": "Order placed successfully: EURUSD BUY 0.01",
  "module": "mt5_communication",
  "extra": {
    "ticket": 123456789,
    "symbol": "EURUSD"
  }
}
```

**Backend Flask:**
```python
def log_and_broadcast(level, message, module, **extra):
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'level': level,
        'message': message,
        'module': module,
        'extra': extra
    }
    socketio.emit('logs_update', log_entry, room='logs')
```

---

### 5. `signals_update`

Novo sinal de trading recebido.

**Payload:**
```json
{
  "uuid": "signal_1234567890",
  "symbol": "EURUSD",
  "side": "buy",
  "volume": 0.01,
  "tp": 50,
  "sl": 30,
  "source": "RSI_Strategy",
  "confidence": 0.85,
  "timestamp": "2024-01-01T12:00:00Z",
  "validators": [
    {
      "name": "AI_Validator",
      "type": "ai",
      "approved": true,
      "confidence": 0.92,
      "reason": "Strong bullish pattern detected",
      "timestamp": "2024-01-01T12:00:01Z"
    },
    {
      "name": "RSI_Strategy",
      "type": "strategy",
      "approved": true,
      "confidence": 0.85,
      "reason": "RSI oversold + trend confirmation",
      "timestamp": "2024-01-01T12:00:01Z"
    }
  ],
  "status": "approved"
}
```

---

### 6. `account_update`

Atualização de informações da conta.

**Payload:**
```json
{
  "balance": 10000.00,
  "equity": 10250.50,
  "margin": 500.00,
  "free_margin": 9750.50,
  "margin_level": 2050.10,
  "profit": 250.50,
  "currency": "USD"
}
```

---

### 7. `error`

Erro do servidor.

**Payload:**
```json
{
  "error": "Failed to place order",
  "details": "Insufficient margin",
  "code": "INSUFFICIENT_MARGIN"
}
```

---

### 8. `connected`

Confirmação de conexão bem-sucedida.

**Payload:**
```json
{
  "message": "Connected to MT5 Trading Dashboard",
  "server_time": "2024-01-01T12:00:00Z"
}
```

---

### 9. `disconnected`

Notificação de desconexão.

**Payload:**
```json
{
  "reason": "Server shutdown",
  "reconnect": true
}
```

---

## Reconexão Automática

O cliente implementa reconexão automática:

```javascript
socket.on('disconnect', (reason) => {
  console.log('Disconnected:', reason);
  
  if (reason === 'io server disconnect') {
    // Servidor desconectou, reconectar manualmente
    socket.connect();
  }
  // Caso contrário, Socket.IO reconecta automaticamente
});

socket.on('connect_error', (error) => {
  console.error('Connection error:', error);
  // Tentar novamente após delay
});
```

**Configuração de Reconexão:**
```javascript
const socket = io('ws://127.0.0.1:9090', {
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 3000,
  reconnectionDelayMax: 10000
});
```

---

## Exemplo Completo Backend Flask

```python
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import time
from threading import Thread

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Thread para broadcast de cotações
def quote_broadcaster():
    while True:
        # Obter cotações do MT5
        quotes = get_mt5_quotes()  # Sua função
        for quote in quotes:
            socketio.emit('quotes', quote, room='quotes')
        time.sleep(1)

# Thread para broadcast de posições
def position_broadcaster():
    while True:
        positions = get_open_positions()  # Sua função
        socketio.emit('positions_update', positions, room='positions')
        time.sleep(2)

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('connected', {
        'message': 'Connected to MT5 Trading Dashboard',
        'server_time': time.time()
    })

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')

@socketio.on('subscribe')
def handle_subscribe(data):
    channels = data.get('channels', [])
    for channel in channels:
        join_room(channel)
    emit('subscribed', {'channels': channels})

@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    channels = data.get('channels', [])
    for channel in channels:
        leave_room(channel)
    emit('unsubscribed', {'channels': channels})

@socketio.on('heartbeat')
def handle_heartbeat(data):
    emit('heartbeat_ack', {'timestamp': time.time()})

if __name__ == '__main__':
    # Iniciar threads de broadcast
    Thread(target=quote_broadcaster, daemon=True).start()
    Thread(target=position_broadcaster, daemon=True).start()
    
    # Iniciar servidor
    socketio.run(app, host='127.0.0.1', port=9090, debug=True)
```

---

## Exemplo Completo Frontend React

```typescript
import { useEffect, useState } from 'react';
import { wsService } from './services/websocket.service';

function App() {
  const [connected, setConnected] = useState(false);
  const [quotes, setQuotes] = useState<any[]>([]);

  useEffect(() => {
    // Conectar
    wsService.connect();

    // Eventos de conexão
    wsService.on('internal:connected', () => {
      setConnected(true);
      wsService.subscribe(['quotes', 'positions', 'orders']);
    });

    wsService.on('internal:disconnected', () => {
      setConnected(false);
    });

    // Eventos de dados
    wsService.on('quotes', (data) => {
      setQuotes(prev => [data, ...prev].slice(0, 10));
    });

    return () => {
      wsService.disconnect();
    };
  }, []);

  return (
    <div>
      <h1>Status: {connected ? 'Conectado' : 'Desconectado'}</h1>
      <ul>
        {quotes.map((q, i) => (
          <li key={i}>{q.symbol}: {q.bid} / {q.ask}</li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Testes com wscat

Instale wscat:
```bash
npm install -g wscat
```

Conecte ao servidor:
```bash
wscat -c ws://127.0.0.1:9090
```

Envie mensagens:
```json
{"event": "subscribe", "data": {"channels": ["quotes"]}}
```

---

## Segurança

1. **Autenticação JWT**: Sempre valide tokens
2. **Rate Limiting**: Limite mensagens por cliente
3. **Validação de Payload**: Valide todos os dados recebidos
4. **CORS**: Configure origens permitidas
5. **SSL/TLS**: Use WSS em produção

---

## Performance

- **Throttling**: Limite frequência de broadcasts (ex: cotações a cada 1s)
- **Rooms**: Use rooms para segmentar clientes
- **Compression**: Ative compressão Socket.IO
- **Binary Data**: Use binary para dados grandes

---

## Troubleshooting

**Problema:** Cliente não conecta
- Verifique firewall/porta 9090
- Confirme que Flask-SocketIO está rodando
- Verifique URL no `.env`

**Problema:** Desconexões frequentes
- Aumente timeout de heartbeat
- Verifique estabilidade da rede
- Revise logs do servidor

**Problema:** Dados não chegam
- Confirme que cliente fez `subscribe`
- Verifique se servidor está emitindo para room correto
- Veja console do navegador para erros
