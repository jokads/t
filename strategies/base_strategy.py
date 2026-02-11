# strategies/base_strategy_ai_hardcore.py
from __future__ import annotations
import json
import logging
import threading
import time
import socket
import random
from datetime import datetime
from queue import Queue, Empty
from typing import Dict, Optional, Any, List, Iterable
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

logger = logging.getLogger("strategy_base_ai")
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    logger.addHandler(sh)
logger.setLevel(logging.INFO)


# -------------------------
# Signal dataclass (serializable)
# -------------------------
@dataclass
class Signal:
    symbol: str
    action: str  # BUY / SELL / HOLD
    confidence: float  # 0..1
    price: float
    timestamp: str
    strategy: str
    tp: Optional[float] = None
    sl: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    meta_votes: Dict[str, Any] = field(default_factory=dict)  # votes from other strategies / ai
    source: Optional[str] = None  # who requested (strategy engine / external)

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "symbol": self.symbol,
            "action": self.action,
            "confidence": self.confidence,
            "price": self.price,
            "timestamp": self.timestamp,
            "strategy": self.strategy,
            "tp": self.tp,
            "sl": self.sl,
            "metadata": self.metadata,
            "meta_votes": self.meta_votes,
            "source": self.source,
        }
        return out


# -------------------------
# Minimal socket client used by SignalSender (keeps original behaviour)
# -------------------------
class SocketClient:
    def __init__(self, host="127.0.0.1", port=9090, timeout=2.0, retries=2):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries

    def send(self, payload: Dict) -> Dict:
        data = json.dumps(payload).encode("utf-8")
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                    s.sendall(data)
                    s.shutdown(socket.SHUT_WR)
                    resp = s.recv(65536)
                    if resp:
                        return json.loads(resp.decode("utf-8"))
                    return {"status": "error", "reason": "no_response"}
            except Exception as e:
                last_exc = e
                time.sleep(0.05 + random.random() * 0.05)
        logger.debug("SocketClient failed: %s", last_exc)
        return {"status": "error", "reason": str(last_exc)}


# -------------------------
# SignalSender (threaded, rate-limited)
# -------------------------
class SignalSender:
    def __init__(self, host="127.0.0.1", port=9090, rate_limit_per_sec=4.0):
        self.client = SocketClient(host=host, port=port)
        self.queue: Queue[Dict] = Queue()
        self._stop = threading.Event()
        self.rate_limit_per_sec = rate_limit_per_sec
        self._last_send_time = 0.0
        self._lock = threading.Lock()
        self.stats = {"sent": 0, "failed": 0, "fallback": 0}
        self.worker = threading.Thread(target=self._worker_loop, daemon=True, name="SignalSenderWorker")
        self.worker.start()

    def enqueue(self, signal: Dict):
        try:
            self.queue.put_nowait(signal)
        except Exception:
            self.queue.put(signal)

    def stop(self):
        self._stop.set()
        if self.worker.is_alive():
            self.worker.join(timeout=2.0)

    def _worker_loop(self):
        while not self._stop.is_set():
            try:
                signal = self.queue.get(timeout=1.0)
            except Empty:
                time.sleep(0.01)
                continue
            with self._lock:
                now = time.time()
                min_interval = 1.0 / max(0.0001, self.rate_limit_per_sec)
                elapsed = now - self._last_send_time
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                self._last_send_time = time.time()
            resp = self.client.send(signal)
            if resp.get("status") != "error":
                self.stats["sent"] += 1
            else:
                self.stats["failed"] += 1
            self.queue.task_done()


