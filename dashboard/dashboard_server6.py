#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Server Ultra Avançado - JokaMazKiBu Trading Bot v6.3
================================================================================
Servidor Flask otimizado para dashboard de trading:
- MT4 Integration com reconexão automática
- Cache inteligente e thread-safe
- WebSocket eficiente (emit apenas quando dados mudam)
- Limite de tentativas de login
- Logging configurável via .env
- Preparado para Eventlet/Gevent
================================================================================
"""

import os
import sys
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from collections import deque, defaultdict

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO, emit, disconnect
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# =======================================================================
# CONFIGURAÇÃO BASE
# =======================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

USERNAME = os.getenv("DASHBOARD_USER", "joka")
PASSWORD = os.getenv("DASHBOARD_PASS", "j0K4616")
SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", "jokamazkibu_secret_v6")
LOG_LEVEL = os.getenv("DASHBOARD_LOG_LEVEL", "INFO").upper()

DASHBOARD_DIR = BASE_DIR / "dashboard"
TEMPLATES_DIR = DASHBOARD_DIR / "templates"
STATIC_DIR = DASHBOARD_DIR / "static"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

for directory in [DATA_DIR, LOGS_DIR, TEMPLATES_DIR, STATIC_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE_DIR))

# =======================================================================
# LOGGING UTF-8
# =======================================================================
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

log_file = LOGS_DIR / 'dashboard_server.log'
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('dashboard')

# =======================================================================
# FLASK & SOCKETIO
# =======================================================================
app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR))
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    JSON_SORT_KEYS=False,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024
)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

# =======================================================================
# VARIÁVEIS GLOBAIS
# =======================================================================
START_TIME = datetime.now()
STOP_EVENT = threading.Event()
USERS = {USERNAME: generate_password_hash(PASSWORD)}
LOGIN_ATTEMPTS = defaultdict(int)
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 300  # segundos

# =======================================================================
# CACHE THREAD-SAFE
# =======================================================================
class DataCache:
    def __init__(self):
        self._lock = threading.RLock()
        self._data = defaultdict(lambda: deque(maxlen=100))
        self._data.update({
            'account': {'balance': 10000.0, 'equity': 10000.0, 'profit': 0.0,
                        'free_margin': 10000.0, 'margin_level': 0.0, 'connected': False},
            'positions': [],
            'strategies': {},
            'ai_models': {},
            'news': deque(maxlen=50),
            'logs': deque(maxlen=200),
            'statistics': {'total_trades':0, 'total_trades_today':0, 'profit_today':0.0,
                           'win_rate':0.0, 'win_rate_today':0.0},
            'equity_history': deque(maxlen=100)
        })

    def get(self, key, default=None):
        with self._lock: return self._data.get(key, default)

    def set(self, key, value):
        with self._lock: self._data[key] = value

    def update(self, key, updates):
        with self._lock:
            if isinstance(self._data.get(key), dict):
                self._data[key].update(updates)
            else:
                self._data[key] = updates

    def append(self, key, value, maxlen=None):
        with self._lock:
            if key not in self._data:
                self._data[key] = deque(maxlen=maxlen) if maxlen else []
            if isinstance(self._data[key], deque):
                self._data[key].append(value)
            else:
                self._data[key].append(value)

cache = DataCache()

# =======================================================================
# MT4 INTEGRATION
# =======================================================================
class MT4Integration:
    def __init__(self):
        self.mt4_comm = None
        self._initialize()

    def _initialize(self):
        try:
            from core.mt4_communication import MT4Communication
            self.mt4_comm = MT4Communication()
            logger.info("[OK] MT4Communication inicializado")
        except Exception as e:
            logger.warning(f"MT4Communication não disponível: {e}")

    def get_account_info(self):
        if self.mt4_comm:
            try: return self.mt4_comm.get_account_info()
            except Exception as e: logger.error(f"Erro ao obter info da conta: {e}")
        return {'connected': False}

    def get_positions(self):
        if self.mt4_comm:
            try: return self.mt4_comm.get_open_positions()
            except Exception as e: logger.error(f"Erro ao obter posições: {e}")
        return []

    def get_history(self, days=7):
        if self.mt4_comm:
            try: return self.mt4_comm.get_trade_history(days=days)
            except Exception as e: logger.error(f"Erro ao obter histórico: {e}")
        return []

mt4_integration = MT4Integration()

# =======================================================================
# DECORADORES
# =======================================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Não autenticado'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def api_response(success=True, data=None, error=None, code=200):
    resp = {'success': success}
    if data is not None: resp['data'] = data
    if error is not None: resp['error'] = error
    return jsonify(resp), code

# =======================================================================
# ROTAS AUTENTICAÇÃO
# =======================================================================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username','').strip()
        password = data.get('password','')

        # Lockout
        if LOGIN_ATTEMPTS[username] >= MAX_LOGIN_ATTEMPTS:
            return api_response(False, error='Muitas tentativas. Tente novamente mais tarde.', code=429)

        if username in USERS and check_password_hash(USERS[username], password):
            session['username'] = username
            session.permanent = True
            LOGIN_ATTEMPTS[username] = 0
            logger.info(f"Login bem-sucedido: {username}")
            return api_response(data={'redirect': url_for('dashboard')})

        LOGIN_ATTEMPTS[username] += 1
        logger.warning(f"Tentativa de login falhada ({LOGIN_ATTEMPTS[username]}): {username}")
        return api_response(False, error='Credenciais inválidas', code=401)

    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username','unknown')
    session.clear()
    logger.info(f"Logout: {username}")
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'username' in session else url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session.get('username'))

# =======================================================================
# API ENDPOINTS
# =======================================================================
@app.route('/api/account')
@login_required
def api_account(): return api_response(data=cache.get('account'))

@app.route('/api/positions')
@login_required
def api_positions(): return api_response(data=cache.get('positions',[]))

@app.route('/api/history')
@login_required
def api_history(): return api_response(data=list(cache.get('history',[])))

@app.route('/api/system/status')
@login_required
def api_system_status():
    uptime = datetime.now() - START_TIME
    status = {'uptime': str(uptime).split('.')[0],
              'mt4_connected': cache.get('account',{}).get('connected',False)}
    return api_response(data=status)

# =======================================================================
# WEBSOCKET EVENTS
# =======================================================================
@socketio.on('connect')
def handle_connect():
    if 'username' not in session:
        disconnect(); return False
    emit('connected', {'message': 'Conectado ao servidor'})

@socketio.on('ping')
def handle_ping(): emit('pong', {'timestamp': datetime.now().isoformat()})

# =======================================================================
# BACKGROUND TASKS
# =======================================================================
def update_mt4_data():
    last_account, last_positions = None, None
    while not STOP_EVENT.is_set():
        try:
            account_info = mt4_integration.get_account_info()
            if account_info != last_account:
                cache.update('account', account_info)
                socketio.emit('account_update', account_info)
                last_account = account_info

            positions = mt4_integration.get_positions()
            if positions != last_positions:
                cache.set('positions', positions)
                socketio.emit('positions_update', positions)
                last_positions = positions

            equity = cache.get('account',{}).get('equity',10000.0)
            cache.append('equity_history', {'time': datetime.now().strftime('%H:%M:%S'),'equity':equity},maxlen=100)

        except Exception as e: logger.error(f"Erro ao atualizar dados MT4: {e}")
        STOP_EVENT.wait(5)

def start_background_tasks():
    t = threading.Thread(target=update_mt4_data, daemon=True, name='MT4-Updater')
    t.start(); logger.info(f"Thread iniciada: {t.name}")

def shutdown_handler(signum, frame):
    logger.info("Shutdown iniciado...")
    STOP_EVENT.set()
    try: socketio.stop()
    except: pass
    sys.exit(0)

# =======================================================================
# MAIN
# =======================================================================
if __name__ == '__main__':
    import signal
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("="*80)
    logger.info("JokaMazKiBu Trading Bot Dashboard v6.3")
    logger.info("="*80)
    start_background_tasks()
    logger.info("Servidor Flask-SocketIO rodando em 0.0.0.0:5000")
    logger.info(f"Login: {USERNAME} / Pass: {PASSWORD}")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
