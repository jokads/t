# Guia de Integração Backend - MT5 Trading Dashboard

## 📋 Visão Geral

Este guia detalha como implementar o backend Flask que se integra ao seu projeto existente em `C:\bot-mt5\` e serve o frontend React.

---

## 🎯 Objetivos

1. Criar API REST Flask que expõe endpoints do contrato OpenAPI
2. Implementar servidor WebSocket (Flask-SocketIO) para dados em tempo real
3. Integrar com módulos existentes: `trading_bot_core.py`, `mt5_communication.py`, `ai_manager.py`
4. Implementar autenticação, auditoria e segurança
5. Rodar em Windows 11 com HTTPS (opcional)

---

## 📁 Estrutura de Arquivos Recomendada

```
C:\bot-mt5\
├── trading_bot_core.py          # Seu bot existente
├── mt5_communication.py         # Ponte MT5
├── ai_manager.py                # AIManager
├── strategies/                  # Estratégias
├── telegram_handler.py          # Telegram
├── mq4/                         # Arquivos MQ4
│
└── dashboard/                   # NOVO - Backend Flask
    ├── app.py                   # Aplicação Flask principal
    ├── config.py                # Configurações
    ├── auth.py                  # Autenticação JWT
    ├── routes/
    │   ├── __init__.py
    │   ├── account.py           # Endpoints de conta
    │   ├── trading.py           # Endpoints de trading
    │   ├── strategies.py        # Endpoints de estratégias
    │   ├── config_routes.py     # Endpoints de configuração
    │   ├── logs.py              # Endpoints de logs
    │   └── webhooks.py          # Webhooks
    ├── websocket/
    │   ├── __init__.py
    │   └── handlers.py          # Handlers WebSocket
    ├── services/
    │   ├── __init__.py
    │   ├── mt5_service.py       # Wrapper para mt5_communication
    │   ├── strategy_service.py  # Gerenciamento de estratégias
    │   └── audit_service.py     # Auditoria
    ├── middleware/
    │   ├── __init__.py
    │   ├── auth_middleware.py   # Middleware de autenticação
    │   └── rate_limit.py        # Rate limiting
    ├── audit/
    │   └── trades_audit.jsonl   # Logs de auditoria
    ├── certs/                   # Certificados SSL (opcional)
    │   ├── cert.pem
    │   └── key.pem
    ├── .env                     # Variáveis de ambiente
    ├── requirements.txt         # Dependências Python
    └── README.md                # Documentação
```

---

## 🔧 Passo 1: Instalação de Dependências

### requirements.txt

```txt
Flask==3.0.0
Flask-CORS==4.0.0
Flask-SocketIO==5.3.5
python-socketio==5.10.0
eventlet==0.33.3
PyJWT==2.8.0
python-dotenv==1.0.0
MetaTrader5==5.0.45
requests==2.31.0
waitress==2.1.2
```

### Instalar

```bash
cd C:\bot-mt5\dashboard
pip install -r requirements.txt
```

---

## 🔧 Passo 2: Configuração (.env)

### dashboard/.env

```env
# Flask
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here-change-in-production

# Server
HOST=127.0.0.1
PORT=5000
WS_PORT=9090

# Authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
JWT_SECRET=your-jwt-secret-here
JWT_EXPIRATION=3600

# MT5 Paths (ajuste conforme seu projeto)
MT5_COMM_PATH=C:\bot-mt5\mt5_communication.py
TRADING_BOT_PATH=C:\bot-mt5\trading_bot_core.py
AI_MANAGER_PATH=C:\bot-mt5\ai_manager.py
STRATEGIES_PATH=C:\bot-mt5\strategies

# Audit
AUDIT_FILE=C:\bot-mt5\dashboard\audit\trades_audit.jsonl

# HTTPS (opcional)
USE_HTTPS=false
CERT_FILE=C:\bot-mt5\dashboard\certs\cert.pem
KEY_FILE=C:\bot-mt5\dashboard\certs\key.pem

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
```

---

## 🔧 Passo 3: Autenticação (auth.py)

```python
import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify

SECRET_KEY = os.getenv('JWT_SECRET', 'your-jwt-secret')
JWT_EXPIRATION = int(os.getenv('JWT_EXPIRATION', 3600))

