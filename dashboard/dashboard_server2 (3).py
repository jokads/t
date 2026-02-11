# dashboard_server.py
"""
Dashboard server melhorado para o seu projeto de trading (MT4 + IA).

Principais melhorias:
 - Compatibilidade Flask 3 (before_serving) com fallback
 - Inicialização idempotente de background tasks
 - Segurança de sessão/headers básicos
 - Rate-limit simples para endpoints de IA
 - Endpoint para salvar config manualmente
 - Uptime, logs e tratamento de erros
 - Pontos claros de integração com mt4_communication / ai_manager / trading_data
"""
import os
import io
import csv
import time
import json
import random
import signal
import threading
import logging
from datetime import datetime, timedelta
from functools import wraps
from importlib import import_module

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for, session,
    send_file
)
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

SECRET_KEY = os.environ.get('DASHBOARD_SECRET_KEY', 'super_secret_key_jokamazkibu_v5_1')

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
# session / security config
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_COOKIE_SECURE'] = False  # True em produção com HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# SocketIO (threading para Windows)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s - %(message)s')
logger = logging.getLogger('dashboard')

# runtime info
START_TIME = datetime.utcnow()
stop_event = threading.Event()
_background_started = False
_background_lock = threading.Lock()

# ──────────────────────────────────────────────────────────────────────────────
# UTIL: autenticação / JSON seguro / rate-limit simples
# ──────────────────────────────────────────────────────────────────────────────
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Não autenticado'}), 401
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

def api_error(message, code=400):
    return jsonify({'success': False, 'error': message}), code

def safe_get_json(force=False):
    """Wrapper robusto para request.get_json com tratamento."""
    try:
        return request.get_json(force=force)
    except Exception:
        return None

# Simple in-memory rate-limit by IP (not persistent) - suitable for dev/test
_RATE_LIMIT = {}
def ip_rate_limited(ip, key, interval_seconds=1):
    """Return True if rate-limited (should block). key distinguishes endpoints."""
    now = time.time()
    store = _RATE_LIMIT.setdefault((ip, key), 0)
    if now - store < interval_seconds:
        return True
    _RATE_LIMIT[(ip, key)] = now
    return False

# ──────────────────────────────────────────────────────────────────────────────
# PERSISTÊNCIA SIMPLES (JSON)
# ──────────────────────────────────────────────────────────────────────────────
def _load_json_file(name, default):
    path = os.path.join(DATA_DIR, name)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            logger.exception("Falha a ler %s", path)
    return default

def _save_json_file(name, data):
    path = os.path.join(DATA_DIR, name)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("Falha a gravar %s", path)

# ──────────────────────────────────────────────────────────────────────────────
# INTEGRAÇÃO DINÂMICA COM SEUS MÓDULOS (mt4, ai_manager, trading_data)
# - Se os módulos existirem no PYTHONPATH, serão carregados automaticamente.
# - Convenção mínima: mt4.get_account(), mt4.get_positions(), mt4.close_position(ticket)
#                   ai_manager.load_models(), ai_manager.analyze(prompt, model), ai_manager.list_models()
#                   trading_data.init_db()
# ──────────────────────────────────────────────────────────────────────────────
_external = {}
def try_load_module(name):
    try:
        mod = import_module(name)
        logger.info("Módulo externo carregado: %s", name)
        _external[name] = mod
        return mod
    except Exception:
        logger.debug("Módulo externo NÃO encontrado: %s", name)
        return None

_mt4 = try_load_module('mt4_communication')
_ai_manager = try_load_module('ai_manager')
_trading_data = try_load_module('trading_data')

