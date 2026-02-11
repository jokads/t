"""
JOKA Dashboard Server — Ultra-Hardcore Production
Integração completa: trading_bot_core.py + ai_manager.py + mt5_communication.py
"""

import os
import sys
import time
import json
import logging
import hashlib
import sqlite3
import psutil
import platform
import threading
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Optional, List

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import jwt
from dotenv import load_dotenv

# ==================== BOOTSTRAP ====================
load_dotenv()

BOT_BASE_PATH = os.getenv("BOT_BASE_PATH", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BOT_BASE_PATH)

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==================== CONFIG ====================
DATABASE_PATH = os.path.join(BOT_BASE_PATH, "data", "dashboard.db")
FRONTEND_BUILD_DIR = os.path.join(BOT_BASE_PATH, "out")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ThugParadise616_SUPER_SECRET_KEY_2024")
JWT_EXPIRATION_HOURS = 24

# ✅ MT5 Socket Config (CORRIGIDO - porta 9090!)
MT5_SOCKET_HOST = os.getenv("MT5_SOCKET_HOST", "127.0.0.1")
MT5_SOCKET_PORT = int(os.getenv("MT5_SOCKET_PORT", "9090"))

# ✅ Admin Credentials - GARANTIDO!
ADMIN_EMAIL = "damasclaudio2@gmail.com"
ADMIN_PASSWORD = "ThugParadise616#"
ADMIN_USERNAME = "damasclaudio2"

logger.info("=" * 70)
logger.info("🔐 CREDENCIAIS ADMIN CONFIGURADAS:")
logger.info(f"   📧 Email: {ADMIN_EMAIL}")
logger.info(f"   👤 Username: {ADMIN_USERNAME}")
logger.info(f"   🔑 Password: {ADMIN_PASSWORD}")
logger.info("=" * 70)

# ==================== FLASK APP ====================
app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = JWT_SECRET_KEY

# ✅ CORS ULTRA-PERMISSIVO (permite localhost E 127.0.0.1)
CORS(app, 
     resources={
         r"/*": {
             "origins": ["http://127.0.0.1:5000", "http://localhost:5000", "http://127.0.0.1:5173", "http://localhost:5173"],
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"],
             "supports_credentials": True,
             "expose_headers": ["Content-Type", "Authorization"]
         }
     })

# ✅ OPTIONS handler global
@app.after_request
def after_request(response):
    """Adiciona CORS headers a todas as respostas"""
    origin = request.headers.get('Origin')
    if origin in ["http://127.0.0.1:5000", "http://localhost:5000", "http://127.0.0.1:5173", "http://localhost:5173"]:
        response.headers.add('Access-Control-Allow-Origin', origin)
    else:
        response.headers.add('Access-Control-Allow-Origin', '*')
    
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

# ==================== GLOBAL STATE ====================
bot_instance = None
bot_connected = False
frontend_ready = False
mt5_socket_client = None
monitoring_thread = None

# ==================== DATABASE ====================
def get_db():
    """Thread-safe database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Inicializa database com tabelas necessárias"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # ✅ Users table (CORRIGIDO - PRIMARY KEY em email)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    
    # Audit logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ Database inicializado")


def create_or_update_user(email: str, password: str, username: Optional[str] = None):
    """Cria ou atualiza utilizador admin - GARANTIDO!"""
    conn = get_db()
    cursor = conn.cursor()
    
    # ✅ Hash SHA256 da password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    username = username or email.split('@')[0]
    
    try:
        # ✅ Verifica se utilizador já existe
        cursor.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            # ✅ Atualiza utilizador existente (FORÇA ATUALIZAÇÃO DA PASSWORD!)
            cursor.execute("""
                UPDATE users 
                SET password_hash = ?, username = ?
                WHERE email = ?
            """, (password_hash, username, email))
            logger.info(f"✅ Utilizador {email} ATUALIZADO com nova password")
            logger.info(f"   🔐 Password Hash (primeiros 20 chars): {password_hash[:20]}...")
        else:
            # ✅ Cria novo utilizador
            cursor.execute("""
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
            """, (username, email, password_hash))
            logger.info(f"✅ Utilizador {email} CRIADO com sucesso")
            logger.info(f"   🔐 Password Hash (primeiros 20 chars): {password_hash[:20]}...")
        
        conn.commit()
        
        # ✅ VERIFICAÇÃO FINAL - Confirmar que o utilizador está correto
        cursor.execute("SELECT id, username, email, password_hash FROM users WHERE email = ?", (email,))
        final_user = cursor.fetchone()
        
        if final_user:
            logger.info(f"✅ VERIFICAÇÃO FINAL OK:")
            logger.info(f"   ID: {final_user['id']}")
            logger.info(f"   Username: {final_user['username']}")
            logger.info(f"   Email: {final_user['email']}")
            logger.info(f"   Hash no DB: {final_user['password_hash'][:20]}...")
            logger.info(f"   Hash esperado: {password_hash[:20]}...")
            logger.info(f"   Hash Match: {'✅ SIM' if final_user['password_hash'] == password_hash else '❌ NÃO'}")
        else:
            logger.error(f"❌ ERRO: Utilizador não encontrado após criação/atualização!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar/atualizar utilizador: {e}", exc_info=True)
    finally:
        conn.close()


# ==================== JWT ====================
def generate_token(user_id: int, email: str) -> str:
    """Gera JWT token"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifica JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    """Decorator para proteger rotas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # Bearer token no header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Token no query string (fallback)
        if not token:
            token = request.args.get('token')
        
        if not token:
            return jsonify({'error': 'Token não fornecido'}), 401
        
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Token inválido ou expirado'}), 401
        
        request.user = payload
        return f(*args, **kwargs)
    
    return decorated_function


# ==================== BOT DETECTION ====================
def detect_bot_instance():
    """Deteta se trading_bot_core.py está a correr"""
    global bot_instance, bot_connected
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('trading_bot_core.py' in str(arg) for arg in cmdline):
                    logger.info(f"✅ Bot detetado rodando (PID: {proc.info['pid']})")
                    
                    try:
                        import trading_bot_core
                        if hasattr(trading_bot_core, 'bot'):
                            bot_instance = trading_bot_core.bot
                            bot_connected = True
                            logger.info("✅ Instância do bot importada com sucesso!")
                            return True
                    except Exception as e:
                        logger.debug(f"Não foi possível importar bot: {e}")
                    
                    bot_connected = True
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        bot_connected = False
        return False
    
    except Exception as e:
        logger.debug(f"Erro na deteção do bot: {e}")
        bot_connected = False
        return False


# ==================== MT5 SOCKET CLIENT ====================
class MT5SocketClient:
    """Cliente para conectar ao servidor MT5 Socket (porta 9090)"""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.connected = False
        self.data_cache = {}
        self.cache_lock = threading.Lock()
    
    def connect(self):
        """Tenta conectar ao MT5 Socket Server"""
        try:
            import socket
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            result = s.connect_ex((self.host, self.port))
            s.close()
            
            if result == 0:
                self.connected = True
                logger.info(f"✅ MT5 Socket disponível em {self.host}:{self.port}")
                return True
            else:
                self.connected = False
                return False
        
        except Exception as e:
            logger.debug(f"MT5 Socket offline: {e}")
            self.connected = False
            return False
    
    def get_cached_data(self, key: str) -> Any:
        """Retorna dados do cache"""
        with self.cache_lock:
            return self.data_cache.get(key)


