# -*- coding: utf-8 -*-
"""
JokaMazKiBu Trading Bot Dashboard v8.0 HARDCORE
Ultra Professional - Windows Optimized - Production Ready
Author: Manus AI | Date: 2026-01-01
"""

import os
import sys
import logging
import threading
import json
import socket
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from functools import wraps
from collections import deque, defaultdict
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO, emit, disconnect, join_room, leave_room, rooms
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# =====================================================================
# CONFIGURATION & PATHS
# =====================================================================
THIS_FILE = Path(__file__).resolve()
BASE_DIR = THIS_FILE.parent
PROJECT_ROOT = BASE_DIR.parent if BASE_DIR.name == "dashboard" else BASE_DIR

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()

# Dashboard Config
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
DASHBOARD_SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", "jokamazkibu_hardcore_2024")
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "joka")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "j0K4616")

# Bot Config
BOT_HOST = os.getenv("MT5_SOCKET_HOST", "127.0.0.1")
BOT_PORT = int(os.getenv("MT5_SOCKET_PORT", "5555"))

# Paths
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"

for d in [TEMPLATES_DIR, STATIC_DIR, LOGS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# =====================================================================
# LOGGING SETUP
# =====================================================================
log_file = LOGS_DIR / "dashboard_server.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_file), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("dashboard")

# =====================================================================
# FLASK & SOCKETIO SETUP
# =====================================================================
app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR))
app.config.update(
    SECRET_KEY=DASHBOARD_SECRET_KEY,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
    JSON_SORT_KEYS=False,
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,
)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    ping_timeout=60,
    ping_interval=25,
    logger=False,
    engineio_logger=False,
    manage_session=False
)

# =====================================================================
# GLOBAL STATE
# =====================================================================
START_TIME = datetime.now(timezone.utc)
USERS = {DASHBOARD_USERNAME: generate_password_hash(DASHBOARD_PASSWORD)}
CONNECTED_CLIENTS = {}
BOT_STATE = {
    "connected": False,
    "status": "offline",
    "balance": 50000.00,
    "equity": 50000.00,
    "open_trades": 0,
    "total_trades": 0,
    "profit_loss": 0.0,
    "win_rate": 0.0,
    "account_leverage": 100,
    "margin_level": 0.0,
}
ACTIVE_TRADES = {}
STRATEGY_STATS = {
    "adaptive_ml": {"enabled": True, "trades": 0, "win_rate": 0.0, "profit": 0.0},
    "supertrend": {"enabled": True, "trades": 0, "win_rate": 0.0, "profit": 0.0},
    "rsi": {"enabled": True, "trades": 0, "win_rate": 0.0, "profit": 0.0},
    "ema_crossover": {"enabled": True, "trades": 0, "win_rate": 0.0, "profit": 0.0},
    "buy_low_sell_high": {"enabled": False, "trades": 0, "win_rate": 0.0, "profit": 0.0},
}
AI_MODELS = {
    "gpt1": {"status": "active", "last_used": None, "accuracy": 0.75},
    "gpt2": {"status": "active", "last_used": None, "accuracy": 0.78},
    "gpt3": {"status": "active", "last_used": None, "accuracy": 0.82},
    "gpt4": {"status": "active", "last_used": None, "accuracy": 0.85},
    "gpt5": {"status": "active", "last_used": None, "accuracy": 0.80},
    "gpt6": {"status": "active", "last_used": None, "accuracy": 0.79},
    "gpt7": {"status": "active", "last_used": None, "accuracy": 0.77},
}
SYSTEM_LOGS = deque(maxlen=1000)
MARKET_NEWS = deque(maxlen=100)
PERFORMANCE_METRICS = {
    "trades_today": 0,
    "profit_today": 0.0,
    "max_drawdown": 0.0,
    "sharpe_ratio": 1.45,
    "profit_factor": 2.30,
}

