# strategies/buy_low_sell_high_ai_hardcore.py
from __future__ import annotations
import time
import json
import logging
import threading
import random
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import pandas as pd
import numpy as np

logger = logging.getLogger("BuyLowSellHighAI")
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    logger.addHandler(sh)
logger.setLevel(logging.INFO)


@dataclass
class Signal:
    symbol: str
    action: str                # "BUY" | "SELL"
    confidence: float          # 0..1
    entry_price: float
    tp: float
    sl: float
    lot_size: float
    timestamp: str
    strategy: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    meta_votes: Dict[str, Any] = field(default_factory=dict)
    ai_votes: List[str] = field(default_factory=list)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "tp": self.tp,
            "sl": self.sl,
            "lot_size": self.lot_size,
            "timestamp": self.timestamp,
            "strategy": self.strategy,
            "metadata": self.metadata,
            "meta_votes": self.meta_votes,
            "ai_votes": self.ai_votes,
            "reason": self.reason,
        }


class SocketClient:
    def __init__(self, host="127.0.0.1", port=9090, timeout=0.5, retries=1):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries

    def send_request(self, payload: Dict) -> Dict:
        import socket
        data = json.dumps(payload).encode("utf-8")
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                    s.sendall(data + b"\n")
                    s.settimeout(self.timeout)
                    resp = s.recv(65536)
                    if resp:
                        return json.loads(resp.decode("utf-8"))
                    return {"status": "error", "reason": "no_response"}
            except Exception as e:
                last_exc = e
                time.sleep(0.05 + random.random() * 0.05)
        logger.debug("SocketClient failed: %s", last_exc)
        return {"status": "error", "reason": str(last_exc)}