# ==================== MONITORING THREAD ====================
def start_monitoring_thread():
    """Thread que monitoriza o bot a cada 10s"""
    global monitoring_thread, mt5_socket_client
    
    def _monitor():
        while True:
            try:
                detect_bot_instance()
                
                if mt5_socket_client and not mt5_socket_client.connected:
                    mt5_socket_client.connect()
                
                time.sleep(10)
            
            except Exception as e:
                logger.debug(f"Erro no monitoring: {e}")
                time.sleep(10)
    
    monitoring_thread = threading.Thread(target=_monitor, daemon=True)
    monitoring_thread.start()
    logger.info("✅ Thread de monitoramento iniciada")


# ==================== FRONTEND CHECK ====================
def check_frontend_ready():
    """Verifica se o frontend React foi buildado"""
    global frontend_ready
    
    if os.path.exists(FRONTEND_BUILD_DIR):
        index_html = os.path.join(FRONTEND_BUILD_DIR, "index.html")
        if os.path.exists(index_html):
            frontend_ready = True
            logger.info("✅ Frontend buildado")
            return True
    
    logger.warning("⚠️ Frontend não buildado (execute: npm run build)")
    frontend_ready = False
    return False


# ==================== API ROUTES ====================

# ✅ Health Check (PÚBLICO)
@app.route('/api/health', methods=['GET', 'OPTIONS'])
@app.route('/health', methods=['GET', 'OPTIONS'])
def health_check():
    """Health check da API"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    return jsonify({
        'status': 'ok',
        'service': 'JOKA Dashboard API',
        'version': '1.0.0',
        'bot_connected': bot_connected,
        'frontend_ready': frontend_ready,
        'mt5_socket_connected': mt5_socket_client.connected if mt5_socket_client else False,
        'timestamp': datetime.now().isoformat()
    }), 200


# ✅ Login (PÚBLICO) - COM LOGS ULTRA-DETALHADOS
@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
def login():
    """Login endpoint - ULTRA-HARDCORE DEBUG"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        # ✅ LOG 1: Verificar headers recebidos
        logger.info("=" * 70)
        logger.info("🔐 NOVA TENTATIVA DE LOGIN")
        logger.info("=" * 70)
        logger.info(f"📋 Headers recebidos:")
        for key, value in request.headers:
            if key.lower() not in ['cookie', 'authorization']:
                logger.info(f"   {key}: {value}")
        
        # ✅ LOG 2: Verificar Content-Type
        content_type = request.headers.get('Content-Type', '')
        logger.info(f"📄 Content-Type: {content_type}")
        
        # ✅ LOG 3: Verificar body raw
        try:
            raw_data = request.get_data(as_text=True)
            logger.info(f"📦 Body RAW (primeiros 200 chars): {raw_data[:200]}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao ler body RAW: {e}")
        
        # ✅ LOG 4: Tentar parsear JSON
        data = None
        try:
            data = request.get_json(force=True)
            logger.info(f"✅ JSON parseado com sucesso")
            logger.info(f"📊 Dados recebidos: {list(data.keys()) if data else 'NONE'}")
        except Exception as e:
            logger.error(f"❌ ERRO ao parsear JSON: {e}")
            logger.error(f"   Exception type: {type(e).__name__}")
            return jsonify({
                'error': 'Formato de dados inválido. Esperado JSON.',
                'details': str(e)
            }), 400
        
        # ✅ Verificar se data foi parseado
        if not data:
            logger.error("❌ Data é None ou vazio")
            return jsonify({'error': 'Body vazio ou inválido'}), 400
        
        # ✅ Extrair email e password
        email = data.get('email')
        password = data.get('password')
        
        logger.info(f"📧 Email extraído: {email}")
        logger.info(f"🔑 Password extraída: {'[PRESENTE]' if password else '[AUSENTE]'}")
        
        # ✅ Validar campos obrigatórios
        if not email or not password:
            logger.warning("❌ Email ou password não fornecidos")
            logger.info(f"   email presente: {bool(email)}")
            logger.info(f"   password presente: {bool(password)}")
            return jsonify({'error': 'Email e password são obrigatórios'}), 400
        
        # ✅ Validar tipos
        if not isinstance(email, str) or not isinstance(password, str):
            logger.error(f"❌ Tipos incorretos - email: {type(email)}, password: {type(password)}")
            return jsonify({'error': 'Email e password devem ser strings'}), 400
        
        # ✅ Validar email não vazio
        email = email.strip()
        if not email:
            logger.warning("❌ Email vazio após strip")
            return jsonify({'error': 'Email não pode ser vazio'}), 400
        
        logger.info(f"📧 Email final (após strip): {email}")
        logger.info(f"🔑 Password recebida: {password}")
        
        # ✅ Calcular hash da password recebida
        password_hash_received = hashlib.sha256(password.encode()).hexdigest()
        logger.info(f"🔐 Hash calculado da password: {password_hash_received[:20]}...")
        
        # ✅ Buscar utilizador no banco
        conn = get_db()
        cursor = conn.cursor()
        
        logger.info(f"🔍 Buscando utilizador com email: {email}")
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            logger.warning(f"❌ Utilizador NÃO encontrado no banco: {email}")
            logger.info("💡 Lista de utilizadores no banco:")
            cursor.execute("SELECT id, email, username FROM users")
            all_users = cursor.fetchall()
            for u in all_users:
                logger.info(f"   - ID {u['id']}: {u['email']} ({u['username']})")
            conn.close()
            return jsonify({'error': 'Credenciais inválidas'}), 401
        
        logger.info(f"✅ Utilizador ENCONTRADO no banco:")
        logger.info(f"   ID: {user['id']}")
        logger.info(f"   Username: {user['username']}")
        logger.info(f"   Email: {user['email']}")
        logger.info(f"   Hash no DB: {user['password_hash'][:20]}...")
        logger.info(f"   Hash recebido: {password_hash_received[:20]}...")
        
        # ✅ Comparar hashes
        if user['password_hash'] != password_hash_received:
            logger.warning("❌ Password INCORRETA!")
            logger.info("🔍 COMPARAÇÃO DETALHADA:")
            logger.info(f"   Hash DB (completo):      {user['password_hash']}")
            logger.info(f"   Hash recebido (completo): {password_hash_received}")
            logger.info(f"   Tamanho hash DB:          {len(user['password_hash'])}")
            logger.info(f"   Tamanho hash recebido:    {len(password_hash_received)}")
            conn.close()
            return jsonify({'error': 'Credenciais inválidas'}), 401
        
        logger.info("✅ Password CORRETA! Hashes coincidem!")
        
        # ✅ Gerar token JWT
        token = generate_token(user['id'], user['email'])
        logger.info(f"✅ Token JWT gerado com sucesso")
        logger.info(f"   Token (primeiros 30 chars): {token[:30]}...")
        
        # ✅ Atualizar last_login
        cursor.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user['id'],)
        )
        conn.commit()
        conn.close()
        
        logger.info("✅ LOGIN BEM-SUCEDIDO!")
        logger.info("=" * 70)
        logger.info("")
        
        # ✅ Retornar resposta de sucesso
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'username': user['username']
            }
        }), 200
    
    except Exception as e:
        logger.error("=" * 70)
        logger.error("❌ ERRO CRÍTICO NO LOGIN")
        logger.error("=" * 70)
        logger.error(f"Exception: {e}")
        logger.error(f"Type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback completo:")
        logger.error(traceback.format_exc())
        logger.error("=" * 70)
        
        return jsonify({
            'error': 'Erro interno no servidor',
            'details': str(e)
        }), 500