def generate_token(username):
    """Gera token JWT"""
    payload = {
        'username': username,
        'exp': datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    """Verifica token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Decorator para proteger rotas"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Token no header Authorization: Bearer <token>
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Token is invalid or expired'}), 401
        
        # Adiciona username ao request
        request.current_user = payload['username']
        return f(*args, **kwargs)
    
    return decorated
```

---

## 🔧 Passo 4: Serviço MT5 (services/mt5_service.py)

```python
import sys
import os

# Adicionar caminho do projeto ao sys.path
sys.path.insert(0, 'C:\\bot-mt5')

# Importar módulos existentes
try:
    from mt5_communication import MT5Communication
    from ai_manager import AIManager
except ImportError as e:
    print(f"Erro ao importar módulos: {e}")
    MT5Communication = None
    AIManager = None

class MT5Service:
    """Wrapper para mt5_communication.py"""
    
    def __init__(self):
        if MT5Communication:
            self.mt5_comm = MT5Communication()
        else:
            self.mt5_comm = None
    
    def get_account_info(self):
        """Retorna informações da conta"""
        if not self.mt5_comm:
            return self._mock_account()
        
        try:
            account = self.mt5_comm.get_account_info()
            return {
                'balance': account.balance,
                'equity': account.equity,
                'margin': account.margin,
                'free_margin': account.margin_free,
                'margin_level': account.margin_level,
                'profit': account.profit,
                'currency': account.currency,
                'leverage': account.leverage,
                'server': account.server,
                'name': account.name,
                'number': account.login
            }
        except Exception as e:
            print(f"Erro ao obter conta: {e}")
            return self._mock_account()
    
    def get_positions(self):
        """Retorna posições abertas"""
        if not self.mt5_comm:
            return []
        
        try:
            positions = self.mt5_comm.get_positions()
            return [self._format_position(p) for p in positions]
        except Exception as e:
            print(f"Erro ao obter posições: {e}")
            return []
    
    def get_orders(self, status='open'):
        """Retorna ordens"""
        if not self.mt5_comm:
            return []
        
        try:
            orders = self.mt5_comm.get_orders()
            return [self._format_order(o) for o in orders]
        except Exception as e:
            print(f"Erro ao obter ordens: {e}")
            return []
    
    def place_order(self, payload):
        """
        Envia ordem para MT5
        Chama mt5_communication._process_signal_payload(payload)
        """
        if not self.mt5_comm:
            return {'success': False, 'error': 'MT5 não conectado'}
        
        try:
            # Chamar método do seu mt5_communication
            result = self.mt5_comm._process_signal_payload(payload)
            return result
        except Exception as e:
            print(f"Erro ao enviar ordem: {e}")
            return {'success': False, 'error': str(e)}
    
    def close_position(self, ticket, audit_note=''):
        """Fecha posição"""
        if not self.mt5_comm:
            return {'success': False, 'error': 'MT5 não conectado'}
        
        try:
            result = self.mt5_comm.close_position(int(ticket))
            return {'success': result, 'message': 'Posição fechada'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _format_position(self, position):
        """Formata posição para JSON"""
        return {
            'ticket': position.ticket,
            'symbol': position.symbol,
            'type': 'buy' if position.type == 0 else 'sell',
            'volume': position.volume,
            'price_open': position.price_open,
            'price_current': position.price_current,
            'sl': position.sl,
            'tp': position.tp,
            'profit': position.profit,
            'swap': position.swap,
            'commission': position.commission,
            'time': position.time.isoformat() if hasattr(position.time, 'isoformat') else str(position.time),
            'comment': position.comment
        }
    
    def _format_order(self, order):
        """Formata ordem para JSON"""
        return {
            'ticket': order.ticket,
            'symbol': order.symbol,
            'type': order.type_description,
            'volume': order.volume_initial,
            'price_open': order.price_open,
            'sl': order.sl,
            'tp': order.tp,
            'time_setup': order.time_setup.isoformat() if hasattr(order.time_setup, 'isoformat') else str(order.time_setup),
            'state': order.state_description,
            'comment': order.comment
        }
    
    def _mock_account(self):
        """Dados mock para testes"""
        return {
            'balance': 10000.00,
            'equity': 10250.50,
            'margin': 500.00,
            'free_margin': 9750.50,
            'margin_level': 2050.10,
            'profit': 250.50,
            'currency': 'USD',
            'leverage': 100,
            'server': 'Demo',
            'name': 'Test Account',
            'number': 12345678
        }

# Instância global
mt5_service = MT5Service()
```

---

## 🔧 Passo 5: Rotas de Trading (routes/trading.py)

```python
from flask import Blueprint, request, jsonify
from auth import token_required
from services.mt5_service import mt5_service
from services.audit_service import audit_service
import uuid
from datetime import datetime

trading_bp = Blueprint('trading', __name__)

@trading_bp.route('/api/positions', methods=['GET'])
@token_required
def get_positions():
    """GET /api/positions - Retorna posições abertas"""
    try:
        positions = mt5_service.get_positions()
        return jsonify(positions), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/orders', methods=['GET'])
@token_required
def get_orders():
    """GET /api/orders - Retorna ordens"""
    try:
        status = request.args.get('status', 'open')
        orders = mt5_service.get_orders(status)
        return jsonify(orders), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/place', methods=['POST'])
@token_required
def place_order():
    """
    POST /api/place - Envia ordem
    
    Payload esperado:
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
        "audit_note": "Ordem manual"
    }
    """
    try:
        data = request.get_json()
        
        # Validação básica
        required_fields = ['symbol', 'side', 'volume']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Campo obrigatório: {field}'}), 400
        
        # Gerar UUID se não fornecido
        if 'uuid' not in data:
            data['uuid'] = f"manual_{int(datetime.now().timestamp())}"
        
        # Valores padrão
        data.setdefault('source', 'manual_dashboard')
        data.setdefault('confidence', 1.0)
        data.setdefault('force', False)
        data.setdefault('dry_run', False)
        
        # Auditoria
        audit_service.log_action(
            user=request.current_user,
            action='place_order',
            details=data,
            ip_address=request.remote_addr
        )
        
        # Enviar ordem
        result = mt5_service.place_order(data)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'ticket': result.get('ticket'),
                'message': 'Ordem enviada com sucesso',
                'dry_run': data.get('dry_run', False)
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido')
            }), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/close', methods=['POST'])
@token_required
def close_order():
    """POST /api/close - Fecha ordem/posição"""
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        audit_note = data.get('audit_note', '')
        
        if not order_id:
            return jsonify({'error': 'order_id é obrigatório'}), 400
        
        # Auditoria
        audit_service.log_action(
            user=request.current_user,
            action='close_order',
            details={'order_id': order_id, 'note': audit_note},
            ip_address=request.remote_addr
        )
        
        # Fechar
        result = mt5_service.close_position(order_id, audit_note)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Ordem fechada com sucesso'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('error')
            }), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/history', methods=['GET'])
@token_required
def get_history():
    """GET /api/history - Histórico de trades"""
    try:
        # Implementar conforme seu sistema
        # Exemplo: mt5_service.get_history(from_date, to_date, limit)
        return jsonify([]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## 🔧 Passo 6: Aplicação Principal (app.py)

```python
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv
import os

# Carregar .env
load_dotenv()

# Criar app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# CORS
CORS(app, origins=os.getenv('CORS_ORIGINS', '*').split(','))

# SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins=os.getenv('CORS_ORIGINS', '*').split(','),
    async_mode='eventlet'
)

# Importar rotas
from routes.account import account_bp
from routes.trading import trading_bp
from routes.strategies import strategies_bp
from routes.config_routes import config_bp
from routes.logs import logs_bp
from routes.webhooks import webhooks_bp
from auth import generate_token

# Registrar blueprints
app.register_blueprint(account_bp)
app.register_blueprint(trading_bp)
app.register_blueprint(strategies_bp)
app.register_blueprint(config_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(webhooks_bp)

# Importar handlers WebSocket
from websocket.handlers import register_websocket_handlers
register_websocket_handlers(socketio)

# Rota de login
@app.route('/api/login', methods=['POST'])
def login():
    from flask import request
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # Validar credenciais (simplificado)
    if username == os.getenv('ADMIN_USERNAME') and password == os.getenv('ADMIN_PASSWORD'):
        token = generate_token(username)
        return jsonify({
            'token': token,
            'expires_in': int(os.getenv('JWT_EXPIRATION', 3600)),
            'user': {'username': username, 'role': 'admin'}
        }), 200
    else:
        return jsonify({'error': 'Credenciais inválidas'}), 401

# Health check
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'mt5_connected': True,  # Verificar conexão real
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    }), 200

# Executar
if __name__ == '__main__':
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('WS_PORT', 9090))
    
    print(f"🚀 MT5 Trading Dashboard Backend")
    print(f"📡 WebSocket: ws://{host}:{port}")
    print(f"🌐 REST API: http://{host}:5000")
    
    socketio.run(
        app,
        host=host,
        port=port,
        debug=True
    )
```

---

## 🔧 Passo 7: Handlers WebSocket (websocket/handlers.py)

```python
from flask_socketio import emit, join_room, leave_room
from threading import Thread
import time

def register_websocket_handlers(socketio):
    """Registra handlers WebSocket"""
    
    @socketio.on('connect')
    def handle_connect():
        print(f'Cliente conectado')
        emit('connected', {
            'message': 'Conectado ao MT5 Trading Dashboard',
            'server_time': time.time()
        })
    
    @socketio.on('disconnect')
    def handle_disconnect():
        print(f'Cliente desconectado')
    
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
    
    # Thread para broadcast de cotações
    def quote_broadcaster():
        while True:
            # Obter cotações do MT5
            # quotes = mt5_service.get_quotes()
            # for quote in quotes:
            #     socketio.emit('quotes', quote, room='quotes')
            time.sleep(1)
    
    # Iniciar thread
    Thread(target=quote_broadcaster, daemon=True).start()
```

---

## 🔧 Passo 8: Auditoria (services/audit_service.py)

```python
import json
import os
from datetime import datetime

class AuditService:
    def __init__(self):
        self.audit_file = os.getenv('AUDIT_FILE', 'audit/trades_audit.jsonl')
        os.makedirs(os.path.dirname(self.audit_file), exist_ok=True)
    
    def log_action(self, user, action, details, ip_address=None):
        """Grava ação em arquivo de auditoria"""
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user': user,
            'action': action,
            'details': details,
            'ip_address': ip_address
        }
        
        with open(self.audit_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
    
    def get_audit_logs(self, limit=50, offset=0):
        """Lê logs de auditoria"""
        if not os.path.exists(self.audit_file):
            return []
        
        with open(self.audit_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        logs = [json.loads(line) for line in lines]
        return logs[offset:offset+limit]

audit_service = AuditService()
```

---

## 🚀 Passo 9: Executar Backend

### Modo Desenvolvimento

```bash
cd C:\bot-mt5\dashboard
python app.py
```

### Modo Produção (Waitress)

```bash
waitress-serve --host=127.0.0.1 --port=9090 app:app
```

---

## 🧪 Passo 10: Testar Endpoints

### Teste com curl

```bash
# Login
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"admin123\"}"

# Health Check
curl http://localhost:5000/api/health

# Account (com token)
curl http://localhost:5000/api/account \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

# Place Order
curl -X POST http://localhost:5000/api/place \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"EURUSD\",\"side\":\"buy\",\"volume\":0.01,\"tp\":50,\"sl\":30,\"dry_run\":true}"
```

---

## 🔒 Passo 11: HTTPS (Opcional)

### Gerar Certificado Auto-assinado

```powershell
# PowerShell (como Administrador)
cd C:\bot-mt5\dashboard\certs

# Gerar certificado
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

### Configurar Flask

```python
if os.getenv('USE_HTTPS', 'false').lower() == 'true':
    cert_file = os.getenv('CERT_FILE')
    key_file = os.getenv('KEY_FILE')
    socketio.run(app, host=host, port=port, certfile=cert_file, keyfile=key_file)
else:
    socketio.run(app, host=host, port=port)
```

---

## 🛡️ Segurança

1. **Altere credenciais padrão** em `.env`
2. **Use HTTPS em produção**
3. **Implemente rate limiting** (Flask-Limiter)
4. **Valide todos os inputs**
5. **Mantenha logs de auditoria**
6. **Não exponha erros detalhados** ao cliente

---

## 📝 Checklist de Implementação

- [ ] Instalar dependências (`pip install -r requirements.txt`)
- [ ] Configurar `.env` com caminhos corretos
- [ ] Implementar `auth.py` (JWT)
- [ ] Implementar `services/mt5_service.py` (integração MT5)
- [ ] Implementar rotas REST (account, trading, strategies, etc)
- [ ] Implementar handlers WebSocket
- [ ] Implementar auditoria
- [ ] Testar endpoints com curl
- [ ] Testar WebSocket com wscat
- [ ] Conectar frontend React
- [ ] Configurar HTTPS (opcional)
- [ ] Documentar customizações

---

## 🐛 Troubleshooting

**Erro: ModuleNotFoundError: No module named 'mt5_communication'**
- Verifique `sys.path.insert(0, 'C:\\bot-mt5')` em `mt5_service.py`
- Confirme que `mt5_communication.py` existe

**Erro: Port already in use**
- Altere porta em `.env` (PORT ou WS_PORT)
- Ou mate processo: `netstat -ano | findstr :9090` e `taskkill /PID <PID> /F`

**Frontend não conecta**
- Verifique CORS_ORIGINS em `.env`
- Confirme que backend está rodando
- Veja console do navegador para erros

---

## 📞 Próximos Passos

1. Implemente rotas faltantes (strategies, config, logs)
2. Adicione validadores AI ao fluxo de ordens
3. Implemente broadcast WebSocket de cotações em tempo real
4. Configure serviço Windows para auto-start
5. Adicione testes unitários (pytest)

---

**Documentação Completa:**
- `API_CONTRACT.yaml` - Contrato OpenAPI v3
- `WEBSOCKET_SPEC.md` - Especificação WebSocket
- `PAYLOAD_EXAMPLES.md` - Exemplos de payloads