# ──────────────────────────────────────────────────────────────────────────────
# DATA MANAGER (Thread-safe, pluggable)
# ──────────────────────────────────────────────────────────────────────────────
class DataManager:
    def __init__(self):
        self._lock = threading.RLock()
        self.strategies = _load_json_file('strategies.json', {
            'ema_crossover': {'name': 'EMA Crossover', 'enabled': True, 'performance': 12.5, 'trades': 150, 'params': {'fast': 9, 'slow': 21}},
            'rsi_divergence': {'name': 'RSI Divergence', 'enabled': False, 'performance': -2.1, 'trades': 50, 'params': {'period': 14, 'threshold': 30}},
            'supertrend': {'name': 'Supertrend', 'enabled': True, 'performance': 8.9, 'trades': 90, 'params': {'atr_period': 10, 'multiplier': 3.0}},
        })
        self.ai_models = _load_json_file('ai_models.json', {
            'llama_3_2_1b': {'name': 'Llama-3.2-1B', 'specialty': 'Análise Rápida', 'available': True},
            'nous_hermes': {'name': 'Nous-Hermes-2', 'specialty': 'Sentimento', 'available': True},
        })
        self.users = _load_json_file('users.json', {"joka": generate_password_hash("jokapass123")})

        # runtime
        self.account_data = {'balance': 5000.00, 'equity': 5000.00, 'profit': 0.00, 'margin': 0.00, 'free_margin':5000.00, 'margin_level':1000.0, 'currency':'USD'}
        self.positions = []
        self.system_status = {'mt4_connected': False if _mt4 else True, 'bot_running': True, 'news_api_connected': True}
        self.stats = {'profit_today': 0.0, 'total_trades_today': 0, 'winning_trades': 0, 'win_rate': 0.0, 'ai_consensus': {'recommendation':'HOLD','confidence':0}}
        self.news = _load_json_file('news.json', [])
        self.signals = _load_json_file('signals.json', [])
        self.equity_history = _load_json_file('equity_history.json', [{'time': datetime.utcnow().strftime('%H:%M:%S'),'equity':5000.0}])

    def snapshot(self):
        with self._lock:
            return {
                'account_data': dict(self.account_data),
                'positions': [dict(p) for p in self.positions],
                'strategies': dict(self.strategies),
                'ai_models': dict(self.ai_models),
                'system_status': dict(self.system_status),
                'stats': dict(self.stats),
                'news': list(self.news),
                'signals': list(self.signals),
                'equity_history': list(self.equity_history)
            }

    def save_config(self):
        with self._lock:
            _save_json_file('strategies.json', self.strategies)
            _save_json_file('ai_models.json', self.ai_models)
            _save_json_file('users.json', self.users)
            _save_json_file('news.json', self.news)
            _save_json_file('signals.json', self.signals)
            _save_json_file('equity_history.json', self.equity_history)

    def update_account_and_positions(self):
        """Prefer external mt4 module; fallback to simulation."""
        with self._lock:
            if _mt4:
                try:
                    acct_fn = getattr(_mt4, 'get_account', None)
                    pos_fn = getattr(_mt4, 'get_positions', None)
                    if acct_fn and pos_fn:
                        acct = acct_fn()
                        pos = pos_fn()
                        if isinstance(acct, dict):
                            self.account_data = acct
                        if isinstance(pos, list):
                            self.positions = pos
                        return
                except Exception:
                    logger.exception("Erro ao usar mt4_communication")
            # fallback simulation
            if random.random() < 0.06 and self.system_status.get('bot_running', True):
                ticket = random.randint(100000, 999999)
                symbol = random.choice(['EURUSD','GBPUSD','USDJPY','XAUUSD'])
                side = random.choice(['BUY','SELL'])
                volume = round(random.uniform(0.01, 0.1), 2)
                open_price = round(random.uniform(1.0, 1.3), 5)
                self.positions.append({
                    'ticket': ticket, 'symbol': symbol, 'type': side, 'volume': volume,
                    'open_price': open_price, 'current_price': open_price,
                    'sl': round(open_price - 0.005,5) if side=='BUY' else round(open_price + 0.005,5),
                    'tp': round(open_price + 0.01,5) if side=='BUY' else round(open_price - 0.01,5),
                    'profit': 0.0, 'strategy': random.choice(list(self.strategies.keys()))
                })
                self.stats['total_trades_today'] += 1

            total_profit = 0.0
            new_positions = []
            for p in self.positions:
                price_change = random.uniform(-0.0005, 0.0005)
                p['current_price'] = round(p.get('current_price', p.get('open_price', 1.0)) + price_change, 5)
                if p.get('type') == 'BUY':
                    p['profit'] = round((p['current_price'] - p['open_price']) * 100000 * p['volume'], 2)
                else:
                    p['profit'] = round((p['open_price'] - p['current_price']) * 100000 * p['volume'], 2)
                total_profit += p['profit']
                if random.random() < 0.008:
                    self.account_data['balance'] += p['profit']
                    self.stats['profit_today'] += p['profit']
                    if p['profit'] > 0:
                        self.stats['winning_trades'] += 1
                    continue
                new_positions.append(p)
            self.positions = new_positions
            self.account_data['profit'] = round(total_profit, 2)
            self.account_data['equity'] = round(self.account_data['balance'] + total_profit, 2)
            self.account_data['margin'] = round(len(self.positions) * 1000 * random.uniform(0.9, 1.1), 2)
            self.account_data['free_margin'] = round(self.account_data['equity'] - self.account_data['margin'], 2)
            self.account_data['margin_level'] = round((self.account_data['equity'] / self.account_data['margin']) * 100 if self.account_data['margin'] > 0 else 10000, 2)
            if self.stats['total_trades_today'] > 0:
                self.stats['win_rate'] = round((self.stats['winning_trades'] / self.stats['total_trades_today']) * 100, 1)
            # equity history
            if not self.equity_history or self.equity_history[-1]['equity'] != self.account_data['equity']:
                self.equity_history.append({'time': datetime.utcnow().strftime('%H:%M:%S'), 'equity': self.account_data['equity']})
                if len(self.equity_history) > 1000:
                    self.equity_history.pop(0)

    def toggle_strategy(self, strategy_key, enabled):
        with self._lock:
            if strategy_key in self.strategies:
                self.strategies[strategy_key]['enabled'] = bool(enabled)
                self.save_config()
                return True
            return False

    def update_strategy_params(self, strategy_key, params):
        with self._lock:
            if strategy_key in self.strategies:
                self.strategies[strategy_key].setdefault('params', {})
                self.strategies[strategy_key]['params'].update(params)
                self.save_config()
                return True
            return False

    def get_ai_analysis(self):
        """Prefer ai_manager if available; fallback to simulated analysis."""
        with self._lock:
            if _ai_manager:
                try:
                    list_fn = getattr(_ai_manager, 'list_models', None)
                    analyze_fn = getattr(_ai_manager, 'analyze', None)
                    models = list_fn() if list_fn else list(self.ai_models.keys())
                    analysis = []
                    for m in models:
                        try:
                            resp = analyze_fn("market status", m) if analyze_fn else None
                            if isinstance(resp, dict):
                                analysis.append({
                                    'ai_name': self.ai_models.get(m, {}).get('name', m),
                                    'specialty': self.ai_models.get(m, {}).get('specialty', ''),
                                    'recommendation': resp.get('recommendation', random.choice(['BUY','SELL','HOLD'])),
                                    'confidence': resp.get('confidence', random.randint(50,99)),
                                    'response': resp.get('text', str(resp))
                                })
                        except Exception:
                            logger.exception("Erro ai_manager.analyze %s", m)
                    # consensus
                    buys = sum(1 for a in analysis if a['recommendation']=='BUY')
                    sells = sum(1 for a in analysis if a['recommendation']=='SELL')
                    holds = sum(1 for a in analysis if a['recommendation']=='HOLD')
                    consensus = 'BUY' if buys>max(sells,holds) else 'SELL' if sells>max(buys,holds) else 'HOLD'
                    total_conf = round(sum(a['confidence'] for a in analysis)/len(analysis),0) if analysis else 0
                    self.stats['ai_consensus'] = {'recommendation': consensus, 'confidence': total_conf}
                    return analysis
                except Exception:
                    logger.exception("Erro geral ai_manager")
            # fallback simulated
            analysis = []
            for key, model in self.ai_models.items():
                if model.get('available', False):
                    recommendation = random.choice(['BUY','SELL','HOLD'])
                    confidence = random.randint(50,99)
                    analysis.append({'ai_name': model['name'], 'specialty': model.get('specialty'), 'recommendation': recommendation, 'confidence': confidence, 'response': f"{recommendation} ({confidence}%)"})
            buys = sum(1 for a in analysis if a['recommendation']=='BUY')
            sells = sum(1 for a in analysis if a['recommendation']=='SELL')
            holds = sum(1 for a in analysis if a['recommendation']=='HOLD')
            consensus = 'BUY' if buys>max(sells,holds) else 'SELL' if sells>max(buys,holds) else 'HOLD'
            total_conf = round(sum(a['confidence'] for a in analysis)/len(analysis),0) if analysis else 0
            self.stats['ai_consensus'] = {'recommendation': consensus, 'confidence': total_conf}
            return analysis

    def get_news_update(self):
        with self._lock:
            new = {'id': random.randint(100,999), 'time': datetime.utcnow().strftime('%H:%M:%S'), 'source':'AI Feed', 'title': 'Alerta', 'content':'Volatilidade detectada.'}
            self.news.insert(0, new)
            self.news = self.news[:200]
            return list(self.news)

    def close_position(self, ticket):
        with self._lock:
            if _mt4:
                try:
                    fn = getattr(_mt4, 'close_position', None)
                    if fn:
                        return bool(fn(ticket))
                except Exception:
                    logger.exception("Erro mt4.close_position")
            initial = len(self.positions)
            self.positions = [p for p in self.positions if p.get('ticket') != ticket]
            return len(self.positions) < initial

    def force_refresh(self):
        with self._lock:
            self.update_account_and_positions()

