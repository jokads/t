# mt5_communication_improved.py
from __future__ import annotations

import os
import time
import json
import socket
import threading
from decimal import Decimal, ROUND_DOWN, InvalidOperation
import asyncio
import numpy as np
import math
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, Callable, List, Tuple

import pandas as pd
import MetaTrader5 as mt5
import websockets
from websockets import WebSocketServerProtocol

# aiohttp used for optional HTTP fallback endpoints
from aiohttp import web

from dotenv import load_dotenv

# simple local logger (replace by your utils.logger if you prefer)
import logging
log = logging.getLogger("mt5_comm")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    log.addHandler(h)
log.setLevel(logging.INFO)

load_dotenv()

# ENV / defaults
ACCOUNT = int(os.getenv("MT5_ACCOUNT", "0") or 0)
PASSWORD = os.getenv("MT5_PASSWORD", None)
SERVER = os.getenv("MT5_SERVER", None)

HOST_ENV = os.getenv("MT5_SOCKET_HOST", "127.0.0.1")
PORT_ENV = int(os.getenv("MT5_SOCKET_PORT", "9090") or 9090)
IN_MAX_VOLUME = 5.0

ORDER_DEVIATION = int(os.getenv("MT5_ORDER_DEVIATION", "10") or 10)
MAGIC_NUMBER = int(os.getenv("MT5_MAGIC_NUMBER", "123456") or 123456)
DEFAULT_VOLUME = float(os.getenv("MT5_DEFAULT_VOLUME", "0.01") or 0.01)
MAX_RETRIES = int(os.getenv("MT5_MAX_RETRIES", "3") or 3)
VOLUME_STEP = float(os.getenv("MT5_VOLUME_STEP", "0.01") or 0.01)

# rate limiting: min seconds between order proposals per client (by IP)
CLIENT_MIN_INTERVAL = float(os.getenv("MT5_CLIENT_MIN_INTERVAL", "0.2") or 0.2)

# optional auth token for clients
CLIENT_TOKEN = os.getenv("MT5_CLIENT_TOKEN", None)

# WebSocket options
WS_MAX_SIZE = int(os.getenv("MT5_WS_MAX_SIZE", "2000000").replace("_",""))
WS_PING_INTERVAL = float(os.getenv("MT5_WS_PING_INTERVAL", "20.0"))
WS_PING_TIMEOUT = float(os.getenv("MT5_WS_PING_TIMEOUT", "20.0"))

# HTTP fallback port (port + 1 by default)
HTTP_FALLBACK_ENABLED = os.getenv("MT5_HTTP_FALLBACK", "1") != "0"
HTTP_FALLBACK_PORT = int(os.getenv("MT5_HTTP_PORT", str(PORT_ENV + 1)))

def _find_free_port(host: str, start_port: int, max_tries: int = 50) -> int:
    for p in range(start_port, start_port + max_tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, p))
            s.close()
            return p
        except OSError:
            s.close()
            continue
    raise OSError(f"No free port in {host}:{start_port}-{start_port+max_tries}")