class BuyLowSellHighAI:
    """
    Hardcore BuyLowSellHigh strategy:
    - Uses RSI, MACD, ATR, ADX, Volume spike and simple FVG detection.
    - Integrates votes from other strategies and AIManager.
    - Conservative risk defaults; auditable output.
    """

    DEFAULTS = dict(
        short_ema=12, long_ema=26,
        macd_fast=12, macd_slow=26, macd_signal=9,
        rsi_period=14, rsi_overbought=70, rsi_oversold=30,
        atr_period=14, adx_period=14,
        volume_spike_mult=2.0,
        min_confidence=0.55, lookback=400, default_lots=0.01,
        sock_host="127.0.0.1", sock_port=9090, sock_timeout_s=0.5, sock_retries=1,
        ai_timeout=0.6,
        lot_cap=0.10, lot_base=0.01,
        dedup_seconds=1.0,
        min_bars=60,
        fvg_lookback=6,  # how many recent bars to check for FVG
    )

    def __init__(
        self,
        symbol: str,
        ai_manager: Optional[Any] = None,
        other_strategies: Optional[List[Any]] = None,
        market_data: Optional[Any] = None,
        cfg: Optional[Dict[str, Any]] = None
    ):
        self.symbol = symbol
        self.cfg = {**self.DEFAULTS, **(cfg or {})}
        self.client = SocketClient(self.cfg["sock_host"], self.cfg["sock_port"], self.cfg["sock_timeout_s"], self.cfg["sock_retries"])
        self.ai_manager = ai_manager
        self.other_strategies = other_strategies or []
        self.market_data = market_data
        self.executor = ThreadPoolExecutor(max_workers=3)
        self._seen_signals: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._registered_meta: Dict[str, Dict[str, Any]] = {}  # name -> {vote,conf}
        logger.info("BuyLowSellHighAI initialized for %s", self.symbol)

    # ---------- public API for other strategies to publish simple votes/meta ----------
    def register_strategy_info(self, strategy_name: str, info: Dict[str, Any]) -> None:
        """Other strategies call this to publish their vote: {'vote':'BUY'|'SELL', 'conf':0.6}"""
        with self._lock:
            self._registered_meta[strategy_name] = dict(info)
            logger.debug("[%s] registered meta %s -> %s", self.symbol, strategy_name, info)

    def clear_registered_info(self):
        with self._lock:
            self._registered_meta.clear()

    def get_registered_votes(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._registered_meta)

    # ---------- indicators ----------
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if len(df) < max(self.cfg["min_bars"], 30):
            return df

        # EMA diff
        df["ema_short"] = df["close"].ewm(span=self.cfg["short_ema"], adjust=False).mean()
        df["ema_long"] = df["close"].ewm(span=self.cfg["long_ema"], adjust=False).mean()
        df["ema_diff"] = df["ema_short"] - df["ema_long"]

        # RSI
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        df["rsi"] = 100 - (100 / (1 + (gain.rolling(self.cfg["rsi_period"]).mean() / (loss.rolling(self.cfg["rsi_period"]).mean() + 1e-9))))

        # ATR
        hl = df["high"] - df["low"]
        hc = (df["high"] - df["close"].shift()).abs()
        lc = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df["atr"] = tr.rolling(self.cfg["atr_period"]).mean().fillna(method="bfill").fillna(1e-9)

        # MACD
        fast = df["close"].ewm(span=self.cfg["macd_fast"], adjust=False).mean()
        slow = df["close"].ewm(span=self.cfg["macd_slow"], adjust=False).mean()
        macd = fast - slow
        signal = macd.ewm(span=self.cfg["macd_signal"], adjust=False).mean()
        df["macd"] = macd
        df["macd_signal"] = signal
        df["macd_hist"] = macd - signal

        # ADX (rudimentary)
        up = df["high"].diff().fillna(0)
        down = -df["low"].diff().fillna(0)
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)
        tr_smooth = df["atr"].replace(0, 1e-9)
        plus_di = 100 * pd.Series(plus_dm).rolling(self.cfg["adx_period"]).sum().fillna(0) / (tr_smooth + 1e-9)
        minus_di = 100 * pd.Series(minus_dm).rolling(self.cfg["adx_period"]).sum().fillna(0) / (tr_smooth + 1e-9)
        df["adx"] = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)).fillna(0)

        # Volume spike
        if "volume" in df.columns:
            df["vol_spike"] = df["volume"] / (df["volume"].rolling(20).mean().replace(0, np.nan) + 1e-9)
        else:
            df["vol_spike"] = 1.0

        # Merge small meta features from other strategies (last known vote/conf)
        with self._lock:
            for name, info in self._registered_meta.items():
                vote_col = f"meta_{name}_vote"
                conf_col = f"meta_{name}_conf"
                vote_val = 0
                if info.get("vote") in ("BUY", "LONG", 1):
                    vote_val = 1
                elif info.get("vote") in ("SELL", "SHORT", -1):
                    vote_val = -1
                df[vote_col] = vote_val
                df[conf_col] = float(info.get("conf", 0.0))

        df = df.replace([np.inf, -np.inf], np.nan).dropna()
        return df

    # ---------- Fair Value Gap simple detector ----------
    def detect_fvg(self, df: pd.DataFrame, lookback: int = 6) -> Dict[str, bool]:
        """
        Simple FVG check:
        - bullish FVG: exists if there was a bearish candle followed by a gap up where low of current bar > high of prior
          (we check a small window). This is a heuristic, not institutional FVG.
        - returns dict {"bull_fvg": bool, "bear_fvg": bool}
        """
        out = {"bull_fvg": False, "bear_fvg": False}
        if len(df) < 3:
            return out
        # look at the most recent N bars
        recent = df.tail(lookback).reset_index(drop=True)
        # bullish gap: a large down candle then price gapped above its high (implies imbalance)
        for i in range(2, len(recent)):
            prev = recent.loc[i - 2]
            mid = recent.loc[i - 1]
            cur = recent.loc[i]
            # bearish -> bullish gap
            if (prev["close"] < prev["open"]) and (cur["low"] > prev["high"]):
                out["bull_fvg"] = True
            # bullish -> bearish gap
            if (prev["close"] > prev["open"]) and (cur["high"] < prev["low"]):
                out["bear_fvg"] = True
        return out

    # ---------- ask AIManager (async with timeout) ----------
    def _ask_ai(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ask ai_manager.evaluate_signal in a thread to avoid blocking main loop."""
        if not self.ai_manager:
            return {}
        try:
            fut = self.executor.submit(lambda: self.ai_manager.evaluate_signal(payload, timeout=self.cfg["ai_timeout"]))
            return fut.result(timeout=self.cfg["ai_timeout"] + 0.1)
        except FuturesTimeout:
            logger.warning("[%s] AIManager timeout", self.symbol)
            return {"error": "timeout"}
        except Exception as e:
            logger.debug("[%s] AIManager call failed: %s", self.symbol, e)
            return {"error": str(e)}

    # ---------- lot sizing policy ----------
    def _estimate_lot_size(self, confidence: float, ai_approved: bool) -> float:
        base = float(self.cfg["lot_base"])
        cap = float(self.cfg["lot_cap"])
        # conservative mapping
        if confidence < 0.55:
            return base
        if confidence < 0.70:
            target = base * 2
        elif confidence < 0.85:
            target = base * 3
        else:
            target = base * 5
        # require ai approval to go above base*2
        if target > base * 2 and not ai_approved:
            target = base * 2
        return round(min(target, cap), 4)

    # ---------- dedupe helper ----------
    def _dedupe_check(self, action: str, price: float) -> bool:
        sig_id = f"{self.symbol}-{action}-{int(price*1e5)}"
        now = time.time()
        with self._lock:
            last = self._seen_signals.get(sig_id, 0.0)
            if now - last < float(self.cfg["dedup_seconds"]):
                return False
            self._seen_signals[sig_id] = now
        return True

    # ---------- main generator ----------
    def generate_signal(self, df: Optional[pd.DataFrame]) -> Optional[Signal]:
        """
        Primary entry:
         - df: OHLCV pandas DataFrame (index sequential, columns: open,high,low,close,volume)
         - returns Signal or None
        """
        try:
            # ensure data
            if df is None or len(df) < self.cfg["min_bars"]:
                # try market_data provider if configured
                if self.market_data and hasattr(self.market_data, "get_ohlcv"):
                    try:
                        df = self.market_data.get_ohlcv(self.symbol, bars=self.cfg["lookback"])
                    except Exception:
                        return None
                else:
                    return None

            df = df.tail(self.cfg["lookback"]).copy()
            df_ind = self.compute_indicators(df)
            if df_ind.empty:
                return None
            last = df_ind.iloc[-1]
            price = float(last["close"])

            # Base heuristics -> action/conf
            action = "HOLD"
            conf = 0.0

            # RSI extremes strongly influence
            if last["rsi"] >= self.cfg["rsi_overbought"]:
                action = "SELL"
                conf = max(conf, min(1.0, 0.5 + (last["rsi"] - self.cfg["rsi_overbought"]) / 60.0))
            elif last["rsi"] <= self.cfg["rsi_oversold"]:
                action = "BUY"
                conf = max(conf, min(1.0, 0.5 + (self.cfg["rsi_oversold"] - last["rsi"]) / 60.0))

            # EMA & MACD confirmations
            if action == "HOLD":
                if last["ema_diff"] > 0 and last["macd_hist"] > 0:
                    action = "BUY"
                    conf = max(conf, 0.55)
                elif last["ema_diff"] < 0 and last["macd_hist"] < 0:
                    action = "SELL"
                    conf = max(conf, 0.55)

            # volume spike increases confidence
            if float(last.get("vol_spike", 1.0)) > self.cfg["volume_spike_mult"]:
                conf = min(1.0, conf + 0.15)

            # ADX: if trend strong, increase weight of ema/macd
            if float(last.get("adx", 0.0)) > 25 and action != "HOLD":
                conf = min(1.0, conf + 0.10)

            # FVG: if FVG aligns with action, increase confidence
            fvg = self.detect_fvg(df, lookback=self.cfg["fvg_lookback"])
            if action == "BUY" and fvg.get("bull_fvg"):
                conf = min(1.0, conf + 0.12)
            if action == "SELL" and fvg.get("bear_fvg"):
                conf = min(1.0, conf + 0.12)

            if action == "HOLD" or conf < self.cfg["min_confidence"]:
                return None

            # incorporate other strategies votes (meta_features)
            meta = self.get_registered_votes()
            agree = 0
            sum_conf = 0.0
            for name, info in meta.items():
                if info.get("vote") == action:
                    agree += 1
                    sum_conf += float(info.get("conf", 0.0))
            meta_avg_conf = (sum_conf / agree) if agree > 0 else 0.0
            # blend meta average
            if agree > 0:
                conf = min(1.0, (conf + meta_avg_conf) / 2.0)

            # ask AIManager
            ai_payload = {
                "symbol": self.symbol,
                "action": action,
                "price": price,
                "confidence": round(float(conf), 3),
                "strategy": "BuyLowSellHighAI",
                "meta_votes": meta,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            ai_res = self._ask_ai(ai_payload)
            ai_votes = ai_res.get("votes") if isinstance(ai_res, dict) else []
            ai_approved = bool(ai_res.get("approved")) if isinstance(ai_res, dict) else False

            # final consensus rule:
            # - if AI explicitly approves -> pass
            # - else require conf >= min_confidence and (either some meta agree or ai_votes majority)
            meta_total = len(meta)
            meta_fraction = (agree / meta_total) if meta_total > 0 else 0.0
            ai_vote_majority = False
            if isinstance(ai_votes, list) and len(ai_votes) > 0:
                if action == "BUY":
                    ai_vote_majority = ai_votes.count("BUY") >= max(1, (len(ai_votes)//2)+1)
                elif action == "SELL":
                    ai_vote_majority = ai_votes.count("SELL") >= max(1, (len(ai_votes)//2)+1)

            consensus_ok = False
            if ai_approved:
                consensus_ok = True
            elif meta_total > 0 and meta_fraction >= 0.5 and conf >= self.cfg["min_confidence"]:
                consensus_ok = True
            elif ai_vote_majority and conf >= self.cfg["min_confidence"]:
                consensus_ok = True
            elif meta_total == 0 and conf >= 0.8:
                # standalone strong signal
                consensus_ok = True

            if not consensus_ok:
                logger.debug("[%s] no consensus action=%s conf=%.3f meta_frac=%.2f ai_ok=%s", self.symbol, action, conf, meta_fraction, ai_approved)
                return None

            # prepare TP/SL using ATR
            atr = float(last["atr"])
            if action == "BUY":
                tp = price + 2.0 * atr
                sl = price - 1.0 * atr
            else:
                tp = price - 2.0 * atr
                sl = price + 1.0 * atr

            # final lot sizing
            lot = self._estimate_lot_size(conf, ai_approved)

            # dedupe
            if not self._dedupe_check(action, price):
                return None

            sig = Signal(
                symbol=self.symbol,
                action=action,
                confidence=float(round(conf, 4)),
                entry_price=price,
                tp=float(round(tp, 6)),
                sl=float(round(sl, 6)),
                lot_size=float(lot),
                timestamp=datetime.utcnow().isoformat() + "Z",
                strategy="BuyLowSellHighAI",
                metadata={
                    "rsi": float(last["rsi"]),
                    "ema_diff": float(last["ema_diff"]),
                    "macd_hist": float(last["macd_hist"]),
                    "vol_spike": float(last.get("vol_spike", 1.0)),
                    "fvg": fvg,
                },
                meta_votes=meta,
                ai_votes=ai_votes or [],
                reason=f"consensus_ok ai_approved={ai_approved} meta_fraction={meta_fraction:.2f}"
            )

            # async send to socket (non-blocking)
            try:
                self.executor.submit(self._send_signal_socket, sig.to_dict())
            except Exception:
                logger.debug("[%s] failed to submit socket send", self.symbol)

            logger.info("[%s] generated signal: %s", self.symbol, {"action": action, "conf": conf, "lot": lot, "reason": sig.reason})
            return sig

        except Exception as e:
            logger.exception("[%s] generate_signal exception: %s", self.symbol, e)
            return None

    def _send_signal_socket(self, payload: Dict[str, Any]) -> None:
        try:
            self.client.send_request({
                "type": "trade_signal",
                "strategy": "BuyLowSellHighAI",
                "signals": [payload],
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.debug("[%s] socket send exception: %s", self.symbol, e)

    # ---------- status ----------
    def get_status(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "cfg": self.cfg,
            "registered_meta": self.get_registered_votes(),
            "seen_signals": dict(self._seen_signals),
        }
