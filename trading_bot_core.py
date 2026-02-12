# trading_bot_core_with_strategies.py — HARDCORE / PRODUCTION (improved)
from __future__ import annotations

import os
import sys
import time
import collections
import signal
import json
import logging
import csv
# dashboard_server.py
import threading
from flask import Flask
import math
import MetaTrader5 as mt5

import numpy as np
import importlib.util
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from threading import Lock, Event
from typing import Dict, Optional, Tuple, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import deque


BOT_BASE_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_BASE_PATH)
BASE_DIR = BOT_BASE_PATH
MAX_SIGNAL_BUFFER = 50  # valor default se não definido no env

# --------------------------- TRADING BOT -------------------------
import os
import logging
from threading import Lock, Event
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple, Optional

from mt5_communication import MT5Communication
from ai_manager import AIManager
from strategies.risk_manager import RiskManager
from strategies.strategy_engine import StrategyEngine
from strategies.deep_q_learning import StrategyDataCollector, BacktestEngine, MultiIAAdaptiveTrainer, OnlineLearningScheduler, ReplayBuffer, RunningNormalizer,  DQNAgent, TradingEnv
from strategies.core_models import TradeDirection
from strategies.models import TradeSignal
from logging.handlers import TimedRotatingFileHandler

from strategies.models import TradeDirection

import logging as _logging
for _n in ("websockets", "websockets.server", "websockets.http11", "websockets.asyncio"):
    _logging.getLogger(_n).setLevel(_logging.WARNING)

def _sanitize_dqn_output(raw_out) -> "TradeDirection":
    """
    Normaliza saída do DeepQ / DQN / qualquer agente para TradeDirection.
    Aceita: str, int, enum TradeDirection, tuple/list onde primeiro elemento é a decisão, etc.
    Sempre retorna TradeDirection (nunca lança).
    """
    try:
        # Primeiro elemento se for tupla/list
        primary = raw_out[0] if isinstance(raw_out, (list, tuple)) and len(raw_out) > 0 else raw_out

        # Se já é um TradeDirection
        try:
            if isinstance(primary, TradeDirection):
                return primary
        except Exception:
            pass

        # Strings como 'SELL','BUY','LONG','SHORT'
        if isinstance(primary, str):
            p = primary.strip().upper()
            if p in ("BUY", "LONG", "CALL", "B", "1"):
                return TradeDirection.BUY
            if p in ("SELL", "SHORT", "PUT", "S", "-1"):
                return TradeDirection.SELL
            if p in ("HOLD", "NONE", "WAIT", "NO_TRADE"):
                return TradeDirection.HOLD

        # Números (mapeie conforme seu agente: 0=sell,1=hold,2=buy por exemplo)
        if isinstance(primary, int):
            if primary == 2:
                return TradeDirection.BUY
            if primary == 0:
                return TradeDirection.SELL
            return TradeDirection.HOLD

        # objetos enum-like com .name ou .value
        try:
            nm = getattr(primary, "name", None) or getattr(primary, "value", None)
            if isinstance(nm, str):
                return _sanitize_dqn_output(nm)
        except Exception:
            pass
    except Exception:
        pass

    return TradeDirection.HOLD

# utils dentro do trading_bot_core.py (ou util_module.py)
def normalize_trade_direction(val, TradeDirectionClass=None):
    """
    Normaliza vários formatos (str, enum, tuple/list com elementos) para um valor seguro
    do enum TradeDirection (ou string 'BUY'/'SELL'/'HOLD' se TradeDirectionClass for None).
    """
    try:
        # Se vier tuple/list, preferir o 1º elemento que não seja None
        if isinstance(val, (list, tuple)) and len(val) > 0:
            # recursivo: pega o primeiro elemento válido
            return normalize_trade_direction(val[0], TradeDirectionClass)

        # Se já for o enum (instância)
        if TradeDirectionClass is not None:
            # tenta detectar se já é enum da classe
            try:
                if isinstance(val, TradeDirectionClass):
                    return val
            except Exception:
                pass

        # strings e enums com .name
        if hasattr(val, "name"):
            sval = str(val.name).upper()
        else:
            sval = str(val).upper()

        if "BUY" in sval or "LONG" in sval:
            out = "BUY"
        elif "SELL" in sval or "SHORT" in sval:
            out = "SELL"
        elif "HOLD" in sval or "NONE" in sval or sval.strip() == "":
            out = "HOLD"
        else:
            out = "HOLD"

        if TradeDirectionClass is not None:
            # tentar mapear para enum
            try:
                # se o enum aceita string names
                return TradeDirectionClass[out]
            except Exception:
                # fallback: tenta instanciar com nome
                try:
                    return TradeDirectionClass(out)
                except Exception:
                    # último recurso: retorna membro HOLD se existir
                    try:
                        return TradeDirectionClass["HOLD"]
                    except Exception:
                        # se tudo falhar, retorna string
                        return out
        return out

    except Exception:
        # fallback seguro
        if TradeDirectionClass:
            try:
                return TradeDirectionClass["HOLD"]
            except Exception:
                return "HOLD"
        return "HOLD"


def _normalize_deep_q_output(self, raw) -> Optional[Dict[str, Any]]:
    """
    Converte a saída do deep_q.predict para um dict padronizado:
    {'decision': 'BUY'|'SELL'|'HOLD', 'confidence':0..1, 'tp_pips':float, 'sl_pips':float, 'raw': raw}
    Retorna None se não conseguir normalizar.
    """
    try:
        if raw is None:
            return None

        # dict já padronizado
        if isinstance(raw, dict):
            dec = raw.get("decision") or raw.get("action") or raw.get("signal")
            if isinstance(dec, TradeDirection):
                dec = dec.name
            dec = str(dec).upper() if dec is not None else "HOLD"
            if dec == "LONG":
                dec = "BUY"
            if dec == "SHORT":
                dec = "SELL"
            if dec not in ("BUY", "SELL", "HOLD"):
                return None

            conf = max(0.0, min(1.0, _safe_float(raw.get("confidence") or raw.get("conf") or 0.0)))
            tp = max(1.0, _safe_float(raw.get("tp_pips") or raw.get("tp") or raw.get("take_profit") or 1.0))
            sl = max(1.0, _safe_float(raw.get("sl_pips") or raw.get("sl") or raw.get("stop_loss") or 1.0))
            return {"raw": raw, "decision": dec, "confidence": conf, "tp_pips": tp, "sl_pips": sl}

        # tuple/list → ('SELL', TradeDirection.HOLD) ou ('SELL', 0.23, tp, sl)
        if isinstance(raw, (list, tuple)) and len(raw) >= 1:
            dec = raw[0]
            if isinstance(dec, TradeDirection):
                dec = dec.name
            dec = str(dec).upper()
            if dec == "LONG":
                dec = "BUY"
            if dec == "SHORT":
                dec = "SELL"
            if dec not in ("BUY", "SELL", "HOLD"):
                return None
            conf = _safe_float(raw[1] if len(raw) > 1 else 0.0)
            tp = _safe_float(raw[2] if len(raw) > 2 else 1.0)
            sl = _safe_float(raw[3] if len(raw) > 3 else 1.0)
            conf = max(0.0, min(1.0, conf if conf <= 1.0 else conf / 100.0))
            return {"raw": raw, "decision": dec, "confidence": conf, "tp_pips": max(1.0, tp), "sl_pips": max(1.0, sl)}

        # string => parse com seu parser robusto
        if isinstance(raw, str) and callable(getattr(self, "_parse_response_full", None)):
            try:
                d, c, tp, sl = self._parse_response_full(raw)
                return {"raw": raw, "decision": d, "confidence": c, "tp_pips": tp, "sl_pips": sl}
            except Exception:
                return None

    except Exception:
        self.logger.debug("normalize_deep_q_output failed for %r", raw, exc_info=True)

    return None

# --------------------------- BOOTSTRAP ---------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
load_dotenv()

LOG_LEVEL = str(os.getenv("LOG_LEVEL", "INFO")).upper()

# resolve nível numericamente, fallback para INFO
_level = getattr(logging, LOG_LEVEL, None)
if not isinstance(_level, int):
    try:
        _level = logging.getLevelName(LOG_LEVEL)
        if isinstance(_level, str):
            _level = logging.INFO
    except Exception:
        _level = logging.INFO

logger = logging.getLogger("TradingBot")
logger.setLevel(_level)
logger.propagate = False

# garante pelo menos um handler (evita "No handlers could be found")
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | TradingBot | %(message)s"))
    logger.addHandler(sh)

# reduzir ruído do websockets (handshakes HTTP indevidos)
try:
    for _n in ("websockets", "websockets.server", "websockets.http11", "websockets.asyncio"):
        logging.getLogger(_n).setLevel(logging.WARNING)
except Exception:
    # não falhar por causa do ajuste de níveis de bibliotecas externas
    pass


# Evita múltiplos handlers duplicados
if not logger.handlers:
    # Formatter padrão
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    # Diretório de logs
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "trading_bot.log")

    # --------------------------- File Handler ---------------------------
    try:
        # TimedRotatingFileHandler é mais seguro no Windows
        fh = TimedRotatingFileHandler(
            log_file_path,
            when="midnight",   # rotaciona diariamente
            interval=1,
            backupCount=7,     # mantém 7 dias de logs
            encoding="utf-8",
            delay=True
        )
        fh.setFormatter(fmt)
        fh.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        logger.addHandler(fh)
    except Exception as e:
        print(f"⚠️ Falha ao criar FileHandler: {e}", file=sys.stderr)

    # --------------------------- Stream Handler ---------------------------
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    ch.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.addHandler(ch)

logger.info("✅ Logger TradingBot inicializado com sucesso")

# --------------------------- CONFIG ------------------------------
LLAMA_MODEL_PATH = os.getenv("LLAMA_MODEL_PATH") or os.getenv("MODEL_PATH")
SYMBOLS = [s.strip() for s in os.getenv("TRADE_SYMBOLS", "EURUSD").split(",") if s.strip()]
if not SYMBOLS:
    SYMBOLS = ["EURUSD"]

VOLUME = float(os.getenv("TRADE_VOLUME", "0.01"))
MIN_VOLUME = float(os.getenv("MIN_VOLUME", "0.01"))
MAX_VOLUME = float(os.getenv("MAX_VOLUME", "1.0"))

LOOP_INTERVAL = float(os.getenv("LOOP_INTERVAL", "1.0"))
MIN_TRADE_INTERVAL = float(os.getenv("MIN_TRADE_INTERVAL", "30"))

