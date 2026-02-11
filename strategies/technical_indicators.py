# strategies/technical_indicators_hardcore_v2.py  (FIXED — socket-only payloads, robust & serializable)
from __future__ import annotations
import threading
import time
import json
import logging
import socket
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Callable
import pandas as pd
import numpy as np

# -----------------------
# Logging setup
# -----------------------
ROOT = Path(__file__).parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("technical_indicators_hardcore")
if not logger.handlers:
    fh = logging.FileHandler(LOG_DIR / "technical_indicators_hardcore.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"))
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    logger.addHandler(sh)
logger.setLevel(logging.INFO)

# -----------------------
# Signal Manager
# -----------------------
class SignalManager:
    """Gerencia sinais recebidos e histórico, thread-safe, integração com strategies e AI"""
    def __init__(self, max_history: int = 10000):
        self._queue: List[Dict[str, Any]] = []
        self._history: List[Dict[str, Any]] = []
        self._max_history = int(max_history)
        self._lock = threading.Lock()
        self._event = threading.Event()
 
    def add_signal(self, signal: Dict[str, Any]) -> None:
        with self._lock:
            now = time.time()
            s = {**signal, "received_at": now}
            self._queue.append(s)
            self._history.append(s)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            self._event.set()
            logger.debug("Signal queued: %s", s.get("symbol"))

    def get_next(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self._queue:
                    return self._queue.pop(0)
            time.sleep(0.01)
        return None

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)

signal_manager = SignalManager()