def _safe_json(obj):
    try:
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")
        if isinstance(obj, pd.Series):
            return obj.to_dict()
        if hasattr(obj, "_asdict"):
            return dict(obj._asdict())
        if isinstance(obj, (list, tuple)):
            return [_safe_json(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _safe_json(v) for k, v in obj.items()}
        # try json
        json.dumps(obj)
        return obj
    except Exception:
        try:
            return str(obj)
        except Exception:
            return None

class MT5Communication:
    """
    Robust MT5 <-> WebSocket/HTTP bridge with optional AIManager injection.
    """

    def __init__(self, host: str = HOST_ENV, port: int = PORT_ENV, ws_workers: int = 6, ai_manager: Optional[Any] = None, auto_start=True):
        self._mt5_lock = threading.RLock()
        self.connected = False
        self.host = host
        self.port_requested = port
        self.port = _find_free_port(host, port)
        if self.port != port:
            log.warning("Requested port %d busy -> using free port %d", port, self.port)


        # executor for blocking MT5 calls
        self._blocking_executor = ThreadPoolExecutor(max_workers=max(2, ws_workers))

        # websocket server control (async loop in separate thread)
        self._ws_thread_stop_evt = threading.Event()
        self._ws_thread = None
        self._ws_loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_server = None
        self._ws_started_evt = threading.Event()
        self._request_cache: Dict[str, Dict[str, Any]] = {}
        self._request_cache_lock = threading.RLock()
        self.log = log  # use self.log consistentemente
      
        self._metrics_lock = threading.RLock()
        self._client_lock = threading.RLock()

        # config: permite permitir trades quando AI não está presente (segurança: default False)
        self.allow_trades_without_ai = bool(os.getenv("MT5_ALLOW_WITHOUT_AI", "0") == "1")
        # HTTP fallback server (aiohttp)
        self._http_runner = None
        self._http_site = None

        # track last request time per client (rate limiting)
        self._client_last_ts: Dict[str, float] = {}

        # ai manager optional
        self.ai_manager = ai_manager

        # metrics
        self.metrics = {"ws_connections":0, "orders_placed":0, "orders_failed":0}

        # connect to MT5
        self._connect_mt5()

        # start ws thread
        self._start_websocket_thread()

    # ---------------- MT5 connect / util ----------------
    def _connect_mt5(self):
        """
        Conecta ao MT5 de forma segura, com retries e shutdown prévio.
        """
        with self._mt5_lock:
            retries = 0
            backoff = 2  # segundos

            # garante estado limpo: tenta fechar qualquer instância anterior
            try:
                mt5.shutdown()
            except Exception:
                pass

            while retries < MAX_RETRIES:
                try:
                    if ACCOUNT and ACCOUNT != 0:
                        ok = mt5.initialize(login=ACCOUNT, password=PASSWORD, server=SERVER)
                    else:
                        ok = mt5.initialize()

                    if ok:
                        self.connected = True
                        acct = mt5.account_info()
                        log.info("MT5 connected successfully | account_info available=%s", bool(acct))
                        return
                    else:
                        err = mt5.last_error()
                        log.warning("mt5.initialize failed %s, retry %d/%d", err, retries+1, MAX_RETRIES)
                except Exception as e:
                    log.exception("Exception initializing MT5 (attempt %d): %s", retries+1, e)

                retries += 1
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 10)  # backoff progressivo

            self.connected = False
            raise RuntimeError("Unable to initialize MT5 after maximum retries")

    def get_account_info(self) -> Dict[str, Any]:
        with self._mt5_lock:
            info = mt5.account_info()
        if not info:
            return {}
        try:
            return {
                "login": getattr(info, "login", None),
                "balance": float(getattr(info, "balance", 0.0)),
                "equity": float(getattr(info, "equity", 0.0)),
                "leverage": getattr(info, "leverage", None)
            }
        except Exception:
            return {"login": getattr(info, "login", None)}

    def get_symbol_data(self, symbol: str, timeframe=mt5.TIMEFRAME_M1, n: int = 100) -> pd.DataFrame:
        """
        Retorna dados OHLC do MT5 em DataFrame, com retries, thread-safe e normalização hardcore.
        """
        max_retries = 3
        backoff = 0.5

        for attempt in range(1, max_retries + 1):
            try:
                with self._mt5_lock:
                    info = mt5.symbol_info(symbol)
                    if not info:
                        log.warning(f"{symbol}: symbol_info unavailable")
                        return pd.DataFrame()

                    if not info.visible:
                        try:
                            mt5.symbol_select(symbol, True)
                            log.debug(f"{symbol}: symbol auto-selected")
                        except Exception as e:
                            log.warning(f"{symbol}: symbol_select failed: {e}")

                    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, int(n))
                
                if rates is None or len(rates) == 0:
                    log.warning(f"{symbol}: no rates returned (attempt {attempt})")
                    raise RuntimeError("No market data")

                df = pd.DataFrame(rates)
                if "time" in df.columns:
                    df["time"] = pd.to_datetime(df["time"], unit="s")
                
                # atributos extras de conveniência
                setattr(df, "symbol", symbol)
                setattr(df, "timeframe", timeframe)
                setattr(df, "last_time", df["time"].iloc[-1] if not df.empty else None)
                
                return df

            except Exception as e:
                log.debug(f"{symbol}: get_symbol_data attempt {attempt} failed: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)  # backoff progressivo

        # fallback hardcore: retorna DataFrame vazio mas com metadados
        df = pd.DataFrame()
        setattr(df, "symbol", symbol)
        setattr(df, "timeframe", timeframe)
        setattr(df, "last_time", None)
        return df

    def pips_to_price(self, symbol: str, pips: float, order_type: int, is_tp: bool) -> float:
        """
        Converte pips em preço para BUY/SELL e TP/SL, usando point e dígitos corretos.
        """
        with self._mt5_lock:
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)

        if not info or not tick:
            raise ValueError(f"{symbol}: symbol or tick unavailable")

        point = float(getattr(info, "point", 0.0))
        digits = int(getattr(info, "digits", 5))

        if order_type == mt5.ORDER_TYPE_BUY:
            base = float(tick.ask)
            price = base + pips * point if is_tp else base - pips * point
        elif order_type == mt5.ORDER_TYPE_SELL:
            base = float(tick.bid)
            price = base - pips * point if is_tp else base + pips * point
        else:
            raise ValueError(f"Unknown order_type: {order_type}")

        return round(price, digits)
    
    def get_open_positions(self):
        # exemplo usando MetaTrader5
        import MetaTrader5 as mt5
        positions = mt5.positions_get()
        return [p._asdict() for p in positions] if positions else []

    def send_order(
        self,
        symbol: str,
        order_type: int,
        volume: float = DEFAULT_VOLUME,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        sl_pips: Optional[float] = None,
        tp_pips: Optional[float] = None,
        source: str = "UNKNOWN",
        max_retries: int = 3,
        retry_backoff: float = 0.5
    ) -> Dict[str, Any]:
        """
        MT5 Order Sender — HARDCORE, safe & audited.
        Melhorias:
        - Normaliza volume de acordo com symbol_info (min/step/max)
        - Checa margem disponível (via self.get_account_info())
        - Ajusta SL/TP de acordo com trade_stops_level
        - Retries com backoff + jitter e candidate fillings
        - Audit em orders_audit.jsonl
        - Retorno padronizado
        """
        import time, json, datetime, random, math, logging
        self.log = getattr(self, "log", logging.getLogger("mt5_comm"))

        # safety defaults
        BASE_VOLUME = float(getattr(self, "base_volume", 0.01))
        GLOBAL_MAX_VOLUME = float(getattr(self, "max_volume", 0.1))
        ORDER_DEVIATION = int(getattr(self, "order_deviation", 20))
        MAGIC_NUMBER = int(getattr(self, "magic_number", 123456))
        DRY_RUN = bool(getattr(self, "dry_run", False))

        def _audit(entry: dict):
            try:
                with open("orders_audit.jsonl", "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
            except Exception:
                self.log.debug("audit write failed", exc_info=True)

        def _safe_json(obj):
            try:
                return json.loads(json.dumps(obj, default=str))
            except Exception:
                return str(obj)

        if order_type not in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL):
            return {"ok": False, "error": "invalid_order_type", "source": source}

        attempt = 0
        retry_backoff = float(retry_backoff or 0.5)
        candidate_fillings = [None]
        for fill_attr in ("ORDER_FILLING_IOC", "ORDER_FILLING_FOK"):
            if hasattr(mt5, fill_attr):
                candidate_fillings.append(getattr(mt5, fill_attr))

        while attempt < max_retries:
            attempt += 1
            try:
                with self._mt5_lock:
                    info = mt5.symbol_info(symbol)
                    tick = mt5.symbol_info_tick(symbol)

                if not info or not tick:
                    raise RuntimeError("symbol info / tick unavailable")

                # price (market)
                price = float(tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid)

                # convert pips -> price if given
                try:
                    if sl_pips is not None:
                        sl = self.pips_to_price(symbol, float(sl_pips), order_type, is_tp=False)
                    if tp_pips is not None:
                        tp = self.pips_to_price(symbol, float(tp_pips), order_type, is_tp=True)
                except Exception as e:
                    self.log.debug("pips_to_price failed, fallback: %s", e)

                # broker constraints
                vol_min = float(getattr(info, "volume_min", 0.01) or 0.01)
                vol_step = float(getattr(info, "volume_step", 0.01) or 0.01)
                vol_max = float(getattr(info, "volume_max", GLOBAL_MAX_VOLUME) or GLOBAL_MAX_VOLUME)

                # clamp incoming requested volume
                requested_vol = float(volume or BASE_VOLUME)
                if requested_vol <= 0:
                    requested_vol = BASE_VOLUME

                # attempt margin check / exposure adjustment if available
                try:
                    acct = getattr(self, "get_account_info", None)
                    if callable(acct):
                        acc = self.get_account_info()
                        balance = float(acc.get("balance", acc.get("equity", 0.0)) or 0.0)
                    else:
                        balance = 0.0
                except Exception:
                    balance = 0.0

                # compute a safe maximum from account if possible (example policy)
                # note: user can override policy by passing self.policy_max_volume
                policy_max = min(vol_max, GLOBAL_MAX_VOLUME)
                if balance and balance > 0:
                    # simple risk-cap example: 0.02% of balance per trade -> adjustable externally
                    risk_pct = getattr(self, "per_trade_risk_pct", 0.0002)
                    # estimate pip value -> fallback to env or 1.0
                    pip_val = float(getattr(self, "pip_value_est", 1.0))
                    # if sl provided, compute volume cap by risk
                    if sl is not None and price and pip_val:
                        sl_pips_est = abs((price - sl) / (getattr(info, "point", 1e-5)))
                        if sl_pips_est > 0:
                            risk_amount = max(1.0, balance * risk_pct)
                            vol_by_risk = risk_amount / max(1.0, sl_pips_est * pip_val)
                            policy_max = min(policy_max, vol_by_risk)
                # final raw vol before rounding
                raw_vol = min(requested_vol, policy_max)

                # normalize to step and min
                steps = math.floor(raw_vol / vol_step) if vol_step > 0 else int(raw_vol)
                if steps <= 0:
                    steps = 1
                # determina casas decimais a partir de vol_step
                dec_places = max(0, -int(Decimal(str(vol_step)).as_tuple().exponent)) if vol_step else 2
                normalized_vol = round(min(max(steps * vol_step, vol_min), vol_max), dec_places)


                # extra policy: if requested volume >> vol_max, log an audit event
                if requested_vol > vol_max:
                    self.log.warning("[VOLUME_VIOLATION] %s requested %.2f > vol_max %.2f", source, requested_vol, vol_max)
                    _audit({
                        "ts": datetime.datetime.utcnow().isoformat(),
                        "event": "volume_violation",
                        "symbol": symbol,
                        "requested_volume": requested_vol,
                        "forced_volume": normalized_vol,
                        "source": source
                    })

                # ---------- STOP LEVEL / MIN DIST ----------
                try:
                    stop_level = int(getattr(info, "trade_stops_level", 0) or 0)
                    point = float(getattr(info, "point", 0.00001) or 0.00001)
                    min_dist = stop_level * point
                    # adjust SL/TP if too close
                    if sl is not None and abs(price - sl) < min_dist:
                        sl = (price - min_dist) if order_type == mt5.ORDER_TYPE_BUY else (price + min_dist)
                    if tp is not None and abs(tp - price) < min_dist:
                        tp = (price + min_dist) if order_type == mt5.ORDER_TYPE_BUY else (price - min_dist)
                except Exception as e:
                    self.log.debug("stop level adjust failed: %s", e)

                # round SL/TP to digits
                digits = int(getattr(info, "digits", 5) or 5)
                try:
                    sl = round(float(sl), digits) if sl is not None else 0.0
                except Exception:
                    sl = 0.0
                try:
                    tp = round(float(tp), digits) if tp is not None else 0.0
                except Exception:
                    tp = 0.0

                # final volume to send
                vol_to_send = float(normalized_vol)

                self.log.info("[ORDER_PREP] %s %s price=%.8f vol=%.2f sl=%s tp=%s (req=%.2f, policy_max=%.2f)",
                            source,
                            symbol,
                            price,
                            vol_to_send,
                            sl or "None",
                            tp or "None",
                            requested_vol,
                            policy_max)

                # dry-run support
                if DRY_RUN:
                    _audit({
                        "ts": datetime.datetime.utcnow().isoformat(),
                        "event": "dry_run_order",
                        "symbol": symbol,
                        "type": "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL",
                        "volume": vol_to_send,
                        "price": price,
                        "sl": sl,
                        "tp": tp,
                        "source": source,
                    })
                    return {"ok": True, "dry_run": True, "volume": vol_to_send, "result": None}

                # ---------- SEND attempts with different filling policies ----------
                for fill in candidate_fillings:
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": vol_to_send,
                        "type": order_type,
                        "price": price,
                        "sl": sl,
                        "tp": tp,
                        "deviation": ORDER_DEVIATION,
                        "magic": MAGIC_NUMBER,
                        "comment": f"AI_TRADE:{source}"
                    }
                    if fill:
                        req["type_filling"] = fill

                    try:
                        with self._mt5_lock:
                            result = mt5.order_send(req)
                    except Exception as e:
                        self.log.debug("mt5.order_send exception: %s", e, exc_info=True)
                        result = None

                    # normalize result
                    retcode = getattr(result, "retcode", None) if result is not None else None

                    # success codes vary by platform; most common: TRADE_RETCODE_DONE / TRADE_RETCODE_PLACED
                    if retcode in (getattr(mt5, "TRADE_RETCODE_DONE", 10009), getattr(mt5, "TRADE_RETCODE_PLACED", 10004)):
                        _audit({
                            "ts": datetime.datetime.utcnow().isoformat(),
                            "event": "order_sent",
                            "symbol": symbol,
                            "type": "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL",
                            "volume": vol_to_send,
                            "price": price,
                            "sl": sl,
                            "tp": tp,
                            "result": _safe_json(result),
                            "source": source,
                            "attempt": attempt,
                            "filling": fill
                        })
                        self.log.info("ORDER OK %s %s vol=%.2f source=%s retcode=%s", symbol, "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL", vol_to_send, source, retcode)
                        return {"ok": True, "result": _safe_json(result), "volume": vol_to_send, "retcode": retcode}

                    # specific reject handling (insufficient margin, invalid volume, market closed...)
                    # many MT5 retcodes are negative or specific ints — include result for debugging
                    self.log.warning("order_send returned retcode=%s (attempt=%d, filling=%s) -> result=%s", retcode, attempt, fill, getattr(result, "comment", str(result)))
                    _audit({
                        "ts": datetime.datetime.utcnow().isoformat(),
                        "event": "order_failed",
                        "symbol": symbol,
                        "volume": vol_to_send,
                        "price": price,
                        "sl": sl,
                        "tp": tp,
                        "retcode": retcode,
                        "result": _safe_json(result),
                        "source": source,
                        "attempt": attempt,
                        "filling": fill
                    })

                # soft backoff jitter and retry
                sleep_time = min(retry_backoff * (2 ** (attempt - 1)) + random.random() * 0.1, 5.0)
                time.sleep(sleep_time)

            except Exception as e:
                self.log.exception("send_order exception (%s) attempt=%d", source, attempt)
                _audit({
                    "ts": datetime.datetime.utcnow().isoformat(),
                    "event": "send_exception",
                    "symbol": symbol,
                    "error": str(e),
                    "source": source,
                    "attempt": attempt
                })
                if attempt >= max_retries:
                    return {"ok": False, "error": str(e), "source": source}

        return {"ok": False, "error": "max_retries_exceeded", "source": source}

    def place_trade(
        self,
        symbol: str,
        side: str,
        volume: float = DEFAULT_VOLUME,
        tp_pips: Optional[float] = None,
        sl_pips: Optional[float] = None,
        tp: Optional[float] = None,
        sl: Optional[float] = None,
        source: str = "UNKNOWN",
        confidence: float = 0.0,
        uuid: Optional[str] = None,
        max_retries: int = 3,
        ask_strategies: bool = True,
        ask_ai: bool = True,
        approval_threshold: float = 0.5,
        timeout_per_validator: float = 1.0,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Advanced place_trade (corrigida/robusta).
        Veja comentários na PR/issue para justificar cada comportamento.
        """
        import time, json, datetime, logging, re
        from concurrent.futures import ThreadPoolExecutor, as_completed

        log = getattr(self, "log", logging.getLogger("mt5_comm"))
        audit_callable = getattr(self, "_audit", None)

        result_summary = {
            "ok": False,
            "reason": None,
            "uuid": uuid,
            "symbol": symbol,
            "side": side,
            "requested_volume": volume,
            "confidence": confidence,
            "validators": [],
            "approval": None,
            "final_send": None,
            "intent": None,
        }

        try:
            side_up = (side or "").strip().upper()
            if side_up == "LONG":
                side_up = "BUY"
            elif side_up == "SHORT":
                side_up = "SELL"

            if side_up not in ("BUY", "SELL"):
                return {"ok": False, "error": "invalid_side", "uuid": uuid}

            order_type = mt5.ORDER_TYPE_BUY if side_up == "BUY" else mt5.ORDER_TYPE_SELL

            def _f(x, d=0.0):
                try:
                    return float(x)
                except Exception:
                    return float(d)

            requested_vol = max(_f(volume, DEFAULT_VOLUME), DEFAULT_VOLUME)
            confidence = max(0.0, min(1.0, _f(confidence, 0.0)))

            intent = {
                "symbol": symbol,
                "side": side_up,
                "requested_volume": requested_vol,
                "tp_pips": None if tp_pips is None else _f(tp_pips),
                "sl_pips": None if sl_pips is None else _f(sl_pips),
                "tp_price": None if tp is None else _f(tp),
                "sl_price": None if sl is None else _f(sl),
                "source": source,
                "confidence": confidence,
                "uuid": uuid,
                "ts": datetime.datetime.utcnow().isoformat() + "Z",
            }
            result_summary["intent"] = intent

            if force:
                log.warning("[place_trade] FORCE enabled -> skipping validators for %s %s", symbol, side_up)

            # ---------- normalizer ----------
            def normalize_validator_res(res):
                """
                Normaliza resposta de validator.

                APPROVE semantics:
                - True => explicit approve
                - False => explicit reject
                - None => abstain / couldn't decide (HOLD-like)

                Retorna dict com keys: approve (True/False/None), confidence, reason, suggested_volume, tp_pips, sl_pips, tp_price, sl_price
                """
                out = {
                    "approve": None,
                    "confidence": 0.0,
                    "reason": "no_response",
                    "suggested_volume": None,
                    "tp_pips": None,
                    "sl_pips": None,
                    "tp_price": None,
                    "sl_price": None
                }
                try:
                    if res is None:
                        out["reason"] = "no_response"
                        out["approve"] = None
                        return out

                    # boolean -> explicit approve/reject
                    if isinstance(res, bool):
                        out["approve"] = bool(res)
                        out["confidence"] = 1.0 if res else 0.0
                        out["reason"] = "bool"
                        return out

                    # numeric -> confidence value (0..1 or 0..100)
                    if isinstance(res, (int, float)):
                        val = float(res)
                        # normalize if likely percent (e.g., >1.0)
                        if val > 1.0:
                            val = max(0.0, min(100.0, val)) / 100.0
                        out["confidence"] = min(1.0, max(0.0, val))
                        out["approve"] = out["confidence"] >= 0.5
                        out["reason"] = "numeric"
                        return out

                    # dict -> extract structured info
                    if isinstance(res, dict):
                        # explicit approve field preferred (but allow None)
                        if "approve" in res or "approved" in res:
                            raw_ap = res.get("approve", res.get("approved"))
                            # keep explicit False as explicit rejection
                            if raw_ap is None:
                                out["approve"] = None
                            else:
                                out["approve"] = bool(raw_ap)

                        # decision field
                        dec = (str(res.get("decision") or res.get("action") or "")).upper().strip()
                        if dec == "LONG":
                            dec = "BUY"
                        if dec == "SHORT":
                            dec = "SELL"

                        if dec:
                            if dec == "HOLD":
                                # HOLD is *abstenção* — não tratamos como veto automático
                                out["approve"] = None
                                out["reason"] = "hold_abstain"
                            elif dec in ("BUY", "SELL"):
                                if dec != side_up:
                                    # explicit conflict: validator says opposite side -> explicit reject
                                    out["approve"] = False
                                    out["reason"] = f"decision_conflict:{dec}"
                                else:
                                    # explicit match -> approve (unless explicitly overridden)
                                    # if approve already set to False by field, keep it; otherwise mark approve True
                                    if out["approve"] is not False:
                                        out["approve"] = True
                                        out["reason"] = "decision_match"

                        # confidence extraction (try various keys)
                        conf_candidate = res.get("confidence", res.get("conf", res.get("score", None)))
                        if conf_candidate is not None:
                            try:
                                c = float(conf_candidate)
                                if c > 1.0:
                                    c = max(0.0, min(100.0, c)) / 100.0
                                out["confidence"] = min(1.0, max(0.0, c))
                            except Exception:
                                out["confidence"] = 0.0

                        # suggested volume
                        if "suggested_volume" in res:
                            try:
                                out["suggested_volume"] = float(res.get("suggested_volume"))
                            except Exception:
                                out["suggested_volume"] = None

                        # TP/SL extraction (pips and price)
                        for k in ("tp_pips", "sl_pips", "tp", "sl", "tp_price", "sl_price"):
                            if k in res and res.get(k) is not None:
                                try:
                                    v = float(res.get(k))
                                    if k in ("tp_pips", "sl_pips"):
                                        out[k] = v
                                    else:
                                        # put price under *_price
                                        if k in ("tp", "sl"):
                                            out[k + "_price"] = v
                                        else:
                                            out[k] = v
                                except Exception:
                                    pass

                        # fallback reason
                        if out["approve"] is True and out["reason"] == "no_response":
                            out["reason"] = "explicit_approve_or_decision"
                        return out

                    # string heuristic
                    if isinstance(res, str):
                        s = res.upper().replace(",", ".")
                        # detect explicit buy/sell/hod
                        if "HOLD" in s or "NO TRADE" in s or "ABSTAIN" in s:
                            out["approve"] = None
                            out["reason"] = "hold_abstain"
                        elif "BUY" in s and side_up == "BUY":
                            out["approve"] = True
                            out["reason"] = "text_buy"
                        elif "SELL" in s and side_up == "SELL":
                            out["approve"] = True
                            out["reason"] = "text_sell"
                        # confidence percent
                        m = re.search(r"(\d{1,3})\s*%\b", s)
                        if m:
                            out["confidence"] = min(1.0, max(0.0, float(m.group(1)) / 100.0))
                        else:
                            m2 = re.search(r"CONF(?:IDENCE)?\s*[:=]\s*(0(?:\.\d+)?|1(?:\.0+)?|0?\.\d+)", s)
                            if m2:
                                try:
                                    out["confidence"] = min(1.0, max(0.0, float(m2.group(1))))
                                except Exception:
                                    pass
                        out["reason"] = out["reason"] if out["reason"] != "no_response" else "text_parse"
                        return out

                    return out
                except Exception as e:
                    out["reason"] = f"normalize_error:{e}"
                    out["approve"] = None
                    out["confidence"] = 0.0
                    return out

            validators = []

            # ------------------------------
            # 1) Strategy engine validators
            # ------------------------------
            strat_engine = getattr(self, "strategy_engine", None)
            if ask_strategies and strat_engine and not force:
                candidate_methods = ("validate_trade", "vote_trade", "assess_trade", "evaluate_signal", "run_strategies_on_intent")
                methods = [getattr(strat_engine, m) for m in candidate_methods if callable(getattr(strat_engine, m, None))]
                if methods:
                    with ThreadPoolExecutor(max_workers=min(4, len(methods))) as exe:
                        futures = {exe.submit(m, dict(intent)): getattr(m, "__name__", str(m)) for m in methods}
                        try:
                            for fut in as_completed(futures, timeout=max(0.5, timeout_per_validator * len(futures))):
                                name = futures[fut]
                                try:
                                    r = fut.result(timeout=0.01)
                                except Exception as e:
                                    r = {"error": str(e)}
                                norm = normalize_validator_res(r)
                                entry = {"type": "strategy", "name": name, "raw": r, **norm}
                                validators.append(entry)
                        except Exception:
                            # collect done futures
                            for fut, name in futures.items():
                                if fut.done():
                                    try:
                                        r = fut.result()
                                    except Exception as e:
                                        r = {"error": str(e)}
                                    norm = normalize_validator_res(r)
                                    entry = {"type": "strategy", "name": name, "raw": r, **norm}
                                    validators.append(entry)
                else:
                    log.debug("strategy_engine present but no validation methods found")

            # ------------------------------
            # 2) AI manager validator
            # ------------------------------
            ai_obj = getattr(self, "ai_manager", None) or getattr(self, "ai", None)
            ai_raw = None
            if ask_ai and ai_obj and not force:
                for method_name in ("vote_trade", "evaluate_signal", "request_trade_decision", "request"):
                    fn = getattr(ai_obj, method_name, None)
                    if callable(fn):
                        try:
                            try:
                                ai_raw = fn(intent, timeout=timeout_per_validator)
                            except TypeError:
                                ai_raw = fn(intent)
                        except Exception as e:
                            ai_raw = {"error": str(e)}
                        break
                norm = normalize_validator_res(ai_raw)
                validators.append({"type": "ai", "name": getattr(ai_obj, "__class__", type(ai_obj)).__name__, "raw": ai_raw, **norm})

            result_summary["validators"] = validators

            # ------------------------------
            # 3) Aggregate approvals (robust)
            # ------------------------------
            if force:
                approved = True
                approval_reason = "force"
            else:
                if not validators:
                    approved = True
                    approval_reason = "no_validators_default_allow"
                else:
                    # positive explicit approves
                    positive_votes = [v for v in validators if v.get("approve") is True and v.get("confidence", 0.0) > 0.0]
                    # explicit rejections (approve explicitly False) excluding hold_abstain
                    explicit_rejections = [v for v in validators if v.get("approve") is False and v.get("reason") != "hold_abstain"]
                    if positive_votes:
                        score = sum(v.get("confidence", 0.0) for v in positive_votes) / len(positive_votes)
                        approved = score >= approval_threshold
                        approval_reason = f"score={score:.3f},threshold={approval_threshold}"
                    else:
                        if explicit_rejections:
                            approved = False
                            approval_reason = f"explicit_rejection_votes_found,count={len(explicit_rejections)}"
                        else:
                            # only abstains / neutral responses -> allow original signal
                            approved = True
                            approval_reason = "only_abstain_votes_allow_original_signal"

            result_summary["approval"] = {"approved": bool(approved), "reason": approval_reason, "validators_count": len(validators)}

            # audit validators + intent
            try:
                audit_entry = {
                    "ts": datetime.datetime.utcnow().isoformat(),
                    "event": "place_trade_intent",
                    "intent": intent,
                    "validators": validators,
                    "approval": result_summary["approval"]
                }
                if callable(audit_callable):
                    try:
                        audit_callable(audit_entry)
                    except Exception:
                        log.debug("audit callable failed", exc_info=True)
                else:
                    try:
                        with open("trade_validators_audit.jsonl", "a", encoding="utf-8") as fh:
                            fh.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
                    except Exception:
                        log.debug("audit file write failed", exc_info=True)
            except Exception:
                log.debug("audit outer failed", exc_info=True)

            if not approved:
                log.info("Trade NOT approved for %s %s -> %s", symbol, side_up, result_summary["approval"])
                result_summary["reason"] = "not_approved"
                return {"ok": False, "error": "not_approved", "detail": result_summary}

            # ------------------------------
            # 4) build final tp/sl and volume (allow validators to suggest)
            # ------------------------------
            final_volume = requested_vol
            suggested_vols = [v.get("suggested_volume") for v in validators if v.get("suggested_volume")]
            if suggested_vols:
                try:
                    final_volume = min(requested_vol, float(min(suggested_vols)))
                except Exception:
                    pass

            final_tp_price = intent.get("tp_price")
            final_sl_price = intent.get("sl_price")
            final_tp_pips = intent.get("tp_pips")
            final_sl_pips = intent.get("sl_pips")

            for v in validators:
                if v.get("tp_price"):
                    final_tp_price = final_tp_price or v.get("tp_price")
                if v.get("sl_price"):
                    final_sl_price = final_sl_price or v.get("sl_price")
                if v.get("tp_pips"):
                    final_tp_pips = final_tp_pips or v.get("tp_pips")
                if v.get("sl_pips"):
                    final_sl_pips = final_sl_pips or v.get("sl_pips")

            def convert_pips_to_price_safe(symbol, pips, side_type):
                try:
                    if pips is None:
                        return None
                    if hasattr(self, "pips_to_price") and callable(getattr(self, "pips_to_price")):
                        return float(self.pips_to_price(symbol, float(pips), mt5.ORDER_TYPE_BUY if side_type == "BUY" else mt5.ORDER_TYPE_SELL, is_tp=(pips == final_tp_pips)))
                    info = mt5.symbol_info(symbol)
                    tick = mt5.symbol_info_tick(symbol)
                    if info and tick:
                        point = float(info.point or 0.00001)
                        base_price = float(tick.ask if side_up == "BUY" else tick.bid)
                        if side_up == "BUY":
                            return round(base_price + float(pips) * point, int(info.digits or 5))
                        else:
                            return round(base_price - float(pips) * point, int(info.digits or 5))
                except Exception:
                    return None

            send_kwargs = {}
            if final_tp_price is not None:
                send_kwargs["tp"] = final_tp_price
            elif final_tp_pips is not None:
                converted_tp = convert_pips_to_price_safe(symbol, final_tp_pips, side_up)
                if converted_tp:
                    send_kwargs["tp"] = converted_tp
                else:
                    send_kwargs["tp_pips"] = final_tp_pips

            if final_sl_price is not None:
                send_kwargs["sl"] = final_sl_price
            elif final_sl_pips is not None:
                converted_sl = convert_pips_to_price_safe(symbol, final_sl_pips, side_up)
                if converted_sl:
                    send_kwargs["sl"] = converted_sl
                else:
                    send_kwargs["sl_pips"] = final_sl_pips

            # call send_order
            send_res = self.send_order(
                symbol=symbol,
                order_type=order_type,
                volume=final_volume,
                tp_pips=send_kwargs.get("tp_pips"),
                sl_pips=send_kwargs.get("sl_pips"),
                tp=send_kwargs.get("tp"),
                sl=send_kwargs.get("sl"),
                source=source,
                max_retries=max_retries
            )

            result_summary["final_send"] = send_res

            if isinstance(send_res, dict):
                send_res.setdefault("audit", {})
                send_res["audit"].update({
                    "place_uuid": uuid,
                    "validators": validators,
                    "approval": result_summary["approval"],
                    "intent": intent
                })

            return send_res

        except Exception as e:
            log.exception("place_trade HARD FAIL %s (%s)", symbol, source)
            return {"ok": False, "error": "unexpected_error", "details": str(e), "uuid": uuid, "source": source}


    def symbol_info_tick(self, symbol: str):
        """Wrapper para mt5.symbol_info_tick (pode retornar None)."""
        try:
            with self._mt5_lock:
                return mt5.symbol_info_tick(symbol)
        except Exception:
            log.debug("symbol_info_tick wrapper failed for %s", symbol, exc_info=True)
            return None

    def get_tick(self, symbol: str) -> float:
        """Retorna preço de mercado aproximado (ask para BUY, bid para SELL não especificado)."""
        try:
            tick = self.symbol_info_tick(symbol)
            if not tick:
                return 0.0
            # retorna tuple (bid, ask) se quiser; por compatibilidade retorna ask
            try:
                return float(tick.ask)
            except Exception:
                # fallback
                return float(getattr(tick, "last", 0.0) or 0.0)
        except Exception:
            return 0.0

    # --- public adjust_sl_tp para ser chamado pela estratégia ---
    def adjust_sl_tp(
        self,
        symbol: str,
        direction_or_price: Any,
        sl: Optional[float],
        tp: Optional[float]
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Ajusta Stop Loss e Take Profit para obedecer regras do MT5.

        Interface flexível:
        - adjust_sl_tp(symbol, 'BUY'/'SELL', sl, tp)
        - adjust_sl_tp(symbol, price_float, sl, tp)

        Retorna: (sl_adj, tp_adj)
        """
        try:
            # ---------------- 1) Symbol info ----------------
            with self._mt5_lock:
                info = mt5.symbol_info(symbol)
            if not info or not info.point:
                log.error("adjust_sl_tp: symbol_info inválido para %s", symbol)
                return sl, tp

            point = float(info.point)
            min_stop_points = info.trade_stops_level or 10
            min_stop = min_stop_points * point

            # ---------------- 2) Tick / preço base ----------------
            tick = self.symbol_info_tick(symbol)
            price = None
            order_type = mt5.ORDER_TYPE_BUY

            if isinstance(direction_or_price, str):
                direction = direction_or_price.upper()
                if direction not in ("BUY", "SELL"):
                    log.error("adjust_sl_tp: direção inválida %s", direction)
                    return sl, tp

                if not tick:
                    log.error("adjust_sl_tp: tick indisponível para %s", symbol)
                    return sl, tp

                price = float(tick.ask if direction == "BUY" else tick.bid)
                order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

            else:
                try:
                    price = float(direction_or_price)
                except Exception:
                    log.error("adjust_sl_tp: preço inválido %s", direction_or_price)
                    return sl, tp

                # inferir direção via TP
                if tp is not None:
                    order_type = mt5.ORDER_TYPE_BUY if tp > price else mt5.ORDER_TYPE_SELL

            if price <= 0:
                log.error("adjust_sl_tp: preço base inválido (%s)", price)
                return sl, tp

            # ---------------- 3) Ajuste SL / TP ----------------
            sl_adj, tp_adj = sl, tp

            if order_type == mt5.ORDER_TYPE_BUY:
                if sl_adj is not None:
                    sl_adj = min(sl_adj, price - min_stop)
                if tp_adj is not None:
                    tp_adj = max(tp_adj, price + min_stop)
            else:  # SELL
                if sl_adj is not None:
                    sl_adj = max(sl_adj, price + min_stop)
                if tp_adj is not None:
                    tp_adj = min(tp_adj, price - min_stop)
            digits = int(getattr(info, "digits", 5) or 5)
            # ---------------- 4) Arredondamento por point ----------------
            def round_price(v: Optional[float]) -> Optional[float]:
                if v is None:
                    return None
                return round(v, digits) if v is not None else None

            sl_adj = round_price(sl_adj)
            tp_adj = round_price(tp_adj)

            # ---------------- 5) Hook interno opcional ----------------
            if hasattr(self, "_adjust_sl_tp") and callable(self._adjust_sl_tp):
                try:
                    sl_adj, tp_adj = self._adjust_sl_tp(symbol, price, sl_adj, tp_adj, order_type)
                except Exception:
                    log.debug("_adjust_sl_tp hook falhou", exc_info=True)

            return sl_adj, tp_adj

        except Exception as e:
            log.exception("adjust_sl_tp failed for %s: %s", symbol, e)
            return sl, tp
    
    def _is_market_open(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        return tick is not None


    def _normalize_volume(self, symbol: str, requested_volume: float) -> tuple[bool, float]:
        """
        Normaliza o volume solicitado para obedecer aos requisitos do broker.

        - Usa symbol_info (volume_min, volume_step, volume_max) se disponível
        - Aplica floor para steps (não arredonda para cima)
        - Aplica clamp global IN_MAX_VOLUME e DEFAULT_VOLUME
        - Retorna (ok: bool, normalized_volume: float)
        """
        try:
            # --------------------------
            # 1. Parse seguro do volume solicitado
            # --------------------------
            try:
                req = float(requested_volume)
                if req <= 0:
                    raise ValueError("Volume inválido")
            except Exception:
                req = float(DEFAULT_VOLUME)

            # --------------------------
            # 2. Fetch symbol_info sob lock
            # --------------------------
            info = None
            try:
                with self._mt5_lock:
                    info = mt5.symbol_info(symbol)
            except Exception:
                info = None

            # --------------------------
            # 3. Extrai min, step e max do symbol_info ou defaults
            # --------------------------
            min_vol = float(getattr(info, "volume_min", 0.01) or 0.01)
            step = float(getattr(info, "volume_step", VOLUME_STEP) or VOLUME_STEP or 0.01)
            max_vol = float(getattr(info, "volume_max", IN_MAX_VOLUME) or IN_MAX_VOLUME)

            # --------------------------
            # 4. Garantias defensivas
            # --------------------------
            min_vol = max(min_vol, 0.01)
            step = max(step, 0.01)
            max_vol = min(max_vol, IN_MAX_VOLUME)

            # --------------------------
            # 5. Clamp inicial do requested volume
            # --------------------------
            req = max(min_vol, min(req, max_vol))

            # --------------------------
            # 6. Normalização usando Decimal para precisão
            # --------------------------
            try:
                d_req = Decimal(str(req))
                d_step = Decimal(str(step))

                # Floor para múltiplos de step
                steps = (d_req / d_step).to_integral_value(rounding=ROUND_DOWN)
                steps = max(Decimal(1), steps)
                normalized_dec = steps * d_step

                # Clamp final
                normalized_dec = min(max(normalized_dec, Decimal(str(min_vol))), Decimal(str(max_vol)))
                normalized_dec = min(normalized_dec, Decimal(str(IN_MAX_VOLUME)))

                # Determina casas decimais baseado no step
                step_exp = -d_step.as_tuple().exponent if d_step.as_tuple().exponent < 0 else 0
                dec_places = min(max(int(step_exp), 0), 8)

                normalized = float(
                    normalized_dec.quantize(Decimal((0, (1,), -dec_places))) if dec_places > 0
                    else normalized_dec.quantize(Decimal(1))
                )

            except Exception:
                # Fallback seguro com math.floor
                steps = max(1, int(math.floor(req / step)))
                normalized = steps * step
                normalized = max(min_vol, min(normalized, IN_MAX_VOLUME))

            # --------------------------
            # 7. Round final (4 casas decimais padrão Forex)
            # --------------------------
            normalized = round(normalized, 4)

            # --------------------------
            # 8. Debug: log ajustes significativos
            # --------------------------
            if log.isEnabledFor(logging.DEBUG) and abs(normalized - req) > max(1e-6, 0.1 * req):
                log.debug(
                    "_normalize_volume adjusted significantly: symbol=%s requested=%s normalized=%s (min=%s step=%s max=%s IN_MAX=%s)",
                    symbol, requested_volume, normalized, min_vol, step, max_vol, IN_MAX_VOLUME
                )

            return True, normalized

        except Exception as e:
            log.exception("_normalize_volume unexpected error for %s: %s", symbol, e)
            return False, float(DEFAULT_VOLUME)

    def _extract_effective_volume_from_result(self, result: Dict[str, Any]) -> Optional[float]:
        """
        Tenta extrair o volume efetivo do resultado retornado por send_order/place_trade.
        Lida com estruturas: {'request': {...}}, {'result': {'request': {...}}}, resultado convertido via _safe_json, etc.
        """
        try:
            if not isinstance(result, dict):
                return None
            # check top-level keys
            for key in ("normalized_volume", "effective_volume", "volume"):
                if key in result and result[key] is not None:
                    try:
                        return float(result[key])
                    except Exception:
                        pass
            # check request object
            req = result.get("request") or result.get("result") or result.get("out")
            if isinstance(req, dict):
                for k in ("volume", "vol", "normalized_volume"):
                    if k in req and req[k] is not None:
                        try:
                            return float(req[k])
                        except Exception:
                            pass
            # nested deeper
            rr = result.get("result")
            if isinstance(rr, dict):
                rreq = rr.get("request") or rr.get("request_data")
                if isinstance(rreq, dict) and rreq.get("volume") is not None:
                    try:
                        return float(rreq.get("volume"))
                    except Exception:
                        pass
            return None
        except Exception:
            return None
    
    def _validate_stops(self, symbol, price, sl, tp):
        info = mt5.symbol_info(symbol)
        point = getattr(info, "point", 0.00001)
        min_distance = getattr(info, "trade_stops_level", 10) * point  # nível mínimo de stops
        if sl:
            if abs(price - sl) < min_distance:
                sl = price - min_distance if sl < price else price + min_distance
        if tp:
            if abs(price - tp) < min_distance:
                tp = price + min_distance if tp > price else price - min_distance
        return sl, tp

    def _process_signal_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa um payload de sinal completo de forma defensiva:
        1) chama engine de strategies (run_strategies_on_payload) — fallback se não existir
        2) passa pelo AIManager para aprovação/ajuste (_call_ai_on_signal ou fallback)
        3) normaliza & valida payload (volume, side, symbol, stops) via _normalize_volume
        4) executa o trade via place_trade/send_order de forma segura
        Retorna dict com o mesmo formato de self.place_trade / send_order (inclui campos de auditoria).
        """
        sig_uuid = None
        try:
            # sanity
            if not isinstance(payload, dict):
                log.error("[Signal] payload invalid type: %s", type(payload))
                return {"ok": False, "error": "invalid_payload_type"}

            sig_uuid = payload.get("uuid") or payload.get("id") or None

            # ---------------- 1) run strategies (defensivo) ----------------
            try:
                fn = getattr(self, "run_strategies_on_payload", None)
                if callable(fn):
                    signals = fn(payload)
                else:
                    # fallback: use payload as-is but normalize minimal keys
                    signals = payload.copy()
            except Exception as e:
                log.exception("[Signal] Strategy processing failed: %s", e)
                return {"ok": False, "error": "strategy_error", "details": str(e), "uuid": sig_uuid}

            # ensure signals is a dict
            if not isinstance(signals, dict):
                try:
                    # attempt to coerce (if list/tuple, take first dict or wrap)
                    if isinstance(signals, (list, tuple)) and signals:
                        first = signals[0]
                        signals = first if isinstance(first, dict) else {"signals": signals}
                    else:
                        signals = {"signals": signals}
                except Exception:
                    signals = {"signals": signals}

            # ---------------- 2) call AI manager (defensivo) ----------------
            try:
                # bypass if requested by incoming payload (explicit flag from WS)
                if payload.get("_bypass_ai") or signals.get("_bypass_ai") or signals.get("bypass_ai"):
                    ai_res = {"approved": True, "reason": "bypass_flag", "adjusted_payload": signals}
                else:
                    # prefer internal wrapper if present
                    if callable(getattr(self, "_call_ai_on_signal", None)):
                        ai_res = self._call_ai_on_signal(signals, timeout=2.0)
                    else:
                        # fallback: try to call ai_manager methods directly if available
                        ai_res = None
                        ai_obj = getattr(self, "ai_manager", None) or getattr(self, "ai", None)
                        if ai_obj:
                            for name in ("vote_trade", "evaluate_signal", "request_trade_decision", "request", "request_trade"):
                                fn = getattr(ai_obj, name, None)
                                if callable(fn):
                                    try:
                                        try:
                                            ai_res = fn(signals, timeout=2.0)
                                        except TypeError:
                                            ai_res = fn(signals)
                                    except Exception as e:
                                        ai_res = {"error": str(e)}
                                    break
                        # if no ai present, ai_res stays None (handled below)

                    # if no ai present, ai_res stays None (handled below)
            except Exception as e:
                log.exception("[Signal] AIManager call failed: %s", e)
                return {"ok": False, "error": "ai_error", "details": str(e), "uuid": sig_uuid}

            # make ai_res a normalized dict
            try:
                if ai_res is None:
                    # configurable: allow by default only if configured by env (use safe default False in prod)
                    default_approve = bool(getattr(self, "allow_trades_without_ai", False))
                    ai_res = {"approved": bool(default_approve), "reason": "no_ai", "adjusted_payload": signals}
                elif isinstance(ai_res, dict):
                    # keep as-is (we'll normalize below)
                    pass
                elif isinstance(ai_res, bool):
                    ai_res = {"approved": bool(ai_res), "adjusted_payload": signals}
                elif isinstance(ai_res, (int, float)):
                    conf = float(ai_res)
                    if conf > 1.0:
                        conf = conf / 100.0
                    ai_res = {"approved": conf >= 0.5, "confidence": conf, "adjusted_payload": signals}
                else:
                    # unknown type -> wrap
                    ai_res = {"approved": False, "reason": "ai_unknown_response_type", "raw": str(ai_res), "adjusted_payload": signals}
            except Exception:
                ai_res = {"approved": False, "reason": "ai_normalization_failed", "raw": str(ai_res), "adjusted_payload": signals}

            # debug keys
            try:
                log.debug("[Signal][AI] ai_res keys=%s", list(ai_res.keys()) if isinstance(ai_res, dict) else type(ai_res))
            except Exception:
                pass

            # determine approved flag robustly
            approved_flag = None
            try:
                if isinstance(ai_res, dict):
                    approved_flag = ai_res.get("approved", ai_res.get("approve", None))
                    if approved_flag is None:
                        approval_obj = ai_res.get("approval")
                        if isinstance(approval_obj, dict):
                            approved_flag = approval_obj.get("approved", None)
                    # if still None, try confidence
                    if approved_flag is None:
                        conf = ai_res.get("confidence", ai_res.get("conf", None))
                        try:
                            if conf is not None:
                                conff = float(conf)
                                if conff > 1.0:
                                    conff = conff / 100.0
                                approved_flag = conff >= 0.5
                        except Exception:
                            approved_flag = None
                if approved_flag is None:
                    default_approve = bool(getattr(self, "allow_trades_without_ai", False))
                    approved_flag = bool(default_approve)
            except Exception:
                approved_flag = False

            if not approved_flag:
                log.info("[Signal] AI rejected signal for %s: %s", signals.get("symbol") or payload.get("symbol"), ai_res.get("reason") if isinstance(ai_res, dict) else str(ai_res))
                return {
                    "ok": False,
                    "error": "rejected_by_ai",
                    "reason": ai_res.get("reason") if isinstance(ai_res, dict) else "rejected",
                    "ai_result": _safe_json(ai_res),
                    "uuid": sig_uuid
                }

            # ---------------- 3) normalize adjusted payload (accept many aliases) ----------------
            adj = {}
            if isinstance(ai_res, dict):
                adj = ai_res.get("adjusted_payload") or ai_res.get("adjusted") or ai_res.get("payload") or signals or {}
            if not isinstance(adj, dict):
                # fallback: if it's a list/tuple, try to take first dict, else wrap
                if isinstance(adj, (list, tuple)) and adj:
                    adj = adj[0] if isinstance(adj[0], dict) else {"value": adj}
                else:
                    adj = signals or {}

            symbol = str(adj.get("symbol") or adj.get("pair") or signals.get("symbol") or payload.get("symbol") or "").upper().strip()
            side_raw = str(adj.get("side") or adj.get("decision") or adj.get("action") or signals.get("side") or payload.get("side") or "").strip().upper()
            if side_raw in ("LONG",):
                side = "BUY"
            elif side_raw in ("SHORT",):
                side = "SELL"
            else:
                side = side_raw

            if not symbol or side not in ("BUY", "SELL"):
                log.error("[Signal] Invalid payload after AI adjustment: %s", _safe_json(adj))
                return {"ok": False, "error": "invalid_payload", "details": "missing_symbol_or_side", "uuid": sig_uuid}

            # parse volume accepting multiple fields
            def _safe_float(v, default=DEFAULT_VOLUME):
                try:
                    if v is None or v == "":
                        return float(default)
                    return float(v)
                except Exception:
                    return float(default)

            requested_volume = _safe_float(adj.get("volume") or adj.get("lot_size") or adj.get("lots") or adj.get("lot") or signals.get("volume") or DEFAULT_VOLUME)

            # parse TP/SL - accept pips and prices
            tp = None
            sl = None
            tp_pips = None
            sl_pips = None

            # price candidates
            for k in ("tp", "take_profit", "tp_price", "take_profit_price"):
                if k in adj and adj.get(k) is not None:
                    try:
                        tp = float(adj.get(k))
                        break
                    except Exception:
                        pass
            for k in ("sl", "stop_loss", "sl_price", "stop_loss_price"):
                if k in adj and adj.get(k) is not None:
                    try:
                        sl = float(adj.get(k))
                        break
                    except Exception:
                        pass
            # pips candidates
            for k in ("tp_pips", "take_profit_pips"):
                if k in adj and adj.get(k) is not None:
                    try:
                        tp_pips = float(adj.get(k))
                        break
                    except Exception:
                        pass
            for k in ("sl_pips", "stop_loss_pips"):
                if k in adj and adj.get(k) is not None:
                    try:
                        sl_pips = float(adj.get(k))
                        break
                    except Exception:
                        pass

            log.info("[Signal] Received request symbol=%s side=%s requested_volume=%s uuid=%s", symbol, side, requested_volume, sig_uuid)

            # 3.1) normalize volume using helper (preferred)
            try:
                ok_norm, normalized_vol = self._normalize_volume(symbol, requested_volume)
            except Exception as e:
                log.exception("[Signal] volume normalization failed: %s", e)
                ok_norm, normalized_vol = False, max(0.01, min(float(requested_volume or DEFAULT_VOLUME), IN_MAX_VOLUME))

            # final safety clamps
            try:
                normalized_vol = float(normalized_vol)
                normalized_vol = max(0.01, min(normalized_vol, IN_MAX_VOLUME))
            except Exception:
                normalized_vol = float(DEFAULT_VOLUME)

            if abs(float(requested_volume) - float(normalized_vol)) > 1e-9:
                log.info("[Signal] Volume normalization for %s: requested=%s -> normalized=%s (uuid=%s)", symbol, requested_volume, normalized_vol, sig_uuid)

            # ---------------- 4) place trade via place_trade (defensivo) ----------------
            try:
                place_fn = getattr(self, "place_trade", None)
                if not callable(place_fn):
                    log.error("[Signal] place_trade not available on MT5Communication")
                    return {"ok": False, "error": "place_trade_unavailable", "uuid": sig_uuid}

                send_kwargs = {
                    "symbol": symbol,
                    "side": side,
                    "volume": normalized_vol,
                    "max_retries": MAX_RETRIES
                }
                # prefer absolute price if provided
                if tp is not None:
                    send_kwargs["tp"] = tp
                elif tp_pips is not None:
                    send_kwargs["tp_pips"] = tp_pips

                if sl is not None:
                    send_kwargs["sl"] = sl
                elif sl_pips is not None:
                    send_kwargs["sl_pips"] = sl_pips

                result = place_fn(**send_kwargs)

            except Exception as e:
                log.exception("[Signal] Trade placement failed for %s %s: %s", symbol, side, e)
                return {
                    "ok": False,
                    "error": "trade_error",
                    "details": str(e),
                    "uuid": sig_uuid,
                    "requested_volume": requested_volume,
                    "normalized_volume": normalized_vol
                }

            # attempt to extract effective volume from result
            effective_vol = self._extract_effective_volume_from_result(result)

            # annotate result with audit fields
            if isinstance(result, dict):
                result.setdefault("audit", {})
                result["audit"].update({
                    "uuid": sig_uuid,
                    "requested_volume": requested_volume,
                    "normalized_volume": normalized_vol,
                    "effective_volume": effective_vol
                })

            log.info("[Signal] Trade attempt summary symbol=%s side=%s req=%s norm=%s eff=%s uuid=%s",
                    symbol, side, requested_volume, normalized_vol, effective_vol, sig_uuid)

            return result

        except Exception as e:
            log.exception("[Signal] Unexpected error processing payload: %s", e)
            return {"ok": False, "error": "unexpected_error", "details": str(e), "uuid": sig_uuid}

    # ---------------- open positions ----------------
    def get_open_trades(self) -> List[Dict[str, Any]]:
        """
        Returns a list of current open positions, safely wrapped.
        """
        try:
            with self._mt5_lock:
                positions = mt5.positions_get()
            return _safe_json(positions) if positions else []
        except Exception as e:
            log.exception(f"get_open_trades failed: {e}")
            return []

    def get_open_trades_count(self) -> int:
        """
        Returns the count of open positions.
        """
        try:
            trades = self.get_open_trades()
            return len(trades)
        except Exception as e:
            log.exception(f"get_open_trades_count failed: {e}")
            return 0

    # ---------------- shutdown ----------------
    def shutdown(self, wait: float = 5.0):
        log = getattr(self, "logger", None)
        if log:
            log.info("Shutdown MT5Communication requested")

        # ---------------- WebSocket ----------------
        try:
            if hasattr(self, "_ws_thread_stop_evt"):
                self._ws_thread_stop_evt.set()

            if hasattr(self, "_ws_loop") and self._ws_loop and self._ws_loop.is_running():
                if hasattr(self, "_stop_ws_loop"):
                    asyncio.run_coroutine_threadsafe(
                        self._stop_ws_loop(), self._ws_loop
                    )

            if hasattr(self, "_ws_thread") and self._ws_thread and self._ws_thread.is_alive():
                self._ws_thread.join(timeout=wait)

        except Exception:
            if log:
                log.exception("Error stopping WebSocket")

        # ---------------- HTTP fallback ----------------
        try:
            if hasattr(self, "_http_runner") and self._http_runner:
                asyncio.run(self._stop_http())
        except Exception:
            if log:
                log.exception("Error stopping HTTP fallback")

        # ---------------- MT5 ----------------
        try:
            with self._mt5_lock:
                import MetaTrader5 as mt5
                mt5.shutdown()
                if log:
                    log.info("MT5 shutdown")
        except Exception:
            if log:
                log.exception("mt5.shutdown error")

        # ---------------- Executor ----------------
        try:
            if hasattr(self, "_blocking_executor"):
                self._blocking_executor.shutdown(wait=True)
        except Exception:
            pass



    def _start_websocket_thread(self):
        """Inicia thread que roda um event loop com servidor websockets (tolerante a HTTP hits)."""
        # não reiniciar se já está a correr
        if getattr(self, "_ws_thread", None) and self._ws_thread.is_alive():
            log.debug("_start_websocket_thread: already running")
            return

        # reset events
        try:
            self._ws_started_evt.clear()
        except Exception:
            pass
        self._ws_thread_stop_evt.clear()

        def _thread_target():
            import websockets
            from websockets import exceptions as _ws_exceptions
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._ws_loop = loop
            server = None

            # define um exception handler leve para o loop (suprime spam de stack trace)
            def _loop_exc_handler(loop, context):
                try:
                    # log apenas debug — evita prints do asyncio
                    msg = context.get("message", "")
                    exc = context.get("exception")
                    log.debug("ws loop exception handler: %s %s", msg, exc)
                except Exception:
                    pass

            loop.set_exception_handler(_loop_exc_handler)

            # resolve handler (compatibilidade com _ws_handler ou _handle_client)
            handler = getattr(self, "_ws_handler", None) or getattr(self, "_handle_client", None)
            if not callable(handler):
                log.error("_start_websocket_thread: no websocket handler (_ws_handler/_handle_client) found")
                self._ws_loop = None
                try:
                    if not self._ws_started_evt.is_set():
                        self._ws_started_evt.set()
                except Exception:
                    pass
                return

            async def process_request(path, request_headers):
                """
                Graceful handler for non-WebSocket hits.
                Return None to continue WebSocket handshake.
                Otherwise return (status, headers, body).
                """
                try:
                    upgrade = request_headers.get("Upgrade", "")
                    connection_hdr = request_headers.get("Connection", "")
                    # consider it a WS handshake only when both headers indicate an upgrade
                    if isinstance(upgrade, str) and "websocket" in upgrade.lower() and isinstance(connection_hdr, str) and "upgrade" in connection_hdr.lower():
                        return None

                    # If the client is doing a regular HTTP request (keep-alive etc),
                    # respond with a small informative body so it doesn't cause a noisy stacktrace.
                    body = b"MT5 WebSocket endpoint. Use WebSocket handshake or POST to HTTP fallback endpoint.\n"
                    headers = [
                        ("Content-Type", "text/plain; charset=utf-8"),
                        ("Content-Length", str(len(body)))
                    ]
                    return 200, headers, body
                except Exception:
                    # In case of any unexpected header shapes, avoid raising and return a sane fallback.
                    return 200, [("Content-Type", "text/plain")], b"OK"


            async def _ws_main():
                nonlocal server
                try:
                    server = await websockets.serve(
                        handler,
                        self.host,
                        self.port,
                        ping_interval=globals().get("WS_PING_INTERVAL", None),
                        ping_timeout=globals().get("WS_PING_TIMEOUT", None),
                        max_size=globals().get("WS_MAX_SIZE", None),
                        open_timeout=10,  # HARDCORE FIX: timeout handshake 10s
                        process_request=process_request,
                    )
                    self._ws_server = server
                    log.info("WebSocket server listening %s:%d", self.host, self.port)

                    # sinaliza que o servidor iniciou
                    if not self._ws_started_evt.is_set():
                        self._ws_started_evt.set()

                    # espera até receber sinal de parada
                    while not self._ws_thread_stop_evt.is_set():
                        await asyncio.sleep(0.2)

                    log.info("_ws_main: shutdown requested, closing server")
                    try:
                        server.close()
                        await server.wait_closed()
                    except Exception as e:
                        log.debug("_ws_main: server close error: %s", e)

                except (_ws_exceptions.InvalidMessage, _ws_exceptions.InvalidUpgrade, ConnectionResetError, EOFError, ValueError, AssertionError) as e:
                    # HARDCORE FIX: Erros esperáveis quando um cliente HTTP normal acerta no porto WS.
                    # Suprimir completamente (não logar WARNING)
                    log.debug("_ws_main handshake error (suppressed): %s", str(e)[:80])
                    # garante sinalização para não bloquear quem espera o started_evt
                    if not self._ws_started_evt.is_set():
                        try:
                            self._ws_started_evt.set()
                        except Exception:
                            pass
                    return
                except Exception as e:
                    # Erro inesperado: log com stack
                    log.exception("_ws_main crashed: %s", e)
                    if not self._ws_started_evt.is_set():
                        try:
                            self._ws_started_evt.set()
                        except Exception:
                            pass
                    return

            try:
                loop.run_until_complete(_ws_main())
            except Exception as e:
                log.exception("_start_websocket_thread: loop crashed: %s", e)
            finally:
                try:
                    pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                except Exception:
                    pending = []
                if pending:
                    for t in pending:
                        try:
                            t.cancel()
                        except Exception:
                            pass
                    try:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception:
                        pass

                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                try:
                    loop.close()
                except Exception:
                    pass

                self._ws_loop = None
                self._ws_server = None
                log.info("WebSocket loop closed (thread ending)")

        # start thread
        self._ws_thread = threading.Thread(target=_thread_target, name="mt5-ws-loop", daemon=True)
        self._ws_thread.start()

        # wait um curto período para server sinalizar ready
        started = False
        try:
            started = bool(self._ws_started_evt.wait(timeout=6.0))
        except Exception:
            started = False

        if not started:
            log.warning("WebSocket thread started but server didn't signal ready (timeout).")
        else:
            log.info("WebSocket server start signalled")


    def _stop_websocket_thread(self, timeout: float = 5.0):
        """
        Para o servidor websocket de forma segura (síncrono).
        - Seta o evento de stop
        - acorda a loop para que saia do sleep rápido
        - tenta fechar server cleanly via call_soon_threadsafe
        - aguarda join do thread
        """
        try:
            if not getattr(self, "_ws_thread", None):
                log.debug("_stop_websocket_thread: no ws thread to stop")
                return

            # sinaliza pedido de parada
            try:
                if getattr(self, "_ws_thread_stop_evt", None):
                    self._ws_thread_stop_evt.set()
            except Exception:
                pass

            # se o loop existir, ordena fechamento do server e acorda-o
            try:
                if getattr(self, "_ws_loop", None):
                    loop = self._ws_loop
                    # se tivermos server, fechamos via call_soon_threadsafe
                    if getattr(self, "_ws_server", None):
                        try:
                            # chama server.close() dentro da loop de forma thread-safe
                            loop.call_soon_threadsafe(self._ws_server.close)
                        except Exception:
                            # fallback: apenas acorda loop
                            try:
                                loop.call_soon_threadsafe(lambda: None)
                            except Exception:
                                pass
                    else:
                        # apenas acorda loop para que ele perceba o evento de stop
                        try:
                            loop.call_soon_threadsafe(lambda: None)
                        except Exception:
                            pass
            except Exception as e:
                log.debug("_stop_websocket_thread: error waking loop: %s", e)

            # aguarda o thread encerrar
            try:
                self._ws_thread.join(timeout=timeout)
                if self._ws_thread.is_alive():
                    log.warning("_stop_websocket_thread: thread still alive after join")
                else:
                    log.info("_stop_websocket_thread: stopped cleanly")
            except Exception as e:
                log.exception("_stop_websocket_thread join failed: %s", e)

        except Exception as e:
            log.exception("_stop_websocket_thread failed: %s", e)

    # ---------------- ai evaluation / enrichment helper ----------------
    def _call_ai_on_signal(
        self,
        payload: Dict[str, Any],
        timeout: float = 2.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Chama o AIManager de forma segura usando self._blocking_executor, com retries.
        Normaliza vários tipos de resposta do AI para um dict:
        { approved: bool, adjusted_payload: dict, reason: str, meta: dict, raw: Any }
        Retorna um dict com essas chaves. Em caso de erro/timeout retorna approved=False.
        """
        if not self.ai_manager:
            log.error("[AI] AIManager não configurado — TRADE BLOQUEADO")
            return {"approved": False, "adjusted_payload": payload, "reason": "ai_manager_missing", "meta": {}, "raw": None}
       
        # if payload explicitly asks to bypass ai, short-circuit
        if isinstance(payload, dict) and payload.get("_bypass_ai"):
            return {"approved": True, "adjusted_payload": payload, "reason": "bypass_flag", "raw": None}

        # Escolhe um método plausível no ai_manager
        candidate_names = ("request_trade_decision", "vote_trade", "evaluate_signal", "request", "request_trade")
        ai_fn = None
        for name in candidate_names:
            fn = getattr(self.ai_manager, name, None)
            if callable(fn):
                ai_fn = fn
                break

        if ai_fn is None:
            log.error("[AI] AIManager não expõe nenhum método conhecido (%s) — TRADE BLOQUEADO", ", ".join(candidate_names))
            return {"approved": False, "adjusted_payload": payload, "reason": "ai_method_missing", "meta": {}, "raw": None}
        
        def _invoke_ai():
            """Invocado na thread pool (bloqueante). Deve retornar qualquer tipo; será normalizado."""
            return ai_fn(payload)

        # Normalizador de resposta do AI -> dict consistente
        def _normalize(raw) -> Dict[str, Any]:
            out = {
                "approved": False,
                "adjusted_payload": dict(payload),
                "reason": "no_reason",
                "meta": {},
                "raw": raw
            }
            try:
                # dict: prefer campos explícitos
                if isinstance(raw, dict):
                    out["raw"] = raw
                    out["meta"] = raw.get("meta", {})
                    # explicit approval fields
                    if "approved" in raw:
                        out["approved"] = bool(raw.get("approved"))
                    elif "approve" in raw:
                        out["approved"] = bool(raw.get("approve"))
                    elif "decision" in raw:
                        # allow decision-based approval: BUY/SELL -> approve True, HOLD -> False
                        dec = str(raw.get("decision")).upper()
                        if dec == "HOLD":
                            out["approved"] = False
                        elif dec in ("BUY", "SELL", "LONG", "SHORT"):
                            out["approved"] = True

                    # confidence fallback
                    conf = raw.get("confidence", raw.get("conf", raw.get("score", None)))
                    if conf is not None:
                        try:
                            c = float(conf)
                            if c > 1.0:
                                c = c / 100.0
                            # if confidence exists but no explicit approved, mark approved if >=0.5
                            if "approved" not in raw and "approve" not in raw:
                                out["approved"] = c >= 0.5
                            out["meta"]["confidence"] = c
                        except Exception:
                            pass

                    # adjusted payload suggestions
                    for key in ("side", "volume", "tp_pips", "sl_pips", "tp", "sl", "tp_price", "sl_price", "suggested_volume"):
                        if key in raw and raw.get(key) is not None:
                            try:
                                out["adjusted_payload"][key] = raw.get(key)
                            except Exception:
                                out["adjusted_payload"][key] = raw.get(key)

                    out["reason"] = str(raw.get("reason", out["reason"]))
                    return out

                # boolean -> approved or not
                if isinstance(raw, bool):
                    out["approved"] = raw
                    out["reason"] = "bool_response"
                    return out

                # numeric -> treated as confidence
                if isinstance(raw, (int, float)):
                    c = float(raw)
                    if c > 1.0:
                        c = c / 100.0
                    out["meta"]["confidence"] = c
                    out["approved"] = c >= 0.5
                    out["reason"] = "numeric_confidence"
                    return out

                # string -> heurística simples (procura BUY/SELL/HOLD e percent)
                if isinstance(raw, str):
                    s = raw.upper()
                    out["approved"] = ("BUY" in s or "SELL" in s) and ("HOLD" not in s)
                    import re
                    m = re.search(r"(\d{1,3})\s*%", s)
                    if m:
                        try:
                            c = float(m.group(1)) / 100.0
                            out["meta"]["confidence"] = c
                            if "approved" not in out:
                                out["approved"] = c >= 0.5
                        except Exception:
                            pass
                    out["reason"] = "text_parse"
                    return out

                # fallback: unknown type -> treat as reject but record raw
                out["approved"] = False
                out["reason"] = "unknown_response_type"
                return out

            except Exception as e:
                log.exception("[AI] normalize error: %s", e)
                out["approved"] = False
                out["reason"] = "normalize_exception"
                out["meta"].update({"normalize_error": str(e)})
                return out

        # Safety: ensure at least one attempt
        if not isinstance(max_retries, int) or max_retries < 1:
            max_retries = 1

        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                future = self._blocking_executor.submit(_invoke_ai)
                raw = future.result(timeout=timeout)
                norm = _normalize(raw)

                # if approved, apply small safety: don't blindly accept crazy volume types
                if norm.get("approved"):
                    try:
                        adj = dict(norm.get("adjusted_payload", payload) or payload)
                        # coerce volume to float safely if present
                        if "volume" in adj:
                            try:
                                adj["volume"] = float(adj["volume"])
                            except Exception:
                                adj["volume"] = float(DEFAULT_VOLUME)
                        norm["adjusted_payload"] = adj
                    except Exception:
                        pass

                # attach raw for debugging and return
                norm.setdefault("raw", raw)
                return norm

            except Exception as e:
                last_exc = e
                log.warning("[AI][Attempt %d/%d] Erro chamando AI: %s", attempt, max_retries, e)
                # se último attempt, retorna erro estruturado
                if attempt >= max_retries:
                    log.error("[AI] Todas tentativas falharam — TRADE BLOQUEADO: %s", e)
                    return {
                        "approved": False,
                        "adjusted_payload": payload,
                        "reason": "ai_error_or_timeout",
                        "meta": {"error": str(e)},
                        "raw": None
                    }
                # pequena espera antes do retry
                time.sleep(0.1)

        # fallback final (não deve chegar aqui)
        return {"approved": False, "adjusted_payload": payload, "reason": "ai_unknown_failure", "meta": {"error": str(last_exc)}, "raw": None}


    # ---------------- client handler ----------------
    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str):
        # improved ws handler: robust parsing, auth, rate-limit, centralized processing
        peer = getattr(websocket, "remote_address", None) or ("unknown", 0)
        try:
            client_ip, client_port = peer
        except Exception:
            client_ip = str(peer[0]) if isinstance(peer, (list, tuple)) and len(peer) > 0 else str(peer)
            client_port = peer[1] if isinstance(peer, (list, tuple)) and len(peer) > 1 else 0

        client_id = f"{client_ip}:{client_port}"
        log.info("[WS] Client connected %s", client_id)
        with self._metrics_lock:
            self.metrics["ws_connections"] = self.metrics.get("ws_connections", 0) + 1

        try:
            async for message in websocket:
                start_ts = time.time()

                # ---------- parse JSON ----------
                try:
                    data = json.loads(message)
                    if not isinstance(data, dict):
                        raise ValueError("message is not a JSON object")
                except Exception as e:
                    await websocket.send(json.dumps({"status": "error", "detail": "invalid_json"}))
                    log.debug("[WS] Invalid JSON from %s: %s", client_id, e)
                    continue

                # ---------- auth ----------
                if CLIENT_TOKEN:
                    token = data.get("token") or data.get("auth")
                    if token != CLIENT_TOKEN:
                        await websocket.send(json.dumps({"status": "error", "detail": "auth_failed"}))
                        log.warning("[WS] Auth failed from %s", client_id)
                        continue

                # ---------- rate limit by IP ----------
                now = time.time()
                last = self._client_last_ts.get(client_ip, 0.0)
                if now - last < CLIENT_MIN_INTERVAL:
                    await websocket.send(json.dumps({"status": "error", "detail": "rate_limited"}))
                    continue
                self._client_last_ts[client_ip] = now

                # ---------- action ----------
                action = str(data.get("action") or "").strip().lower()
                if not action:
                    await websocket.send(json.dumps({"status": "error", "detail": "missing action"}))
                    continue

                # ---------- ping ----------
                if action == "ping":
                    await websocket.send(json.dumps({"status": "ok", "time": time.time()}))
                    continue

                # ---------- get_data ----------
                if action == "get_data":
                    symbol = str(data.get("symbol") or "").upper()
                    n = min(int(data.get("n", 100)), 1000)
                    if not symbol:
                        await websocket.send(json.dumps({"status": "error", "detail": "missing symbol"}))
                        continue
                    loop = asyncio.get_running_loop()
                    df = await loop.run_in_executor(self._blocking_executor, self.get_symbol_data, symbol, mt5.TIMEFRAME_M1, n)
                    await websocket.send(json.dumps({"status": "ok", "data": _safe_json(df)}))
                    continue

                # ---------- get_open_trades ----------
                if action == "get_open_trades":
                    loop = asyncio.get_running_loop()
                    trades = await loop.run_in_executor(self._blocking_executor, self.get_open_trades)
                    await websocket.send(json.dumps({"status": "ok", "trades": _safe_json(trades)}))
                    continue

                # ---------- trade_signal / proposed_signal / place_trade (high-level) ----------
                if action in ("trade_signal", "proposed_signal", "place_trade"):
                    # shape minimal payload - let _process_signal_payload own normalization/AI/risk
                    symbol = str(data.get("symbol") or "").upper()
                    side = str(data.get("side") or data.get("decision") or "").upper()
                    if side in ("LONG",):
                        side = "BUY"
                    elif side in ("SHORT",):
                        side = "SELL"

                    if not symbol or side not in ("BUY", "SELL"):
                        await websocket.send(json.dumps({"status": "error", "detail": "missing symbol or invalid side"}))
                        continue

                    payload = {
                        "symbol": symbol,
                        "side": side,
                        # accept several possible names for volume
                        "volume": float(data.get("volume", data.get("lot_size", DEFAULT_VOLUME))),
                        "tp_pips": data.get("tp_pips"),
                        "sl_pips": data.get("sl_pips"),
                        "tp": data.get("tp"),
                        "sl": data.get("sl"),
                        "uuid": data.get("uuid") or data.get("id"),
                        "source": data.get("source", "ws"),
                        "received_at": now,
                        # pass through raw payload for auditing if needed
                        "_raw": data
                    }

                    # if bypass requested, call process directly with bypass flag
                    bypass_ai = bool(data.get("bypass_ai", False))
                    if bypass_ai:
                        # mark in payload to indicate bypass
                        payload["_bypass_ai"] = True

                    # centralize processing: delegate to _process_signal_payload (runs AI/risk/normalization/place_trade)
                    loop = asyncio.get_running_loop()
                    try:
                        result = await loop.run_in_executor(self._blocking_executor, lambda: self._process_signal_payload(payload))
                    except Exception as e:
                        log.exception("[WS] Error processing signal for %s: %s", client_id, e)
                        await websocket.send(json.dumps({"status": "error", "detail": "processing_failed", "error": str(e)}))
                        continue

                    # uniform response: include ai_reason, audit if present
                    try:
                        response = {"status": "ok" if result.get("ok") else "error", "action": "placed" if result.get("ok") else "failed", "result": _safe_json(result)}
                        # if AI rejected include reason
                        if result.get("error") == "rejected_by_ai":
                            response["status"] = "rejected_by_ai"
                            response["reason"] = result.get("reason")
                        await websocket.send(json.dumps(response))
                    except Exception:
                        # fallback safe send (avoid serialization errors)
                        await websocket.send(json.dumps({"status": "ok" if result.get("ok") else "error", "result": str(result)}))
                    continue

                # ---------- send_order (low-level) ----------
                if action == "send_order":
                    symbol = str(data.get("symbol") or "").upper()
                    order_type = data.get("type")
                    if symbol is None or order_type is None:
                        await websocket.send(json.dumps({"status":"error","detail":"missing symbol or type"}))
                        continue

                    # normalize order_type: accept numeric MT5 constants or strings "BUY"/"SELL"
                    try:
                        if isinstance(order_type, str):
                            ot = order_type.strip().upper()
                            if ot in ("BUY", "LONG"):
                                order_type_val = int(mt5.ORDER_TYPE_BUY)
                            elif ot in ("SELL", "SHORT"):
                                order_type_val = int(mt5.ORDER_TYPE_SELL)
                            else:
                                # maybe passed name like "ORDER_TYPE_BUY"
                                order_type_val = int(getattr(mt5, order_type, order_type))
                        else:
                            order_type_val = int(order_type)
                    except Exception:
                        await websocket.send(json.dumps({"status":"error","detail":"invalid order type"}))
                        continue

                    payload = {
                        "symbol": symbol,
                        "order_type": int(order_type),
                        "volume": float(data.get("volume", DEFAULT_VOLUME)),
                        "sl": data.get("sl"),
                        "tp": data.get("tp"),
                        "sl_pips": data.get("sl_pips"),
                        "tp_pips": data.get("tp_pips"),
                        "uuid": data.get("uuid") or data.get("id"),
                        "source": data.get("source", "ws")
                    }

                    # optionally pass through AI check (use existing _call_ai_on_signal)
                    bypass_ai = bool(data.get("bypass_ai", False))
                    if not bypass_ai:
                        loop = asyncio.get_running_loop()
                        ai_res = await loop.run_in_executor(self._blocking_executor, lambda: self._call_ai_on_signal(payload))
                    else:
                        ai_res = {"approved": True, "adjusted_payload": payload, "reason": "bypass_ai"}

                    if not ai_res.get("approved", False):
                        await websocket.send(json.dumps({"status": "rejected_by_ai", "reason": ai_res.get("reason"), "ai_result": _safe_json(ai_res)}))
                        continue
                   
                    adj = ai_res.get("adjusted_payload", payload)
                    loop = asyncio.get_running_loop()
                    
                    try:
                        res = await loop.run_in_executor(self._blocking_executor, lambda: self.send_order(
                            symbol=adj.get("symbol"),
                            order_type=int(adj.get("order_type") or order_type),
                            volume=float(adj.get("volume", DEFAULT_VOLUME)),
                            sl=adj.get("sl"),
                            tp=adj.get("tp"),
                            sl_pips=adj.get("sl_pips"),
                            tp_pips=adj.get("tp_pips")
                        ))
                        await websocket.send(json.dumps({"status": "ok", "action": "sent", "result": _safe_json(res)}))
                    except Exception as e:
                        log.exception("[WS] send_order failed for %s: %s", client_id, e)
                        await websocket.send(json.dumps({"status": "error", "detail": "send_order_failed", "error": str(e)}))
                    continue

                # unknown action
                await websocket.send(json.dumps({"status": "error", "detail": "unknown action"}))

        except websockets.ConnectionClosed as e:
            # HARDCORE FIX: Graceful disconnect
            log.debug("[WS] Client disconnected %s (code=%s)", client_id, getattr(e, 'code', 'N/A'))
        except Exception as e:
            log.error("[WS] Unexpected exception for %s: %s", client_id, str(e)[:200])
        finally:
            # cleanup
            try:
                self._client_last_ts.pop(client_ip, None)
            except Exception:
                pass
            with self._metrics_lock:
                self.metrics["ws_connections"] = max(0, self.metrics.get("ws_connections", 1) - 1)
            log.debug("[WS] Connection closed %s", client_id)

# quick manual run
if __name__ == "__main__":
    comm = MT5Communication()
    log.info("MT5Communication improved running. Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping by user")
        comm.shutdown()
