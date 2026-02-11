#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JokaMazKiBu Trading Bot Dashboard - Refatorado e Otimizado v5.0
Arquivo: dashboard_server.py

Versão otimizada:
- Otimização do loop de broadcast para evitar sobrecarga.
- Remoção da simulação de estatísticas no broadcast (serão atualizadas via API/Polling no cliente).
- Melhor tratamento de dados reais do MT4 e NewsAPI.
- Estrutura de caminhos ajustada para a raiz do projeto.
"""

from __future__ import annotations

import os
import sys
import threading
import sqlite3
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from pathlib import Path
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    session,
    send_from_directory,
)
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# --- Configuração de Caminhos ---
# Assume-se que o script está sendo executado a partir da pasta 'dashboard'
# e a raiz do projeto é o diretório pai.
BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent

TEMPLATES_PATH = DASHBOARD_DIR / "templates"
STATIC_PATH = DASHBOARD_DIR / "static"
DATA_PATH = BASE_DIR / "data"
LOG_PATH = BASE_DIR / "logs"

# AI model paths (ajuste por variável de ambiente se necessário)
# Ajustando para usar caminhos relativos à BASE_DIR
CAMINHO_MODELOS_GPT4ALL = os.getenv("CAMINHO_MODELOS_GPT4ALL", str(BASE_DIR / "gpt4all" / "models"))
CAMINHO_LLAMA_EXE = os.getenv("CAMINHO_LLAMA_EXE", str(BASE_DIR / "llama.cpp" / "build" / "bin" / "Release" / "llama-cli.exe"))
CAMINHO_LLAMA_MODEL = os.getenv("CAMINHO_LLAMA_MODEL", str(BASE_DIR / "llama.cpp" / "models" / "mistral-7b-instruct-v0.1.Q4_K_S.gguf"))

# Credenciais básicas (use variáveis de ambiente em produção)
DASHBOARD_USER = os.getenv("DASHBOARD_USERNAME", "joka")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "j0K4616")
SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", "jokamazkibu_ultra_secret_key_2024")

# Logging
os.makedirs(LOG_PATH, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH / "dashboard_server.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("dashboard_server")

# --- Import core modules (safe import with warnings) ---
try:
    # Ajustando o import para refletir a estrutura de pastas
    sys.path.append(str(BASE_DIR))
    from core.mt4_communication import MT4Communication  # type: ignore
except Exception as e:
    logger.warning("Não foi possível importar core.mt4_communication: %s", e)
    MT4Communication = None  # type: ignore

try:
    from core.news_api_manager import NewsAPIManager  # type: ignore
except Exception as e:
    logger.warning("Não foi possível importar core.news_api_manager: %s", e)
    NewsAPIManager = None  # type: ignore

# --- Flask + SocketIO (single instances) ---
app = Flask(__name__, template_folder=str(TEMPLATES_PATH), static_folder=str(STATIC_PATH), static_url_path="/static")
app.secret_key = SECRET_KEY
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Type-only imports for linters
if TYPE_CHECKING:
    from core.mt4_communication import MT4Communication as _MT4Comm  # type: ignore
    from core.news_api_manager import NewsAPIManager as _NewsAPI  # type: ignore

mt4_comm: Optional["_MT4Comm"] = None
news_api_manager: Optional["_NewsAPI"] = None

# --- AI Manager (simulações; adapte para GPT4All/llama) ---
class AIManager:
    def __init__(self):
        self.logger = logging.getLogger("ai_manager")
        self.models = {
            "nous-hermes": {"name": "Nous-Hermes-2-Mistral-7B", "file": "Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf", "specialty": "Análise Técnica", "available": False, "status": "offline"},
            "orca-mini": {"name": "Orca-Mini-3B", "file": "orca-mini-3b-gguf2-q4_0.gguf", "specialty": "Sentimento e Notícias", "available": False, "status": "offline"},
            "llama-3b": {"name": "Llama-3.2-3B", "file": "Llama-3.2-3B-Instruct-Q4_0.gguf", "specialty": "Gestão de Risco", "available": False, "status": "offline"},
            "llama-1b": {"name": "Llama-3.2-1B", "file": "Llama-3.2-1B-Instruct-Q4_0.gguf", "specialty": "Momentum", "available": False, "status": "offline"},
            "phi3": {"name": "Phi-3-Mini", "file": "Phi-3-mini-4k-instruct.Q4_0.gguf", "specialty": "Volatilidade", "available": False, "status": "offline"},
            "qwen2": {"name": "Qwen2-1.5B", "file": "qwen2-1_5b-instruct-q4_0.gguf", "specialty": "Correlações", "available": False, "status": "offline"},
            "mistral": {"name": "Mistral-7B (CÉREBRO)", "file": "mistral-7b-instruct-v0.1.Q4_K_S.gguf", "specialty": "Coordenação Geral", "available": False, "status": "offline", "is_llama_cpp": True},
        }
        self._check_models_availability()

    def _check_models_availability(self):
        try:
            if os.path.isdir(CAMINHO_MODELOS_GPT4ALL):
                for mid, info in self.models.items():
                    if not info.get("is_llama_cpp", False):
                        path = Path(CAMINHO_MODELOS_GPT4ALL) / info["file"]
                        info["available"] = path.exists()
                        info["status"] = "online" if info["available"] else "offline"
                        if info["available"]:
                            self.logger.info("Modelo disponível: %s", info["name"])
            if Path(CAMINHO_LLAMA_EXE).exists() and Path(CAMINHO_LLAMA_MODEL).exists():
                self.models["mistral"]["available"] = True
                self.models["mistral"]["status"] = "online"
                self.logger.info("Mistral (llama.cpp) disponível")
        except Exception:
            self.logger.exception("Erro ao checar disponibilidade de modelos")

    def _prepare_specialized_prompt(self, model_id: str, prompt: str) -> str:
        messages = {
            "nous-hermes": f"Como especialista em análise técnica, responda em PT: {prompt}",
            "orca-mini": f"Como especialista em sentimento e notícias, responda em PT: {prompt}",
            "llama-3b": f"Como especialista em gestão de risco, responda em PT: {prompt}",
            "llama-1b": f"Como especialista em momentum, responda em PT: {prompt}",
            "phi3": f"Como especialista em volatilidade, responda em PT: {prompt}",
            "qwen2": f"Como especialista em correlações entre pares, responda em PT: {prompt}",
            "mistral": f"Coordene e resuma em PT: {prompt}",
        }
        return messages.get(model_id, prompt)

    def _simulate_response(self, model_id: str, prompt: str) -> str:
        # Simulação de resposta mais rica para o dashboard
        samples = {
            "nous-hermes": "Análise Técnica: Reversão potencial detectada no RSI (14) em 72.5. Aguardar confirmação do volume.",
            "orca-mini": "Sentimento/Notícias: Sentimento neutro (52%). Próxima notícia macro de alto impacto em 2h.",
            "llama-3b": "Gestão de Risco: Risco adequado (0.5% por trade). Considere SL apertado (20 pips) para a próxima operação.",
            "llama-1b": "Momentum: Momentum enfraquecendo no curto prazo (MACD cruzando para baixo).",
            "phi3": "Volatilidade: ATR (14) crescente (0.0005) — volatilidade aumentada. Ajustar tamanho da posição.",
            "qwen2": "Correlações: Alta correlação (0.92) entre EUR/USD e GBP/USD. Evitar exposição dupla.",
            "mistral": "Consenso das IAs: Oportunidade moderada. Coordenar execução com risco baixo. Alvo: 1.0850.",
        }
        return samples.get(model_id, f"Análise ({model_id}) em processamento...")

    def query_ai(self, model_id: str, prompt: str, timeout: int = 30) -> Dict[str, Any]:
        try:
            if model_id not in self.models:
                return {"success": False, "error": "Modelo não encontrado"}
            info = self.models[model_id]
            if not info.get("available", False):
                return {"success": False, "error": "Modelo não disponível"}
            
            # TODO: Aqui deve ser a chamada real ao modelo (GPT4All ou Llama.cpp)
            # Por enquanto, mantemos a simulação
            specialized = self._prepare_specialized_prompt(model_id, prompt)
            response = self._simulate_response(model_id, specialized)
            
            return {"success": True, "response": response, "ai_name": info["name"], "specialty": info.get("specialty")}
        except Exception:
            logger.exception("Erro ao consultar IA %s", model_id)
            return {"success": False, "error": "Erro interno"}

    def query_all_ais(self, prompt: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for mid in list(self.models.keys()):
            if self.models[mid].get("available", False):
                resp = self.query_ai(mid, prompt)
                if resp.get("success"):
                    results.append(resp)
        return results

# --- TradingDataManager (refatorado) ---
class TradingDataManager:
    def __init__(self):
        self.logger = logging.getLogger("trading_data")
        self.data_lock = threading.Lock()
        os.makedirs(DATA_PATH, exist_ok=True)
        self.db_path = DATA_PATH / "dashboard_data.db"
        self._init_database()
        self._init_demo_data()

    def _init_database(self):
        try:
            # Usar check_same_thread=False é necessário para threading, mas pode ser perigoso.
            # Como estamos usando Flask-SocketIO com threading, mantemos por compatibilidade.
            self.db_connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cur = self.db_connection.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket INTEGER, symbol TEXT, type TEXT, volume REAL, open_price REAL, close_price REAL, sl REAL, tp REAL, profit REAL, open_time TIMESTAMP, close_time TIMESTAMP, strategy TEXT, reason TEXT, status TEXT)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, direction TEXT, confidence REAL, source TEXT, strategy TEXT, timestamp TIMESTAMP, executed BOOLEAN DEFAULT 0)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS ai_analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, ai_model TEXT, analysis TEXT, confidence REAL, timestamp TIMESTAMP)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            self.db_connection.commit()
            self.logger.info("Banco inicializado: %s", self.db_path)
        except Exception:
            self.logger.exception("Erro inicializando DB")

    def _init_demo_data(self):
        now = datetime.now()
        self.demo_data = {
            "account": {"balance": 5000.0, "equity": 5000.0, "margin": 0.0, "free_margin": 5000.0, "margin_level": 0.0, "profit": 0.0},
            "positions": [],
            "signals": [],
            "indicators": {},
            "news": [{"title": "Aguardando notícias...", "content": "...", "time": now.strftime("%H:%M") }],
            "ai_analyses": {},
            "strategies": {"ema_crossover": {"enabled": True, "performance": 75.2, "trades": 45}, "supertrend": {"enabled": False, "performance": 62.1, "trades": 22}},
            "system_status": {"cpu": 15, "memory": 45, "disk": 60, "latency_ms": 50, "last_update": now.isoformat()},
        }

    def get_statistics(self) -> Dict[str, Any]:
        # Esta função deve ser chamada com moderação ou otimizada para o DB
        try:
            cur = self.db_connection.cursor()
            today = datetime.now().date().isoformat()
            
            # Estatísticas de hoje
            cur.execute("SELECT COUNT(*), SUM(CASE WHEN profit>0 THEN 1 ELSE 0 END), SUM(profit) FROM trades WHERE DATE(open_time)=?", (today,))
            row_today = cur.fetchone() or (0, 0, 0.0)
            total_today, winners_today, profit_today = row_today[0] or 0, row_today[1] or 0, row_today[2] or 0.0
            win_rate_today = (winners_today / total_today * 100) if total_today else 0.0
            
            # Estatísticas totais (exemplo)
            cur.execute("SELECT COUNT(*), SUM(CASE WHEN profit>0 THEN 1 ELSE 0 END), SUM(profit) FROM trades")
            row_total = cur.fetchone() or (0, 0, 0.0)
            total_trades, total_winners, total_profit = row_total[0] or 0, row_total[1] or 0, row_total[2] or 0.0
            
            return {
                "profit_today": round(profit_today, 2), 
                "total_trades_today": total_today, 
                "win_rate_today": round(win_rate_today, 2), 
                "winning_trades_today": winners_today,
                "total_profit": round(total_profit, 2),
                "total_trades": total_trades,
            }
        except Exception:
            self.logger.exception("Erro ao obter estatisticas")
            return {"profit_today": 0.0, "total_trades_today": 0, "win_rate_today": 0.0, "winning_trades_today": 0, "total_profit": 0.0, "total_trades": 0}

    def get_account_data(self):
        with self.data_lock:
            return dict(self.demo_data.get("account", {}))

    def get_positions(self):
        return list(self.demo_data.get("positions", []))

    def get_signals(self):
        return list(self.demo_data.get("signals", []))

    def get_indicators(self):
        return dict(self.demo_data.get("indicators", {}))

    def get_news(self):
        return list(self.demo_data.get("news", []))

    def get_ai_analyses(self):
        return dict(self.demo_data.get("ai_analyses", {}))

    def get_strategies(self):
        return dict(self.demo_data.get("strategies", {}))

    def get_system_status(self):
        return dict(self.demo_data.get("system_status", {}))

    def update_strategy_status(self, strategy: str, enabled: bool) -> bool:
        with self.data_lock:
            if strategy in self.demo_data["strategies"]:
                self.demo_data["strategies"][strategy]["enabled"] = bool(enabled)
                self.logger.info("Estratégia %s -> %s", strategy, enabled)
                return True
            return False

# --- Instâncias seguras ---
data_manager = TradingDataManager()
ai_manager = AIManager()

# --- Helpers to safely call mt4_comm methods with fallback ---

def _safe_mt4_call(method_name: str, *args, default=None, **kwargs):
    global mt4_comm
    try:
        if mt4_comm is None:
            return default
        method = getattr(mt4_comm, method_name, None)
        if callable(method):
            return method(*args, **kwargs)
        return default
    except Exception:
        logger.exception("Erro ao chamar %s em mt4_comm", method_name)
        return default

# --- Start external services in controlled manner ---

def _safe_start_service(obj: Any, name: str):
    try:
        if hasattr(obj, "start"):
            obj.start()
            logger.info("%s iniciado com sucesso.", name)
        else:
            logger.warning("%s não possui método 'start'.", name)
    except Exception:
        logger.exception("Erro rodando %s.start()", name)


def start_services(config_manager=None):
    global mt4_comm, news_api_manager
    try:
        if MT4Communication is not None and mt4_comm is None:
            try:
                # O MT4Communication deve ser capaz de receber dados via socket/pipe
                mt4_comm = MT4Communication(config_manager=config_manager) if config_manager else MT4Communication()
                t = threading.Thread(target=_safe_start_service, args=(mt4_comm, "MT4Communication"), daemon=True)
                t.start()
            except Exception:
                logger.exception("Falha ao iniciar MT4Communication")

        if NewsAPIManager is not None and news_api_manager is None:
            try:
                news_api_manager = NewsAPIManager()
                t2 = threading.Thread(target=_safe_start_service, args=(news_api_manager, "NewsAPIManager"), daemon=True)
                t2.start()
            except Exception:
                logger.exception("Falha ao iniciar NewsAPIManager")
    except Exception:
        logger.exception("Erro em start_services")

# --- Rotas ---
@app.route('/')
def index():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == DASHBOARD_USER and password == DASHBOARD_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            session.permanent = True
            logger.info("Login OK: %s", username)
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Credenciais inválidas')
    return render_template('login.html')


@app.route('/logout')
def logout():
    user = session.get('username', 'Unknown')
    session.clear()
    logger.info("Logout: %s", user)
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')


@app.route('/api/health')
def api_health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


@app.route('/api/status')
def api_status():
    mt4_connected = bool(_safe_mt4_call('is_connected', default=False))
    news_ready = news_api_manager is not None and hasattr(news_api_manager, 'get_latest_articles')
    
    return jsonify({
        "mt4_connected": mt4_connected, 
        "news_ready": news_ready,
        "ai_models_available": sum(1 for m in ai_manager.models.values() if m.get('available'))
    })


@app.route('/api/account')
def api_account():
    try:
        # Tenta obter dados reais do MT4, senão usa dados de demonstração
        balance = _safe_mt4_call('get_balance', default=data_manager.get_account_data().get('balance'))
        equity = _safe_mt4_call('get_equity', default=data_manager.get_account_data().get('equity'))
        margin = _safe_mt4_call('get_margin', default=0.0)
        free_margin = _safe_mt4_call('get_free_margin', default=0.0)
        margin_level = _safe_mt4_call('get_margin_level', default=0.0)
        
        # Calcula o lucro/prejuízo com base em equity e balance
        profit = (equity or 0.0) - (balance or 0.0)
        
        return jsonify({"success": True, "data": {
            "balance": round(balance or 0.0, 2), 
            "equity": round(equity or 0.0, 2), 
            "margin": round(margin or 0.0, 2), 
            "free_margin": round(free_margin or 0.0, 2), 
            "margin_level": round(margin_level or 0.0, 2), 
            "profit": round(profit or 0.0, 2)
        }})
    except Exception:
        logger.exception("Erro /api/account")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/positions')
def api_positions():
    try:
        positions = _safe_mt4_call('get_open_positions', default=data_manager.get_positions()) or []
        normalized = []
        for pos in positions:
            try:
                # Normalização de dados (mantida)
                if hasattr(pos, '_asdict'):
                    rec = pos._asdict()
                elif hasattr(pos, '__dict__'):
                    rec = dict(pos.__dict__)
                elif isinstance(pos, dict):
                    rec = dict(pos)
                else:
                    rec = {"raw": str(pos)}
            except Exception:
                rec = {"raw": str(pos)}
            for key in ('open_price', 'current_price', 'profit', 'sl', 'tp'):
                if key in rec and isinstance(rec[key], (float, int)):
                    rec[key] = round(rec[key], 5 if 'price' in key else 2)
            normalized.append(rec)
        return jsonify({"success": True, "data": normalized})
    except Exception:
        logger.exception("Erro /api/positions")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/signals')
def api_signals():
    try:
        raw = _safe_mt4_call('get_signals', default=data_manager.get_signals()) or []
        out = []
        for s in raw:
            # Normalização de dados (mantida)
            if hasattr(s, '_asdict'):
                rec = s._asdict()
            elif hasattr(s, '__dict__'):
                rec = dict(s.__dict__)
            elif isinstance(s, dict):
                rec = dict(s)
            else:
                rec = {"raw": str(s)}
            if 'timestamp' in rec and isinstance(rec['timestamp'], datetime):
                rec['timestamp'] = rec['timestamp'].isoformat()
            if 'confidence' in rec and isinstance(rec['confidence'], float):
                rec['confidence'] = round(rec['confidence'], 3)
            out.append(rec)
        return jsonify({"success": True, "data": out})
    except Exception:
        logger.exception("Erro /api/signals")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/indicators')
def api_indicators():
    try:
        raw = _safe_mt4_call('get_indicators', default=data_manager.get_indicators()) or {}
        def normalize_item(item):
            if hasattr(item, '_asdict'):
                d = item._asdict()
            elif hasattr(item, '__dict__'):
                d = dict(item.__dict__)
            elif isinstance(item, dict):
                d = dict(item)
            else:
                return item
            for k, v in list(d.items()):
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
                elif isinstance(v, float):
                    d[k] = round(v, 6)
            return d
        if isinstance(raw, dict):
            data = {k: normalize_item(v) for k, v in raw.items()}
        else:
            data = [normalize_item(v) for v in raw]
        return jsonify({"success": True, "data": data})
    except Exception:
        logger.exception("Erro /api/indicators")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/news')
def api_news():
    try:
        if news_api_manager is None or not hasattr(news_api_manager, 'get_latest_articles'):
            return jsonify({"success": True, "data": data_manager.get_news()})
        
        articles = news_api_manager.get_latest_articles(limit=10)
        
        def norm(a):
            title = getattr(a, 'title', a.get('title') if isinstance(a, dict) else str(a))
            desc = getattr(a, 'description', a.get('description', ''))
            published = getattr(a, 'publishedAt', getattr(a, 'published_at', None))
            time_str = published.strftime('%H:%M') if hasattr(published, 'strftime') else (published or '')
            return {"title": title, "content": desc or '', "time": time_str, "impact": getattr(a, 'impact', 'neutral'), "source": getattr(a, 'source', 'NewsAPI')}
        
        data = [norm(a) for a in articles]
        return jsonify({"success": True, "data": data})
    except Exception:
        logger.exception("Erro /api/news")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/ai/models')
def api_ai_models():
    try:
        ms = {mid: {"name": info["name"], "specialty": info.get("specialty"), "available": info.get("available"), "status": info.get("status")} for mid, info in ai_manager.models.items()}
        return jsonify({"success": True, "data": ms})
    except Exception:
        logger.exception("Erro /api/ai/models")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    try:
        payload = request.get_json() or {}
        message = (payload.get('message') or '').strip()
        model_id = payload.get('model', 'all')
        if not message:
            return jsonify({"success": False, "error": "Mensagem vazia"}), 400
        if model_id == 'all':
            res = ai_manager.query_all_ais(message)
            return jsonify({"success": True, "type": "multiple", "data": res})
        else:
            res = ai_manager.query_ai(model_id, message)
            return jsonify({"success": True, "type": "single", "data": res})
    except Exception:
        logger.exception("Erro /api/ai/chat")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/strategies')
def api_strategies():
    try:
        return jsonify({"success": True, "data": data_manager.get_strategies()})
    except Exception:
        logger.exception("Erro /api/strategies")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/strategies/toggle', methods=['POST'])
def api_strategies_toggle():
    try:
        payload = request.get_json() or {}
        strategy = payload.get('strategy', '')
        enabled = bool(payload.get('enabled', False))
        if not strategy:
            return jsonify({"success": False, "error": "Estratégia não especificada"}), 400
        ok = data_manager.update_strategy_status(strategy, enabled)
        if ok:
            return jsonify({"success": True, "message": f"Estratégia {strategy} {'ativada' if enabled else 'desativada'}"})
        return jsonify({"success": False, "error": "Estratégia não encontrada"}), 404
    except Exception:
        logger.exception("Erro /api/strategies/toggle")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/system/status')
def api_system_status():
    try:
        status = data_manager.get_system_status()
        status['mt4_connected'] = bool(_safe_mt4_call('is_connected', default=status.get('mt4_connected', False)))
        return jsonify({"success": True, "data": status})
    except Exception:
        logger.exception("Erro /api/system/status")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/statistics')
def api_statistics():
    try:
        # Esta rota agora usa a função otimizada do data_manager
        stats = data_manager.get_statistics()
        return jsonify({"success": True, "data": stats})
    except Exception:
        logger.exception("Erro /api/statistics")
        return jsonify({"success": False, "error": "erro interno"}), 500


@app.route('/api/system/restart', methods=['POST'])
def api_system_restart():
    logger.info("Solicitado restart do sistema via API (simulado)")
    return jsonify({"success": True, "message": "Reinício simulado iniciado"})


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_PATH, filename)

# --- SOCKET.IO broadcast ---

_bg_stop_event: threading.Event = threading.Event()
_bg_task = None

def background_ai_broadcast(stop_event: Optional[threading.Event] = None):
    """
    Broadcast loop that periodically emits news and AI messages.
    Estatísticas e dados de conta são atualizados via API/Polling no cliente para evitar sobrecarga.
    """
    # Aumentando o intervalo para reduzir a carga no servidor
    INTERVAL = int(os.getenv('AI_BROADCAST_INTERVAL', '60')) 
    logger.info("Background AI broadcast iniciado (intervalo %ss)", INTERVAL)
    stop_event = stop_event or _bg_stop_event
    
    # Prompt base para as IAs
    ai_prompt = "Qual a análise de mercado atual para EURUSD e GBPUSD? Resuma em uma frase."
    
    while not stop_event.is_set():
        try:
            # 1. Broadcast de Notícias
            if news_api_manager is not None and hasattr(news_api_manager, 'get_latest_articles'):
                try:
                    latest = news_api_manager.get_latest_articles(limit=5)
                except Exception:
                    logger.exception("Erro ao obter noticias no broadcast")
                    latest = []
            else:
                latest = data_manager.get_news()

            news_payload = []
            for a in latest:
                try:
                    title = getattr(a, 'title', a.get('title') if isinstance(a, dict) else str(a))
                    content = getattr(a, 'description', a.get('description', ''))
                    published = getattr(a, 'publishedAt', getattr(a, 'published_at', None))
                    time_str = published.strftime('%H:%M') if hasattr(published, 'strftime') else (published or '')
                except Exception:
                    title = str(a)
                    content = ''
                    time_str = ''
                news_payload.append({"title": title, "content": content or '', "time": time_str})

            try:
                socketio.emit('ai_news', {"data": news_payload})
            except Exception:
                logger.exception("Falha ao emitir ai_news")

            # 2. Broadcast de Análises de IA
            ai_results = ai_manager.query_all_ais(ai_prompt)
            if ai_results:
                try:
                    socketio.emit('ai_analyses', {"data": ai_results})
                except Exception:
                    logger.exception("Falha ao emitir ai_analyses")
            
            # 3. Broadcast de Dados de Conta (Opcional, se o MT4Communication for passivo)
            # Se o MT4Communication for ativo (recebe dados e os armazena), ele deve emitir
            # o evento 'account_update' diretamente. Se for passivo (o dashboard o consulta),
            # podemos fazer uma consulta leve aqui.
            # Decisão: Manter a consulta de conta via API/Polling no cliente, mas adicionar um
            # evento de "heartbeat" ou "status" para manter a conexão viva e informar o status.
            
            # Heartbeat/Status
            status_payload = {
                "mt4_connected": bool(_safe_mt4_call('is_connected', default=False)),
                "timestamp": datetime.now().isoformat()
            }
            try:
                socketio.emit('system_heartbeat', status_payload)
            except Exception:
                logger.exception("Falha ao emitir system_heartbeat")

        except Exception:
            logger.exception("Erro no loop do broadcast AI")

        try:
            socketio.sleep(INTERVAL)
        except Exception:
            time.sleep(INTERVAL)

    logger.info("Background AI broadcast finalizado")


@socketio.on('connect')
def handle_connect():
    global _bg_task, _bg_stop_event
    logger.info("Cliente conectado via SocketIO")
    # start background task once
    if _bg_task is None:
        _bg_stop_event.clear()
        _bg_task = socketio.start_background_task(background_ai_broadcast, _bg_stop_event)
    emit('connected', {'message': 'Conectado ao servidor de WebSocket'}, broadcast=False)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Cliente desconectado via SocketIO')

# --- Inicialização ---

def create_directories():
    needed = [DASHBOARD_DIR, TEMPLATES_PATH, STATIC_PATH, DATA_PATH, LOG_PATH]
    for d in needed:
        os.makedirs(d, exist_ok=True)


if __name__ == '__main__':
    try:
        create_directories()
        start_services()
        host = os.getenv('DASHBOARD_HOST', '0.0.0.0') # Alterado para 0.0.0.0 para acesso externo
        port = int(os.getenv('DASHBOARD_PORT', '5000'))
        debug = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        logger.info("Iniciando servidor em %s:%s (debug=%s)", host, port, debug)
        socketio.run(app, host=host, port=port, debug=debug, use_reloader=debug)
    except KeyboardInterrupt:
        logger.info("Servidor interrompido pelo usuário")
        try:
            _bg_stop_event.set()
        except Exception:
            pass
        sys.exit(0)
    except Exception:
        logger.exception("Erro fatal ao iniciar servidor")
        sys.exit(1)