# -----------------------
# Technical Indicators Hardcore v2
# -----------------------
class TechnicalIndicatorsHardcore:
    """Indicadores ultracompletos, thread-safe, cache inteligente, socket-only I/O"""
    def __init__(self, cache_duration: float = 30.0, socket_host: str = "127.0.0.1", socket_port: int = 9999, socket_timeout: float = 1.0):
        self.cache: Dict[str, Any] = {}
        self.cache_lock = threading.Lock()
        self.cache_duration = float(cache_duration)
        self.registry: Dict[str, Callable[..., Any]] = {}
        self.ai_manager: Optional[Any] = None
        self.strategy_engine: Optional[Any] = None
        self.socket_host = socket_host
        self.socket_port = int(socket_port)
        self.socket_timeout = float(socket_timeout)
        self.socket_lock = threading.Lock()  # serialize socket access
        self._register_all_indicators()
        logger.info("TechnicalIndicatorsHardcore v2 initialized with %d indicators", len(self.registry))

    # -----------------------
    # Helpers
    # -----------------------
    def get_all_indicators(self) -> List[str]:
        """Retorna lista de todos os nomes de indicadores disponíveis"""
        return list(self.registry.keys())

    def _ensure_df(self, data: Union[pd.DataFrame, List[Any]]) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            rows = []
            for md in data:
                # supports dict-like or object-like rows
                if isinstance(md, dict):
                    rows.append({
                        "timestamp": md.get("timestamp"),
                        "open": float(md.get("open", 0.0) or 0.0),
                        "high": float(md.get("high", 0.0) or 0.0),
                        "low": float(md.get("low", 0.0) or 0.0),
                        "close": float(md.get("close", 0.0) or 0.0),
                        "volume": float(md.get("volume", 0.0) or 0.0),
                        "symbol": md.get("symbol"),
                    })
                else:
                    rows.append({
                        "timestamp": getattr(md, "timestamp", None),
                        "open": float(getattr(md, "open", 0.0) or 0.0),
                        "high": float(getattr(md, "high", 0.0) or 0.0),
                        "low": float(getattr(md, "low", 0.0) or 0.0),
                        "close": float(getattr(md, "close", 0.0) or 0.0),
                        "volume": float(getattr(md, "volume", 0.0) or 0.0),
                        "symbol": getattr(md, "symbol", None),
                    })
            df = pd.DataFrame(rows)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.sort_values("timestamp").reset_index(drop=True)
        for c in ("open","high","low","close","volume"):
            df[c] = pd.to_numeric(df.get(c, 0.0), errors="coerce").ffill().fillna(0.0)
        return df

    def _to_serializable(self, obj: Any) -> Any:
        """Converte objetos pandas/numpy para tipos JSON-serializáveis."""
        if isinstance(obj, pd.Series):
            # preserve name when possible
            return [self._to_serializable(x) for x in obj.tolist()]
        if isinstance(obj, pd.DataFrame):
            return [self._to_serializable(r) for r in obj.to_dict(orient="records")]
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return [self._to_serializable(x) for x in obj.tolist()]
        if pd.isna(obj):
            return None
        if isinstance(obj, (pd.Timestamp,)):
            return obj.isoformat()
        return obj

    def _safe_socket_send(self, payload: Dict[str, Any], host: Optional[str] = None, port: Optional[int] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Envio seguro de payload via socket com delimitador newline e retorno de JSON ack.

        - Sempre envia JSON seguido de '\n' (linha).
        - Tenta ler até o primeiro '\n' recebido ou até timeout.
        - Retorna dict: {ok: bool, ack: parsed_json_or_raw_string, raw: raw_bytes}
        """
        host = host or self.socket_host
        port = int(port or self.socket_port)
        timeout = float(timeout or self.socket_timeout)

        # ensure JSON serializable
        try:
            js = json.dumps(payload, ensure_ascii=False, default=str)
        except Exception as e:
            logger.debug("Payload not JSON serializable directly: %s", e)
            # fallback: convert values
            payload2 = json.loads(json.dumps(self._to_serializable(payload), default=str))
            js = json.dumps(payload2, ensure_ascii=False)

        data = js.encode("utf-8") + b"\n"

        with self.socket_lock:
            try:
                with socket.create_connection((host, port), timeout=timeout) as s:
                    s.settimeout(timeout)
                    s.sendall(data)
                    # read until newline or timeout
                    buf = b""
                    try:
                        while True:
                            chunk = s.recv(4096)
                            if not chunk:
                                break
                            buf += chunk
                            if b"\n" in buf:
                                break
                    except socket.timeout:
                        # partial read allowed
                        pass

                    raw = buf
                    if not raw:
                        return {"ok": True, "ack": None, "raw": b""}

                    # split at newline and parse first line
                    first_line = raw.split(b"\n")[0]
                    try:
                        parsed = json.loads(first_line.decode("utf-8", errors="ignore"))
                        return {"ok": True, "ack": parsed, "raw": raw}
                    except Exception:
                        # return raw decoded if not JSON
                        try:
                            text = first_line.decode("utf-8", errors="ignore")
                            return {"ok": True, "ack": text, "raw": raw}
                        except Exception:
                            return {"ok": True, "ack": None, "raw": raw}
            except Exception as e:
                logger.debug("Socket send failed: %s", e)
                return {"ok": False, "ack": None, "raw": None}

    # -----------------------
    # Core indicators
    # -----------------------
    def _sma(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        return df["close"].rolling(period, min_periods=1).mean()
    
    def _ema(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        return df["close"].ewm(span=period, adjust=False).mean()

    def _rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(period, min_periods=period).mean()
        avg_loss = loss.rolling(period, min_periods=period).mean()
        # apply Wilder smoothing where possible
        for i in range(period, len(df)):
            try:
                avg_gain.iat[i] = (avg_gain.iat[i-1]*(period-1)+gain.iat[i])/period
                avg_loss.iat[i] = (avg_loss.iat[i-1]*(period-1)+loss.iat[i])/period
            except Exception:
                pass
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _atr(self, df: pd.DataFrame, period: int = 14, ma_type: str = "wilder", fillna: bool = False) -> pd.Series:
        df = df.copy()
        if df.empty:
            return pd.Series(dtype=float, name=f"ATR_{period}")
        high = pd.to_numeric(df.get("high"), errors="coerce")
        low = pd.to_numeric(df.get("low"), errors="coerce")
        close = pd.to_numeric(df.get("close"), errors="coerce")

        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        ma_type = (ma_type or "wilder").strip().lower()
        if ma_type == "sma":
            atr_series = tr.rolling(window=period, min_periods=1).mean()
        elif ma_type == "ema":
            atr_series = tr.ewm(span=period, adjust=False, min_periods=1).mean()
        else:
            alpha = 1.0 / float(period)
            atr_series = tr.ewm(alpha=alpha, adjust=False, min_periods=1).mean()

        atr_series.name = f"ATR_{period}"
        if fillna:
            cumsum = tr.expanding(min_periods=1).mean()
            atr_series = atr_series.fillna(cumsum)
        atr_series = atr_series.astype(float)
        atr_series.index = df.index
        return atr_series

    # -----------------------
    # Auto-register indicators
    # -----------------------
    def _register_all_indicators(self):
        base_indicators = {
            "sma": self._sma,
            "ema": self._ema,
            "rsi": self._rsi,
            "atr": self._atr,
        }
        self.registry.update(base_indicators)
        periods = [3,5,8,10,12,14,15,20,21,34,50,89,100,144,200,260]
        for name, func in base_indicators.items():
            for p in periods:
                # use default args to avoid late-binding
                self.registry[f"{name}_{p}"] = (lambda df, func=func, period=p: func(df, period))

    # -----------------------
    # Compute all indicators (returns JSON-serializable data)
    # -----------------------
    def compute_all_indicators(self, df: Union[pd.DataFrame, List[Any]], symbol: Optional[str] = None) -> Dict[str, Any]:
        df = self._ensure_df(df)
        cache_key = f"{symbol or 'unknown'}_{len(df)}"
        with self.cache_lock:
            if cache_key in self.cache and (time.time() - self.cache[cache_key]["ts"]) < self.cache_duration:
                return self.cache[cache_key]["data"]

        out: Dict[str, Any] = {}
        for name, func in self.registry.items():
            try:
                res = func(df)
                out[name] = self._to_serializable(res)
            except Exception as e:
                out[name] = None
                logger.warning("Indicator %s failed: %s", name, e)

        with self.cache_lock:
            self.cache[cache_key] = {"ts": time.time(), "data": out}
        return out

    # -----------------------
    # Gather signals from strategies + AI managers (socket-only)
    # -----------------------
    def gather_signals(self, market_data: Union[pd.DataFrame, List[Any]], timeout: float = 1.5) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []

        # Strategy Engine (local aggregation allowed)
        if self.strategy_engine:
            try:
                aggregated_signal = self.strategy_engine.run_strategies_aggregated(market_data, timeout=timeout)
                # standardize: expect list of dicts
                if isinstance(aggregated_signal, dict) and "aggregated_signals" in aggregated_signal:
                    signals += aggregated_signal.get("aggregated_signals", [])
                elif isinstance(aggregated_signal, list):
                    signals += aggregated_signal
            except Exception as e:
                logger.warning("Failed to gather strategy signals: %s", e)

        # AI Manager: send market_data via socket and expect JSON reply with 'signals' key
        if self.ai_manager is not None:
            try:
                payload = {
                    "type": "request_signal",
                    "market_data": self._to_serializable(self._ensure_df(market_data).to_dict(orient="records")),
                    "timestamp": time.time(),
                }
                rsp = self._safe_socket_send(payload, timeout=timeout)
                if rsp.get("ok") and rsp.get("ack") is not None:
                    ack = rsp.get("ack")
                    # If ack is dict and contains 'signals' key, use it
                    if isinstance(ack, dict) and "signals" in ack and isinstance(ack["signals"], list):
                        signals += ack["signals"]
                    # If ack is string, try parse JSON
                    elif isinstance(ack, str):
                        try:
                            parsed = json.loads(ack)
                            if isinstance(parsed, dict) and "signals" in parsed and isinstance(parsed["signals"], list):
                                signals += parsed["signals"]
                        except Exception:
                            # not JSON — ignore or log
                            logger.debug("AI ack not JSON with signals: %s", ack)
            except Exception as e:
                logger.warning("Failed to gather AI signals: %s", e)

        # Normalize signals to be list of dicts
        normalized: List[Dict[str, Any]] = []
        for s in signals:
            if isinstance(s, dict):
                normalized.append(s)
            else:
                # attempt to parse if string
                try:
                    parsed = json.loads(s) if isinstance(s, str) else None
                    if isinstance(parsed, dict):
                        normalized.append(parsed)
                except Exception:
                    pass

        return normalized

# -----------------------
# Singleton
# -----------------------
technical_indicators_hardcore = TechnicalIndicatorsHardcore()
logger.info("TechnicalIndicatorsHardcore v2 ready. Registry size: %d", len(technical_indicators_hardcore.registry))
