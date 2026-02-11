# strategies/rsi_strategy_improved.py
"""
RSI Divergence Pro - Advanced, AI-aware and Multi-Source Consensus Strategy
Hardened / fixes for symmetric BUY/SELL signals, robust payloads and normalization
Generated: 2026-01-02
"""
from __future__ import annotations
import json
import logging
import time
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

# prefer project models if available
try:
    from strategies.models import TradeSignal, TradeDirection, OrderType, AccountInfo  # type: ignore
    HAS_TRADE_SIGNAL = True
except Exception:
    HAS_TRADE_SIGNAL = False
    from enum import Enum

    class TradeDirection(Enum):
        BUY = "BUY"; SELL = "SELL"; HOLD = "HOLD"
        @classmethod
        def from_any(cls, v: Any) -> "TradeDirection":
            if isinstance(v, cls): return v
            if v is None: return cls.HOLD
            s = str(v).strip().upper()
            if s in ("BUY","LONG","B"): return cls.BUY
            if s in ("SELL","SHORT","S"): return cls.SELL
            return cls.HOLD
    @dataclass
    class TradeSignal:
        symbol: str
        direction: Union[TradeDirection, str]
        lot_size: float = 0.01
        order_type: str = "MARKET"
        entry_price: Optional[float] = None
        sl: Optional[float] = None
        tp: Optional[float] = None
        strategy: Optional[str] = None
        confidence: Optional[float] = None
        metadata: Dict[str, Any] = field(default_factory=dict)
        timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

        def to_payload(self) -> Dict[str, Any]:
            return {
                "symbol": self.symbol,
                "direction": (self.direction.value if hasattr(self.direction, "value") else str(self.direction)),
                "order_type": str(self.order_type),
                "lot_size": float(self.lot_size),
                "entry_price": self.entry_price,
                "sl": self.sl,
                "tp": self.tp,
                "strategy": self.strategy,
                "confidence": self.confidence,
                "metadata": self.metadata or {},
                "timestamp": self.timestamp.isoformat()
            }

# optional heavy deps
try:
    import numpy as np  # type: ignore
    import pandas as pd  # type: ignore
    HAS_PANDAS = True
except Exception:
    HAS_PANDAS = False

ROOT_DIR = Path(__file__).parent
log = logging.getLogger("strategy.rsi_divergence_pro")
if not log.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    log.addHandler(sh)
log.setLevel(logging.INFO)

# small socket sender for optional auto_send
class SocketClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 9090, timeout: float = 0.5, retries: int = 2, backoff: float = 0.15):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff

    def send(self, payload: Union[str, bytes, Dict]) -> bool:
        data = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
        last_ex = None
        for attempt in range(self.retries + 1):
            try:
                with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                    if isinstance(data, str):
                        data_b = data.encode("utf-8")
                    else:
                        data_b = data
                    s.sendall(data_b)
                log.debug("SocketClient: sent payload")
                return True
            except Exception as e:
                last_ex = e
                log.debug("SocketClient attempt %d failed: %s", attempt + 1, e)
                time.sleep(self.backoff)
        log.warning("SocketClient failed: %s", last_ex)
        return False

# constants / caps
MAX_LOT = 0.10
DEFAULT_MIN_CONF = 0.55
DEFAULT_COOLDOWN = 30.0