AI_TIMEOUT = float(os.getenv("AI_TIMEOUT", "10"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")

MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "5"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.55"))

TRADE_HISTORY_CSV = os.path.join(BASE_DIR, os.getenv("TRADE_HISTORY_CSV", "trade_history.csv"))
STRATEGIES_DIR = os.getenv("STRATEGIES_DIR") or os.path.join(BASE_DIR, "strategies")

# signal buffer limits
MAX_SIGNAL_BUFFER = int(os.getenv("MAX_SIGNAL_BUFFER", "400"))
SIGNAL_PROCESS_BATCH = int(os.getenv("SIGNAL_PROCESS_BATCH", "6"))

# --------------------------- UTIL --------------------------------
def _safe_float(val, default=0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

# --- AI / trade helpers injected ---
def _normalize_direction(raw) -> str:
    """
    Normaliza valores possíveis para 'BUY' | 'SELL' | 'HOLD'
    Aceita strings, enums, tuples ('SELL', ...), etc.
    """
    try:
        if raw is None:
            return "HOLD"
        # se for tuple/list: toma o primeiro elemento
        if isinstance(raw, (tuple, list)) and len(raw) >= 1:
            raw = raw[0]
        # strings: normaliza
        if isinstance(raw, str):
            s = raw.strip().upper()
            if s in ("BUY", "LONG", "B", "1"): return "BUY"
            if s in ("SELL", "SHORT", "S", "-1"): return "SELL"
            return "HOLD"
        # se for enum-like com .name
        try:
            n = getattr(raw, "name", None) or getattr(raw, "value", None)
            if isinstance(n, str):
                return _normalize_direction(n)
        except Exception:
            pass
    except Exception:
        pass
    return "HOLD"

def _ensure_sl_pips(signal: dict) -> float:
    """
    Garante que há um sl_pips no sinal; tenta calcular a partir de price e stop_loss.
    Retorna float sl_pips (>=0.0).
    """
    try:
        sl_pips = None
        if "sl_pips" in signal:
            sl_pips = float(signal.get("sl_pips") or 0.0)
        if not sl_pips:
            price = signal.get("price") or signal.get("entry_price") or signal.get("price_entry")
            stop = signal.get("stop_loss") or signal.get("sl") or signal.get("stop")
            if price is not None and stop is not None:
                price_f = float(price); stop_f = float(stop)
                # pips calc (assume 1 pip = 0.0001 for FX; adapt if BTC etc)
                # tenta detectar escala: se price > 1000 -> instrumento grande (ex: BTC), usa absolute diff
                if price_f > 1000:
                    sl_pips = abs(price_f - stop_f)
                else:
                    sl_pips = abs(price_f - stop_f) / 0.0001
            else:
                sl_pips = float(os.getenv("DEFAULT_SL_PIPS", "10"))
        return float(max(0.0, sl_pips))
    except Exception:
        return float(os.getenv("DEFAULT_SL_PIPS", "10"))
# --- end helpers ---


def _ensure_csv_headers(path: str, headers: list):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(headers)


def sanitize_for_json(obj):
    """Tenta transformar objeto em JSON-safe para logging (strip big objects)."""
    try:
        return json.loads(json.dumps(obj, default=str, ensure_ascii=False))
    except Exception:
        try:
            return str(obj)
        except Exception:
            return "<unserializable>"

# --------------------------- STRATEGY LOADER ----------------------
def import_module_from_path(path: str, module_name: Optional[str] = None):
    import importlib.util
    import sys
    import os
    module_name = module_name or f"strategy_{os.path.splitext(os.path.basename(path))[0]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load spec from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def discover_strategies(strategies_dir: str) -> List[Any]:
    out = []
    if not os.path.isdir(strategies_dir):
        logger.warning("Strategies dir not found: %s", strategies_dir)
        return out
    for fn in os.listdir(strategies_dir):
        if not fn.endswith('.py'):
            continue
        path = os.path.join(strategies_dir, fn)
        try:
            mod = import_module_from_path(path)
        except Exception as e:
            logger.exception("Failed importing strategy module %s: %s", fn, e)
            continue
        candidates = []
        for attr_name in dir(mod):
            try:
                obj = getattr(mod, attr_name)
            except Exception:
                continue
            if isinstance(obj, type):
                if attr_name.lower().endswith('strategy') or attr_name.lower().endswith('agent') or attr_name.lower().endswith('engine'):
                    candidates.append((attr_name, obj))
                else:
                    try:
                        from strategies.base_strategy import BaseStrategy as ProjectBase
                    except Exception:
                        ProjectBase = None
                    if ProjectBase is not None and isinstance(obj, type) and issubclass(obj, ProjectBase):
                        candidates.append((attr_name, obj))
        name = os.path.splitext(fn)[0]
        if not candidates:
            for guess in (name.capitalize(), ''.join([p.capitalize() for p in name.split('_')]) + 'Strategy', 'Strategy'):
                if hasattr(mod, guess):
                    obj = getattr(mod, guess)
                    if isinstance(obj, type):
                        candidates.append((guess, obj))
        for cname, cls in candidates:
            out.append({"name": cname, "module": mod, "class": cls, "path": path})
    return out


class TradingBot:
    def __init__(self):

        # --- AUTO-INJECTED DEFAULTS to avoid AttributeError ---
        self.force_send = getattr(self, 'force_send', False)
        self.min_confidence = getattr(self, 'min_confidence', float(os.getenv('MIN_CONFIDENCE', '0.55')))
        # ----------------------------------------------------
        # ---------- Estado inicial ----------
        self.state = {
            'status': 'STOPPED',
            'balance': 0.0,
            'equity': 0.0,
            'positions': [],
            'last_signal': None,
            'last_update': None
        }

        # ---------- Logger (usa o global do bootstrap) ----------
        try:
            from __main__ import logger as global_logger
            self.logger = global_logger
        except ImportError:
            # fallback caso o logger global não esteja disponível
            self.logger = logging.getLogger("TradingBot")
            self.logger.setLevel(logging.INFO)
            if not self.logger.handlers:
                ch = logging.StreamHandler(sys.stdout)
                ch.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
                self.logger.addHandler(ch)

        self.logger.info("Inicializando TradingBot (robusto)...")

        # ---------- Concurrency primitives ----------
        self._lock = Lock()
        self._running = Event()
        self._running.set()
        self.force_send = False

        # ---------- Concurrency Primitives ----------
        self._trade_lock = Lock()
        self._csv_lock = Lock()
        try:
            max_sig = int(os.getenv("MAX_SIGNAL_BUFFER", str(MAX_SIGNAL_BUFFER)))
        except Exception:
            max_sig = MAX_SIGNAL_BUFFER
        self._signal_buffer = deque(maxlen=max_sig)
        self._signal_lock = Lock()
        self._running = Event()
        self._running.set()
        # máximo de threads para rodar estratégias paralelas
        self._strat_executor = ThreadPoolExecutor(max_workers=int(os.getenv("MAX_STRAT_THREADS", "4")))
        
        self._ai_executor = ThreadPoolExecutor(max_workers=4) 

        # ---------- Core Components (injetáveis) ----------
        self.mt5: Optional[Any] = None
        self.ai: Optional[Any] = None
        self.risk_manager: Optional[Any] = None
        self.strategy_engine: Optional[Any] = None
        self.deep_q_agent: Optional[Any] = None
        self.deep_q_strategy: Optional[Any] = None

        # ---------- Estratégias / estado ----------
        self.strategies: List[Any] = []
        self.strategy_defs: List[Dict[str, Any]] = []
        self._strategies_loaded = False
        # se risk_manager ainda não foi criado e temos mt5_comm, inicializa
        if getattr(self, 'risk_manager', None) is None and getattr(self, 'mt5_comm', None) is not None:
            try:
                self.risk_manager = RiskManager(mt5_comm=self.mt5_comm)
                self.logger.info("RiskManager initialized after MT5 boot.")
            except Exception as e:
                self.logger.warning("Failed to init RiskManager after MT5: %s", e)

    # ---------- Métodos de estado para dashboard ----------
    def update_state(self):
        """Atualiza estado interno do bot"""
        try:
            self.state['balance'] = self.get_balance()  # método seu existente
            self.state['equity'] = self.get_equity()
            self.state['positions'] = self.get_positions()
        except Exception as e:
            self.logger.warning("Falha ao atualizar estado: %s", e)
        self.state['last_update'] = datetime.utcnow().isoformat()

    def save_state(self):
        """Salva estado em arquivo JSON para o dashboard"""
        try:
            state_file = os.path.join(BOT_BASE_PATH, 'bot_state.json')
            with open(state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            self.logger.warning("Falha ao salvar bot_state.json: %s", e)

    def load_state(self):
        """Carrega estado salvo"""
        try:
            state_file = os.path.join(BOT_BASE_PATH, 'bot_state.json')
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    self.state = json.load(f)
        except Exception as e:
            self.logger.warning("Falha ao carregar bot_state.json: %s", e)

        # ---------- Executors (safe limits) ----------
        def _safe_int_env(name: str, default: int) -> int:
            try:
                v = int(os.getenv(name, str(default)))
                return max(1, v)
            except Exception:
                return default

        ai_workers = _safe_int_env("AI_WORKERS", 2)
        strat_workers = _safe_int_env("STRAT_WORKERS", 4)
        max_allowed = int(os.getenv("MAX_EXECUTOR_WORKERS", "32"))
        ai_workers = min(ai_workers, max_allowed)
        strat_workers = min(strat_workers, max_allowed)

        try:
            self._ai_executor = ThreadPoolExecutor(max_workers=ai_workers)
        except Exception:
            self._ai_executor = ThreadPoolExecutor(max_workers=2)
        try:
            self._strat_executor = ThreadPoolExecutor(max_workers=strat_workers)
        except Exception:
            self._strat_executor = ThreadPoolExecutor(max_workers=4)

        # ---------- CSV History (garante headers) ----------
        try:
            # garante que diretório exista
            path_dir = os.path.dirname(TRADE_HISTORY_CSV) or BASE_DIR
            os.makedirs(path_dir, exist_ok=True)
        except Exception:
            pass
        try:
            self._ensure_csv_headers(TRADE_HISTORY_CSV, ["ts", "symbol", "decision", "volume", "tp_pips", "sl_pips", "conf", "result"])
        except Exception:
            self.logger.debug("Falha ao criar/garantir CSV headers", exc_info=True)

        # ---------- Parâmetros globais (defensivos) ----------
        try:
            self.min_trade_interval = float(os.getenv("MIN_TRADE_INTERVAL", str(MIN_TRADE_INTERVAL)))
        except Exception:
            self.min_trade_interval = MIN_TRADE_INTERVAL
        try:
            self.min_confidence = float(os.getenv("MIN_CONFIDENCE", str(MIN_CONFIDENCE)))
        except Exception:
            self.min_confidence = MIN_CONFIDENCE
        try:
            self.max_concurrent_trades = int(os.getenv("MAX_CONCURRENT_TRADES", str(MAX_CONCURRENT_TRADES)))
        except Exception:
            self.max_concurrent_trades = MAX_CONCURRENT_TRADES

        try:
            # Support legacy DRY_RUN env or bool-like strings
            dr = os.getenv("DRY_RUN", "false").strip().lower()
            self.dry_run = dr in ("1", "true", "yes", "y") or (dr == "on")
        except Exception:
            self.dry_run = DRY_RUN

        # ---------- runtime flags for signal handling ----------
        try:
            self.force_send = os.getenv("FORCE_SEND", "0").lower() in ("1", "true", "yes")
        except Exception:
            self.force_send = False
        try:
            self.ai_sync_timeout = float(os.getenv("AI_SYNC_TIMEOUT", "2.0"))
        except Exception:
            self.ai_sync_timeout = 2.0
        try:
            self.ai_conf_margin = float(os.getenv("AI_CONF_MARGIN", "0.07"))
        except Exception:
            self.ai_conf_margin = 0.07
        try:
            self.default_lot = float(os.getenv("DEFAULT_LOT", str(VOLUME)))
        except Exception:
            self.default_lot = VOLUME

        # ---------- Placeholders / wiring will be done after components init ----------
        # Note: don't try to access self.mt5.strategy_engine/ai_manager here because mt5 may not exist yet.

        # ---------- Inicialização de AI (tenta com resiliência) ----------
        try:
            # usa função local que trata logs internamente
            self.init_ai()
            self.logger.info("AIManager inicializado com sucesso (ou None se falha silenciosa).")
        except Exception as e:
            # usa self.logger (definido acima)
            self.logger.exception("Falha ao inicializar AIManager — continuando sem IA: %s", e)
            self.ai = None

        # ---------- Inicialização de MT5Communication (não obrigatória) ----------
        # Não ligar automaticamente se a intenção for injetar mt5 depois; só tenta se ENV pedir
        try:
            auto_init_mt5 = os.getenv("AUTO_INIT_MT5", "0").lower() in ("1", "true", "yes")
        except Exception:
            auto_init_mt5 = False

        if auto_init_mt5:
            try:
                # init_mt5 fará logging próprio
                self.init_mt5()
            except Exception as e:
                self.logger.warning("init_mt5 falhou (continuando): %s", e)

        # ---------- Inicialização do StrategyEngine (tenta mas não quebra) ----------
        try:
            self.strategy_engine = StrategyEngine(strategies=self.strategies, ai_manager=self.ai)
            self.logger.info("StrategyEngine pronto.")
        except Exception as e:
            self.logger.warning("Falha ao inicializar StrategyEngine: %s", e)
            self.strategy_engine = None

        # ---------- Inicialização do Deep Q Agent (opcional / defensivo) ----------
        try:
            self.init_deep_q_agent(retry=5)  # tenta 5 vezes até MT5 estar pronto
        except Exception as e:
            self.logger.debug("Deep Q init falhou (ignored): %s", e, exc_info=True)
            self.deep_q_agent = None

        # ---------- Final summary ----------
        try:
            self.logger.info(
                "TradingBot inicializado | AI=%s | RiskManager=%s | StrategyEngine=%s | DeepQ=%s | DRY_RUN=%s",
                "ON" if self.ai else "OFF",
                "ON" if self.risk_manager else "OFF",
                "ON" if self.strategy_engine else "OFF",
                "ON" if (self.deep_q_agent or self.deep_q_strategy) else "OFF",
                bool(self.dry_run),
            )
        except Exception:
            # fallback minimal message
            self.logger.info("TradingBot iniciado (status resumido indisponível).")

    # ---------- Métodos utilitários ----------
    def _ensure_csv_headers(self, path: str, headers: List[str]):
        import os, csv
        if not os.path.exists(path):
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            self.logger.info(f"CSV criado com headers: {headers}")

    # ---------- init helpers ----------
    def init_mt5(self, backoff: float = 5.0, max_attempts: int = 5) -> MT5Communication:
        attempt = 0
        start_port = int(os.getenv("MT5_SOCKET_PORT", "9090"))
        host = os.getenv("MT5_SOCKET_HOST", "127.0.0.1")
        while attempt < max_attempts and self._running.is_set():
            attempt += 1
            try:
                mt5_comm = MT5Communication(host=host, port=start_port, ai_manager=self.ai)
                info = mt5_comm.get_account_info() or {}
                login = info.get('login') if isinstance(info, dict) else getattr(info, 'login', '?')
                balance = info.get('balance') if isinstance(info, dict) else getattr(info, 'balance', '?')
                self.logger.info("MT5 connected | Account=%s | Balance=%s", login, balance)
                # set both aliases so different parts do not break
                self.mt5 = mt5_comm
                self.mt5_comm = mt5_comm
                return mt5_comm
            except Exception as e:
                self.logger.exception("Failed to connect MT5 (attempt %d), retry in %ss: %s", attempt, backoff, e)
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 60)
        raise RuntimeError("Unable to initialize MT5")


    def init_ai(self, backoff: float = 3.0, max_attempts: int = 2) -> Optional[AIManager]:
        if getattr(self, "ai", None) is not None:
            self.logger.warning("AIManager already initialized — reusing instance")
            return self.ai

        attempt = 0
        while attempt < max_attempts and self._running.is_set():
            attempt += 1
            try:
                ai = AIManager(
                    mode="LIVE",
                    enable_llama=True,
                    max_total_timeout=float(os.getenv("AI_TIMEOUT", AI_TIMEOUT)),
                    max_models=int(os.getenv("AI_MAX_MODELS", "1")),
                    n_threads=int(os.getenv("AI_THREADS", "2")),
                    n_ctx=int(os.getenv("AI_N_CTX", "256")),
                )
                self.logger.info(f"AIManager initialized | mode={getattr(ai,'mode','unknown')} | timeout={getattr(ai,'max_total_timeout', getattr(ai,'model_timeout', 'unknown'))}s")
                self.ai = ai
                return ai
            except Exception as e:
                self.logger.exception(f"Failed to initialize AIManager (attempt {attempt}): {e}")
                if attempt < max_attempts:
                    time.sleep(min(backoff, 10))
                    backoff *= 1.5

        self.logger.critical("AIManager unavailable after attempts — continuing WITHOUT AI")
        self.ai = None
        return None

    # ---------- strategies management ----------
    def load_strategies(self, strategies_dir: Optional[str] = None):
        strategies_dir = strategies_dir or STRATEGIES_DIR
        logger.info("Discovering strategies in %s", strategies_dir)
        defs = discover_strategies(strategies_dir)
        self.strategy_defs = defs
        instances = []

        for d in defs:
            name = d.get('name', '<unknown>')
            path = d.get('path', '<unknown>')
            try:
                cls = d.get('class')
                if not isinstance(cls, type):
                    logger.warning("Skipping strategy %s: 'class' is not a type", name)
                    continue
                inst = None
                try:
                    inst = cls()
                except TypeError:
                    fallback_errors = []
                    try:
                        inst = cls(symbol=SYMBOLS[0])
                    except Exception as e:
                        fallback_errors.append(f"symbol= failed: {e}")
                    if inst is None:
                        try:
                            inst = cls(symbol=SYMBOLS[0], timeframe=int(os.getenv('DEFAULT_TIMEFRAME', '15')))
                        except Exception as e:
                            fallback_errors.append(f"symbol+timeframe= failed: {e}")
                    if inst is None:
                        try:
                            inst = cls(SYMBOLS[0])
                        except Exception as e:
                            fallback_errors.append(f"positional(symbol) failed: {e}")
                    if inst is None:
                        logger.debug("Strategy %s instantiation fallbacks failed: %s", name, "; ".join(fallback_errors))
                except Exception as e:
                    logger.exception("Strategy %s instantiation unexpected error: %s", name, e)
                    inst = None

                if inst is not None:
                    instances.append({'def': d, 'instance': inst})
                    logger.info("Loaded strategy %s from %s", name, path)
                else:
                    logger.warning("Skipping strategy %s (could not instantiate)", name)
            except Exception as e:
                logger.exception("Failed processing strategy definition %s (%s): %s", name, path, e)

        # deep q explicit
        dq_path = os.path.join(strategies_dir, 'deep_q_learning.py')
        try:
            if os.path.exists(dq_path):
                mod = import_module_from_path(dq_path)
                if hasattr(mod, 'DeepQLearningStrategy'):
                    try:
                        dq = getattr(mod, 'DeepQLearningStrategy')()
                        self.deep_q_strategy = dq
                        logger.info('Loaded DeepQLearningStrategy')
                    except Exception as e:
                        logger.exception('Failed to instantiate DeepQLearningStrategy: %s', e)
        except Exception:
            logger.debug("Deep Q load check failed", exc_info=True)

        self.strategies = [x['instance'] for x in instances if 'instance' in x and x['instance'] is not None]
        self._strategies_loaded = True
        return self.strategies
    
        def _normalize_ai_response(self, raw_res, default_conf: float, external_signal: dict = None) -> Dict[str, Any]:
            """
            Normaliza a resposta do AIManager para: {'approved': bool|None, 'decision': 'BUY'|'SELL'|'HOLD',
            'confidence': 0..1, 'tp_pips': float, 'sl_pips': float, 'raw': raw_res}
            Não lança - sempre retorna dict.
            """
            out = {
                "approved": None,
                "decision": "HOLD",
                "confidence": float(max(0.0, min(1.0, default_conf))),
                "tp_pips": None,
                "sl_pips": None,
                "raw": raw_res
            }
            try:
                if raw_res is None:
                    return out

                # dict-like
                if isinstance(raw_res, dict):
                    # approved / approve
                    if "approved" in raw_res:
                        out["approved"] = None if raw_res.get("approved") is None else bool(raw_res.get("approved"))
                    elif "approve" in raw_res:
                        out["approved"] = None if raw_res.get("approve") is None else bool(raw_res.get("approve"))

                    # decision
                    dec = str(raw_res.get("decision") or raw_res.get("action") or raw_res.get("signal") or "").upper()
                    if dec in ("LONG",): dec = "BUY"
                    if dec in ("SHORT",): dec = "SELL"
                    if dec in ("BUY", "SELL", "HOLD"):
                        out["decision"] = dec

                    # confidence
                    conf = raw_res.get("confidence", raw_res.get("conf", raw_res.get("score", None)))
                    if conf is not None:
                        try:
                            c = float(conf)
                            if c > 1.0:
                                c = c / 100.0
                            out["confidence"] = max(0.0, min(1.0, c))
                        except Exception:
                            pass

                    # tp/sl (pips or price) - prefer pips keys
                    for k in ("tp_pips", "sl_pips", "tp", "sl", "tp_price", "sl_price"):
                        if k in raw_res and raw_res.get(k) is not None:
                            try:
                                val = float(raw_res.get(k))
                                if "tp" in k and "tp" not in out:
                                    out["tp_pips"] = val
                                if "sl" in k and "sl_pips" not in out:
                                    out["sl_pips"] = val
                            except Exception:
                                pass

                    return out

                # boolean -> explicit approve/reject
                if isinstance(raw_res, bool):
                    out["approved"] = bool(raw_res)
                    out["confidence"] = 1.0 if bool(raw_res) else 0.0
                    return out

                # numeric -> confidence
                if isinstance(raw_res, (int, float)):
                    c = float(raw_res)
                    if c > 1.0:
                        c = c / 100.0
                    out["confidence"] = max(0.0, min(1.0, c))
                    out["approved"] = out["confidence"] >= 0.5
                    return out

                # string heuristic
                if isinstance(raw_res, str):
                    s = raw_res.upper()
                    if "BUY" in s and "SELL" not in s:
                        out["decision"] = "BUY"
                    elif "SELL" in s and "BUY" not in s:
                        out["decision"] = "SELL"
                    # confidence percents
                    import re
                    m = re.search(r"(\d{1,3})\s*%", s)
                    if m:
                        try:
                            out["confidence"] = max(0.0, min(1.0, float(m.group(1)) / 100.0))
                        except Exception:
                            pass
                    # set approved if clearly BUY/SELL and confidence ok
                    if out["decision"] in ("BUY", "SELL") and out["confidence"] >= 0.5:
                        out["approved"] = True
                    return out

            except Exception:
                try:
                    self.logger.debug("_normalize_ai_response error", exc_info=True)
                except Exception:
                    pass

            # fallback: if external_signal present and has confidence, try to honour it later
            return out


    # ---------- parse helpers ----------
    def _parse_response_full(self, text: str):
        """
        Parser ultra-robusto de resposta de IA.
        Extrai: decision (BUY/SELL/HOLD), confidence [0..1], tp_pips, sl_pips
        Nunca lança exceção. Nunca retorna TP/SL <= 0.
        """

        import json
        import re

        # ================= CONFIG PADRÃO =================
        DEFAULT_DECISION = "HOLD"
        DEFAULT_CONFIDENCE = 0.5
        DEFAULT_TP = 10.0
        DEFAULT_SL = 10.0

        # ================= SANITIZA INPUT =================
        raw = str(text or "").strip()
        if not raw:
            return DEFAULT_DECISION, DEFAULT_CONFIDENCE, DEFAULT_TP, DEFAULT_SL

        # normalização base
        raw_norm = raw.replace(",", ".")
        raw_up = raw_norm.upper()

        # =================================================
        # 1️⃣ TENTATIVA: JSON (inclusive JSON “sujo” no meio do texto)
        # =================================================
        try:
            jstart = raw_norm.find("{")
            jend = raw_norm.rfind("}")
            if jstart != -1 and jend != -1 and jend > jstart:
                payload = raw_norm[jstart:jend + 1]
                data = json.loads(payload)

                def _norm_dec(v):
                    v = str(v or "").upper()
                    if v in ("LONG", "BUY", "CALL"):
                        return "BUY"
                    if v in ("SHORT", "SELL", "PUT"):
                        return "SELL"
                    if v in ("HOLD", "WAIT", "NONE", "NO_TRADE"):
                        return "HOLD"
                    return DEFAULT_DECISION

                decision = _norm_dec(
                    data.get("decision") or
                    data.get("action") or
                    data.get("signal")
                )

                conf_raw = data.get("confidence") or data.get("conf") or data.get("score")
                confidence = _safe_float(conf_raw, DEFAULT_CONFIDENCE)
                if confidence > 1.0:
                    confidence = confidence / 100.0
                confidence = max(0.0, min(1.0, confidence))

                tp = _safe_float(data.get("tp_pips") or data.get("tp") or data.get("take_profit"), DEFAULT_TP)
                sl = _safe_float(data.get("sl_pips") or data.get("sl") or data.get("stop_loss"), DEFAULT_SL)

                tp = abs(tp)
                sl = abs(sl)

                return (
                    decision,
                    confidence,
                    max(1.0, tp),
                    max(1.0, sl),
                )
        except Exception:
            pass  # cai para regex

        # =================================================
        # 2️⃣ DECISION via regex textual
        # =================================================
        decision = DEFAULT_DECISION
        if re.search(r"\b(BUY|LONG|CALL)\b", raw_up) and not re.search(r"\b(SELL|SHORT|PUT)\b", raw_up):
            decision = "BUY"
        elif re.search(r"\b(SELL|SHORT|PUT)\b", raw_up) and not re.search(r"\b(BUY|LONG|CALL)\b", raw_up):
            decision = "SELL"

        # =================================================
        # 3️⃣ CONFIDENCE
        # =================================================
        confidence = DEFAULT_CONFIDENCE

        # formato CONF: 0.73
        m = re.search(r"\bCONF(?:IDENCE)?\s*[:=]\s*([01](?:\.\d+)?|\d{1,3})\b", raw_up)
        if m:
            confidence = _safe_float(m.group(1), DEFAULT_CONFIDENCE)
        else:
            # formato 72%
            m = re.search(r"(\d{1,3})\s*%", raw_up)
            if m:
                confidence = _safe_float(m.group(1), DEFAULT_CONFIDENCE)

        if confidence > 1.0:
            confidence /= 100.0
        confidence = max(0.0, min(1.0, confidence))

        # =================================================
        # 4️⃣ TP / SL explícitos
        # =================================================
        tp = DEFAULT_TP
        sl = DEFAULT_SL

        m_tp = re.search(r"\bTP(?:_PIPS)?\s*[:=]\s*(-?\d+(?:\.\d+)?)", raw_up)
        m_sl = re.search(r"\bSL(?:_PIPS)?\s*[:=]\s*(-?\d+(?:\.\d+)?)", raw_up)

        if m_tp:
            tp = abs(_safe_float(m_tp.group(1), DEFAULT_TP))
        if m_sl:
            sl = abs(_safe_float(m_sl.group(1), DEFAULT_SL))

        # =================================================
        # 5️⃣ FALLBACK NUMÉRICO (último recurso)
        # =================================================
        if tp <= 0 or sl <= 0:
            nums = [
                abs(float(n)) for n in re.findall(r"\b\d+(?:\.\d+)?\b", raw_norm)
                if 0.5 <= float(n) <= 10000
            ]
            if tp <= 0 and len(nums) >= 1:
                tp = nums[0]
            if sl <= 0 and len(nums) >= 2:
                sl = nums[1]

        # =================================================
        # 6️⃣ CLAMP FINAL (NUNCA ZERO)
        # =================================================
        tp = max(1.0, tp)
        sl = max(1.0, sl)

        return decision, confidence, tp, sl


    # ---------- order sizing ----------
    def _calculate_volume(self, symbol: str, sl_pips: float) -> float:
        """
        Calcula volume de lotes considerando:
        - risco percentual da conta (via risk_manager se disponível)
        - SL em pips
        - overrides por variável de ambiente (PIP_VALUE, MIN_VOLUME, MAX_VOLUME, VOLUME_STEP)
        - ajustes via AI / Deep Q (se implementados)
        - normaliza entre MIN_VOLUME e MAX_VOLUME
        - arredonda para múltiplos de VOLUME_STEP (usa floor para não exceder)
        Retorna: volume em lotes (float)
        """
        import math, os
        
        if sl_pips is None:
            # tentativa rápida: usar env ou atributo
            try:
                sl_pips = float(os.getenv("DEFAULT_SL_PIPS", "10"))
            except Exception:
                sl_pips = 10.0
                
        # defaults configuráveis via env
        DEFAULT_VOLUME = float(os.getenv("DEFAULT_VOLUME", "0.01"))
        step = float(os.getenv("VOLUME_STEP", "0.01"))
        # pip value per lot estimate (permite override por símbolo: <SYMBOL>_PIP_VALUE)
        pip_value_est = float(os.getenv(f"{symbol}_PIP_VALUE", os.getenv("PIP_VALUE_EST", "1.0")))

        # MIN/MAX volume (ambiente ou atributos da classe)
        MIN_VOLUME = float(getattr(self, "MIN_VOLUME", float(os.getenv("MIN_VOLUME", "0.01"))))
        MAX_VOLUME = float(getattr(self, "MAX_VOLUME", float(os.getenv("MAX_VOLUME", "100.0"))))

        # --- obter saldo/equity com fallback ---
        balance = 1000.0
        try:
            # prefira mt5_comm se existir (interface pode variar)
            acct = None
            if hasattr(self, "mt5_comm") and getattr(self, "mt5_comm") is not None:
                try:
                    acct = getattr(self.mt5_comm, "get_account_info", lambda: None)()
                except Exception:
                    acct = None
            # fallback para self.mt5 (ex: MetaTrader5 wrapper)
            if acct is None and hasattr(self, "mt5") and getattr(self, "mt5") is not None:
                try:
                    acct = getattr(self.mt5, "get_account_info", lambda: None)()
                except Exception:
                    acct = None

            if acct:
                if isinstance(acct, dict):
                    balance = float(acct.get("balance", acct.get("equity", balance)))
                else:
                    balance = float(getattr(acct, "balance", getattr(acct, "equity", balance)))
        except Exception:
            # deixa balance como default
            pass

        # --- risco base (pct) ---
        risk_pct = float(os.getenv("DEFAULT_RISK_PCT", "0.005"))  # 0.5% por default
        try:
            if hasattr(self, "risk_manager") and callable(getattr(self.risk_manager, "get_risk_pct", None)):
                try:
                    maybe = self.risk_manager.get_risk_pct(symbol, balance)
                    # aceitar se for número válido
                    risk_pct = float(maybe) if maybe is not None else risk_pct
                except Exception as e:
                    self.logger.debug("%s: risk_manager.get_risk_pct erro: %s", symbol, e)
        except Exception:
            pass

        # risco em valor absoluto (never below 1.0)
        risk_amount = max(1.0, balance * float(max(0.0, risk_pct)))

        # --- cálculo do raw_vol ---
        raw_vol = DEFAULT_VOLUME
        try:
            sl_pips_val = float(sl_pips) if sl_pips is not None else 0.0
            if sl_pips_val > 0:
                # evita divisão por zero: pip_value_est permit override por SYMBOL_PIP_VALUE env
                pv = float(max(1e-9, pip_value_est))
                raw_vol = risk_amount / (sl_pips_val * pv)
            else:
                raw_vol = DEFAULT_VOLUME
        except Exception as e:
            self.logger.debug("%s: erro ao calcular raw_vol: %s", symbol, e)
            raw_vol = DEFAULT_VOLUME

        # --- ajuste por AI / Deep Q (se disponível) ---
        try:
            if hasattr(self, "ai") and callable(getattr(self.ai, "adjust_volume", None)):
                try:
                    adj = self.ai.adjust_volume(symbol, raw_vol, sl_pips_val)
                    if adj is not None and float(adj) > 0:
                        raw_vol = float(adj)
                except Exception as e:
                    self.logger.debug("%s: ai.adjust_volume falhou: %s", symbol, e)
            elif hasattr(self, "deep_q_strategy") and callable(getattr(self.deep_q_strategy, "adjust_volume", None)):
                try:
                    adj = self.deep_q_strategy.adjust_volume(symbol, raw_vol, sl_pips_val)
                    if adj is not None and float(adj) > 0:
                        raw_vol = float(adj)
                except Exception as e:
                    self.logger.debug("%s: deep_q_strategy.adjust_volume falhou: %s", symbol, e)
        except Exception:
            pass

        # --- limites por símbolo (env override possível) ---
        try:
            symbol_max = os.getenv(f"{symbol}_MAX_VOLUME")
            if symbol_max is not None:
                symbol_max_volume = float(symbol_max)
            else:
                symbol_max_volume = float(MAX_VOLUME)
        except Exception:
            symbol_max_volume = float(MAX_VOLUME)

        try:
            vol = max(MIN_VOLUME, min(raw_vol, symbol_max_volume))
        except Exception:
            vol = float(DEFAULT_VOLUME)

        # --- arredondamento seguro pelo step (usa floor para não ultrapassar) ---
        try:
            if step <= 0:
                step = 0.01
            # evitar problemas de precisão: usar margem pequena
            vol = math.floor((vol + 1e-12) / step) * step
            vol = max(MIN_VOLUME, vol)
        except Exception as e:
            self.logger.debug("%s: erro ao arredondar volume: %s", symbol, e)
            vol = float(MIN_VOLUME)

        # --- info de debug ---
        try:
            self.logger.debug(
                "%s | SL=%.2f pips | Balance=%.2f | RiskPct=%.4f | PipVal=%s | RawVol=%.6f | FinalVol=%.4f (step=%s)",
                symbol,
                sl_pips if sl_pips is not None else 0.0,
                balance,
                risk_pct,
                pip_value_est,
                raw_vol,
                vol,
                step,
            )
        except Exception:
            # ignore logging errors
            pass

        # retorno com precisão segura (mantém 2 casas decimais por compatibilidade)
        try:
            return float(round(vol, 2))
        except Exception:
            return float(vol)

    
    # dentro da classe TradingBot
    def init_deep_q_agent(self, retry: int = 5):
        """
        Inicializa o Deep Q Agent de forma robusta usando o ambiente real de trading.
        ⚠️ NÃO inicializar antes do MT5 estar pronto.
        retry: número de tentativas automáticas caso MT5 ainda não esteja conectado
        """
        import time
        import numpy as np
        attempt = 0

        while attempt < retry:
            attempt += 1
            try:
                # ----------------------------
                # Verifica MT5
                # ----------------------------
                connected = False
                comm = getattr(self, "mt5", None) or getattr(self, "mt5_comm", None)
                if comm is not None:
                    connected = bool(getattr(comm, "is_connected", lambda: True)())
                if not connected:
                    self.logger.warning("DeepQ: MT5 not ready yet.")
                    time.sleep(1.0)
                    continue


                # ----------------------------
                # Escolhe símbolo de teste
                # ----------------------------
                sample_symbol = getattr(self, "symbols", ["EURUSD"])[0]
                market_data = self.mt5.get_symbol_data(sample_symbol)
                account_info = self.mt5.get_account_info()

                # ----------------------------
                # Importa classes de Deep Q
                # ----------------------------
                from strategies.deep_q_learning import TradingEnv, DQNAgent, TradeDirection

                # ----------------------------
                # Cria ambiente seguro
                # ----------------------------
                env = TradingEnv(market_data=market_data, account_info=account_info)

                # ----------------------------
                # Inferência de state_size/action_size
                # ----------------------------
                state_size = 1
                action_size = 2

                if hasattr(env, "observation_space") and hasattr(env.observation_space, "shape"):
                    state_size = int(np.prod(env.observation_space.shape))
                elif hasattr(env, "state_size"):
                    state_size = int(env.state_size)

                if hasattr(env, "action_space") and hasattr(env.action_space, "n"):
                    action_size = int(env.action_space.n)
                elif hasattr(env, "action_size"):
                    action_size = int(env.action_size)

                # ----------------------------
                # Inicializa DQNAgent
                # ----------------------------
                self.deep_q_agent = DQNAgent(
                    state_size=state_size,
                    action_size=action_size,
                    env=env,
                    lr=1e-3,
                    gamma=0.99,
                    batch_size=64,
                    buffer_size=20_000,
                    tau=0.005,
                    prioritized=True,
                    symbol=sample_symbol,
                    timeframe=getattr(self, "timeframe", 15),
                    # Garantindo mapeamento seguro de TradeDirection
                    action_map={
                        0: TradeDirection.SELL,
                        1: TradeDirection.HOLD,
                        2: TradeDirection.BUY,
                    },
                )

                self.logger.info(
                    "DeepQ inicializado | state_size=%d | action_size=%d | framework=%s",
                    self.deep_q_agent.state_size,
                    self.deep_q_agent.action_size,
                    getattr(self.deep_q_agent, "framework", "unknown"),
                )
                return  # sucesso

            except Exception as e:
                self.logger.exception(
                    "Falha ao inicializar DeepQ (tentativa %d/%d): %s", attempt, retry, e
                )
                time.sleep(1.0)

        # fallback final
        self.logger.error("DeepQ Agent não pôde ser inicializado após %d tentativas", retry)
        self.deep_q_agent = None


    def process_and_maybe_send_signal(self, sig_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recebe item do buffer { 'source':..., 'symbol':..., 'signal': {...} }
        Normaliza e decide envio com fallback AI quick-confirm quando necessário.
        """
        try:
            # --- small local helpers (self-contained) ---
            def _local_sanitize(x):
                try:
                    return sanitize_for_json(x)
                except Exception:
                    try:
                        return str(x)
                    except Exception:
                        return "<unserializable>"

            def _local_safe_float(v, default=0.0):
                try:
                    if v is None:
                        return float(default)
                    if isinstance(v, str):
                        v = v.strip().replace(",", ".")
                        if v == "":
                            return float(default)
                    return float(v)
                except Exception:
                    return float(default)

            def _local_normalize_direction(raw) -> str:
                try:
                    if raw is None:
                        return "HOLD"
                    if isinstance(raw, (tuple, list)) and len(raw) >= 1:
                        raw = raw[0]
                    if isinstance(raw, str):
                        s = raw.strip().upper()
                        if s in ("BUY", "LONG", "B", "1", "LONG:"):
                            return "BUY"
                        if s in ("SELL", "SHORT", "S", "-1", "SHORT:"):
                            return "SELL"
                        return "HOLD"
                    # enum-like objects
                    name = getattr(raw, "name", None) or getattr(raw, "value", None)
                    if isinstance(name, str):
                        return _local_normalize_direction(name)
                except Exception:
                    pass
                return "HOLD"

            def _local_ensure_sl_tp_pips(raw) -> tuple[float, float]:
                """
                Retorna (sl_pips, tp_pips) — tenta extrair ou calcular a partir de price/stop.
                """
                try:
                    sl = raw.get("sl_pips", None)
                    if sl is None:
                        sl = raw.get("sl", None) or raw.get("stop_loss", None)
                    tp = raw.get("tp_pips", None)
                    if tp is None:
                        tp = raw.get("tp", None) or raw.get("take_profit", None)
                    slf = _local_safe_float(sl, 0.0)
                    tpf = _local_safe_float(tp, 0.0)
                    # if sl missing, attempt to compute from price and stop_loss
                    if slf <= 0.0:
                        price = raw.get("price") or raw.get("entry_price") or raw.get("open")
                        stop = raw.get("stop_loss") or raw.get("sl") or raw.get("stop")
                        try:
                            if price is not None and stop is not None:
                                price_f = float(price)
                                stop_f = float(stop)
                                # quick heuristic: if price > 1000 treat absolute diff, else pips-based (0.0001)
                                if price_f > 1000:
                                    slf = abs(price_f - stop_f)
                                else:
                                    slf = abs(price_f - stop_f) / 0.0001
                        except Exception:
                            slf = float(os.getenv("DEFAULT_SL_PIPS", "10"))
                    if tpf <= 0.0:
                        # if tp missing, default small TP = sl or 1 pip
                        default_tp = max(1.0, slf) if slf > 0.0 else float(os.getenv("DEFAULT_TP_PIPS", "1"))
                        tpf = float(os.getenv("DEFAULT_TP_PIPS", str(default_tp)))
                    return float(max(0.0, slf)), float(max(0.0, tpf))
                except Exception:
                    return float(os.getenv("DEFAULT_SL_PIPS", "10")), float(os.getenv("DEFAULT_TP_PIPS", "1"))

            # --- start main logic ---
            sym = sig_item.get("symbol")
            raw = sig_item.get("signal", {}) or {}
            if not sym or not raw:
                return {"result": "invalid_signal_format"}

            # defensive defaults for attributes that sometimes missing
            self.force_send = getattr(self, "force_send", False)
            self.min_confidence = getattr(self, "min_confidence", float(os.getenv("MIN_CONFIDENCE", "0.55")))
            # margin + timeout config (defaults if not present)
            self.ai_conf_margin = getattr(self, "ai_conf_margin", float(os.getenv("AI_CONF_MARGIN", "0.05")))
            self.ai_sync_timeout = getattr(self, "ai_sync_timeout", float(os.getenv("AI_SYNC_TIMEOUT", "3.0")))
            require_ai_confirmation = getattr(self, "require_ai_confirmation", False)  # opt-in behavior

            conf = _local_safe_float(raw.get("confidence", raw.get("conf", 0.0)), 0.0)
            decision = _local_normalize_direction(raw.get("decision") or raw.get("action") or raw.get("side") or "")
            if decision in ("LONG",):
                decision = "BUY"
            if decision in ("SHORT",):
                decision = "SELL"

            if decision not in ("BUY", "SELL"):
                self.logger.debug("Signal ignored (not BUY/SELL): %s", _local_sanitize(raw))
                return {"result": "invalid_action"}

            # ensure tp/sl pips
            sl_pips, tp_pips = _local_ensure_sl_tp_pips(raw)

            # ------------ Immediate accept path (force or high-confidence) ------------
            if self.force_send or conf >= self.min_confidence:
                self.logger.info(
                    "Signal accepted immediate (force=%s/conf=%.3f >= min_confidence=%.3f)",
                    self.force_send,
                    conf,
                    self.min_confidence,
                )
                # optional: require AI confirmation even for high-conf if flag set
                if require_ai_confirmation and getattr(self, "ai", None):
                    try:
                        fn = getattr(self.ai, "evaluate_signal", None) or getattr(self.ai, "vote_trade", None) or getattr(
                            self.ai, "assess_signal", None
                        )
                        if callable(fn):
                            fut = self._ai_executor.submit(lambda: fn({"symbol": sym, **raw}, timeout=self.ai_sync_timeout))
                            try:
                                res = fut.result(timeout=self.ai_sync_timeout + 0.5)
                            except Exception as e:
                                self.logger.debug("%s: AI quick confirm for high-conf failed/timeout: %s", sym, e)
                                res = None
                            if isinstance(res, dict):
                                new_conf = _local_safe_float(res.get("confidence", res.get("conf", conf)), conf)
                                approved = res.get("approved", None)
                                if not (approved is True or new_conf >= self.min_confidence or self.force_send):
                                    self.logger.info(
                                        "%s: AI rejected high-conf signal (approved=%s new_conf=%.3f). Rejecting.", sym, approved, new_conf
                                    )
                                    return {"result": "rejected_by_ai", "confidence": new_conf}
                                # else adopt new_conf
                                conf = new_conf
                    except Exception as e:
                        self.logger.debug("%s: Exception during AI quick confirm (high-conf): %s", sym, e)

                ai_like = {
                    "decision": decision,
                    "confidence": conf,
                    "tp_pips": float(tp_pips),
                    "sl_pips": float(sl_pips),
                    "raw_source": sig_item.get("source", "strategy"),
                }
                # pass through to execute_trade, but ensure execute_trade exists
                try:
                    if not hasattr(self, "execute_trade") or not callable(self.execute_trade):
                        return {"result": "execute_trade_missing"}
                    return self.execute_trade(sym, ai_like)
                except Exception as e:
                    self.logger.exception("execute_trade failed for %s: %s", sym, e)
                    return {"result": "error", "error": str(e)}

            # ------------ Low-confidence: try quick AI confirm ------------
            lower_bound = max(0.0, self.min_confidence - self.ai_conf_margin)
            if lower_bound <= conf < self.min_confidence and getattr(self, "ai", None):
                self.logger.info(
                    "%s: low-conf(%.3f) near threshold(%.3f). Trying quick AI confirm (timeout=%.2fs)",
                    sym,
                    conf,
                    self.min_confidence,
                    self.ai_sync_timeout,
                )
                try:
                    fn = getattr(self.ai, "evaluate_signal", None) or getattr(self.ai, "vote_trade", None) or getattr(
                        self.ai, "assess_signal", None
                    )
                    if callable(fn):
                        fut = self._ai_executor.submit(lambda: fn({"symbol": sym, **raw}, timeout=self.ai_sync_timeout))
                        try:
                            res = fut.result(timeout=self.ai_sync_timeout + 0.5)
                        except Exception as e:
                            self.logger.debug("%s: AI quick confirm failed/timeout: %s", sym, e)
                            res = None
                        if isinstance(res, dict):
                            approved = res.get("approved", None)
                            new_conf = _local_safe_float(res.get("confidence", res.get("conf", conf)), conf)
                            if approved is True or new_conf >= self.min_confidence or self.force_send:
                                self.logger.info("%s: AI quick-approved (new_conf=%.3f). Sending.", sym, new_conf)
                                ai_like = {
                                    "decision": decision,
                                    "confidence": new_conf,
                                    "tp_pips": _local_safe_float(res.get("tp_pips", res.get("tp", tp_pips)), tp_pips),
                                    "sl_pips": _local_safe_float(res.get("sl_pips", res.get("sl", sl_pips)), sl_pips),
                                    "raw_source": sig_item.get("source", "strategy"),
                                }
                                try:
                                    return self.execute_trade(sym, ai_like)
                                except Exception as e:
                                    self.logger.exception("execute_trade failed after AI approval for %s: %s", sym, e)
                                    return {"result": "error", "error": str(e)}
                            else:
                                self.logger.info("%s: AI quick did not approve (approved=%s new_conf=%.3f). Rejected.", sym, approved, new_conf)
                        else:
                            self.logger.debug("%s: AI quick returned non-dict: %s", sym, _local_sanitize(res))
                except Exception as e:
                    self.logger.debug("%s: Exception during AI quick confirm: %s", sym, e)

            # else: reject due to low confidence
            self.logger.info("%s: signal rejected (confidence %.3f < min %.3f)", sym, conf, self.min_confidence)
            return {"result": "low_confidence", "confidence": conf}

        except Exception as e:
            self.logger.exception("process_and_maybe_send_signal failed")
            return {"result": "error", "error": str(e)}
    # ---------- validate / enqueue (substituir) ----------
    def validate_signal(self, sig: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Valida formato de sinal aceitando:
        - {'symbol': 'EURUSD', 'signal': { ... }}
        - {'symbol': 'EURUSD', 'decision': 'BUY', 'confidence': 0.6, ...}
        Retorna (True, None) ou (False, reason).
        """
        if not sig or not isinstance(sig, dict):
            return False, "missing_or_invalid_payload"

        # suporte ambos: payload pode ser wrapper { 'symbol':..., 'signal': {...} }
        symbol = sig.get("symbol") or (sig.get("signal") or {}).get("symbol")
        # sinal real (pode estar em sig['signal'] ou no próprio dict)
        s = sig.get("signal") if "signal" in sig else sig

        if not symbol or not isinstance(symbol, str) or not symbol.strip():
            return False, "missing_symbol"

        # pega decisão/ação/side do sinal normalizado
        try:
            decision = _normalize_direction(
                s.get("decision") if isinstance(s, dict) else None
            ) if isinstance(s, dict) else _normalize_direction(None)
        except Exception:
            decision = "HOLD"

        if decision not in ("BUY", "SELL"):
            return False, "invalid_action"

        return True, None


    def enqueue_signal(self, sig: Dict[str, Any]) -> bool:
        ok, reason = self.validate_signal(sig)
        if not ok:
            self.logger.warning("Signal descartado ao enfileirar: %s motivo=%s", sanitize_for_json(sig), reason)
            return False
        try:
            # garante deque inicializado e thread-safe
            with self._signal_lock:
                if getattr(self, "_signal_buffer", None) is None:
                    from collections import deque
                    self._signal_buffer = deque(maxlen=MAX_SIGNAL_BUFFER)
                self._signal_buffer.append(sig)
            self.logger.info("Signal enfileirado: %s", sanitize_for_json(sig))
            return True
        except Exception as e:
            self.logger.exception("Falha ao enfileirar signal: %s", e)
            return False


    # ---------- helper / execute_trade (substituir bloco antigo) ----------
    def _map_side_to_mt5(self, side_str: Optional[str]) -> str:
        """
        Normaliza side para 'BUY'|'SELL'|'HOLD'.
        Se seu wrapper MT5 exigir constantes (ex: MetaTrader5.ORDER_TYPE_SELL),
        adapte este método para retornar o valor correspondente.
        """
        try:
            if side_str is None:
                return "HOLD"
            s = str(side_str).strip().upper()
            if s in ("BUY", "LONG", "B", "1"):
                return "BUY"
            if s in ("SELL", "SHORT", "S", "-1"):
                return "SELL"
        except Exception:
            pass
        return "HOLD"


    def execute_trade(self, symbol: str, ai_res: Dict[str, Any]) -> Dict[str, Any]:
        import time, os, math
        now = time.time()

        # config / defaults (forçar conversão para float desde o começo)
        min_trade_interval = float(getattr(self, "min_trade_interval", MIN_TRADE_INTERVAL))
        min_volume = float(getattr(self, "MIN_VOLUME", MIN_VOLUME))
        max_volume = float(getattr(self, "MAX_VOLUME", MAX_VOLUME))
        dry_run = bool(getattr(self, "dry_run", DRY_RUN))
        force_send = bool(getattr(self, "force_send", False))
        default_sl_pips = float(os.getenv("DEFAULT_SL_PIPS", "75"))
        default_tp_pips = float(os.getenv("DEFAULT_TP_PIPS", "150"))

        if not hasattr(self, "_last_trade_ts") or self._last_trade_ts is None:
            self._last_trade_ts = {}

        # decisions
        strategy_decision = (
            ai_res.get("strategy_decision")
            or ai_res.get("original_decision")
            or (getattr(self, "last_strategy_decision_for_symbol", {}) or {}).get(symbol, "HOLD")
        )
        strategy_decision = str(strategy_decision).strip().upper()
        if strategy_decision not in ("BUY", "SELL"):
            strategy_decision = "HOLD"

        # AI decision normalization (accept strings, enums, TradeDirection)
        ai_decision_raw = ai_res.get("decision") or ai_res.get("ai_decision") or ai_res.get("action")
        try:
            ai_td = _sanitize_dqn_output(ai_decision_raw)
        except Exception:
            ai_td = None
        try:
            if isinstance(ai_td, TradeDirection):
                ai_decision_str = ai_td.name.upper()
            else:
                ai_decision_str = str(ai_td or "").upper()
        except Exception:
            ai_decision_str = "HOLD"
        if ai_decision_str not in ("BUY", "SELL"):
            ai_decision_str = "HOLD"

        # Deep Q best-effort
        dq_decision_str = "HOLD"
        try:
            if getattr(self, "deep_q_strategy", None) and callable(getattr(self.deep_q_strategy, "predict", None)):
                raw = self.deep_q_strategy.predict(symbol)
                dq_td = _sanitize_dqn_output(raw)
                if isinstance(dq_td, TradeDirection):
                    dq_decision_str = dq_td.name.upper()
                else:
                    dq_decision_str = str(dq_td or "").upper()
                if dq_decision_str not in ("BUY", "SELL"):
                    dq_decision_str = "HOLD"
        except Exception as e:
            self.logger.debug("%s: Deep Q predict failed: %s", symbol, e)

        # combine: strategy -> AI override (if conf) -> DeepQ (fallback)
        decision = strategy_decision
        ai_conf = _safe_float(ai_res.get("confidence", ai_res.get("conf", 0.0)), 0.0)
        ai_min_conf = float(getattr(self, "ai_override_min_confidence", 0.30))  # 🔥 HARDCORE FIX: 0.65 → 0.30
        ai_failed = bool(ai_res.get("ai_failed", False))  # 🔥 HARDCORE FIX: detectar AI falhou

        # 🔥 HARDCORE FIX: Se AI falhou, priorizar estratégia
        if ai_failed:
            self.logger.warning("%s: AI falhou (ai_failed=True), usando estratégia: %s", symbol, strategy_decision)
            decision = strategy_decision
        elif ai_decision_str in ("BUY", "SELL") and ai_conf >= ai_min_conf:
            decision = ai_decision_str
            self.logger.info("%s: AI override ACTIVE -> %s (conf=%.2f)", symbol, decision, ai_conf)
        elif decision == "HOLD" and dq_decision_str in ("BUY", "SELL"):
            decision = dq_decision_str
            self.logger.info("%s: Deep Q override -> %s", symbol, decision)

        # anti-flapping
        last_entry = self._last_trade_ts.get(symbol, ("HOLD", 0.0))
        last_dec = last_entry[0] if isinstance(last_entry, (list, tuple)) and len(last_entry) > 0 else "HOLD"
        last_ts = float(last_entry[1]) if isinstance(last_entry, (list, tuple)) and len(last_entry) > 1 else float(last_entry or 0.0)
        if decision == last_dec and (now - last_ts) < float(min_trade_interval):
            self.logger.debug("%s: min_interval_not_reached (last=%s %.1fs ago)", symbol, last_dec, now - last_ts)
            return {"ok": False, "result": "min_interval_not_reached"}

        if decision not in ("BUY", "SELL"):
            # 🔥 HARDCORE FIX: Logging detalhado
            self.logger.info(
                "%s: HOLD decision | strategy=%s ai=%s(conf=%.2f,failed=%s) dq=%s",
                symbol, strategy_decision, ai_decision_str, ai_conf, ai_failed, dq_decision_str
            )
            return {"ok": False, "result": "hold", "reason": "all_decisions_hold"}

        # ---------- SL/TP extraction (mais robusto) ----------
        sl_pips = _safe_float(ai_res.get("sl_pips") or ai_res.get("sl") or ai_res.get("stop_loss"), default_sl_pips)
        tp_pips = _safe_float(ai_res.get("tp_pips") or ai_res.get("tp") or ai_res.get("take_profit"), default_tp_pips)
        # ensure reasonable defaults (nunca 0/1 por acidente)
        sl_pips = max(1.0, float(sl_pips))
        tp_pips = max(1.0, float(tp_pips))
        # bump unrealistically small ones
        if sl_pips <= 1.0:
            sl_pips = default_sl_pips
        if tp_pips <= 1.0:
            tp_pips = default_tp_pips

        # ---------- compute volume (pass sl_pips when possible) ----------
        try:
            volume = float(self._calculate_volume(symbol, sl_pips))
        except TypeError:
            try:
                volume = float(self._calculate_volume(symbol))
            except Exception:
                volume = float(getattr(self, "default_lot", min_volume))
        except Exception:
            volume = float(getattr(self, "default_lot", min_volume))

        # adjustments (risk / deep_q)
        try:
            if getattr(self, "risk_manager", None) and callable(getattr(self.risk_manager, "adjust_volume", None)):
                v = self.risk_manager.adjust_volume(symbol, volume)
                if v is not None:
                    volume = float(v)
        except Exception as e:
            self.logger.debug("%s: risk_manager.adjust_volume failed: %s", symbol, e)
        try:
            if getattr(self, "deep_q_strategy", None) and callable(getattr(self.deep_q_strategy, "adjust_volume", None)):
                v = self.deep_q_strategy.adjust_volume(symbol, volume)
                if v is not None:
                    volume = float(v)
        except Exception as e:
            self.logger.debug("%s: deep_q_strategy.adjust_volume failed: %s", symbol, e)

        # clamp and round (keep 2 decimals as compatibility)
        volume = max(min_volume, min(volume, max_volume))
        try:
            volume = round(float(volume), 2)
        except Exception:
            volume = float(volume)

        # ---------- DRY RUN ----------
        if dry_run:
            self.logger.info("[DRY_RUN] %s %s vol=%.2f TP=%s SL=%s (conf=%.2f)", symbol, decision, volume, tp_pips, sl_pips, ai_conf)
            self._last_trade_ts[symbol] = (decision, now)
            try:
                self._log_trade_attempt(symbol, decision, volume, tp_pips, sl_pips, ai_conf)
                self._log_trade_result(symbol, decision, volume, tp_pips, sl_pips, ai_conf, "dry_run")
            except Exception:
                pass
            return {"ok": True, "result": "dry_run", "symbol": symbol, "decision": decision, "volume": volume}

        # ---------- prepare send kwargs ----------
        send_kwargs = {
            "symbol": symbol,
            "side": decision,
            "volume": volume,
            "tp_pips": tp_pips,
            "sl_pips": sl_pips,
            "confidence": ai_conf,
            "force": bool(force_send),
            "comment": ai_res.get("raw_source", "strategy"),
        }

        # backend detection
        comm = getattr(self, "mt5_comm", None) or getattr(self, "mt5", None)
        if comm is None:
            self.logger.warning("%s: no MT5 communication backend available", symbol)
            return {"ok": False, "result": "no_mt5_comm"}

        # try multiple method names adaptively, convert side->order_type if needed
        res = None
        last_exc = None
        for method_name in ("place_trade", "send_order", "order_send", "send_order_request", "place_order", "execute_order"):
            fn = getattr(comm, method_name, None)
            if not callable(fn):
                continue
            try:
                try:
                    # attempt kwargs first
                    res = fn(**send_kwargs)
                except TypeError:
                    # if send_order expects order_type:int, try to translate
                    try:
                        # map side->order_type if mt5 constants available
                        if hasattr(mt5, "ORDER_TYPE_BUY") and hasattr(mt5, "ORDER_TYPE_SELL"):
                            order_type = mt5.ORDER_TYPE_BUY if decision == "BUY" else mt5.ORDER_TYPE_SELL
                            # try call common send signature
                            res = fn(symbol, order_type, send_kwargs["volume"], send_kwargs.get("sl_pips"), send_kwargs.get("tp_pips"))
                        else:
                            # try passing dict single arg
                            res = fn(send_kwargs)
                    except TypeError:
                        # try positional minimal (symbol, side, volume)
                        try:
                            res = fn(send_kwargs["symbol"], send_kwargs["side"], send_kwargs["volume"])
                        except Exception as e2:
                            raise e2
                # if call succeeded break
                break
            except Exception as e:
                last_exc = e
                self.logger.debug("%s: comm.%s failed: %s", symbol, method_name, e)

        if res is None and last_exc is not None:
            self.logger.exception("%s: all comm methods attempted and failed, last error: %s", symbol, last_exc)
            return {"ok": False, "result": "error", "error": str(last_exc)}

        # normalize result to dict for logging
        try:
            detail = sanitize_for_json(res)
        except Exception:
            detail = str(res)

        # determine accepted more robustly
        try:
            accepted = False
            if isinstance(res, dict):
                if "ok" in res:
                    accepted = bool(res.get("ok"))
                elif "retcode" in res:
                    rc = int(res.get("retcode") or 0)
                    # common success retcodes (MT5) heuristic
                    accepted = rc in (getattr(mt5, "TRADE_RETCODE_DONE", 10009), getattr(mt5, "TRADE_RETCODE_PLACED", 10004))
                else:
                    # fallback: presence of ticket/order id
                    accepted = any(k in res for k in ("order", "ticket", "deal", "result"))
            else:
                # non-dict (e.g., object/tuple), accept if truthy
                accepted = bool(res)
        except Exception:
            accepted = True

        self._last_trade_ts[symbol] = (decision, now)
        try:
            result_tag = "accepted" if accepted else "rejected"
            self._log_trade_attempt(symbol, decision, volume, tp_pips, sl_pips, ai_conf)
            self._log_trade_result(symbol, decision, volume, tp_pips, sl_pips, ai_conf, result_tag)
        except Exception:
            self.logger.debug("%s: failed writing trade CSV", symbol, exc_info=True)

        self.logger.info("%s: trade result = %s", symbol, detail)
        return {"ok": bool(accepted), "result": result_tag, "detail": detail}

    def _log_trade_attempt(self, symbol, decision, volume, tp_pips, sl_pips, conf):
        with self._csv_lock:
            with open(TRADE_HISTORY_CSV, 'a', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow([int(time.time()), symbol, decision, volume, tp_pips, sl_pips, conf, 'attempt'])

    def _log_trade_result(self, symbol, decision, volume, tp_pips, sl_pips, conf, result):
        with self._csv_lock:
            with open(TRADE_HISTORY_CSV, 'a', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow([int(time.time()), symbol, decision, volume, tp_pips, sl_pips, conf, result])

    # ---------- normalize strategy signal ----------
    def _normalize_strategy_signal(self, sig: Any) -> Optional[Dict[str, Any]]:
        """
        Normaliza o sinal da estratégia para formato padrão do bot.
        Garante que apenas sinais válidos (BUY/SELL) sejam retornados para MT5Communication.
        """
        if sig is None:
            return None

        try:
            # Se for dict
            if isinstance(sig, dict):
                action = str(sig.get('action') or sig.get('decision') or '').upper()
                if action in ('LONG',):
                    action = 'BUY'
                elif action in ('SHORT',):
                    action = 'SELL'

                if action not in ('BUY', 'SELL'):
                    # logger.debug(f"Sinal descartado (ação inválida): {sig}")
                    return None

                conf = _safe_float(sig.get('confidence', sig.get('conf', 0.0)))
                tp = _safe_float(sig.get('tp', sig.get('tp_pips', sig.get('take_profit', 0.0))))
                sl = _safe_float(sig.get('sl', sig.get('sl_pips', sig.get('stop_loss', 0.0))))

                return {
                    'raw': sig,
                    'decision': action,
                    'confidence': conf,
                    'tp_pips': tp,
                    'sl_pips': sl
                }

            # Se for objeto com atributos
            a = getattr(sig, 'action', None) or getattr(sig, 'decision', None)
            if not a:
                return None
            action = str(a).upper()
            if action in ('LONG',):
                action = 'BUY'
            elif action in ('SHORT',):
                action = 'SELL'

            if action not in ('BUY', 'SELL'):
                # logger.debug(f"Sinal descartado (ação inválida objeto): {sig}")
                return None

            conf = _safe_float(getattr(sig, 'confidence', None) or getattr(sig, 'conf', 0.0))
            tp = _safe_float(getattr(sig, 'tp', None) or getattr(sig, 'tp_pips', 0.0))
            sl = _safe_float(getattr(sig, 'sl', None) or getattr(sig, 'sl_pips', 0.0))

            return {
                'raw': sig,
                'decision': action,
                'confidence': conf,
                'tp_pips': tp,
                'sl_pips': sl
            }

        except Exception:
            # logger.exception(f"Erro ao normalizar sinal: {sig}")
            return None


    # ---------- run strategies (parallel) ----------
    def run_strategies_cycle(self):
        """
        Executa todas as strategies carregadas e coleta sinais normalizados.
        Melhorias:
        - aceita vários formatos de retorno (tuple, list, dict, single signal)
        - tolera self._signal_buffer sendo list ou deque
        - timeout/configurável e tratamento robusto de exceptions por future
        - logs mais informativos
        Retorna: número de sinais enfileirados neste ciclo.
        """
        import concurrent.futures as cf
        import os
        import time

        # timeouts configuráveis
        try:
            cycle_timeout = float(os.getenv("STRAT_CYCLE_TIMEOUT", "5.0"))
        except Exception:
            cycle_timeout = 5.0

        # garante strategies carregadas
        if not self._strategies_loaded:
            try:
                self.load_strategies()
            except Exception:
                self.logger.exception("load_strategies falhou")

        futures = []
        symbol_data_map = {}

        # Fetch de dados de mercado por símbolo (resiliente)
        for symbol in SYMBOLS:
            try:
                symbol_data_map[symbol] = self.mt5.get_symbol_data(symbol) if self.mt5 else None
            except Exception as e:
                self.logger.debug("Falha ao buscar dados para %s: %s", symbol, e)
                symbol_data_map[symbol] = None

        # Submete chamadas às strategies (cada uma roda em executor já criado)
        for strat in list(self.strategies or []):
            try:
                futures.append(self._strat_executor.submit(self._call_strategy, strat, symbol_data_map))
            except Exception as e:
                self.logger.exception("Falha ao submeter strategy %s: %s", getattr(strat, "__class__", type(strat)).__name__, e)

        # Deep Q se existir
        if getattr(self, "deep_q_strategy", None):
            try:
                futures.append(self._strat_executor.submit(self._call_deep_q, self.deep_q_strategy, symbol_data_map))
            except Exception as e:
                self.logger.exception("Falha ao submeter deep_q_strategy: %s", e)

        if not futures:
            self.logger.debug("Nenhuma strategy carregada ou executável")
            return 0

        # helper: append seguro ao buffer (suporta list e deque)
        def _append_to_signal_buffer(item: Dict[str, Any]) -> bool:
            try:
                with self._signal_lock:
                    buf = getattr(self, "_signal_buffer", None)
                    if buf is None:
                        # inicializa como deque por segurança
                        from collections import deque
                        self._signal_buffer = deque(maxlen=MAX_SIGNAL_BUFFER)
                        buf = self._signal_buffer

                    if len(buf) < MAX_SIGNAL_BUFFER:
                        # deque and list both have append()
                        buf.append(item)
                        return True
                    else:
                        return False
            except Exception as e:
                self.logger.debug("Erro ao enfileirar sinal: %s", e, exc_info=True)
                return False

        def _normalize_res_list(res_list):
            """
            Aceita vários formatos:
            - [(sym, sig), ...]
            - (sym, sig)
            - {'SYM': sig, ...}
            - [sig, sig2] where each sig may be tuple/dict
            - single signal dict
            Retorna lista de tuples (sym, signal)
            """
            out = []
            try:
                if res_list is None:
                    return out
                # single tuple-like (sym, sig)
                if isinstance(res_list, (tuple, list)) and len(res_list) == 2 and isinstance(res_list[0], str):
                    out.append((res_list[0], res_list[1]))
                    return out
                # dict mapping symbol->signal
                if isinstance(res_list, dict):
                    for k, v in res_list.items():
                        out.append((k, v))
                    return out
                # list of results: could be list of tuples or list of dicts or list of signals
                if isinstance(res_list, list):
                    for item in res_list:
                        if item is None:
                            continue
                        if isinstance(item, (tuple, list)) and len(item) >= 2 and isinstance(item[0], str):
                            out.append((item[0], item[1]))
                        elif isinstance(item, dict) and set(item.keys()) and all(isinstance(k, str) for k in item.keys()):
                            # dict likely mapping symbol->signal (or single-signal dict)
                            # if keys look like symbols, add them; otherwise treat as signal for all SYMBOLS?
                            # heuristic: if dict has 'decision' or 'confidence' consider it a single signal
                            if "decision" in item or "confidence" in item or "tp" in item or "tp_pips" in item:
                                # ambiguous: we don't know symbol -> skip here (caller may handle)
                                out.append((None, item))
                            else:
                                for k, v in item.items():
                                    out.append((k, v))
                        else:
                            # unknown element: skip or wrap
                            out.append((None, item))
                    return out
                # anything else (string, object) -> wrap as single raw
                out.append((None, res_list))
            except Exception:
                self.logger.debug("normalize_res_list crashed for %r", res_list, exc_info=True)
            return out

        processed_count = 0
        # process futures (with overall timeout). as_completed raises TimeoutError if not all done in cycle_timeout
        try:
            for fut in cf.as_completed(futures, timeout=cycle_timeout):
                try:
                    res_list = fut.result()
                except Exception as e:
                    # log exception from this future (if any)
                    try:
                        exc = fut.exception()
                    except Exception:
                        exc = e
                    self.logger.exception("Falha ao executar strategy future: %s", exc)
                    continue

                if not res_list:
                    continue

                pairs = _normalize_res_list(res_list)
                for sym, nsignal in pairs:
                    try:
                        # se strategy retornou sinal sem símbolo, ignorar ou tentar inferir (prefira ignorar)
                        if not sym:
                            self.logger.debug("Strategy retornou sinal sem símbolo (ignorando): %s", sanitize_for_json(nsignal))
                            continue

                        # normaliza nome do símbolo e verifica dados de mercado
                        sym_norm = str(sym).strip().upper()
                        if symbol_data_map.get(sym_norm) is None:
                            # tenta com variante original (case-sensitive)
                            if symbol_data_map.get(sym) is None:
                                self.logger.debug("Sem dados de mercado para %s — ignorando sinal", sym)
                                continue
                            else:
                                sym_norm = sym

                        # if signal is None or falsy skip
                        if not nsignal:
                            continue

                        item = {"source": "strategy", "symbol": sym_norm, "signal": nsignal}

                        if _append_to_signal_buffer(item):
                            processed_count += 1
                        else:
                            self.logger.warning("Buffer de sinais cheio — descartando novo sinal para %s", sym_norm)

                    except Exception:
                        self.logger.exception("Erro ao processar item de resultado de strategy")

        except cf.TimeoutError:
            # some futures didn't finish in time: process the ones that did, cancel rest
            self.logger.debug("run_strategies_cycle: timeout after %.2fs — processando apenas futures concluídas", cycle_timeout)
            # process completed futures and try to cancel others
            for fut in futures:
                if fut.done():
                    try:
                        res_list = fut.result()
                    except Exception as e:
                        self.logger.debug("Future done but failed: %s", e)
                        continue
                    pairs = _normalize_res_list(res_list)
                    for sym, nsignal in pairs:
                        try:
                            if not sym:
                                self.logger.debug("Strategy returned unnamed signal (ignoring): %s", sanitize_for_json(nsignal))
                                continue
                            sym_norm = str(sym).strip().upper()
                            if symbol_data_map.get(sym_norm) is None and symbol_data_map.get(sym) is None:
                                continue
                            item = {"source": "strategy", "symbol": sym_norm, "signal": nsignal}
                            if _append_to_signal_buffer(item):
                                processed_count += 1
                            else:
                                self.logger.warning("Buffer full while draining completed futures")
                        except Exception:
                            self.logger.exception("Erro ao processar item (timeout branch)")
                else:
                    try:
                        fut.cancel()
                    except Exception:
                        pass

        # log resumo
        try:
            buf_len = len(getattr(self, "_signal_buffer", []))
        except Exception:
            buf_len = -1
        
        # 🔥 HARDCORE FIX: Logar quais estratégias foram executadas
        executed_strategies = [getattr(s, "__name__", s.__class__.__name__) for s in (self.strategies or [])]
        self.logger.info(
            "run_strategies_cycle concluído — %d sinais enfileirados | buffer_total=%s | estratégias_executadas=%s",
            processed_count, buf_len, executed_strategies
        )

        return processed_count


    def _call_strategy(self, strat, symbol_data_map: Dict[str, Any]):
        """
        Robust strategy caller (PRODUCTION SAFE):

        - aceita function, instance ou class
        - ignora automaticamente engines / backtests
        - suporta sync / async
        - timeout real por chamada
        - NUNCA quebra o ciclo principal
        - normaliza sempre para (symbol, normalized_signal)
        """
        import inspect
        import asyncio
        import concurrent.futures
        import os

        results: list[tuple[str, dict]] = []

        # -------------------------------
        # STRATEGY NAME (100% seguro)
        # -------------------------------
        strat_name = getattr(strat, "__name__", strat.__class__.__name__)

        # -------------------------------
        # BLOQUEIO FORTE DE BACKTEST / ENGINES
        # -------------------------------
        # 🔥 HARDCORE FIX: Whitelist de estratégias conhecidas
        KNOWN_LIVE_STRATEGIES = {
            "supertrendstrategy", "emacrossoverstrategy", "rsistrategy",
            "bollingerstrategy", "ictstrategy", "adaptivemlstrategy",
            "buylowsellhighstrategy", "deepqlearningstrategy"
        }
        
        strat_name_lower = strat_name.lower()
        
        # Permitir estratégias conhecidas
        if any(known in strat_name_lower for known in KNOWN_LIVE_STRATEGIES):
            self.logger.debug("✅ Executing known strategy: %s", strat_name)
            # Continue execution
        elif (
            hasattr(strat, "strategies")
            or hasattr(strat, "run_backtest")
            or strat_name_lower.startswith(("backtest", "engine"))
        ):
            self.logger.debug("⏭️ Skipping non-live strategy: %s", strat_name)
            return results

        # -------------------------------
        # TIMEOUT
        # -------------------------------
        try:
            timeout = float(
                getattr(self, "strategy_call_timeout", os.getenv("STRAT_CALL_TIMEOUT", "2.0"))
            )
        except Exception:
            timeout = 2.0

        # -------------------------------
        # EXECUTOR (sync + async)
        # -------------------------------
        def _execute(fn, *args):
            try:
                if inspect.iscoroutinefunction(fn):
                    return asyncio.run(fn(*args))
                return fn(*args)
            except TypeError:
                # fallback: apenas data
                if len(args) >= 1:
                    return fn(args[0])
                raise

        def _execute_with_timeout(fn, *args):
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exe:
                    future = exe.submit(_execute, fn, *args)
                    return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise
            except Exception as e:
                raise e

        # -------------------------------
        # NORMALIZA RETORNO
        # -------------------------------
        def _normalize(symbol: str, raw):
            if raw is None:
                return None

            # dict direto
            if isinstance(raw, dict):
                norm = self._normalize_strategy_signal(raw)
                return (symbol, norm) if norm else None

            # lista / múltiplos sinais
            if isinstance(raw, (list, tuple)):
                out = []
                for item in raw:
                    try:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            norm = self._normalize_strategy_signal(item[1])
                            if norm:
                                out.append((item[0], norm))
                        else:
                            norm = self._normalize_strategy_signal(item)
                            if norm:
                                out.append((symbol, norm))
                    except Exception:
                        continue
                return out if out else None

            # texto (IA / LLM)
            if isinstance(raw, str) and callable(getattr(self, "_parse_response_full", None)):
                try:
                    d, c, tp, sl = self._parse_response_full(raw)
                    payload = {
                        "decision": d,
                        "confidence": c,
                        "tp_pips": tp,
                        "sl_pips": sl,
                        "raw_text": raw,
                    }
                    norm = self._normalize_strategy_signal(payload)
                    return (symbol, norm) if norm else None
                except Exception:
                    return None

            return None

        # -------------------------------
        # RESOLVE STRATEGY (class → instance)
        # -------------------------------
        try:
            if inspect.isclass(strat):
                try:
                    strat = strat()
                except Exception:
                    strat = strat(ai_manager=getattr(self, "ai", None))
        except Exception:
            self.logger.debug("Failed to instantiate strategy %s", strat_name, exc_info=True)
            return results

        # -------------------------------
        # MÉTODOS ACEITOS (ORDEM IMPORTA)
        # -------------------------------
        method_candidates = (
            "generate_signal",
            "next_signal",
            "signal",
            "step",
            "__call__",
        )

        # -------------------------------
        # LOOP POR SÍMBOLO
        # -------------------------------
        for symbol, data in symbol_data_map.items():
            if data is None:
                continue

            for method_name in method_candidates:
                fn = getattr(strat, method_name, None)
                if not callable(fn):
                    continue

                try:
                    # 🔥 REAL FIX: Logging detalhado
                    self.logger.debug(f"{symbol}: Calling {strat_name}.{method_name}()")
                    
                    # tenta (data, symbol) → fallback para (data)
                    try:
                        raw = _execute_with_timeout(fn, data, symbol)
                    except TypeError as e:
                        self.logger.debug(f"{symbol}: {strat_name}.{method_name}(data, symbol) failed: {e}, trying (data) only")
                        raw = _execute_with_timeout(fn, data)

                    # 🔥 REAL FIX: Logar resultado bruto
                    if raw is None:
                        self.logger.debug(f"{symbol}: {strat_name}.{method_name}() returned None")
                        break
                    else:
                        self.logger.debug(f"{symbol}: {strat_name}.{method_name}() returned: {type(raw).__name__}")

                    normalized = _normalize(symbol, raw)
                    if not normalized:
                        self.logger.debug(f"{symbol}: {strat_name}.{method_name}() normalization failed")
                        break

                    if isinstance(normalized, list):
                        results.extend(normalized)
                    else:
                        results.append(normalized)

                    break  # sucesso → não testa outros métodos

                except concurrent.futures.TimeoutError:
                    self.logger.warning(
                        "Strategy %s.%s timeout (%ss) for %s",
                        strat_name, method_name, timeout, symbol
                    )
                    break

                except Exception as e:
                    self.logger.debug(
                        "Strategy %s.%s error for %s: %s",
                        strat_name, method_name, symbol, e,
                        exc_info=True
                    )
                    break

        return results




    def _call_deep_q(self, dq, symbol_data_map: Dict[str, Any]):
        """
        Chama o módulo Deep Q para todos os símbolos, normaliza sinais e registra logs detalhados.
        Retorna lista de tuplas (symbol, normalized_signal).
        """
        out = []

        if not dq or not hasattr(dq, "predict") or not callable(dq.predict):
            self.logger.debug("DeepQ não disponível ou método predict ausente")
            return out

        def _safe_predict(symbol, data):
            """
            Tenta chamar dq.predict com diferentes assinaturas, retorna None se todas falharem.
            """
            for args in [(data,), (symbol, data), (data, symbol), ()]:
                try:
                    return dq.predict(*args)
                except TypeError:
                    continue
                except Exception as e:
                    self.logger.debug("DeepQ predict exception for %s with args %s: %s", symbol, args, e)
            return None

        for symbol, data in symbol_data_map.items():
            if data is None:
                self.logger.debug("Sem dados de mercado para %s — pulando DeepQ", symbol)
                continue

            try:
                res = _safe_predict(symbol, data)
                if not res:
                    continue

                norm = None

                # ---------- Caso res seja dict ----------
                if isinstance(res, dict):
                    action = res.get("decision") or res.get("action") or res.get("signal")
                    if not action:
                        continue
                    action = str(action).upper()
                    if action == "LONG":
                        action = "BUY"
                    elif action == "SHORT":
                        action = "SELL"
                    if action not in ("BUY", "SELL"):
                        continue

                    norm = {
                        "raw": res,
                        "decision": action,
                        "confidence": max(0.0, min(1.0, _safe_float(res.get("confidence", 0.0)))),
                        "tp_pips": max(1.0, _safe_float(res.get("tp_pips", res.get("tp", 1.0)))),
                        "sl_pips": max(1.0, _safe_float(res.get("sl_pips", res.get("sl", 1.0)))),
                    }

                # ---------- Caso res seja tuple/list ----------
                elif isinstance(res, (tuple, list)) and len(res) >= 1:
                    action = str(res[0]).upper()
                    if action == "LONG":
                        action = "BUY"
                    elif action == "SHORT":
                        action = "SELL"
                    if action not in ("BUY", "SELL"):
                        continue

                    norm = {
                        "raw": res,
                        "decision": action,
                        "confidence": max(0.0, min(1.0, _safe_float(res[1] if len(res) > 1 else 0.0))),
                        "tp_pips": max(1.0, _safe_float(res[2] if len(res) > 2 else 1.0)),
                        "sl_pips": max(1.0, _safe_float(res[3] if len(res) > 3 else 1.0)),
                    }

                if norm:
                    out.append((symbol, norm))
                    self.logger.debug(
                        "DeepQ sinal bufferizado | %s | %s conf=%.2f TP=%.2f SL=%.2f",
                        symbol, norm["decision"], norm["confidence"], norm["tp_pips"], norm["sl_pips"]
                    )

            except Exception:
                self.logger.exception("Falha no processamento DeepQ para %s", symbol)

        return out


    # ---------- PROCESS SIGNAL BUFFER ----------
    def process_signal_buffer(self):
        """
        Consume up to SIGNAL_PROCESS_BATCH signals from the internal buffer and process them.
        - Safe for buffer being deque or list or None.
        - Uses deque.popleft() (O(1)) when possible.
        - Supports configurable parallel processing via env SIGNAL_PROCESS_PARALLEL.
        - Applies per-signal timeout (env SIGNAL_PROCESS_TIMEOUT).
        - Re-queues transiently failing signals up to SIGNAL_RETRY_COUNT times.
        - Always thread-safe around the shared buffer.
        - Logs summary and per-item details (sanitized).
        """
        import os
        import time
        import concurrent.futures
        from collections import deque

        # config
        batch_max = int(os.getenv("SIGNAL_PROCESS_BATCH", str(SIGNAL_PROCESS_BATCH)))
        timeout = float(os.getenv("SIGNAL_PROCESS_TIMEOUT", "5.0"))
        parallel = os.getenv("SIGNAL_PROCESS_PARALLEL", "0").lower() in ("1", "true", "yes")
        max_workers = int(os.getenv("SIGNAL_PROCESS_WORKERS", "4"))
        retry_limit = int(os.getenv("SIGNAL_RETRY_COUNT", "2"))
        requeue_front = os.getenv("SIGNAL_REQUEUE_FRONT", "0").lower() in ("1", "true", "yes")
        start_ts = time.time()

        # defensive: ensure buffer exists and is deque-backed for efficient popleft
        with self._signal_lock:
            if getattr(self, "_signal_buffer", None) is None:
                # initialize empty deque if missing
                self._signal_buffer = deque(maxlen=MAX_SIGNAL_BUFFER)
            elif isinstance(self._signal_buffer, list):
                # convert list -> deque preserving order
                self._signal_buffer = deque(self._signal_buffer, maxlen=MAX_SIGNAL_BUFFER)
            elif not isinstance(self._signal_buffer, deque):
                # unknown type -> make a safe deque copy
                try:
                    self._signal_buffer = deque(self._signal_buffer, maxlen=MAX_SIGNAL_BUFFER)
                except Exception:
                    self._signal_buffer = deque(maxlen=MAX_SIGNAL_BUFFER)

            # pop up to batch_max items
            batch = []
            for _ in range(min(len(self._signal_buffer), batch_max)):
                try:
                    item = self._signal_buffer.popleft()
                except IndexError:
                    break
                except Exception as e:
                    self.logger.debug("process_signal_buffer: popleft error: %s", e, exc_info=True)
                    break
                # ensure item is a dict with minimal keys
                if not isinstance(item, dict):
                    try:
                        item = {"raw": item}
                    except Exception:
                        item = {"raw": str(item)}
                # track retries
                item.setdefault("_signal_retries", 0)
                batch.append(item)

        if not batch:
            # nothing to do
            return

        # worker for single item
        def _worker(item):
            sym = item.get("symbol", "<unknown>")
            try:
                # submit actual processing with timeout using a short-lived executor
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exec_one:
                    fut = exec_one.submit(self.process_and_maybe_send_signal, item)
                    try:
                        res = fut.result(timeout=timeout)
                        self.logger.info("Processed buffered signal for %s -> %s", sym, sanitize_for_json(res))
                        return {"ok": True, "result": res, "item": item}
                    except concurrent.futures.TimeoutError:
                        # treat as transient failure
                        self.logger.warning("Signal processing timeout for %s (timeout=%.2fs)", sym, timeout)
                        return {"ok": False, "error": "timeout", "item": item}
                    except Exception as e:
                        self.logger.exception("Signal processing raised for %s: %s", sym, e)
                        return {"ok": False, "error": str(e), "item": item}
            except Exception as e:
                # protect outer code from unexpected executor errors
                self.logger.exception("Internal worker exception for %s: %s", sym, e)
                return {"ok": False, "error": str(e), "item": item}

        results = []
        # choose parallel or sequential execution
        if parallel and len(batch) > 1:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(batch))) as pool:
                    futures = {pool.submit(_worker, it): it for it in batch}
                    for fut in concurrent.futures.as_completed(futures):
                        try:
                            results.append(fut.result())
                        except Exception as e:
                            self.logger.exception("process_signal_buffer parallel future exception: %s", e)
            except Exception as e:
                # fallback to sequential if pool creation fails
                self.logger.debug("Parallel signal processing failed, falling back to sequential: %s", e, exc_info=True)
                for it in batch:
                    results.append(_worker(it))
        else:
            for it in batch:
                results.append(_worker(it))

        # requeue transient failures with limited retries
        requeued = 0
        with self._signal_lock:
            for r in results:
                if not isinstance(r, dict):
                    continue
                ok = r.get("ok", False)
                item = r.get("item") or {}
                if ok:
                    continue
                # increment retry counter
                item["_signal_retries"] = int(item.get("_signal_retries", 0)) + 1
                if item["_signal_retries"] <= retry_limit:
                    try:
                        if requeue_front:
                            # requeue at front for higher priority
                            self._signal_buffer.appendleft(item)
                        else:
                            self._signal_buffer.append(item)
                        requeued += 1
                        self.logger.debug("Re-queued signal for %s (retry %d/%d)", item.get("symbol", "<unknown>"), item["_signal_retries"], retry_limit)
                    except Exception as e:
                        self.logger.debug("Failed to requeue signal %s: %s", sanitize_for_json(item), e, exc_info=True)
                else:
                    # give up after retries
                    self.logger.warning("Dropping signal for %s after %d retries", item.get("symbol", "<unknown>"), item["_signal_retries"])

        elapsed = time.time() - start_ts
        self.logger.debug("process_signal_buffer: processed=%d requeued=%d batch_size=%d elapsed=%.3fs",
                        len(results), requeued, len(batch), elapsed)

    # ---------- ask_model_with_retries (kept) ----------
    def ask_model_with_retries(self, symbol, data, retries: int = 2, external_signal=None) -> Dict[str, Any]:
        """
        Pergunta ao AIManager ou modelos conectados (LLAMA, DeepQ) sobre trade signals,
        com normalização completa e retries. Logs detalhados de falhas e fallback seguro.
        """
        last_exception = None
        ai_obj = getattr(self, "ai", None) or getattr(self, "ai_manager", None)
        if ai_obj is None:
            raise RuntimeError("AIManager not initialized")

        def _normalize_to_dict(res) -> Dict[str, Any]:
            DEFAULT = {"decision": "HOLD", "confidence": 0.5, "tp_pips": 1.0, "sl_pips": 1.0, "raw": res}
            try:
                if res is None:
                    return DEFAULT

                # dict
                if isinstance(res, dict):
                    dec = (res.get("decision") or res.get("action") or res.get("signal") or "").upper()
                    if dec in ("LONG",): dec = "BUY"
                    if dec in ("SHORT",): dec = "SELL"
                    if dec not in ("BUY","SELL","HOLD"): dec = "HOLD"
                    conf = _safe_float(res.get("confidence") or res.get("conf") or res.get("score") or 0.0, 0.0)
                    conf = max(0.0, min(1.0, conf if conf <= 1.0 else conf/100.0))
                    tp = max(0.0, _safe_float(res.get("tp") or res.get("tp_pips") or res.get("take_profit") or 0.0))
                    sl = max(0.0, _safe_float(res.get("sl") or res.get("sl_pips") or res.get("stop_loss") or 0.0))
                    if tp <= 0 or sl <= 0:
                        return DEFAULT
                    return {"decision": dec, "confidence": conf, "tp_pips": tp, "sl_pips": sl, "raw": res}

                # tuple/list
                if isinstance(res, (list, tuple)):
                    if len(res) >= 4:
                        dec = str(res[0]).upper()
                        if dec in ("LONG",): dec = "BUY"
                        if dec in ("SHORT",): dec = "SELL"
                        if dec not in ("BUY","SELL"): return DEFAULT
                        conf = max(0.0, min(1.0, _safe_float(res[1],0.0)))
                        tp = max(0.0, _safe_float(res[2],0.0))
                        sl = max(0.0, _safe_float(res[3],0.0))
                        if tp <= 0 or sl <= 0:
                            return DEFAULT
                        return {"decision": dec, "confidence": conf, "tp_pips": tp, "sl_pips": sl, "raw": res}
                    if len(res) == 1 and isinstance(res[0], str):
                        dec, conf, tp, sl = self._parse_response_full(res[0])
                        return {"decision": dec, "confidence": conf, "tp_pips": tp, "sl_pips": sl, "raw": res}

                # string
                if isinstance(res, str):
                    dec, conf, tp, sl = self._parse_response_full(res)
                    return {"decision": dec, "confidence": conf, "tp_pips": tp, "sl_pips": sl, "raw": res}

            except Exception as e:
                self.logger.debug("Normalization failed: %s", e)

            return DEFAULT

        for attempt in range(retries + 1):
            try:
                self.logger.debug("AI call attempt %d for %s", attempt, symbol)

                # vote_trade
                if callable(getattr(ai_obj, "vote_trade", None)):
                    try:
                        # 'item' é o dicionário do sinal que você está processando no buffer
                        res = ai_obj.vote_trade(data, symbol=symbol, timeout=AI_TIMEOUT, external_signal=external_signal)
                    except TypeError:
                        res = ai_obj.vote_trade(data, timeout=AI_TIMEOUT)
                    ai_res = _normalize_to_dict(res)
                    self.logger.debug("AIManager vote_trade returned: %s", ai_res)
                    return ai_res

                # LLAMA
                if getattr(ai_obj, "llama", None) is not None and callable(getattr(ai_obj, "query_llama", None)):
                    try:
                        res = ai_obj.query_llama(symbol, data)
                        ai_res = _normalize_to_dict(res)
                        self.logger.debug("LLAMA returned: %s", ai_res)
                        return ai_res
                    except Exception as e:
                        last_exception = e
                        self.logger.warning("LLAMA query failed for %s: %s", symbol, e)

                # Deep Q
                if callable(getattr(ai_obj, "query_deep_q", None)):
                    try:
                        res = ai_obj.query_deep_q(symbol, data)
                        ai_res = _normalize_to_dict(res)
                        self.logger.debug("DeepQ returned: %s", ai_res)
                        return ai_res
                    except Exception as e:
                        last_exception = e
                        self.logger.warning("DeepQ query failed for %s: %s", symbol, e)

                raise RuntimeError("No AI method available")

            except Exception as e:
                last_exception = e
                self.logger.warning("AI call failed for %s, attempt %d: %s", symbol, attempt, e)
                time.sleep(min(0.5, 0.15 * (attempt + 1)))

        self.logger.error("All AI attempts failed for %s, last exception: %s", symbol, last_exception)
        raise last_exception

    # ---------- main loop ----------
    def run(self):
        logger.info(f"Bot starting | symbols={SYMBOLS} | dry_run={DRY_RUN}")

        # ---------- Inicialização MT5 ----------
        if not self.mt5 or not self.mt5.is_connected():
            try:
                self.init_mt5()
                account_info = self.mt5.get_account_info()  # retorna dicionário
                logger.info(f"MT5 initialized successfully | Account={account_info.get('login')} | Balance={account_info.get('balance')}")

            except Exception as e:
                logger.critical(f"Fatal error initializing MT5: {e}", exc_info=True)
                return

        # ---------- Inicialização AI ----------
        if not self.ai:
            try:
                self.init_ai()
                logger.info("AIManager initialized successfully")
            except Exception as e:
                logger.warning(f"AIManager initialization failed, continuing without AI: {e}", exc_info=True)
                self.ai = None

        # ---------- Inicialização do RiskManager ----------
        try:
            self.risk_manager = RiskManager(
                mt5_comm=self.mt5,
                ai_manager=self.ai
            )
            logger.info("RiskManager initialized successfully")
        except Exception as e:
            logger.exception("RiskManager initialization failed")
            self.risk_manager = None
 
        logger.info(f"Component status | MT5=ON | AI={'ON' if self.ai else 'OFF'} | RiskManager={'ON' if self.risk_manager else 'OFF'}")
        
        # trading_bot_core.py - where RiskManager is created (replace original call)
        try:
            if self.mt5_comm is None or self.ai is None:
                raise RuntimeError("Skipping RiskManager init: missing mt5_comm or ai_manager")
            self.risk_manager = RiskManager(mt5_comm=self.mt5_comm, ai_manager=self.ai)
        except Exception as e:
            self.logger.warning("RiskManager initialization skipped/failed: %s", e)
            self.risk_manager = None

        # ---------- Pré-carregamento de strategies ----------
        try:
            self.load_strategies()
            strategy_names = [s.__class__.__name__ for s in self.strategies]
            logger.info(f"{len(self.strategies)} strategies loaded: {strategy_names}")
        except Exception as e:
            logger.exception("Failed to load strategies", exc_info=True)
            self.strategies = []

        # ---------- Main loop ----------
        while self._running.is_set():
            cycle_start = time.time()
            try:
                # 1) Executar todas strategies -> buffer de sinais
                try:
                    self.run_strategies_cycle()
                except Exception as e:
                    logger.exception("run_strategies_cycle failed", exc_info=True)

                # 2) Processar sinais buffered
                try:
                    self.process_signal_buffer()
                except Exception as e:
                    logger.exception("process_signal_buffer failed", exc_info=True)

                # 3) Per-symbol AI fallback + trade execution (paralelo leve)
                if SYMBOLS:
                    with ThreadPoolExecutor(max_workers=len(SYMBOLS)) as exe:
                        futures = {exe.submit(self._process_symbol, sym): sym for sym in SYMBOLS}
                        for fut in as_completed(futures):
                            sym = futures[fut]
                            try:
                                fut.result()
                            except Exception as e:
                                logger.exception(f"{sym}: error in per-symbol thread", exc_info=True)

            except Exception:
                logger.exception("Main loop iteration failed", exc_info=True)

            # ---------- Sleep para manter intervalo ----------
            elapsed = time.time() - cycle_start
            sleep_time = max(0, LOOP_INTERVAL - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("Bot stopped gracefully")


    def _process_symbol(self, symbol: str):
        """
        🔥 REAL FIX: Processa um único símbolo: fetch de dados, extrai sinal do buffer, AI fallback e execução de trade.
        Rodável em ThreadPoolExecutor.
        """
        try:
            data = None
            try:
                data = self.mt5.get_symbol_data(symbol)
            except Exception as e:
                logger.warning(f"{symbol}: failed to fetch data from MT5: {e}")
                return

            if data is None or (hasattr(data, 'empty') and getattr(data, 'empty')):
                logger.debug(f"{symbol}: no market data")
                return

            # 🔥 REAL FIX: Extrair sinal do buffer para este símbolo
            external_signal = None
            try:
                with self._signal_lock:
                    buf = getattr(self, "_signal_buffer", [])
                    # Procurar último sinal para este símbolo
                    for item in reversed(buf):
                        if item.get("symbol") == symbol:
                            sig = item.get("signal")
                            if sig and isinstance(sig, dict):
                                external_signal = sig
                                logger.debug(f"{symbol}: Found signal in buffer: {external_signal.get('action')} conf={external_signal.get('confidence')}")
                                break
            except Exception as e:
                logger.debug(f"{symbol}: Failed to extract signal from buffer: {e}")

            # ---------- AI decision ----------
            ai_res = None
            if self.ai:
                try:
                    ai_res = self.ask_model_with_retries(symbol, data, retries=2, external_signal=external_signal)
                    logger.debug(f"{symbol}: AI decision={ai_res.get('decision')} conf={ai_res.get('confidence'):.2f} "
                                f"tp={ai_res.get('tp_pips')} sl={ai_res.get('sl_pips')}")
                except Exception as e:
                    logger.warning(f"{symbol}: AI call failed: {e}")
                    return

            # 🔥 REAL FIX: Adicionar strategy_decision ao ai_res
            if ai_res and external_signal:
                ai_res["strategy_decision"] = external_signal.get("action") or external_signal.get("decision") or "HOLD"
                logger.debug(f"{symbol}: Added strategy_decision={ai_res['strategy_decision']} to ai_res")

            # ---------- Executar trade ----------
            if ai_res:
                try:
                    trade_res = self.execute_trade(symbol, ai_res)
                    logger.info(f"{symbol}: trade result = {trade_res}")
                except Exception as e:
                    logger.warning(f"{symbol}: execute_trade failed: {e}")

        except Exception:
            logger.exception(f"{symbol}: unhandled exception in _process_symbol")



    # ---------- shutdown ----------
    def shutdown(self):
        self.logger.info("Shutdown requested")
        self._running.clear()

        try:
            if self.mt5:
                self.mt5.shutdown()
        except Exception:
            self.logger.exception("Error shutting down MT5")

        try:
            if getattr(self, 'ai', None) and hasattr(self.ai, 'close'):
                self.ai.close()
        except Exception:
            self.logger.exception("Error closing AI")

        try:
            if hasattr(self, '_ai_executor'):
                self._ai_executor.shutdown(wait=False)
        except Exception:
            self.logger.exception("Error shutting down AI executor")

        try:
            if hasattr(self, '_strat_executor'):
                self._strat_executor.shutdown(wait=False)
        except Exception:
            self.logger.exception("Error shutting down strategy executor")

# ---------- Dashboard integration disabled ----------

# Apenas placeholders, nada será iniciado
logger = logging.getLogger("TradingBot")
_bot_instance = None

def start_dashboard_thread(*args, **kwargs):
    """Dashboard desativado temporariamente."""
    logger.info("Dashboard temporariamente desativado")
    return None

def inject_bot_instance(bot):
    """Dashboard desativado, apenas salva referência."""
    global _bot_instance
    _bot_instance = bot
    return True

def get_injected_bot_instance():
    return _bot_instance

# ---------- Signal handling continua igual ----------
def _register_signal_handlers(bot):
    import signal

    def _handler(sig, _):
        try:
            bot.logger.info("Signal %s received — shutting down", sig)
        except Exception:
            pass
        try:
            bot.shutdown()
        except Exception:
            logger.exception("Error during shutdown")

    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
    except Exception:
        logger.debug("Signal handlers not supported on this platform")

# ====================================================
# ENTRYPOINT
# ====================================================
if __name__ == "__main__":
    # --- cria bot ---
    bot = TradingBot()

    # --- DESATIVAR DASHBOARD ---
    flask_app = None
    dashboard_thread = None
    # não chama start_dashboard_thread nem inject_bot_instance

    # --- signals ---
    _register_signal_handlers(bot)

    # --- run bot ---
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.logger.info("KeyboardInterrupt — shutting down")
        try:
            bot.shutdown()
        except Exception:
            bot.logger.exception("Error during shutdown")
    except Exception:
        bot.logger.exception("Unhandled exception in bot.run()")
        try:
            bot.shutdown()
        except Exception:
            bot.logger.exception("Error during shutdown")