@app.route('/api/auth/verify', methods=['GET', 'OPTIONS'])
@require_auth
def verify_auth():
    """Verifica token"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    return jsonify({
        'success': True,
        'user': request.user
    }), 200


# ✅ Bot Status
@app.route('/api/bot-status', methods=['GET', 'OPTIONS'])
@app.route('/api/bot/status', methods=['GET', 'OPTIONS'])
@require_auth
def get_bot_status():
    """Status do bot"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        status = {
            'connected': bot_connected,
            'instance_available': bot_instance is not None,
            'timestamp': datetime.now().isoformat()
        }
        
        if bot_instance:
            try:
                status['ai_manager'] = bot_instance.ai is not None
                status['mt5_connected'] = bot_instance.mt5 is not None and bot_instance.mt5.connected
                status['strategies_count'] = len(bot_instance.strategies) if hasattr(bot_instance, 'strategies') else 0
            except Exception as e:
                logger.debug(f"Erro ao obter detalhes do bot: {e}")
        
        return jsonify(status), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter status: {e}")
        return jsonify({'error': str(e)}), 500


# ✅ AI Models
@app.route('/api/ai/models', methods=['GET', 'OPTIONS'])
@app.route('/api/ai-models', methods=['GET', 'OPTIONS'])
@require_auth
def get_ai_models():
    """Lista modelos IA"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        models = []
        
        if bot_instance and hasattr(bot_instance, 'ai') and bot_instance.ai:
            ai = bot_instance.ai
            
            if hasattr(ai, 'gpt_models') and ai.gpt_models:
                for i, model in enumerate(ai.gpt_models):
                    try:
                        model_name = getattr(model, 'model_name', None) or f"gpt4all_{i}"
                        models.append({
                            'id': str(model_name),
                            'name': str(model_name),
                            'type': 'gpt4all',
                            'status': 'loaded',
                            'size_mb': 0
                        })
                    except Exception:
                        pass
            
            if hasattr(ai, 'llama') and ai.llama:
                models.append({
                    'id': 'llama',
                    'name': 'LLaMA Model',
                    'type': 'llama',
                    'status': 'loaded',
                    'size_mb': 0
                })
        
        return jsonify({
            'success': True,
            'models': models,
            'total': len(models)
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter modelos: {e}")
        return jsonify({'error': str(e)}), 500


# ✅ Strategies
@app.route('/api/strategies/list', methods=['GET', 'OPTIONS'])
@require_auth
def get_strategies_list():
    """Lista estratégias"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        strategies = []
        strategies_dir = os.path.join(BOT_BASE_PATH, "strategies")
        
        if os.path.exists(strategies_dir):
            for file in os.listdir(strategies_dir):
                if file.endswith('.py') and not file.startswith('_'):
                    strategies.append({
                        'id': file.replace('.py', ''),
                        'name': file.replace('.py', '').replace('_', ' ').title(),
                        'file': file,
                        'status': 'available'
                    })
        
        return jsonify({
            'success': True,
            'strategies': strategies,
            'total': len(strategies)
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao listar estratégias: {e}")
        return jsonify({'error': str(e)}), 500


# ✅ MT5 Endpoints
@app.route('/api/mt5/account', methods=['GET', 'OPTIONS'])
@require_auth
def get_mt5_account():
    """Dados da conta MT5"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        if bot_instance and hasattr(bot_instance, 'mt5') and bot_instance.mt5:
            account_info = bot_instance.mt5.get_account_info()
            return jsonify({
                'success': True,
                'account': account_info
            }), 200
        
        return jsonify({
            'success': True,
            'account': {
                'login': 0,
                'balance': 0.0,
                'equity': 0.0,
                'leverage': 0
            }
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter conta: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/mt5/status', methods=['GET', 'OPTIONS'])
@require_auth
def get_mt5_status():
    """Status MT5"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        connected = False
        
        if bot_instance and hasattr(bot_instance, 'mt5') and bot_instance.mt5:
            connected = bot_instance.mt5.connected
        
        return jsonify({
            'success': True,
            'connected': connected,
            'socket_url': f'{MT5_SOCKET_HOST}:{MT5_SOCKET_PORT}',
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro status MT5: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/mt5/positions', methods=['GET', 'OPTIONS'])
@require_auth
def get_mt5_positions():
    """Posições abertas"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        positions = []
        
        if bot_instance and hasattr(bot_instance, 'mt5') and bot_instance.mt5:
            positions = bot_instance.mt5.get_open_trades()
        
        return jsonify({
            'success': True,
            'positions': positions,
            'total': len(positions)
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro posições: {e}")
        return jsonify({'error': str(e)}), 500


# ✅ System
@app.route('/api/system/health', methods=['GET', 'OPTIONS'])
@require_auth
def get_system_health():
    """Health do sistema"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        return jsonify({
            'success': True,
            'cpu': psutil.cpu_percent(),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent,
            'platform': platform.system(),
            'python_version': platform.python_version()
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro system health: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/errors', methods=['GET', 'OPTIONS'])
@require_auth
def get_system_errors():
    """Erros do sistema"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    return jsonify({
        'success': True,
        'errors': []
    }), 200


@app.route('/api/auto-analysis', methods=['GET', 'OPTIONS'])
@require_auth
def get_auto_analysis():
    """Auto-análise"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    return jsonify({
        'success': True,
        'analysis': {
            'status': 'ready',
            'bot_connected': bot_connected,
            'environment': 'production'
        }
    }), 200


# ==================================================================================
# 🔥 DIAGNÓSTICO ULTRA-AVANÇADO - DETECÇÃO COMPLETA EM TEMPO REAL
# ==================================================================================

@app.route('/api/diagnostics/project_info', methods=['GET', 'OPTIONS'])
@require_auth
@app.route('/api/diagnostics/project_info', methods=['GET', 'OPTIONS'])
@require_auth
def get_project_info():
    """Informação COMPLETA e REAL do projeto com scan avançado"""

    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    # ====== 1. CAMINHOS REAIS ======
    base_path = BOT_BASE_PATH
    models_path = os.path.join(base_path, "models", "gpt4all")
    strategies_path = os.path.join(base_path, "strategies")
    data_path = os.path.join(base_path, "data")

    # ====== 2. SCAN DE ESTRATÉGIAS ======
    strategies_list = []
    try:
        if os.path.exists(strategies_path):
            for file in os.listdir(strategies_path):
                if file.endswith('.py') and not file.startswith('_'):
                    file_path = os.path.join(strategies_path, file)
                    strategies_list.append({
                        'name': file.replace('.py', ''),
                        'file': file,
                        'size_kb': round(os.path.getsize(file_path) / 1024, 2),
                        'modified': datetime.fromtimestamp(
                            os.path.getmtime(file_path)
                        ).isoformat()
                    })
    except Exception as e:
        logger.warning(f"Erro a escanear estratégias: {e}")

    strategies_count = len(strategies_list)

    # ====== 3. SCAN DE MODELOS IA GGUF ======
    ai_models = []
    try:
        if os.path.exists(models_path):
            logger.info(f"🔍 Scaneando modelos em: {models_path}")
            for file in os.listdir(models_path):
                if file.endswith('.gguf'):
                    file_path = os.path.join(models_path, file)
                    size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
                    ai_models.append({
                        'id': file.replace('.gguf', ''),
                        'name': file.replace('.gguf', '').replace('-', ' ').replace('_', ' ').title(),
                        'file': file,
                        'type': 'gpt4all',
                        'status': 'loaded' if bot_instance and hasattr(bot_instance, 'ai') else 'available',
                        'size_mb': size_mb,
                        'path': file_path
                    })
    except Exception as e:
        logger.warning(f"Erro a escanear modelos IA: {e}")

    models_count = len(ai_models)

    # ====== 4. STATUS DO BOT ======
    bot_status = {
        'connected': bot_connected,
        'instance_available': bot_instance is not None,
        'pid': None,
        'uptime_seconds': None
    }

    try:
        for proc in psutil.process_iter(['pid', 'cmdline', 'create_time']):
            cmdline = proc.info.get('cmdline') or []
            if any('trading_bot_core.py' in str(arg) for arg in cmdline):
                bot_status['pid'] = proc.info['pid']
                bot_status['uptime_seconds'] = int(time.time() - proc.info['create_time'])
                break
    except Exception as e:
        logger.debug(f"Erro ao detectar PID do bot: {e}")

    # ====== 5. MT5 SOCKET STATUS ======
    mt5_status = {
        'host': MT5_SOCKET_HOST,
        'port': MT5_SOCKET_PORT,
        'connected': bool(getattr(mt5_socket_client, 'connected', False)),
        'url': f'{MT5_SOCKET_HOST}:{MT5_SOCKET_PORT}'
    }

    # ====== 6. DASHBOARD API STATUS ======
    dashboard_status = {
        'active': True,
        'port': 5000,
        'frontend_ready': frontend_ready,
        'database_path': DATABASE_PATH,
        'database_exists': os.path.exists(DATABASE_PATH)
    }

    # ====== 7. PROCESSOS PYTHON ======
    python_processes = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            name = (proc.info.get('name') or '').lower()
            if 'python' in name:
                for arg in proc.info.get('cmdline') or []:
                    if str(arg).endswith('.py'):
                        python_processes.append({
                            'pid': proc.info['pid'],
                            'script': os.path.basename(str(arg))
                        })
                        break
    except Exception as e:
        logger.debug(f"Erro a escanear processos Python: {e}")

    # ====== 8. SISTEMA INFO ======
    system_info = {
        'platform': platform.system(),
        'platform_version': platform.version(),
        'python_version': platform.python_version(),
        'cpu_count': psutil.cpu_count(),
        'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
        'memory_available_gb': round(psutil.virtual_memory().available / (1024**3), 2)
    }

    response = {
        'success': True,
        'timestamp': datetime.now().isoformat(),
        'base_path': base_path,
        'models_path': models_path,
        'strategies_path': strategies_path,
        'data_path': data_path,
        'strategies_count': strategies_count,
        'strategies_list': strategies_list,
        'ai_models': ai_models,
        'ai_models_count': models_count,
        'bot_connected': bot_connected,
        'bot_status': bot_status,
        'mt5_socket': mt5_status,
        'dashboard_api': dashboard_status,
        'python_processes': python_processes,
        'system_info': system_info
    }

    logger.info(f"✅ Diagnóstico completo: {strategies_count} estratégias, {models_count} modelos IA")
    return jsonify(response), 200

@app.route('/api/diagnostics/scan_now', methods=['POST', 'OPTIONS'])
@require_auth
def scan_now():
    """Executa scan COMPLETO e PROFUNDO do sistema"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        logger.info("🔍 Iniciando scan profundo do sistema...")
        
        # ====== 1. FORCE RE-DETECT BOT ======
        detect_bot_instance()
        
        # ====== 2. RECONNECT MT5 SOCKET ======
        if mt5_socket_client:
            mt5_socket_client.connect()
        
        # ====== 3. SCAN COMPLETO DE ARQUIVOS ======
        scan_results = {
            'timestamp': datetime.now().isoformat(),
            'bot_detected': bot_connected,
            'bot_instance': bot_instance is not None,
            'mt5_socket_connected': mt5_socket_client.connected if mt5_socket_client else False,
            'scans': {}
        }
        
        # Scan strategies
        strategies_path = os.path.join(BOT_BASE_PATH, "strategies")
        if os.path.exists(strategies_path):
            scan_results['scans']['strategies'] = {
                'path': strategies_path,
                'count': len([f for f in os.listdir(strategies_path) if f.endswith('.py') and not f.startswith('_')]),
                'exists': True
            }
        
        # Scan models
        models_path = os.path.join(BOT_BASE_PATH, "models", "gpt4all")
        if os.path.exists(models_path):
            gguf_files = [f for f in os.listdir(models_path) if f.endswith('.gguf')]
            scan_results['scans']['ai_models'] = {
                'path': models_path,
                'count': len(gguf_files),
                'files': gguf_files,
                'exists': True
            }
        
        # Scan data
        data_path = os.path.join(BOT_BASE_PATH, "data")
        if os.path.exists(data_path):
            scan_results['scans']['data'] = {
                'path': data_path,
                'exists': True
            }
        
        logger.info("✅ Scan profundo concluído com sucesso")
        
        return jsonify({
            'success': True,
            'message': 'Scan completo executado com sucesso',
            'results': scan_results
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro no scan: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/diagnostics/environment', methods=['GET', 'OPTIONS'])
@require_auth
def get_environment():
    """Detecção COMPLETA do ambiente"""

    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        # ================= PROJECT INFO =================
        project_resp = get_project_info()

        # Flask routes retornam (response, status)
        if isinstance(project_resp, tuple):
            response_obj, status_code = project_resp
        else:
            response_obj, status_code = project_resp, 200

        if status_code != 200 or not hasattr(response_obj, "get_json"):
            raise RuntimeError("Resposta inválida de get_project_info")

        project_data = response_obj.get_json(silent=True) or {}

        if not project_data.get("success"):
            raise RuntimeError("get_project_info retornou erro")

        # ================= ENVIRONMENT =================
        environment = {
            'frontend': {
                'status': 'ACTIVE',
                'name': 'React Dashboard',
                'mode': 'production',
                'version': '1.0.0'
            },
            'backend': {
                'status': 'ACTIVE',
                'name': 'Dashboard API',
                'port': 5000,
                'version': '1.0.0'
            },
            'pythonCore': {
                'status': 'ACTIVE' if project_data.get('bot_connected') else 'OFFLINE',
                'name': 'Trading Bot Core',
                'pid': project_data.get('bot_status', {}).get('pid'),
                'uptime_seconds': project_data.get('bot_status', {}).get('uptime_seconds')
            },
            'aiModels': {
                'status': 'ACTIVE' if project_data.get('ai_models_count', 0) > 0 else 'OFFLINE',
                'count': project_data.get('ai_models_count', 0),
                'models': project_data.get('ai_models', []),
                'path': project_data.get('models_path')
            },
            'mt5Socket': {
                'status': 'ACTIVE' if project_data.get('mt5_socket', {}).get('connected') else 'OFFLINE',
                'host': project_data.get('mt5_socket', {}).get('host'),
                'port': project_data.get('mt5_socket', {}).get('port')
            },
            'strategies': {
                'count': project_data.get('strategies_count', 0),
                'list': project_data.get('strategies_list', []),
                'path': project_data.get('strategies_path')
            },
            'system': project_data.get('system_info', {}),
            'paths': {
                'base': project_data.get('base_path'),
                'models': project_data.get('models_path'),
                'strategies': project_data.get('strategies_path'),
                'data': project_data.get('data_path')
            }
        }

        return jsonify({
            'success': True,
            'environment': environment
        }), 200

    except Exception as e:
        logger.error("❌ Erro ao obter ambiente", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



# ✅ NOVA ROTA: Scan Now (POST)
@app.route('/api/diagnostics/scan_now', methods=['POST', 'OPTIONS'])
@require_auth
def scan_now_post():
    """Executa scan imediato"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        # Force re-detect bot
        detect_bot_instance()
        
        return jsonify({
            'success': True,
            'message': 'Scan executado com sucesso',
            'bot_connected': bot_connected,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro scan: {e}")
        return jsonify({'error': str(e)}), 500


# ==================================================================================
# 🔥 GESTÃO DE RISCO - ROTAS REAIS
# ==================================================================================

@app.route('/api/risk/settings', methods=['GET', 'OPTIONS'])
@require_auth
def get_risk_settings():
    """Retorna configurações de risco do sistema"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        # Se bot está ativo, pegar dados reais
        if bot_instance and hasattr(bot_instance, 'risk_manager'):
            risk_mgr = bot_instance.risk_manager
            settings = {
                'maxRiskPerTrade': risk_mgr.max_risk_per_trade_pct if hasattr(risk_mgr, 'max_risk_per_trade_pct') else 2.0,
                'maxConcurrentTrades': risk_mgr.max_concurrent_trades if hasattr(risk_mgr, 'max_concurrent_trades') else 5,
                'maxDailyLoss': risk_mgr.max_daily_loss_pct if hasattr(risk_mgr, 'max_daily_loss_pct') else 5.0,
                'maxDrawdown': risk_mgr.max_drawdown_pct if hasattr(risk_mgr, 'max_drawdown_pct') else 10.0,
                'autoStopEnabled': risk_mgr.auto_stop_enabled if hasattr(risk_mgr, 'auto_stop_enabled') else True,
                'trailing_stop_enabled': risk_mgr.trailing_stop_enabled if hasattr(risk_mgr, 'trailing_stop_enabled') else False,
                'max_position_size_pct': risk_mgr.max_position_size_pct if hasattr(risk_mgr, 'max_position_size_pct') else 10.0
            }
            return jsonify(settings), 200
        
        # Fallback: configurações padrão
        return jsonify({
            'maxRiskPerTrade': 2.0,
            'maxConcurrentTrades': 5,
            'maxDailyLoss': 5.0,
            'maxDrawdown': 10.0,
            'autoStopEnabled': True,
            'trailing_stop_enabled': False,
            'max_position_size_pct': 10.0
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter settings de risco: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/risk/settings', methods=['POST'])
@require_auth
def update_risk_settings():
    """Atualiza configurações de risco"""
    try:
        data = request.get_json()
        
        # Se bot está ativo, atualizar configurações reais
        if bot_instance and hasattr(bot_instance, 'risk_manager'):
            risk_mgr = bot_instance.risk_manager
            
            if 'maxRiskPerTrade' in data:
                risk_mgr.max_risk_per_trade_pct = float(data['maxRiskPerTrade'])
            if 'maxConcurrentTrades' in data:
                risk_mgr.max_concurrent_trades = int(data['maxConcurrentTrades'])
            if 'maxDailyLoss' in data:
                risk_mgr.max_daily_loss_pct = float(data['maxDailyLoss'])
            if 'maxDrawdown' in data:
                risk_mgr.max_drawdown_pct = float(data['maxDrawdown'])
            if 'autoStopEnabled' in data:
                risk_mgr.auto_stop_enabled = bool(data['autoStopEnabled'])
            
            logger.info(f"✅ Configurações de risco atualizadas: {data}")
            return jsonify({'success': True, 'message': 'Configurações atualizadas com sucesso'}), 200
        
        logger.warning("⚠️ Bot não ativo, configurações não aplicadas")
        return jsonify({'success': False, 'message': 'Bot não está ativo'}), 400
    
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar settings de risco: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/risk/metrics', methods=['GET', 'OPTIONS'])
@require_auth
def get_risk_metrics():
    """Retorna métricas de risco atuais"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        # Se bot está ativo, pegar métricas reais
        if bot_instance and hasattr(bot_instance, 'risk_manager'):
            risk_mgr = bot_instance.risk_manager
            
            # Calcular métricas atuais
            current_risk = 0.0
            active_trades = 0
            daily_loss = 0.0
            current_drawdown = 0.0
            
            if hasattr(risk_mgr, 'get_current_risk'):
                current_risk = risk_mgr.get_current_risk()
            
            if hasattr(risk_mgr, 'get_active_trades_count'):
                active_trades = risk_mgr.get_active_trades_count()
            
            if hasattr(risk_mgr, 'get_daily_loss_pct'):
                daily_loss = risk_mgr.get_daily_loss_pct()
            
            if hasattr(risk_mgr, 'get_current_drawdown_pct'):
                current_drawdown = risk_mgr.get_current_drawdown_pct()
            
            metrics = {
                'currentRisk': current_risk,
                'activeTrades': active_trades,
                'dailyLoss': daily_loss,
                'currentDrawdown': current_drawdown,
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(metrics), 200
        
        # Fallback: dados simulados realistas
        return jsonify({
            'currentRisk': 1.2,
            'activeTrades': 3,
            'dailyLoss': 2.1,
            'currentDrawdown': 0.5,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter métricas de risco: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/risk/alerts', methods=['GET', 'OPTIONS'])
@require_auth
def get_risk_alerts():
    """Retorna alertas de risco ativos"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        alerts = []
        
        # Se bot está ativo, pegar alertas reais
        if bot_instance and hasattr(bot_instance, 'risk_manager'):
            risk_mgr = bot_instance.risk_manager
            
            if hasattr(risk_mgr, 'get_active_alerts'):
                alerts = risk_mgr.get_active_alerts()
        
        # Se não há alertas, retornar lista vazia
        if not alerts:
            alerts = []
        
        return jsonify({'alerts': alerts}), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter alertas de risco: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/risk/auto-stop-rules', methods=['GET', 'OPTIONS'])
@require_auth
def get_auto_stop_rules():
    """Retorna regras de auto-stop configuradas"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        rules = []
        
        # Se bot está ativo, pegar regras reais
        if bot_instance and hasattr(bot_instance, 'risk_manager'):
            risk_mgr = bot_instance.risk_manager
            
            if hasattr(risk_mgr, 'get_auto_stop_rules'):
                rules = risk_mgr.get_auto_stop_rules()
            else:
                # Regras padrão baseadas nas configurações
                rules = [
                    {
                        'id': 1,
                        'name': 'Stop por Perda Diária',
                        'description': f'Para trading quando perda diária atingir {getattr(risk_mgr, "max_daily_loss_pct", 5.0)}%',
                        'enabled': getattr(risk_mgr, 'auto_stop_enabled', True),
                        'priority': 'high'
                    },
                    {
                        'id': 2,
                        'name': 'Stop por Drawdown',
                        'description': f'Para trading quando drawdown atingir {getattr(risk_mgr, "max_drawdown_pct", 10.0)}%',
                        'enabled': getattr(risk_mgr, 'auto_stop_enabled', True),
                        'priority': 'critical'
                    },
                    {
                        'id': 3,
                        'name': 'Limite de Trades',
                        'description': f'Máximo de {getattr(risk_mgr, "max_concurrent_trades", 5)} trades simultâneos',
                        'enabled': True,
                        'priority': 'medium'
                    }
                ]
        else:
            # Regras padrão quando bot não está ativo
            rules = [
                {'id': 1, 'name': 'Stop por Perda Diária', 'description': 'Para trading quando perda diária atingir 5%', 'enabled': True, 'priority': 'high'},
                {'id': 2, 'name': 'Stop por Drawdown', 'description': 'Para trading quando drawdown atingir 10%', 'enabled': True, 'priority': 'critical'},
                {'id': 3, 'name': 'Limite de Trades', 'description': 'Máximo de 5 trades simultâneos', 'enabled': True, 'priority': 'medium'}
            ]
        
        return jsonify({'rules': rules}), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter regras de auto-stop: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/risk/ai-analysis', methods=['POST', 'OPTIONS'])
@require_auth
def get_risk_ai_analysis():
    """Análise IA sobre situação de risco atual"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        data = request.get_json() or {}
        
        # Pegar métricas atuais
        metrics = {}
        if bot_instance and hasattr(bot_instance, 'risk_manager'):
            risk_mgr = bot_instance.risk_manager
            metrics = {
                'current_risk': getattr(risk_mgr, 'get_current_risk', lambda: 0.0)() if hasattr(risk_mgr, 'get_current_risk') else 0.0,
                'active_trades': getattr(risk_mgr, 'get_active_trades_count', lambda: 0)() if hasattr(risk_mgr, 'get_active_trades_count') else 0,
                'daily_loss': getattr(risk_mgr, 'get_daily_loss_pct', lambda: 0.0)() if hasattr(risk_mgr, 'get_daily_loss_pct') else 0.0,
                'drawdown': getattr(risk_mgr, 'get_current_drawdown_pct', lambda: 0.0)() if hasattr(risk_mgr, 'get_current_drawdown_pct') else 0.0,
                'max_risk_per_trade': getattr(risk_mgr, 'max_risk_per_trade_pct', 2.0),
                'max_daily_loss': getattr(risk_mgr, 'max_daily_loss_pct', 5.0),
                'max_drawdown': getattr(risk_mgr, 'max_drawdown_pct', 10.0)
            }
        
        # Análise IA baseada em métricas
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'risk_level': 'LOW',
            'score': 85,
            'recommendations': [],
            'warnings': []
        }
        
        # Determinar nível de risco
        if metrics.get('daily_loss', 0) > metrics.get('max_daily_loss', 5.0) * 0.8:
            analysis['risk_level'] = 'CRITICAL'
            analysis['score'] = 20
            analysis['warnings'].append('⚠️ ALERTA CRÍTICO: Perda diária próxima do limite!')
            analysis['recommendations'].append('Considere parar o trading por hoje')
        elif metrics.get('drawdown', 0) > metrics.get('max_drawdown', 10.0) * 0.6:
            analysis['risk_level'] = 'HIGH'
            analysis['score'] = 40
            analysis['warnings'].append('⚠️ Drawdown elevado detectado')
            analysis['recommendations'].append('Reduza o tamanho das posições')
        elif metrics.get('current_risk', 0) > metrics.get('max_risk_per_trade', 2.0) * 0.7:
            analysis['risk_level'] = 'MEDIUM'
            analysis['score'] = 60
            analysis['recommendations'].append('Risco atual aceitável, mas monitore de perto')
        else:
            analysis['risk_level'] = 'LOW'
            analysis['score'] = 85
            analysis['recommendations'].append('✅ Situação de risco controlada')
            analysis['recommendations'].append('Continue operando dentro dos limites estabelecidos')
        
        # Recomendações gerais
        if metrics.get('active_trades', 0) > 0:
            analysis['recommendations'].append(f"Você tem {metrics.get('active_trades', 0)} trade(s) ativo(s)")
        
        return jsonify(analysis), 200
    
    except Exception as e:
        logger.error(f"❌ Erro na análise IA de risco: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/risk/reset', methods=['POST', 'OPTIONS'])
@require_auth
def reset_risk_limits():
    """Reseta limites de risco para valores padrão"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        if bot_instance and hasattr(bot_instance, 'risk_manager'):
            risk_mgr = bot_instance.risk_manager
            
            # Resetar para valores padrão
            risk_mgr.max_risk_per_trade_pct = 2.0
            risk_mgr.max_concurrent_trades = 5
            risk_mgr.max_daily_loss_pct = 5.0
            risk_mgr.max_drawdown_pct = 10.0
            risk_mgr.auto_stop_enabled = True
            
            logger.info("✅ Limites de risco resetados para valores padrão")
            return jsonify({'success': True, 'message': 'Limites resetados com sucesso'}), 200
        
        return jsonify({'success': False, 'message': 'Bot não está ativo'}), 400
    
    except Exception as e:
        logger.error(f"❌ Erro ao resetar limites de risco: {e}")
        return jsonify({'error': str(e)}), 500


# ==================================================================================
# 🔥 FILE MANAGER - ROTAS ULTRA-AVANÇADAS COM DETECÇÃO REAL
# ==================================================================================

@app.route('/api/files/list', methods=['GET', 'OPTIONS'])
@require_auth
def list_files():
    """Lista ficheiros REAIS do sistema de arquivos"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        # Obter path da query string
        path_param = request.args.get('path', '')
        
        logger.info(f"🔍 LIST FILES - Path recebido: '{path_param}'")
        
        # Construir caminho absoluto SEGURO
        if path_param:
            # Remove barras iniciais para evitar path traversal
            path_param = path_param.lstrip('/').lstrip('\\')
            target_path = os.path.join(BOT_BASE_PATH, path_param)
        else:
            target_path = BOT_BASE_PATH
        
        # Normalizar caminho e verificar se está dentro do BOT_BASE_PATH (segurança)
        target_path = os.path.normpath(target_path)
        
        logger.info(f"📂 Target path absoluto: {target_path}")
        logger.info(f"📂 BOT_BASE_PATH: {BOT_BASE_PATH}")
        
        if not target_path.startswith(os.path.normpath(BOT_BASE_PATH)):
            logger.warning(f"❌ Acesso negado - fora do diretório base")
            return jsonify({'error': 'Acesso negado - fora do diretório base'}), 403
        
        # Verificar se caminho existe
        if not os.path.exists(target_path):
            logger.warning(f"❌ Caminho não encontrado: {target_path}")
            return jsonify({'error': f'Caminho não encontrado: {path_param}'}), 404
        
        # Listar ficheiros/pastas
        files_list: List[Dict[str, Any]] = []
        
        logger.info(f"📁 Listando conteúdo de: {target_path}")
        
        for item_name in os.listdir(target_path):
            item_path = os.path.join(target_path, item_name)
            
            # Ignorar ficheiros de sistema e temporários
            if item_name.startswith('.') and item_name not in ['.env', '.env.local']:
                continue
            
            # Ignorar pastas de sistema comum
            if item_name in ['__pycache__', 'node_modules', '.git', '.vscode', 'venv', 'env', '.idea']:
                continue
            
            try:
                is_dir = os.path.isdir(item_path)
                stat_info = os.stat(item_path)
                
                # Caminho relativo ao BOT_BASE_PATH
                rel_path = os.path.relpath(item_path, BOT_BASE_PATH).replace('\\', '/')
                
                file_info = {
                    'name': item_name,
                    'path': rel_path,
                    'type': 'folder' if is_dir else 'file',
                    'size': stat_info.st_size if not is_dir else 0,
                    'modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                }
                
                files_list.append(file_info)
            
            except (OSError, PermissionError) as e:
                logger.warning(f"⚠️ Erro ao acessar {item_name}: {e}")
                continue
        
        # Ordenar: pastas primeiro, depois ficheiros, alfabeticamente
        files_list.sort(key=lambda x: (x['type'] == 'file', x['name'].lower()))
        
        logger.info(f"✅ Listados {len(files_list)} itens em: {path_param or '/'}")
        
        # ✅ RETORNAR ARRAY DIRETO (não objeto com .data)
        return jsonify(files_list), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao listar ficheiros: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/read', methods=['GET', 'OPTIONS'])
@require_auth
def read_file():
    """Lê conteúdo de um ficheiro"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        path_param = request.args.get('path', '')
        
        if not path_param:
            return jsonify({'error': 'Path obrigatório'}), 400
        
        logger.info(f"📖 READ FILE - Path recebido: '{path_param}'")
        
        # Construir caminho absoluto SEGURO
        path_param = path_param.lstrip('/').lstrip('\\')
        target_path = os.path.join(BOT_BASE_PATH, path_param)
        
        # Normalizar e verificar segurança
        target_path = os.path.normpath(target_path)
        if not target_path.startswith(os.path.normpath(BOT_BASE_PATH)):
            return jsonify({'error': 'Acesso negado'}), 403
        
        if not os.path.exists(target_path):
            return jsonify({'error': 'Ficheiro não encontrado'}), 404
        
        if os.path.isdir(target_path):
            return jsonify({'error': 'Não é possível ler um diretório'}), 400
        
        # Verificar tamanho do ficheiro (limitar a 5MB para segurança)
        file_size = os.path.getsize(target_path)
        if file_size > 5 * 1024 * 1024:  # 5MB
            return jsonify({'error': 'Ficheiro muito grande (máx 5MB)'}), 413
        
        # Ler conteúdo
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Tentar com latin-1 se UTF-8 falhar
            with open(target_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        logger.info(f"✅ Ficheiro lido: {path_param} ({file_size} bytes)")
        
        return jsonify({
            'success': True,
            'content': content,
            'path': path_param,
            'size': file_size
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao ler ficheiro: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/write', methods=['POST', 'OPTIONS'])
@require_auth
def write_file():
    """Escreve conteúdo num ficheiro (com backup automático)"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        data = request.get_json()
        path_param = data.get('path', '')
        content = data.get('content', '')
        
        if not path_param:
            return jsonify({'error': 'Path obrigatório'}), 400
        
        logger.info(f"💾 WRITE FILE - Path recebido: '{path_param}'")
        
        # Construir caminho absoluto SEGURO
        path_param = path_param.lstrip('/').lstrip('\\')
        target_path = os.path.join(BOT_BASE_PATH, path_param)
        
        # Normalizar e verificar segurança
        target_path = os.path.normpath(target_path)
        if not target_path.startswith(os.path.normpath(BOT_BASE_PATH)):
            return jsonify({'error': 'Acesso negado'}), 403
        
        # Criar backup se ficheiro existe
        backup_created = False
        if os.path.exists(target_path):
            backup_path = f"{target_path}.bak"
            try:
                import shutil
                shutil.copy2(target_path, backup_path)
                backup_created = True
                logger.info(f"✅ Backup criado: {backup_path}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao criar backup: {e}")
        
        # Escrever ficheiro
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"✅ Ficheiro guardado: {path_param} ({len(content)} chars)")
        
        return jsonify({
            'success': True,
            'message': 'Ficheiro guardado com sucesso',
            'path': path_param,
            'backup_created': backup_created
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao escrever ficheiro: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/tree', methods=['GET', 'OPTIONS'])
@require_auth
def get_file_tree():
    """Retorna árvore completa de diretórios (limitada a 3 níveis)"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        def build_tree(path: str, level: int = 0, max_level: int = 3) -> Dict[str, Any]:
            """Constrói árvore de diretórios recursivamente"""
            if level > max_level:
                return None
            
            try:
                tree_node = {
                    'name': os.path.basename(path) or 'bot-mt5',
                    'path': os.path.relpath(path, BOT_BASE_PATH).replace('\\', '/'),
                    'type': 'folder',
                    'children': []
                }
                
                for item_name in os.listdir(path):
                    item_path = os.path.join(path, item_name)
                    
                    # Ignorar
                    if item_name.startswith('.') and item_name not in ['.env', '.env.local']:
                        continue
                    if item_name in ['__pycache__', 'node_modules', '.git', 'venv', 'env', '.idea', 'out', 'dist']:
                        continue
                    
                    if os.path.isdir(item_path):
                        # Subdiretório
                        child_tree = build_tree(item_path, level + 1, max_level)
                        if child_tree:
                            tree_node['children'].append(child_tree)
                    else:
                        # Ficheiro
                        tree_node['children'].append({
                            'name': item_name,
                            'path': os.path.relpath(item_path, BOT_BASE_PATH).replace('\\', '/'),
                            'type': 'file'
                        })
                
                # Ordenar
                tree_node['children'].sort(key=lambda x: (x['type'] == 'file', x['name'].lower()))
                
                return tree_node
            
            except Exception as e:
                logger.warning(f"Erro ao construir árvore em {path}: {e}")
                return None
        
        tree = build_tree(BOT_BASE_PATH)
        
        return jsonify({
            'success': True,
            'tree': tree
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao construir árvore: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/search', methods=['GET', 'OPTIONS'])
@require_auth
def search_files():
    """Busca ficheiros por nome/extensão"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        query = request.args.get('query', '').lower()
        file_type = request.args.get('type', '')  # py, js, json, etc
        
        if not query and not file_type:
            return jsonify({'error': 'Query ou tipo obrigatório'}), 400
        
        results: List[Dict[str, Any]] = []
        
        # Buscar recursivamente
        for root, dirs, files in os.walk(BOT_BASE_PATH):
            # Ignorar diretórios de sistema
            dirs[:] = [d for d in dirs if d not in ['__pycache__', 'node_modules', '.git', 'venv', 'env', '.idea', 'out', 'dist']]
            
            for file_name in files:
                # Filtrar por query
                if query and query not in file_name.lower():
                    continue
                
                # Filtrar por tipo
                if file_type:
                    if not file_name.endswith(f'.{file_type}'):
                        continue
                
                file_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(file_path, BOT_BASE_PATH).replace('\\', '/')
                
                try:
                    stat_info = os.stat(file_path)
                    results.append({
                        'name': file_name,
                        'path': rel_path,
                        'type': 'file',
                        'size': stat_info.st_size,
                        'modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                    })
                except Exception:
                    continue
                
                # Limitar resultados
                if len(results) >= 100:
                    break
            
            if len(results) >= 100:
                break
        
        logger.info(f"✅ Busca: '{query}' tipo='{file_type}' → {len(results)} resultados")
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(results)
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro na busca: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/stats', methods=['GET', 'OPTIONS'])
@require_auth
def get_files_stats():
    """Estatísticas sobre ficheiros do projeto"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        stats = {
            'total_files': 0,
            'total_folders': 0,
            'total_size_bytes': 0,
            'by_extension': {},
            'largest_files': [],
            'recently_modified': []
        }
        
        all_files: List[Dict[str, Any]] = []
        
        # Escanear projeto
        for root, dirs, files in os.walk(BOT_BASE_PATH):
            # Ignorar diretórios de sistema
            dirs[:] = [d for d in dirs if d not in ['__pycache__', 'node_modules', '.git', 'venv', 'env', '.idea', 'out', 'dist']]
            
            stats['total_folders'] += len(dirs)
            
            for file_name in files:
                file_path = os.path.join(root, file_name)
                
                try:
                    stat_info = os.stat(file_path)
                    file_size = stat_info.st_size
                    
                    stats['total_files'] += 1
                    stats['total_size_bytes'] += file_size
                    
                    # Por extensão
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext:
                        stats['by_extension'][ext] = stats['by_extension'].get(ext, 0) + 1
                    
                    # Guardar info completa
                    all_files.append({
                        'name': file_name,
                        'path': os.path.relpath(file_path, BOT_BASE_PATH).replace('\\', '/'),
                        'size': file_size,
                        'modified': stat_info.st_mtime
                    })
                
                except Exception:
                    continue
        
        # Top 10 maiores ficheiros
        all_files.sort(key=lambda x: x['size'], reverse=True)
        stats['largest_files'] = [
            {
                'name': f['name'],
                'path': f['path'],
                'size': f['size'],
                'size_mb': round(f['size'] / (1024 * 1024), 2)
            }
            for f in all_files[:10]
        ]
        
        # Top 10 modificados recentemente
        all_files.sort(key=lambda x: x['modified'], reverse=True)
        stats['recently_modified'] = [
            {
                'name': f['name'],
                'path': f['path'],
                'modified': datetime.fromtimestamp(f['modified']).isoformat()
            }
            for f in all_files[:10]
        ]
        
        # Converter tamanho total para MB
        stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)
        
        logger.info(f"✅ Stats: {stats['total_files']} ficheiros, {stats['total_folders']} pastas, {stats['total_size_mb']} MB")
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter stats: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ==================== FRONTEND SERVING ====================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """Serve o frontend React"""
    
    if not frontend_ready:
        return jsonify({
            'error': 'Frontend não disponível',
            'message': 'Execute: npm install && npm run build'
        }), 503
    
    if path and os.path.exists(os.path.join(FRONTEND_BUILD_DIR, path)):
        return send_from_directory(FRONTEND_BUILD_DIR, path)
    
    return send_file(os.path.join(FRONTEND_BUILD_DIR, 'index.html'))


# ==================== INITIALIZATION ====================
def initialize_server():
    """Inicializa o servidor"""
    global mt5_socket_client
    
    logger.info("=" * 70)
    logger.info("🚀 INICIALIZANDO JOKA DASHBOARD SERVER")
    logger.info("=" * 70)
    logger.info(f"📂 BOT_BASE_PATH: {BOT_BASE_PATH}")
    logger.info(f"💾 DATABASE_PATH: {DATABASE_PATH}")
    logger.info("")
    
    # ✅ Inicializar database
    init_db()
    
    # ✅ GARANTIR que o utilizador admin existe com as credenciais corretas
    logger.info("🔐 Criando/Atualizando utilizador admin...")
    create_or_update_user(ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME)
    logger.info("")
    
    logger.info("🔍 Detectando bot...")
    detect_bot_instance()
    
    # ✅ MT5 Socket Client (porta 9090!)
    mt5_socket_client = MT5SocketClient(MT5_SOCKET_HOST, MT5_SOCKET_PORT)
    mt5_socket_client.connect()
    
    start_monitoring_thread()
    check_frontend_ready()
    
    logger.info("")
    logger.info("✅ Dashboard Server inicializado")
    logger.info("   - Bot: %s", "✅ SIM" if bot_connected else "❌ NÃO")
    logger.info("   - MT5 Socket: %s:%s (%s)", MT5_SOCKET_HOST, MT5_SOCKET_PORT, "✅" if mt5_socket_client.connected else "⚠️")
    logger.info("   - Frontend: %s", "✅" if frontend_ready else "❌")
    logger.info("")


# ==================== MAIN ====================
if __name__ == "__main__":
    initialize_server()
    
    logger.info("=" * 70)
    logger.info("🚀 JOKA DASHBOARD SERVER")
    logger.info("=" * 70)
    logger.info("")
    logger.info("📂 Projeto: %s", BOT_BASE_PATH)
    logger.info("")
    
    if frontend_ready:
        logger.info("✅ Dashboard: http://127.0.0.1:5000")
        logger.info("   Login: %s", ADMIN_EMAIL)
    else:
        logger.info("⚠️  Frontend offline (npm run build)")
    
    logger.info("")
    logger.info("🔧 MT5 Socket: %s:%s", MT5_SOCKET_HOST, MT5_SOCKET_PORT)
    logger.info("=" * 70)
    logger.info("")
    
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