data_manager = DataManager()

# ──────────────────────────────────────────────────────────────────────────────
# SOCKETIO HANDLERS
# ──────────────────────────────────────────────────────────────────────────────
@socketio.on('connect')
def _on_connect():
    sid = request.sid
    logger.info("Client connected: %s", sid)
    emit('connected', {'msg': 'connected'})
    snap = data_manager.snapshot()
    emit('account_update', {'data': snap['account_data']})
    emit('positions_update', {'data': snap['positions']})
    emit('stats_update', {'data': snap['stats']})
    emit('equity_history_update', {'data': snap['equity_history']})
    emit('strategies_update', {'data': snap['strategies']})
    emit('ai_models_update', {'data': snap['ai_models']})

@socketio.on('disconnect')
def _on_disconnect():
    logger.info("Client disconnected: %s", request.sid)

# websocket AI chat rate-limited per sid
_WS_AI_LAST = {}
_WS_AI_INTERVAL = 0.8  # seconds
@socketio.on('chat_with_ai')
def _on_chat_with_ai(payload):
    sid = request.sid
    last = _WS_AI_LAST.get(sid, 0)
    now = time.time()
    if now - last < _WS_AI_INTERVAL:
        emit('chat_response', {'error': 'Rate limit (ws): slow down'}, to=sid)
        return
    _WS_AI_LAST[sid] = now

    model = payload.get('model')
    message = payload.get('message', '')
    if not message:
        emit('chat_response', {'error': 'Mensagem vazia'}, to=sid)
        return

    if _ai_manager:
        try:
            analyze = getattr(_ai_manager, 'analyze', None)
            if analyze:
                res = analyze(message, model)
                emit('chat_response', {'type': 'single', 'data': res}, to=sid)
                return
        except Exception:
            logger.exception("Erro ai_manager.analyze (ws)")

    # fallback
    if model == 'all':
        out = [{'ai_name': v['name'], 'response': f"[{v['name']}] Sim: {message}"} for v in data_manager.ai_models.values() if v.get('available')]
        emit('chat_response', {'type': 'multiple', 'data': out}, to=sid)
    else:
        ai = data_manager.ai_models.get(model)
        if not ai:
            emit('chat_response', {'error': 'Modelo não encontrado'}, to=sid)
        else:
            emit('chat_response', {'type': 'single', 'data': {'ai_name': ai['name'], 'response': f"[{ai['name']}] OK: {message}"}}, to=sid)