class RSIDivergenceStrategy:
    """
    Advanced RSI divergence strategy with AI & peers integration.
    Hardened so sellers also appear symmetrically and payloads are normalized.
    """
    DEFAULTS = {
        "rsi_period": 14,
        "lookback_period": 40,
        "oversold": 30,
        "overbought": 70,
        "min_confidence": DEFAULT_MIN_CONF,
        "cooldown_seconds": DEFAULT_COOLDOWN,
        "atr_period": 14,
        "extrema_window": 5,
        "min_history": 50,
        "ema_trend_period": 50,
        "volatility_threshold": 0.5,
        "peer_consensus_required": 0.6,
        "auto_send": True,
        "socket_host": "127.0.0.1",
        "socket_port": 9090,
        "debug": False,
        "multi_timeframe_confirm": False,
        "higher_tf_fetcher": None,
        "default_lot": 0.01,
    }

    def __init__(
        self,
        symbol: Optional[str] = None,
        timeframe: int = 15,
        ai_manager: Optional[Any] = None,
        mt5_comm: Optional[Any] = None,
        risk_manager: Optional[Any] = None,
        peer_signal_fetcher: Optional[Callable[[], List[Any]]] = None,
        **kwargs
    ):
        cfg = {**self.DEFAULTS, **kwargs}
        self.symbol = (symbol or "").upper() if symbol else None
        self.timeframe = timeframe
        self.ai_manager = ai_manager
        self.mt5_comm = mt5_comm
        self.risk_manager = risk_manager
        self.peer_signal_fetcher = peer_signal_fetcher
        self.higher_tf_fetcher = cfg.get("higher_tf_fetcher")

        # params
        self.rsi_period = int(cfg["rsi_period"])
        self.lookback_period = int(cfg["lookback_period"])
        self.oversold = int(cfg["oversold"])
        self.overbought = int(cfg["overbought"])
        self.min_confidence = float(cfg["min_confidence"])
        self.cooldown_seconds = float(cfg["cooldown_seconds"])
        self.atr_period = int(cfg["atr_period"])
        self.extrema_window = int(cfg["extrema_window"])
        self.min_history = int(cfg["min_history"])
        self.ema_trend_period = int(cfg["ema_trend_period"])
        self.volatility_threshold = float(cfg["volatility_threshold"])
        self.peer_consensus_required = float(cfg["peer_consensus_required"])
        self.auto_send = bool(cfg["auto_send"])
        self.socket_host = str(cfg["socket_host"])
        self.socket_port = int(cfg["socket_port"])
        self.debug = bool(cfg["debug"])
        self.multi_timeframe_confirm = bool(cfg["multi_timeframe_confirm"])
        self.default_lot = float(cfg.get("default_lot", 0.01))

        # runtime
        self._last_signal_ts: Dict[str, float] = {}
        self._seen_signatures: Dict[str, float] = {}
        self._metrics: Dict[str, int] = {"signals_generated": 0, "signals_sent": 0, "signals_blocked": 0}
        self._cooldown_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=int(cfg.get("max_workers", 4)))
        self._socket_client = SocketClient(self.socket_host, self.socket_port, timeout=0.5, retries=2)

        # logger
        self.logger = logging.getLogger(f"strategy.rsi_divergence_pro.{(self.symbol or 'GEN')}")
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        self.logger.info("RSI Divergence Pro init symbol=%s tf=%s rsi=%d", self.symbol, self.timeframe, self.rsi_period)

    # ----------------- utilities -----------------
    def _now(self) -> float:
        return time.monotonic()

    def _is_on_cooldown(self, symbol: str) -> bool:
        with self._cooldown_lock:
            last = self._last_signal_ts.get(symbol, 0.0)
            return (self._now() - last) < self.cooldown_seconds

    def _set_cooldown(self, symbol: str):
        with self._cooldown_lock:
            self._last_signal_ts[symbol] = self._now()

    def _normalize_symbol(self, s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        return str(s).upper().replace("/", "").replace("-", "").strip()

    def _clamp_lot(self, lot: float) -> float:
        if lot is None:
            return 0.0
        if lot <= 0:
            return 0.01
        return min(float(lot), MAX_LOT)

    def _normalize_volume_for_symbol(self, symbol: str, desired_lot: float) -> float:
        """
        Adjust lot to broker constraints using mt5_comm.symbol_info if available.
        Falls back to 0.01 steps if mt5_comm unavailable.
        """
        try:
            if not self.mt5_comm:
                return self._clamp_lot(desired_lot)
            info = None
            try:
                info = self.mt5_comm.symbol_info(symbol)
            except Exception:
                info = None
            if not info:
                return self._clamp_lot(desired_lot)
            # extract safely
            min_vol = float(getattr(info, "volume_min", 0.01) or 0.01)
            step = float(getattr(info, "volume_step", 0.01) or 0.01)
            max_vol = float(getattr(info, "volume_max", MAX_LOT) or MAX_LOT)
            if min_vol <= 0: min_vol = 0.01
            if step <= 0: step = 0.01
            if max_vol <= 0: max_vol = MAX_LOT
            # clamp desired lot
            lot = max(min_vol, min(desired_lot, max_vol))
            # floor to step
            steps = int(lot / step)
            if steps <= 0:
                steps = 1
            normalized = steps * step
            normalized = min(normalized, MAX_LOT)
            # round to step precision
            prec = max(0, int(round(-np.log10(step))) if HAS_PANDAS else 2)
            return round(float(normalized), prec)
        except Exception as e:
            self.logger.debug("normalize_volume_for_symbol failed: %s", e)
            return self._clamp_lot(desired_lot)

    # ----------------- indicators & helpers -----------------
    def _rsi_series(self, closes: List[float]) -> List[float]:
        if HAS_PANDAS:
            s = pd.Series(closes)
            delta = s.diff()
            up = delta.clip(lower=0).ewm(alpha=1/self.rsi_period, adjust=False).mean()
            down = (-delta.clip(upper=0)).ewm(alpha=1/self.rsi_period, adjust=False).mean()
            rs = up / (down.replace(0, 1e-12))
            rsi = 100 - 100 / (1 + rs)
            return rsi.fillna(50).tolist()
        # fallback
        gains = []
        losses = []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i - 1]
            gains.append(max(d, 0.0))
            losses.append(max(-d, 0.0))
        if len(gains) < self.rsi_period:
            return []
        avg_gain = sum(gains[:self.rsi_period]) / self.rsi_period
        avg_loss = sum(losses[:self.rsi_period]) / self.rsi_period
        rsi_vals = [50.0] * (self.rsi_period)
        for i in range(self.rsi_period, len(gains)):
            avg_gain = (avg_gain * (self.rsi_period - 1) + gains[i]) / self.rsi_period
            avg_loss = (avg_loss * (self.rsi_period - 1) + losses[i]) / self.rsi_period
            if avg_loss < 1e-12:
                rsi_vals.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_vals.append(100.0 - 100.0 / (1.0 + rs))
        return rsi_vals

    def _atr_value(self, highs: List[float], lows: List[float], closes: List[float]) -> float:
        if HAS_PANDAS:
            df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
            prev_close = df["close"].shift(1)
            tr = pd.concat([
                df["high"] - df["low"],
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(self.atr_period, min_periods=1).mean().iloc[-1]
            return float(atr if not pd.isna(atr) else 0.0)
        trs = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            trs.append(tr)
        if not trs:
            return 0.0
        return sum(trs[-self.atr_period:]) / min(len(trs), self.atr_period)

    def _ema(self, values: List[float], period: int) -> float:
        if not values or period <= 0:
            return 0.0
        if HAS_PANDAS:
            return float(pd.Series(values).ewm(span=period, adjust=False).mean().iloc[-1])
        alpha = 2.0 / (period + 1.0)
        ema = values[0]
        for v in values[1:]:
            ema = alpha * v + (1 - alpha) * ema
        return ema

    def _find_extrema(self, arr: List[float], window: int = 3) -> Tuple[List[int], List[int]]:
        mins = []
        maxs = []
        n = len(arr)
        half = max(1, window // 2)
        for i in range(half, n - half):
            left = arr[i-half:i]
            right = arr[i+1:i+1+half]
            val = arr[i]
            if val <= min(left + right):
                mins.append(i)
            if val >= max(left + right):
                maxs.append(i)
        return mins, maxs

    def _detect_divergence(self, closes: List[float], rsis: List[float]) -> Optional[TradeDirection]:
        """
        Robust symmetrical divergence detection returning BUY or SELL (TradeDirection).
        Uses lookback window but compares absolute values to avoid off-by-one bugs.
        """
        n = len(closes)
        if n < max(self.lookback_period, self.extrema_window*2 + 2):
            return None
        L = min(self.lookback_period, n)
        pr = closes[-L:]
        rr = rsis[-L:]
        p_mins, p_maxs = self._find_extrema(pr, window=self.extrema_window)
        r_mins, r_maxs = self._find_extrema(rr, window=self.extrema_window)
        # bullish divergence: price makes lower low while RSI makes higher low
        if len(p_mins) >= 2 and len(r_mins) >= 2:
            i1, i2 = p_mins[-2], p_mins[-1]
            # map to real values
            price1, price2 = pr[i1], pr[i2]
            rsi1, rsi2 = rr[i1], rr[i2]
            if price2 < price1 and rsi2 > rsi1 and rsi2 < self.oversold + 15:
                return TradeDirection.BUY
        # bearish divergence: price makes higher high while RSI makes lower high
        if len(p_maxs) >= 2 and len(r_maxs) >= 2:
            i1, i2 = p_maxs[-2], p_maxs[-1]
            price1, price2 = pr[i1], pr[i2]
            rsi1, rsi2 = rr[i1], rr[i2]
            if price2 > price1 and rsi2 < rsi1 and rsi2 > self.overbought - 15:
                return TradeDirection.SELL
        return None

    def _confidence(self, rsi_val: float, atr: float, peers_support: float = 0.0, trend_strength: float = 0.0) -> float:
        score = 0.0
        if rsi_val < self.oversold:
            score += min((self.oversold - rsi_val) / max(1.0, self.oversold), 1.0) * 0.5
        if rsi_val > self.overbought:
            score += min((rsi_val - self.overbought) / max(1.0, 100 - self.overbought), 1.0) * 0.5
        if atr > 0:
            score += 0.12
        score += peers_support * 0.2
        score += max(0.0, min(trend_strength, 0.2))
        return min(score, 0.99)

    # ----------------- main signal generation -----------------
    def generate_signal(
        self,
        market_data: Union["pd.DataFrame", List[Dict[str, Any]]],
        account: Optional[Any] = None,
        timeout_ai: float = 1.5
    ) -> Optional[TradeSignal]:
        symbol = self.symbol or None
        if not symbol:
            if HAS_PANDAS and isinstance(market_data, pd.DataFrame):
                symbol = getattr(market_data, "symbol", None) or None
            else:
                try:
                    if isinstance(market_data, list) and market_data:
                        symbol = market_data[-1].get("symbol")
                except Exception:
                    symbol = None
            if symbol:
                symbol = self._normalize_symbol(symbol)
                self.symbol = symbol
        if not symbol:
            self.logger.debug("generate_signal: no symbol known, abort")
            return None

        if self._is_on_cooldown(symbol):
            self.logger.debug("on cooldown %s", symbol)
            return None

        # extract OHLC lists
        try:
            if HAS_PANDAS and isinstance(market_data, pd.DataFrame):
                closes = market_data["close"].astype(float).tolist()
                highs = market_data["high"].astype(float).tolist()
                lows = market_data["low"].astype(float).tolist()
                volumes = market_data["volume"].astype(float).tolist() if "volume" in market_data.columns else [0.0]*len(closes)
            else:
                closes = [float(x["close"]) for x in market_data]
                highs = [float(x["high"]) for x in market_data]
                lows = [float(x["low"]) for x in market_data]
                volumes = [float(x.get("volume", 0.0)) for x in market_data]
        except Exception as e:
            self.logger.exception("Invalid market_data format: %s", e)
            return None

        if len(closes) < self.min_history:
            self.logger.debug("Not enough history (%d<%d)", len(closes), self.min_history)
            return None

        # compute indicators
        rsis = self._rsi_series(closes)
        if not rsis or len(rsis) < len(closes):
            rsis = [50.0] * (len(closes) - len(rsis)) + rsis if rsis else [50.0] * len(closes)
        atr = self._atr_value(highs, lows, closes)
        if HAS_PANDAS:
            recent_mean = float(pd.Series(closes[-20:]).mean()) if len(closes) >= 20 else float(pd.Series(closes).mean())
        else:
            recent_slice = closes[-20:] if len(closes) >= 20 else closes
            recent_mean = sum(recent_slice) / len(recent_slice) if recent_slice else 0.0

        ema_trend = self._ema(closes[-self.ema_trend_period*2:], self.ema_trend_period) if len(closes) >= self.ema_trend_period*2 else self._ema(closes, self.ema_trend_period)
        trend_strength = 0.0
        try:
            if len(closes) >= 50:
                ema_short = self._ema(closes[-10:], min(10, self.ema_trend_period))
                ema_long = self._ema(closes[-50:], max(50, self.ema_trend_period))
                trend_strength = max(0.0, min(0.2, abs(ema_short - ema_long) / max(1e-6, ema_long)))
        except Exception:
            trend_strength = 0.0

        # volatility filter
        if atr <= 0 or atr < (recent_mean * 1e-6):
            self.logger.debug("atr too small, skip")
            return None

        # detect divergence (BUY or SELL)
        direction = self._detect_divergence(closes, rsis)
        if direction is None:
            self.logger.debug("no divergence")
            return None

        # multi-timeframe optional confirmation
        if self.multi_timeframe_confirm and callable(self.higher_tf_fetcher):
            try:
                higher_df = self.higher_tf_fetcher(symbol, self.timeframe * 4)
                if higher_df is None or (HAS_PANDAS and len(higher_df) < self.min_history // 2):
                    self.logger.debug("no higher tf data")
                    return None
                hi_closes = higher_df["close"].astype(float).tolist() if HAS_PANDAS else [float(x["close"]) for x in higher_df]
                hi_rsis = self._rsi_series(hi_closes)
                hi_dir = self._detect_divergence(hi_closes, hi_rsis)
                if hi_dir is None or (hi_dir != direction):
                    self.logger.debug("higher TF not confirming")
                    return None
            except Exception as e:
                self.logger.debug("higher_tf confirmation failed: %s", e)

        # peer consensus
        peers = []
        try:
            if callable(self.peer_signal_fetcher):
                peers = self.peer_signal_fetcher() or []
        except Exception:
            peers = []
        peers_support = 0.0
        if peers:
            same = 0.0
            total = 0.0
            for p in peers:
                try:
                    pdirection = getattr(p, "direction", None) or (p.get("direction") if isinstance(p, dict) else None)
                    pconf = getattr(p, "confidence", None) or (p.get("confidence", 0.5) if isinstance(p, dict) else 0.5)
                    if isinstance(pdirection, str):
                        pdirection = pdirection.upper()
                    if isinstance(pdirection, TradeDirection):
                        pdirection = pdirection.value
                    if pdirection in ("BUY", "LONG") and direction == TradeDirection.BUY:
                        same += float(pconf or 0.5)
                    if pdirection in ("SELL", "SHORT") and direction == TradeDirection.SELL:
                        same += float(pconf or 0.5)
                    total += float(pconf or 0.5)
                except Exception:
                    continue
            if total > 0:
                peers_support = min(1.0, same / total if total > 0 else 0.0)

        # prepare signal
        entry = float(closes[-1])
        sl, tp = None, None
        if atr > 0:
            if direction == TradeDirection.BUY:
                sl = round(entry - atr * 1.5, 5)
                tp = round(entry + atr * 3.0, 5)
            else:
                sl = round(entry + atr * 1.5, 5)
                tp = round(entry - atr * 3.0, 5)

        confidence = self._confidence(rsis[-1], atr, peers_support, trend_strength)
        if confidence < self.min_confidence:
            self.logger.debug("confidence too low %.3f < %.3f", confidence, self.min_confidence)
            self._metrics["signals_blocked"] += 1
            return None

        payload = {
            "symbol": symbol,
            "strategy": "RSI_DIVERGENCE_PRO",
            "direction": (direction.value if hasattr(direction, "value") else str(direction)),
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "confidence": float(confidence),
            "metrics": {
                "atr": float(atr),
                "rsi": float(rsis[-1]),
                "peers_support": float(peers_support),
                "trend_strength": float(trend_strength)
            },
            "timeframe": self.timeframe,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        # ask AIManager for validation / adjustments (robust)
        ai_approved = True
        ai_reason = ""
        adjusted_payload = dict(payload)
        if self.ai_manager:
            try:
                fn = getattr(self.ai_manager, "evaluate_signal", None) or getattr(self.ai_manager, "request_trade_decision", None) or getattr(self.ai_manager, "request", None)
                if callable(fn):
                    def _call():
                        try:
                            return fn(payload, timeout=timeout_ai)
                        except TypeError:
                            return fn(payload)
                    fut = self._executor.submit(_call)
                    res = fut.result(timeout=timeout_ai + 0.3)
                    if isinstance(res, dict):
                        ai_approved = bool(res.get("approved", True))
                        ai_reason = str(res.get("reason", "") or "")
                        adj = res.get("adjusted_payload") or res.get("payload") or res.get("result")
                        if isinstance(adj, dict):
                            adjusted_payload.update(adj)
                else:
                    ai_approved = True
            except Exception as e:
                self.logger.debug("AIManager call failed: %s", e)
                ai_approved = (confidence >= min(0.8, 1.0))
                ai_reason = "ai_error"

        if not ai_approved:
            self.logger.info("AI rejected signal %s: %s", symbol, ai_reason)
            self._metrics["signals_blocked"] += 1
            return None

        # determine lot: risk_manager preferred, else default, then normalize to broker
        lot = float(self.default_lot)
        try:
            if self.risk_manager:
                ts_obj = TradeSignal(
                    symbol=symbol,
                    direction=direction,
                    lot_size=lot,
                    order_type=(OrderType.MARKET if HAS_TRADE_SIGNAL else "MARKET"),
                    entry_price=adjusted_payload.get("entry"),
                    sl=adjusted_payload.get("sl"),
                    tp=adjusted_payload.get("tp"),
                    strategy="RSI_DIVERGENCE_PRO",
                    confidence=float(confidence),
                    metadata=adjusted_payload.get("metrics", {})
                )
                suggested = None
                try:
                    suggested = self.risk_manager.evaluate_risk(ts_obj, account)  # type: ignore
                except Exception:
                    suggested = None
                if suggested:
                    lot = float(suggested)
        except Exception:
            lot = lot

        # account-aware cap via mt5_comm
        try:
            if self.mt5_comm and hasattr(self.mt5_comm, "get_account_info"):
                ai = self.mt5_comm.get_account_info()
                bal = float(ai.get("balance", 0.0) or 0.0)
                if bal > 0:
                    cap = max(0.01, min(MAX_LOT, bal * 0.0001))
                    lot = min(lot, cap)
        except Exception:
            pass

        # broker normalization
        lot = self._normalize_volume_for_symbol(symbol, lot)
        lot = self._clamp_lot(lot)

        # dedupe
        direction_str = (direction.value if hasattr(direction, "value") else str(direction)).upper()
        sig_key = f"{symbol}:{direction_str}:{round(entry,5)}:{round(confidence,3)}"
        now_ts = time.time()
        if now_ts - self._seen_signatures.get(sig_key, 0.0) < max(1.0, self.cooldown_seconds/4):
            self.logger.debug("duplicate recently seen -> skip")
            return None
        self._seen_signatures[sig_key] = now_ts

        # apply any AI-adjusted lot but force normalization/clamp
        if adjusted_payload.get("volume") is not None:
            try:
                req = float(adjusted_payload.get("volume"))
                lot = self._normalize_volume_for_symbol(symbol, req)
                lot = self._clamp_lot(lot)
            except Exception:
                pass
        if adjusted_payload.get("lot_size") is not None:
            try:
                req = float(adjusted_payload.get("lot_size"))
                lot = self._normalize_volume_for_symbol(symbol, req)
                lot = self._clamp_lot(lot)
            except Exception:
                pass

        # ensure SL/TP exist
        final_sl = adjusted_payload.get("sl", sl)
        final_tp = adjusted_payload.get("tp", tp)
        if final_sl is None or final_tp is None:
            # fallback conservative SL/TP
            if direction == TradeDirection.BUY:
                final_sl = round(entry - atr * 1.2, 5)
                final_tp = round(entry + atr * 2.0, 5)
            else:
                final_sl = round(entry + atr * 1.2, 5)
                final_tp = round(entry - atr * 2.0, 5)

        # build final TradeSignal
        final_signal = TradeSignal(
            symbol=symbol,
            direction=direction,
            lot_size=lot,
            order_type=(OrderType.MARKET if HAS_TRADE_SIGNAL else "MARKET"),
            entry_price=adjusted_payload.get("entry", entry),
            sl=final_sl,
            tp=final_tp,
            strategy="RSI_DIVERGENCE_PRO",
            confidence=float(confidence),
            metadata={"ai_reason": ai_reason, **adjusted_payload.get("metrics", {})}
        )

        self._metrics["signals_generated"] += 1

        # optional send via socket
        if self.auto_send and self._socket_client:
            try:
                payload_out = final_signal.to_payload()
                payload_out["volume"] = float(final_signal.lot_size)
                payload_out["direction"] = (direction_str)
                payload_out["source"] = "RSI_DIVERGENCE_PRO"
                if final_signal.lot_size <= MAX_LOT:
                    self._socket_client.send(payload_out)
                    self._metrics["signals_sent"] += 1
                else:
                    self.logger.warning("Auto-send blocked: lot > MAX_LOT (%s)", final_signal.lot_size)
            except Exception:
                self.logger.debug("socket send failed", exc_info=True)

        # cooldown and return
        self._set_cooldown(symbol)
        return final_signal

    def metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    def shutdown(self):
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass

# EOF