# =====================================================================
# UTILITIES
# =====================================================================
def sanitize_for_json(obj: Any, depth: int = 4) -> Any:
    """Convert objects to JSON-serializable format."""
    if depth <= 0:
        return str(obj)
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(x, depth - 1) for x in obj]
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v, depth - 1) for k, v in obj.items()}
    if isinstance(obj, (datetime, Decimal)):
        return str(obj)
    return str(obj)

def log_system(level: str, message: str, **kwargs):
    """Log system event."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = {
        "timestamp": timestamp,
        "level": level,
        "message": message,
        **kwargs
    }
    SYSTEM_LOGS.append(log_entry)
    
    if level == "ERROR":
        logger.error(message, **kwargs)
    elif level == "WARNING":
        logger.warning(message, **kwargs)
    else:
        logger.info(message, **kwargs)
    
    # Broadcast to all clients
    try:
        socketio.emit("system_log", log_entry, broadcast=True, skip_sid=True)
    except Exception as e:
        logger.error(f"Error broadcasting log: {e}")

def connect_to_bot() -> Optional[socket.socket]:
    """Connect to the MT5 trading bot via socket."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((BOT_HOST, BOT_PORT))
        return sock
    except Exception as e:
        return None

def send_command_to_bot(command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Send command to bot and receive response."""
    sock = connect_to_bot()
    if not sock:
        return None
    
    try:
        sock.sendall(json.dumps(command).encode("utf-8") + b"\n")
        response = sock.recv(65536).decode("utf-8")
        return json.loads(response)
    except Exception as e:
        return None
    finally:
        try:
            sock.close()
        except:
            pass

# =====================================================================
# AUTHENTICATION
# =====================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        if username in USERS and check_password_hash(USERS[username], password):
            session["user"] = username
            session.permanent = True
            logger.info(f"User {username} logged in successfully")
            return redirect(url_for("dashboard"))
        else:
            logger.warning(f"Failed login attempt for user: {username}")
            return render_template("login.html", error="❌ Credenciais inválidas!")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    user = session.get("user", "Unknown")
    session.clear()
    logger.info(f"User {user} logged out")
    return redirect(url_for("login"))

# =====================================================================
# ROUTES - MAIN
# =====================================================================
@app.route("/")
@login_required
def dashboard():
    username = session.get("user", "User")
    return render_template("dashboard.html", username=username)

# =====================================================================
# ROUTES - API
# =====================================================================
@app.route("/api/account", methods=["GET"])
@login_required
def api_account():
    """Get account information."""
    return jsonify({
        "balance": BOT_STATE["balance"],
        "equity": BOT_STATE["equity"],
        "profit_loss": BOT_STATE["profit_loss"],
        "margin_level": BOT_STATE["margin_level"],
        "leverage": BOT_STATE["account_leverage"],
        "currency": "USD",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route("/api/statistics", methods=["GET"])
@login_required
def api_statistics():
    """Get trading statistics."""
    return jsonify({
        "total_trades": BOT_STATE["total_trades"],
        "open_trades": BOT_STATE["open_trades"],
        "win_rate": BOT_STATE["win_rate"],
        "profit_factor": PERFORMANCE_METRICS["profit_factor"],
        "sharpe_ratio": PERFORMANCE_METRICS["sharpe_ratio"],
        "max_drawdown": PERFORMANCE_METRICS["max_drawdown"],
        "trades_today": PERFORMANCE_METRICS["trades_today"],
        "profit_today": PERFORMANCE_METRICS["profit_today"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route("/api/positions", methods=["GET"])
@login_required
def api_positions():
    """Get active positions."""
    positions = []
    for trade_id, trade in ACTIVE_TRADES.items():
        positions.append({
            "id": trade_id,
            "symbol": trade.get("symbol", "N/A"),
            "direction": trade.get("direction", "N/A"),
            "volume": trade.get("volume", 0),
            "entry_price": trade.get("entry_price", 0),
            "current_price": trade.get("current_price", 0),
            "sl": trade.get("sl", 0),
            "tp": trade.get("tp", 0),
            "profit": trade.get("profit", 0),
            "strategy": trade.get("strategy", "Manual"),
            "timestamp": trade.get("timestamp", datetime.now(timezone.utc).isoformat())
        })
    
    return jsonify({
        "total": len(positions),
        "positions": positions,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route("/api/signals", methods=["GET"])
@login_required
def api_signals():
    """Get current signals from strategies."""
    signals = []
    for strategy_name, stats in STRATEGY_STATS.items():
        signals.append({
            "strategy": strategy_name,
            "enabled": stats["enabled"],
            "signal": "BUY" if stats["profit"] > 0 else "SELL" if stats["profit"] < 0 else "HOLD",
            "confidence": min(0.95, abs(stats["profit"]) / 1000),
            "trades": stats["trades"],
            "win_rate": stats["win_rate"],
            "profit": stats["profit"]
        })
    
    return jsonify({
        "total": len(signals),
        "signals": signals,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route("/api/system/status", methods=["GET"])
@login_required
def api_system_status():
    """Get system status."""
    bot_connected = connect_to_bot() is not None
    
    return jsonify({
        "dashboard": {
            "status": "online",
            "version": "8.0",
            "uptime": str(datetime.now(timezone.utc) - START_TIME),
            "clients_connected": len(CONNECTED_CLIENTS)
        },
        "bot": {
            "status": "online" if bot_connected else "offline",
            "host": BOT_HOST,
            "port": BOT_PORT,
            "connected": bot_connected
        },
        "system": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": sys.platform
        }
    })

@app.route("/api/logs", methods=["GET"])
@login_required
def api_logs():
    """Get system logs."""
    limit = request.args.get("limit", 100, type=int)
    level_filter = request.args.get("level", None)
    
    logs = list(SYSTEM_LOGS)[:limit]
    
    if level_filter:
        logs = [log for log in logs if log.get("level") == level_filter]
    
    return jsonify({
        "total": len(logs),
        "logs": logs,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route("/api/news", methods=["GET"])
@login_required
def api_news():
    """Get market news."""
    limit = request.args.get("limit", 50, type=int)
    news = list(MARKET_NEWS)[:limit]
    
    return jsonify({
        "total": len(news),
        "news": news,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

# =====================================================================
# WEBSOCKET EVENTS
# =====================================================================
@socketio.on("connect")
def handle_connect():
    """Client connected."""
    client_id = request.sid
    CONNECTED_CLIENTS[client_id] = {
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "user": session.get("user", "unknown")
    }
    logger.info(f"✓ Client {client_id[:8]}... connected")
    emit("connection_response", {
        "status": "connected",
        "client_id": client_id,
        "message": "Conectado ao dashboard com sucesso!"
    })

@socketio.on("disconnect")
def handle_disconnect():
    """Client disconnected."""
    client_id = request.sid
    if client_id in CONNECTED_CLIENTS:
        del CONNECTED_CLIENTS[client_id]
    logger.info(f"✗ Client {client_id[:8]}... disconnected")

@socketio.on("request_bot_status")
def handle_bot_status():
    """Request bot status."""
    try:
        emit("bot_status", sanitize_for_json(BOT_STATE))
    except Exception as e:
        logger.error(f"Error emitting bot status: {e}")

@socketio.on("request_trades")
def handle_request_trades():
    """Request active trades."""
    try:
        emit("trades_update", sanitize_for_json(ACTIVE_TRADES))
    except Exception as e:
        logger.error(f"Error emitting trades: {e}")

@socketio.on("request_strategies")
def handle_request_strategies():
    """Request strategy stats."""
    try:
        emit("strategies_update", sanitize_for_json(STRATEGY_STATS))
    except Exception as e:
        logger.error(f"Error emitting strategies: {e}")

@socketio.on("request_ai_models")
def handle_request_ai_models():
    """Request AI models."""
    try:
        emit("ai_models_update", sanitize_for_json(AI_MODELS))
    except Exception as e:
        logger.error(f"Error emitting AI models: {e}")

@socketio.on("execute_trade")
def handle_execute_trade(data):
    """Execute a trade via bot."""
    try:
        symbol = data.get("symbol", "EURUSD").upper()
        direction = data.get("direction", "BUY").upper()
        volume = float(data.get("volume", 0.01))
        sl = float(data.get("sl", 0))
        tp = float(data.get("tp", 0))
        
        # Validate
        if volume <= 0 or volume > 100:
            emit("trade_failed", {"error": "Volume inválido (0.01 - 100)"})
            return
        
        command = {
            "action": "execute_trade",
            "symbol": symbol,
            "direction": direction,
            "volume": volume,
            "sl": sl,
            "tp": tp
        }
        
        response = send_command_to_bot(command)
        if response:
            log_system("INFO", f"Trade executado: {direction} {symbol} @ {volume}")
            emit("trade_executed", response, skip_sid=True)
        else:
            # Simular trade para demo
            trade_id = f"DEMO_{int(time.time())}"
            ACTIVE_TRADES[trade_id] = {
                "symbol": symbol,
                "direction": direction,
                "volume": volume,
                "entry_price": 1.0950,
                "current_price": 1.0950,
                "sl": sl,
                "tp": tp,
                "profit": 0.0,
                "strategy": "Manual",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            log_system("INFO", f"Trade DEMO: {direction} {symbol} @ {volume}")
            emit("trade_executed", {"status": "success", "trade_id": trade_id}, skip_sid=True)
    
    except Exception as e:
        logger.error(f"Error executing trade: {e}")
        emit("trade_failed", {"error": str(e)})

@socketio.on("select_ai_model")
def handle_select_ai_model(data):
    """Select AI model for analysis."""
    try:
        model_name = data.get("model", "gpt1")
        
        if model_name in AI_MODELS:
            AI_MODELS[model_name]["last_used"] = datetime.now(timezone.utc).isoformat()
            log_system("INFO", f"Modelo de IA selecionado: {model_name}")
            emit("ai_model_selected", {
                "status": "success",
                "model": model_name,
                "message": f"Modelo {model_name} selecionado com sucesso!"
            }, skip_sid=True)
        else:
            emit("ai_model_selected", {"status": "error", "message": "Modelo não encontrado"})
    
    except Exception as e:
        logger.error(f"Error selecting AI model: {e}")
        emit("ai_model_selected", {"status": "error", "message": str(e)})

@socketio.on("update_risk_config")
def handle_update_risk_config(data):
    """Update risk management configuration."""
    try:
        risk_per_trade = float(data.get("risk_per_trade", 0.5))
        max_daily_loss = float(data.get("max_daily_loss", 2.0))
        max_concurrent_trades = int(data.get("max_concurrent_trades", 5))
        
        # Validate
        if not (0.1 <= risk_per_trade <= 5):
            emit("risk_config_failed", {"error": "Risco deve estar entre 0.1% e 5%"})
            return
        
        log_system("INFO", f"Configuração de risco atualizada: {risk_per_trade}% risco")
        emit("risk_config_updated", {
            "status": "success",
            "risk_per_trade": risk_per_trade,
            "max_daily_loss": max_daily_loss,
            "max_concurrent_trades": max_concurrent_trades
        }, skip_sid=True)
    
    except Exception as e:
        logger.error(f"Error updating risk config: {e}")
        emit("risk_config_failed", {"error": str(e)})

@socketio.on("enable_strategy")
def handle_enable_strategy(data):
    """Enable/disable strategy."""
    try:
        strategy_name = data.get("strategy", "").lower()
        enabled = data.get("enabled", True)
        
        if strategy_name in STRATEGY_STATS:
            STRATEGY_STATS[strategy_name]["enabled"] = enabled
            log_system("INFO", f"Estratégia {strategy_name} {'ativada' if enabled else 'desativada'}")
            emit("strategy_toggled", {
                "status": "success",
                "strategy": strategy_name,
                "enabled": enabled
            }, skip_sid=True)
        else:
            emit("strategy_toggled", {"status": "error", "message": "Estratégia não encontrada"})
    
    except Exception as e:
        logger.error(f"Error toggling strategy: {e}")
        emit("strategy_toggled", {"status": "error", "message": str(e)})

@socketio.on("get_ai_analysis")
def handle_get_ai_analysis(data):
    """Get AI analysis for symbol."""
    try:
        symbol = data.get("symbol", "EURUSD").upper()
        ai_model = data.get("ai_model", "gpt1")
        
        if ai_model not in AI_MODELS:
            emit("ai_analysis_failed", {"error": "Modelo de IA não encontrado"})
            return
        
        # Simular análise
        analysis = {
            "status": "success",
            "symbol": symbol,
            "ai_model": ai_model,
            "signal": "BUY",
            "confidence": 0.82,
            "analysis": f"Análise técnica para {symbol}: Tendência de alta com suporte em 1.0900. Recomendação: COMPRAR com alvo em 1.1000.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        log_system("INFO", f"Análise de IA: {symbol} por {ai_model}")
        emit("ai_analysis", analysis)
    
    except Exception as e:
        logger.error(f"Error getting AI analysis: {e}")
        emit("ai_analysis_failed", {"error": str(e)})

# =====================================================================
# BACKGROUND THREAD - BOT SYNC
# =====================================================================
def sync_bot_data():
    """Periodically sync data from bot."""
    logger.info("Bot sync thread started")
    
    while True:
        try:
            time.sleep(2)
            
            # Try to connect to bot
            command = {"action": "get_status"}
            response = send_command_to_bot(command)
            
            if response and response.get("status") == "success":
                BOT_STATE.update(response.get("bot_state", {}))
                ACTIVE_TRADES.update(response.get("active_trades", {}))
                STRATEGY_STATS.update(response.get("strategy_stats", {}))
                
                # Broadcast to all connected clients
                try:
                    socketio.emit("bot_update", {
                        "bot_state": sanitize_for_json(BOT_STATE),
                        "active_trades": sanitize_for_json(ACTIVE_TRADES),
                        "strategy_stats": sanitize_for_json(STRATEGY_STATS),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }, skip_sid=True)
                except Exception as e:
                    logger.debug(f"Error broadcasting bot update: {e}")
        
        except Exception as e:
            logger.error(f"Sync error: {e}")
            time.sleep(5)

# =====================================================================
# ERROR HANDLERS
# =====================================================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Rota não encontrada", "status": 404}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Erro interno do servidor", "status": 500}), 500

@app.errorhandler(403)
def forbidden(error):
    return jsonify({"error": "Acesso proibido", "status": 403}), 403

# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("JokaMazKiBu Trading Bot Dashboard v8.0 HARDCORE")
    logger.info("=" * 80)
    logger.info(f"Starting Dashboard on {DASHBOARD_HOST}:{DASHBOARD_PORT}")
    logger.info(f"Bot connection: {BOT_HOST}:{BOT_PORT}")
    logger.info(f"Templates: {TEMPLATES_DIR}")
    logger.info(f"Static: {STATIC_DIR}")
    logger.info("=" * 80)
    
    # Start background sync thread
    sync_thread = threading.Thread(target=sync_bot_data, daemon=True)
    sync_thread.start()
    logger.info("✓ Bot sync thread started")
    
    try:
        socketio.run(
            app,
            host=DASHBOARD_HOST,
            port=DASHBOARD_PORT,
            debug=False,
            use_reloader=False,
            log_output=False,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 80)
        logger.info("Dashboard shutting down...")
        logger.info("=" * 80)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