# ──────────────────────────────────────────────────────────────────────────────
# BACKGROUND TASKS
# ──────────────────────────────────────────────────────────────────────────────
def background_realtime_broadcast():
    logger.info("Background realtime broadcaster iniciado.")
    while not stop_event.is_set():
        try:
            data_manager.update_account_and_positions()
            snap = data_manager.snapshot()
            socketio.emit('account_update', {'data': snap['account_data']})
            socketio.emit('positions_update', {'data': snap['positions']})
            socketio.emit('stats_update', {'data': snap['stats']})
            socketio.emit('equity_history_update', {'data': snap['equity_history']})
        except Exception:
            logger.exception("Erro realtime broadcaster")
        socketio.sleep(2)

def background_ai_news_broadcast():
    logger.info("Background ai/news broadcaster iniciado.")
    while not stop_event.is_set():
        try:
            ai_analysis = data_manager.get_ai_analysis()
            socketio.emit('ai_analysis_update', {'data': ai_analysis})
            news_update = data_manager.get_news_update()
            socketio.emit('news_update', {'data': news_update})
        except Exception:
            logger.exception("Erro ai/news broadcaster")
        socketio.sleep(30)

# ──────────────────────────────────────────────────────────────────────────────
# ROUTAS (AUTH / UI / API)
# ──────────────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        stored = data_manager.users.get(username)
        if stored and check_password_hash(stored, password):
            # regenerate simple session: clear then set
            session.clear()
            session.permanent = True
            session['username'] = username
            logger.info("User logged in: %s", username)
            return redirect(url_for('dashboard'))
        error = "Usuário ou senha inválidos."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session.get('username'))