# -------------------------
# Base Strategy AI Hardcore (refatorado)
# -------------------------
class BaseStrategyAI:
    """
    BaseStrategy hardcore (refatorado):
      - Multi-strategy aware: aceita meta-votes de outras strategies
      - Pode consultar um market_data provider (opcional) se passado no construtor
      - Produz Signals com metadata, meta_votes e auditing
      - Usa AIManager (se fornecido) para validação/concordância
    """

    MIN_ATR = 1e-6

    def __init__(
        self,
        symbol: str,
        sender: Optional[SignalSender] = None,
        ai_manager: Optional[Any] = None,
        other_strategies: Optional[List[Any]] = None,
        market_data: Optional[Any] = None,
        cfg: Optional[Dict[str, Any]] = None
    ):
        self.symbol = symbol
        self.sender = sender or SignalSender()
        self.ai_manager = ai_manager
        self.other_strategies = other_strategies or []
        self.market_data = market_data  # optional provider with get_ohlcv(symbol, bars)
        self._lock = threading.RLock()
        self._seen_signatures: Dict[str, float] = {}
        self._registered_meta: Dict[str, Dict[str, Any]] = {}  # external votes/info
        self.cfg = {
            "min_history": 50,
            "dedup_seconds": 5.0,
            "ai_timeout": 0.6,
            "vote_required_fraction": 0.6,  # fraction of registered strategies that must agree
            "min_confidence_to_send": 0.6,
            "strategy_name": "base_strategy_ai",
            **(cfg or {}),
        }

    # ---------------------------
    # Strategy integration API
    # ---------------------------
    def register_strategy_info(self, strategy_name: str, info: Dict[str, Any]) -> None:
        """
        Outras strategies chamam isso para fornecer um 'vote'/'conf' que será usado como meta-feature.
        Exemplo info: {"vote":"BUY","conf":0.6,"reason":"supertrend:up"}
        """
        with self._lock:
            self._registered_meta[strategy_name] = info.copy()
            logger.debug("[%s] registered meta from %s: %s", self.symbol, strategy_name, info)

    def clear_registered_info(self):
        with self._lock:
            self._registered_meta.clear()

    def get_registered_votes(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._registered_meta)

    # ---------------------------
    # Helpers - indicator computations
    # ---------------------------
    @staticmethod
    def _ema(series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        roll_gain = gain.rolling(period).mean()
        roll_loss = loss.rolling(period).mean() + 1e-9
        rs = roll_gain / roll_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(n).mean().fillna(method="bfill").fillna(1e-9)

    # ---------------------------
    # Main indicator builder (fast, vectorized)
    # ---------------------------
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if len(df) < int(self.cfg["min_history"]):
            return df

        # EMA/EMA_DIFF
        df["ema_12"] = self._ema(df["close"], 12)
        df["ema_26"] = self._ema(df["close"], 26)
        df["ema_diff"] = df["ema_12"] - df["ema_26"]

        # RSI
        df["rsi"] = self._rsi(df["close"], 14)

        # ATR
        df["atr"] = self._atr(df, 14).clip(lower=self.MIN_ATR)

        # Bollinger
        df["bb_mid"] = df["close"].rolling(20).mean()
        df["bb_std"] = df["close"].rolling(20).std().fillna(method="bfill")
        df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
        df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]

        # integrate other strategies meta-features (not their full indicators)
        with self._lock:
            for sname, info in self._registered_meta.items():
                try:
                    vote_col = f"meta_{sname}_vote"
                    conf_col = f"meta_{sname}_conf"
                    vote_val = 0
                    if info.get("vote") in ("BUY", "LONG", 1):
                        vote_val = 1
                    elif info.get("vote") in ("SELL", "SHORT", -1):
                        vote_val = -1
                    df[vote_col] = vote_val
                    df[conf_col] = float(info.get("conf", 0.0))
                except Exception:
                    continue

        df = df.replace([np.inf, -np.inf], np.nan).dropna()
        return df

    # ---------------------------
    # Quick fetch helper (if user passes market_data provider)
    # ---------------------------
    def _ensure_ohlcv(self, df: Optional[pd.DataFrame], bars: int = 300) -> pd.DataFrame:
        if df is not None and len(df) >= self.cfg["min_history"]:
            return df
        if self.market_data and hasattr(self.market_data, "get_ohlcv"):
            try:
                df2 = self.market_data.get_ohlcv(self.symbol, bars=bars)
                return df2
            except Exception as e:
                logger.debug("[%s] market_data.get_ohlcv failed: %s", self.symbol, e)
        return pd.DataFrame()  # empty

    # ---------------------------
    # Voting / consensus helpers
    # ---------------------------
    def _collect_votes(self, action: str) -> Dict[str, Any]:
        """
        Return structure with counts and average confidence from registered meta strategies.
        """
        with self._lock:
            votes = {"count": 0, "sum_conf": 0.0, "sources": {}}
            for name, info in self._registered_meta.items():
                vote = info.get("vote")
                conf = float(info.get("conf", 0.0))
                if vote and ((vote == "BUY" and action == "BUY") or (vote == "SELL" and action == "SELL")):
                    votes["count"] += 1
                    votes["sum_conf"] += conf
                    votes["sources"][name] = {"vote": vote, "conf": conf}
            votes["avg_conf"] = (votes["sum_conf"] / votes["count"]) if votes["count"] > 0 else 0.0
            votes["total_registered"] = len(self._registered_meta)
            return votes

    # ---------------------------
    # Main generator - improved logic
    # ---------------------------
    def generate_signal(self, df: Optional[pd.DataFrame] = None, source: Optional[str] = None) -> Optional[Signal]:
        """
        Produces a Signal or None.
        - df optional: if omitted, tries to fetch from market_data provider
        - Source: identifier who requested (StrategyEngine / manual / backtester)
        """
        try:
            df = self._ensure_ohlcv(df)
            if df is None or len(df) < int(self.cfg["min_history"]):
                logger.debug("[%s] insufficient history for %s", self.symbol, self.cfg["strategy_name"])
                return None

            df_ind = self.compute_indicators(df)
            if df_ind.empty:
                return None
            last = df_ind.iloc[-1]
            price = float(last["close"])

            # Base heuristics (RSI + EMA diff) produce base action/confidence
            action = "HOLD"
            conf = 0.0
            if last["rsi"] > 70:
                action = "SELL"
                conf = min(1.0, 0.5 + (last["rsi"] - 70) / 60.0)
            elif last["rsi"] < 30:
                action = "BUY"
                conf = min(1.0, 0.5 + (30 - last["rsi"]) / 60.0)

            if action == "HOLD":
                if last["ema_diff"] > 0:
                    action = "BUY"
                    conf = max(conf, 0.55)
                elif last["ema_diff"] < 0:
                    action = "SELL"
                    conf = max(conf, 0.55)

            # include registered strategies votes into confidence (meta-feature fusion)
            meta_votes_info = self.get_registered_votes()
            # if many strategies voted, increase confidence proportionally
            reg_total = max(1, len(meta_votes_info))
            agree = 0
            sum_conf = 0.0
            for name, inf in meta_votes_info.items():
                if inf.get("vote") == action:
                    agree += 1
                    sum_conf += float(inf.get("conf", 0.0))
            if agree > 0:
                conf = min(1.0, max(conf, (conf + (sum_conf / (agree + 1))) / 2.0))

            # prepare TP/SL using ATR
            atr = max(float(last.get("atr", self.MIN_ATR)), self.MIN_ATR)
            tp, sl = None, None
            if action == "BUY":
                tp = price + 1.5 * atr
                sl = price - 1.0 * atr
            elif action == "SELL":
                tp = price - 1.5 * atr
                sl = price + 1.0 * atr

            # AIManager validation (if available) - ask with minimal timeout
            approved_by_ai = None
            ai_votes = []
            if self.ai_manager:
                try:
                    payload = {
                        "symbol": self.symbol,
                        "action": action,
                        "price": price,
                        "confidence": round(conf, 3),
                        "strategy": self.cfg["strategy_name"],
                        "meta_votes": meta_votes_info
                    }
                    result = self.ai_manager.evaluate_signal(payload, timeout=float(self.cfg["ai_timeout"]))
                    approved_by_ai = bool(result.get("approved")) if isinstance(result, dict) else None
                    ai_votes = result.get("votes", []) if isinstance(result, dict) else []
                except Exception as e:
                    logger.debug("[%s] ai_manager evaluate_signal failed: %s", self.symbol, e)
                    approved_by_ai = None

            # finalize consensus: require either AI approval or fraction of registered strategies
            registered_total = len(meta_votes_info)
            req_fraction = float(self.cfg["vote_required_fraction"])
            votes_for_action = (agree / max(1, registered_total)) if registered_total > 0 else 0.0
            consensus_ok = False
            if approved_by_ai is True:
                consensus_ok = True
            elif registered_total > 0 and votes_for_action >= req_fraction and conf >= float(self.cfg["min_confidence_to_send"]):
                consensus_ok = True
            elif registered_total == 0 and conf >= float(self.cfg["min_confidence_to_send"]):
                # standalone strategy: needs min confidence
                consensus_ok = True

            # deduplicate / rate-limit
            sig_id = f"{self.symbol}-{action}-{int(price*1e5)}"
            now = time.time()
            with self._lock:
                last_ts = self._seen_signatures.get(sig_id, 0)
                if now - last_ts < float(self.cfg["dedup_seconds"]):
                    logger.debug("[%s] dedup skip %s", self.symbol, sig_id)
                    return None
                self._seen_signatures[sig_id] = now

            # If consensus achieved and action is not HOLD, send signal
            if consensus_ok and action != "HOLD":
                sig = Signal(
                    symbol=self.symbol,
                    action=action,
                    confidence=float(round(conf, 4)),
                    price=price,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    strategy=self.cfg["strategy_name"],
                    tp=float(round(tp, 6)) if tp is not None else None,
                    sl=float(round(sl, 6)) if sl is not None else None,
                    metadata={"registered_total": registered_total, "ai_votes": ai_votes},
                    meta_votes=meta_votes_info,
                    source=source or self.cfg["strategy_name"]
                )
                # send asynchronously via SignalSender
                try:
                    self.sender.enqueue(sig.to_dict())
                except Exception as e:
                    logger.debug("[%s] enqueue failed: %s", self.symbol, e)
                logger.info("[%s] signal generated: %s", self.symbol, {"action": action, "conf": conf, "registered_total": registered_total})
                return sig

            # otherwise no signal
            logger.debug("[%s] no consensus | action=%s conf=%.3f votes=%.3f ai_ok=%s", self.symbol, action, conf, (agree / max(1, registered_total)), approved_by_ai)
            return None

        except Exception as e:
            logger.exception("[%s] generate_signal failed: %s", self.symbol, e)
            return None

    # ---------------------------
    # Utility / status
    # ---------------------------
    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "symbol": self.symbol,
                "registered_meta": dict(self._registered_meta),
                "seen_signatures": dict(self._seen_signatures),
                "sender_stats": getattr(self.sender, "stats", {}),
                "cfg": self.cfg,
            }