@app.route('/health', methods=['GET'])
def health():
    uptime = (datetime.utcnow() - START_TIME).total_seconds()
    return jsonify({'ok': True, 'time': datetime.utcnow().isoformat()+'Z', 'uptime_seconds': int(uptime)})

@app.route('/api/account', methods=['GET'])
@login_required
def api_account():
    return jsonify({'success': True, 'data': data_manager.snapshot()['account_data']})

@app.route('/api/positions', methods=['GET'])
@login_required
def api_positions():
    return jsonify({'success': True, 'data': data_manager.snapshot()['positions']})

@app.route('/api/positions/close', methods=['POST'])
@login_required
def api_close_position():
    payload = safe_get_json(force=True) or {}
    ticket = payload.get('ticket')
    if not ticket:
        return api_error('Ticket não fornecido', 400)
    closed = data_manager.close_position(ticket)
    if closed:
        socketio.emit('positions_update', {'data': data_manager.snapshot()['positions']})
        return jsonify({'success': True, 'message': f'Posição {ticket} fechada (simulado/real).'})
    return api_error('Posição não encontrada', 404)

@app.route('/api/strategies', methods=['GET'])
@login_required
def api_strategies():
    return jsonify({'success': True, 'data': data_manager.snapshot()['strategies']})

@app.route('/api/strategies/toggle', methods=['POST'])
@login_required
def api_toggle_strategy():
    payload = safe_get_json(force=True) or {}
    strategy = payload.get('strategy')
    enabled = payload.get('enabled')
    if not strategy or enabled is None:
        return api_error('Dados incompletos', 400)
    ok = data_manager.toggle_strategy(strategy, enabled)
    if ok:
        socketio.emit('strategy_update', {'strategy': strategy, 'enabled': enabled})
        return jsonify({'success': True})
    return api_error('Estratégia não encontrada', 404)

@app.route('/api/strategies/params', methods=['POST'])
@login_required
def api_update_strategy_params():
    payload = safe_get_json(force=True) or {}
    strategy = payload.get('strategy')
    params = payload.get('params')
    if not strategy or not isinstance(params, dict):
        return api_error('Dados inválidos', 400)
    ok = data_manager.update_strategy_params(strategy, params)
    if ok:
        socketio.emit('strategy_params_update', {'strategy': strategy, 'params': params})
        return jsonify({'success': True})
    return api_error('Estratégia não encontrada', 404)

@app.route('/api/ai/models', methods=['GET'])
@login_required
def api_ai_models():
    return jsonify({'success': True, 'data': data_manager.snapshot()['ai_models']})

@app.route('/api/ai/chat', methods=['POST'])
@login_required
def api_ai_chat():
    ip = request.remote_addr or 'anon'
    if ip_rate_limited(ip, 'ai_chat', interval_seconds=1.0):
        return api_error('Rate limit: slow down', 429)
    payload = safe_get_json(force=True) or {}
    model = payload.get('model')
    message = payload.get('message')
    if not model or not message:
        return api_error('Modelo ou mensagem não fornecidos', 400)
    if _ai_manager:
        try:
            analyze = getattr(_ai_manager, 'analyze', None)
            if analyze:
                res = analyze(message, model)
                return jsonify({'success': True, 'type': 'single', 'data': res})
        except Exception:
            logger.exception("Erro ai_manager.analyze (api)")
    # fallback
    if model == 'all':
        responses = [{'ai_name': v['name'], 'specialty': v.get('specialty'), 'response': f"[{v['name']}] Sim: {message}"} for v in data_manager.ai_models.values()]
        return jsonify({'success': True, 'type': 'multiple', 'data': responses})
    ai = data_manager.ai_models.get(model)
    if not ai:
        return api_error('Modelo não encontrado', 404)
    return jsonify({'success': True, 'type': 'single', 'data': {'ai_name': ai['name'], 'response': f"[{ai['name']}] Simulada."}})

@app.route('/api/news', methods=['GET'])
@login_required
def api_news():
    return jsonify({'success': True, 'data': data_manager.snapshot()['news']})

@app.route('/api/signals', methods=['GET'])
@login_required
def api_signals():
    return jsonify({'success': True, 'data': data_manager.snapshot()['signals']})

@app.route('/api/system/status', methods=['GET'])
@login_required
def api_system_status():
    return jsonify({'success': True, 'data': data_manager.snapshot()['system_status']})

@app.route('/api/system/action', methods=['POST'])
@login_required
def api_system_action():
    payload = safe_get_json(force=True) or {}
    action = payload.get('action')
    state = payload.get('state')
    if action == 'bot_toggle':
        new_state = state == 'on'
        data_manager.system_status['bot_running'] = new_state
        socketio.emit('system_status_update', {'data': data_manager.snapshot()['system_status']})
        return jsonify({'success': True, 'message': f'Bot {"ativado" if new_state else "desativado"}'})
    if action == 'mt4_reconnect':
        if _mt4:
            try:
                reconnect = getattr(_mt4, 'connect', None)
                if reconnect:
                    reconnect()
            except Exception:
                logger.exception("Erro reconnect mt4")
        data_manager.system_status['mt4_connected'] = True
        socketio.emit('system_status_update', {'data': data_manager.snapshot()['system_status']})
        return jsonify({'success': True, 'message': 'Tentativa de reconexão MT4 iniciada (simulado).'})
    if action == 'news_reconnect':
        data_manager.system_status['news_api_connected'] = True
        socketio.emit('system_status_update', {'data': data_manager.snapshot()['system_status']})
        return jsonify({'success': True, 'message': 'Reconexão News API (simulado).'})
    if action == 'force_refresh':
        data_manager.force_refresh()
        socketio.emit('account_update', {'data': data_manager.snapshot()['account_data']})
        return jsonify({'success': True, 'message': 'Forçado refresh.'})
    return api_error('Ação desconhecida', 400)

@app.route('/api/indicators', methods=['POST'])
@login_required
def api_indicators():
    payload = safe_get_json(force=True) or {}
    symbol = payload.get('symbol')
    timeframe = payload.get('timeframe', 'M1')
    indicators = {
        'symbol': symbol or 'EURUSD',
        'timeframe': timeframe,
        'ema_fast': 1.12345,
        'ema_slow': 1.12400,
        'rsi': round(random.uniform(20,80), 2),
        'supertrend': random.choice(['BUY','SELL','NEUTRAL'])
    }
    return jsonify({'success': True, 'data': indicators})

@app.route('/api/trades/history', methods=['GET'])
@login_required
def api_trades_history():
    hist = [{'time': h['time'], 'equity': h['equity']} for h in data_manager.equity_history[-200:]]
    return jsonify({'success': True, 'data': hist})

@app.route('/api/export/equity.csv', methods=['GET'])
@login_required
def api_export_equity_csv():
    rows = data_manager.snapshot()['equity_history']
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['time','equity'])
    for r in rows:
        writer.writerow([r.get('time'), r.get('equity')])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='equity_history.csv')

@app.route('/api/save_config', methods=['POST'])
@login_required
def api_save_config():
    """Força salvar configuração no disco (strategies, ai_models, equity_history...)."""
    try:
        data_manager.save_config()
        return jsonify({'success': True, 'message': 'Configurações salvas.'})
    except Exception:
        logger.exception("Erro ao salvar config via API")
        return api_error('Erro ao salvar config', 500)

# ──────────────────────────────────────────────────────────────────────────────
# INIT + STARTUP HOOKS (antes do server aceitar requisições)
# ──────────────────────────────────────────────────────────────────────────────
def init_app():
    """Inicializações idempotentes: init DB, load models, start backgrounds."""
    logger.info("init_app() -> inicializando componentes...")
    if _trading_data:
        try:
            init_db = getattr(_trading_data, 'init_db', None)
            if init_db:
                init_db()
                logger.info("trading_data.init_db() executado.")
        except Exception:
            logger.exception("Erro trading_data.init_db()")
    if _ai_manager:
        try:
            load_models = getattr(_ai_manager, 'load_models', None)
            if load_models:
                load_models()
                logger.info("ai_manager.load_models() executado.")
        except Exception:
            logger.exception("Erro ai_manager.load_models()")

    global _background_started
    with _background_lock:
        if not _background_started:
            try:
                socketio.start_background_task(background_realtime_broadcast)
                socketio.start_background_task(background_ai_news_broadcast)
                _background_started = True
                logger.info("Background tasks iniciadas.")
            except Exception:
                logger.exception("Erro ao iniciar background tasks")

# Register startup hook for Flask >= 3 (before_serving). If absent, init_app will be called in __main__.
if hasattr(app, 'before_serving'):
    @app.before_serving
    def _before_serving():
        init_app()

# Graceful shutdown
def _signal_handler(signum, frame):
    logger.info("Sinal recebido (%s), terminando...", signum)
    stop_event.set()
    data_manager.save_config()

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# Security headers
@app.after_request
def _security_headers(resp):
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('Referrer-Policy', 'no-referrer-when-downgrade')
    return resp

# Error handlers
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api') or request.is_json:
        return api_error('Recurso não encontrado', 404)
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    logger.exception("Erro 500")
    if request.path.startswith('/api') or request.is_json:
        return api_error('Erro interno do servidor', 500)
    return render_template('500.html'), 500

# ──────────────────────────────────────────────────────────────────────────────
# START
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # if Flask <3 lacks before_serving, init here; else before_serving already calls init_app()
    if not hasattr(app, 'before_serving'):
        init_app()
    logger.info("Iniciando servidor Flask-SocketIO em 0.0.0.0:5000 ...")
    try:
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    finally:
        stop_event.set()
        data_manager.save_config()
        logger.info("Servidor terminado, configurações salvas.")
