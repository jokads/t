# strategies/ict_concepts_ai.py
from __future__ import annotations
import time
import math
import json
import random
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger("ICTConceptsAI")
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s | ICT | %(levelname)s | %(message)s"))
    logger.addHandler(sh)
logger.setLevel(logging.INFO)


@dataclass
class Signal:
    symbol: str
    action: str                 # "BUY" | "SELL"
    confidence: float           # 0..1
    entry: float
    tp: float
    sl: float
    lot_recommendation: float
    timestamp: str
    strategy: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    fvg_zones: List[Dict[str, Any]] = field(default_factory=list)
    order_blocks: List[Dict[str, Any]] = field(default_factory=list)
    smt_score: float = 0.0
    meta_votes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    ai_votes: List[str] = field(default_factory=list)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        # ensure json serializable
        d["timestamp"] = d["timestamp"]
        return d


class SocketClient:
    def __init__(self, host="127.0.0.1", port=9090, timeout=0.25, retries=1):
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
                time.sleep(0.03 + random.random() * 0.07)
        logger.debug("SocketClient failed: %s", last_exc)
        return {"status": "error", "reason": str(last_exc)}


class ICTConceptsAI:
    """
    ICT Concepts detection + AI-aware strategy.

    Usage:
        ict = ICTConceptsAI(symbol="EURUSD", ai_manager=ai_mgr, market_data=md)
        signal = ict.generate_signal(df=ohlcv_df)
    """
    DEFAULTS = dict(
        min_candles=80,
        lookback=200,
        fvg_window=3,
        ob_lookback=40,
        atr_period=14,
        min_confidence=0.55,
        ai_timeout=0.6,
        other_strat_timeout=0.2,
        lot_base=0.01,
        lot_cap=0.10,
        dedup_interval=2.0,
        socket_host="127.0.0.1",
        socket_port=9090,
        socket_timeout=0.25,
    )

    def __init__(self,
                 symbol: str,
                 ai_manager: Optional[Any] = None,
                 market_data: Optional[Any] = None,
                 other_strategies: Optional[List[Any]] = None,
                 cfg: Optional[Dict[str, Any]] = None):
        self.symbol = symbol
        self.cfg = {**self.DEFAULTS, **(cfg or {})}
        self.ai_manager = ai_manager
        self.market_data = market_data
        self.other_strategies = other_strategies or []
        self.client = SocketClient(self.cfg["socket_host"], self.cfg["socket_port"], self.cfg["socket_timeout"])
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._seen_signals: Dict[str, float] = {}
        self._signal_history: deque = deque(maxlen=500)
        self._registered_meta: Dict[str, Dict[str, Any]] = {}
        self._lock = None  # user may want their own lock; kept for API parity
        logger.info("ICTConceptsAI initialized for %s", self.symbol)

    # -----------------------
    # Public / integration API
    # -----------------------
    def register_strategy_info(self, name: str, info: Dict[str, Any]) -> None:
        """Other strategies can register votes/info here (meta-votes)."""
        self._registered_meta[name] = dict(info)

    def get_registered_votes(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._registered_meta)

    def clear_registered_info(self):
        self._registered_meta.clear()

    def get_status(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "cfg": self.cfg,
            "registered_meta_count": len(self._registered_meta),
            "history_len": len(self._signal_history),
        }

    # -----------------------
    # Indicators & detection
    # -----------------------
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Returns dataframe enriched with:
        - atr, sma, ema, swings, vol_spike, fvg candidacy flags
        """
        d = df.copy()
        if len(d) < self.cfg["min_candles"]:
            return pd.DataFrame()

        # basic EMAs
        d["ema_8"] = d["close"].ewm(span=8, adjust=False).mean()
        d["ema_21"] = d["close"].ewm(span=21, adjust=False).mean()
        # ATR
        hl = d["high"] - d["low"]
        hc = (d["high"] - d["close"].shift()).abs()
        lc = (d["low"] - d["close"].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        d["atr"] = tr.rolling(self.cfg["atr_period"]).mean().fillna(method="bfill").replace(0, 1e-9)
        # Vol spike
        if "volume" in d.columns:
            d["vol_spike"] = d["volume"] / (d["volume"].rolling(20).mean().replace(0, np.nan) + 1e-9)
        else:
            d["vol_spike"] = 1.0
        # swings (simple pivot detection)
        d["swing_high"] = d["high"][(d["high"].shift(1) < d["high"]) & (d["high"].shift(-1) < d["high"])]
        d["swing_low"] = d["low"][(d["low"].shift(1) > d["low"]) & (d["low"].shift(-1) > d["low"])]
        # remove inf/nans
        d = d.replace([np.inf, -np.inf], np.nan).dropna()
        return d

    def detect_bos(self, df: pd.DataFrame) -> Tuple[Optional[str], Optional[float]]:
        """
        Detect Break of Structure (BOS) using recent swings:
        returns ("BUY"/"SELL", break_price) or (None, None)
        """
        if len(df) < 6:
            return None, None
        # simple: compare last close to last visible swing high/low
        swings_highs = df["swing_high"].dropna().index
        swings_lows = df["swing_low"].dropna().index
        last_close = float(df["close"].iloc[-1])
        # breakout up if last close > recent swing high (excluding most recent bar)
        if not swings_highs.empty:
            last_sw_high_idx = swings_highs[-1]
            last_sw_high_price = float(df.loc[last_sw_high_idx, "high"])
            if last_close > last_sw_high_price:
                return "BUY", last_sw_high_price
        if not swings_lows.empty:
            last_sw_low_idx = swings_lows[-1]
            last_sw_low_price = float(df.loc[last_sw_low_idx, "low"])
            if last_close < last_sw_low_price:
                return "SELL", last_sw_low_price
        return None, None

    def detect_fvg(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detect Fair Value Gaps (FVG) heuristically:
        look for three-bar imbalance: bar i high < bar i+2 low (bullish FVG)
        or bar i low > bar i+2 high (bearish FVG).
        Returns list of zones (side, left, right, low, high)
        """
        zones = []
        w = self.cfg["fvg_window"]
        for i in range(len(df) - w):
            a = df.iloc[i]
            b = df.iloc[i + 1]
            c = df.iloc[i + 2]
            # bullish FVG: a.high < c.low (gap)
            if float(a["high"]) < float(c["low"]):
                low = float(a["high"])
                high = float(c["low"])
                zones.append({"type": "bullish", "index": i, "low": low, "high": high})
            # bearish FVG: a.low > c.high
            if float(a["low"]) > float(c["high"]):
                low = float(c["high"])
                high = float(a["low"])
                zones.append({"type": "bearish", "index": i, "low": low, "high": high})
        # return the most recent N zones (limit to 6)
        return zones[-6:]

    def detect_order_blocks(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Heuristic order-block detection:
        - look for recent bearish engulfing with high wick (supply OB)
        - or bullish engulfing (demand OB)
        - simpler approach but useful as a filter
        """
        obs = []
        lookback = min(self.cfg["ob_lookback"], len(df) - 3)
        for i in range(len(df) - lookback, len(df) - 1):
            prev = df.iloc[i]
            cur = df.iloc[i + 1]
            # bullish OB: cur.close > cur.open and cur body engulfs previous small body
            if (cur["close"] > cur["open"]) and (cur["close"] - cur["open"] > (prev["close"] - prev["open"]) * 1.2):
                obs.append({
                    "type": "demand",
                    "index": i + 1,
                    "low": float(min(cur["open"], cur["close"])),
                    "high": float(max(cur["open"], cur["close"]))
                })
            # bearish OB
            if (cur["close"] < cur["open"]) and ((cur["open"] - cur["close"]) > abs(prev["close"] - prev["open"]) * 1.2):
                obs.append({
                    "type": "supply",
                    "index": i + 1,
                    "low": float(min(cur["open"], cur["close"])),
                    "high": float(max(cur["open"], cur["close"]))
                })
        return obs[-6:]

    def detect_liquidity_sweep(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Detect quick wick that sweeps liquidity (wick > body*X) on last candle.
        Returns dict with side and size if detected.
        """
        last = df.iloc[-1]
        body = abs(last["close"] - last["open"]) + 1e-9
        upper_wick = float(last["high"]) - max(float(last["close"]), float(last["open"]))
        lower_wick = min(float(last["close"]), float(last["open"])) - float(last["low"])
        if upper_wick > body * 3:
            return {"side": "SELL", "size": upper_wick / (body + 1e-9)}
        if lower_wick > body * 3:
            return {"side": "BUY", "size": lower_wick / (body + 1e-9)}
        return None

    def detect_smt_score(self, df: pd.DataFrame) -> float:
        """
        Very simple SMT heuristic: if market_data provided and a correlated pair is available,
        compute return correlation over lookback; then score how instrument moves vs pair.
        Score in [-1,1] where positive means "in sync" (less interesting), negative means divergence (SMT)
        """
        if not self.market_data or not hasattr(self.market_data, "get_ohlcv_pair"):
            return 0.0
        try:
            other_df = self.market_data.get_ohlcv_pair(self.symbol)  # user-defined API expected
            if other_df is None or len(other_df) < 30:
                return 0.0
            look = min(len(df), len(other_df), 60)
            r1 = df["close"].pct_change().dropna().tail(look).values
            r2 = other_df["close"].pct_change().dropna().tail(look).values
            if len(r1) < 10 or len(r2) < 10:
                return 0.0
            corr = np.corrcoef(r1[-look:], r2[-look:])[0, 1]
            # if correlation suddenly low (<0.3) while price made big move -> SMT candidate
            last_move = df["close"].pct_change().tail(3).abs().sum()
            score = float(-corr) * min(1.0, last_move * 10.0)
            return max(-1.0, min(1.0, score))
        except Exception:
            return 0.0

    # -----------------------
    # safe call other strategies & ai
    # -----------------------
    def _call_other_strategy(self, strat, df: pd.DataFrame, timeout: float = 0.2) -> Optional[Dict[str, Any]]:
        try:
            if hasattr(strat, "generate_signal"):
                fut = self.executor.submit(lambda: strat.generate_signal(df))
                try:
                    res = fut.result(timeout=timeout)
                except FuturesTimeout:
                    return None
                if res is None:
                    return None
                if isinstance(res, dict):
                    return res
                if hasattr(res, "to_dict"):
                    return res.to_dict()
                try:
                    return dict(res.__dict__)
                except Exception:
                    return None
            elif hasattr(strat, "compute_indicators"):
                fut = self.executor.submit(lambda: strat.compute_indicators(df))
                try:
                    subdf = fut.result(timeout=timeout)
                except FuturesTimeout:
                    return None
                if isinstance(subdf, pd.DataFrame) and len(subdf) > 0:
                    last = subdf.iloc[-1]
                    # attempt to infer an action using simple heuristics
                    if "ema_diff" in last and "rsi" in last:
                        a = "BUY" if last["ema_diff"] > 0 else "SELL"
                        conf = float(min(1.0, abs(last["ema_diff"]) / (last.get("atr", 1e-9) + 1e-9)))
                        return {"action": a, "confidence": conf}
                return None
        except Exception as e:
            logger.debug("other strategy call failed: %s", e)
            return None

    def _ask_ai(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ask AIManager safely (timeout + exceptions)."""
        if not self.ai_manager:
            return {}
        try:
            fut = self.executor.submit(lambda: self.ai_manager.evaluate_signal(payload, timeout=self.cfg["ai_timeout"]))
            return fut.result(timeout=self.cfg["ai_timeout"] + 0.2)
        except FuturesTimeout:
            logger.warning("[%s] AIManager timeout", self.symbol)
            return {"error": "timeout"}
        except Exception as e:
            logger.debug("AIManager call failed: %s", e)
            return {"error": str(e)}

    # -----------------------
    # helper: lot suggestion
    # -----------------------
    def _suggest_lot(self, confidence: float, smt_score: float) -> float:
        base = float(self.cfg["lot_base"])
        cap = float(self.cfg["lot_cap"])
        # conservative mapping: base for <0.6, scale up for higher conf and negative smt (meaning divergence)
        if confidence < 0.55:
            return base
        if confidence < 0.7:
            target = base * 2
        elif confidence < 0.85:
            target = base * 3
        else:
            target = base * 4
        # if smt_score strongly negative (divergence), be slightly more aggressive
        if smt_score < -0.2:
            target = target * 1.25
        return round(min(target, cap), 4)

    # -----------------------
    # dedupe
    # -----------------------
    def _dedupe(self, action: str, price: float) -> bool:
        key = f"{self.symbol}-{action}-{int(price*1e5)}"
        now = time.time()
        last = self._seen_signals.get(key, 0.0)
        if now - last < float(self.cfg["dedup_interval"]):
            return False
        self._seen_signals[key] = now
        return True

    # -----------------------
    # main generator
    # -----------------------
    def generate_signal(self, df: Optional[pd.DataFrame] = None) -> Optional[Signal]:
        """
        Produces Signal dataclass (or None).
        Non-blocking / robust: uses market_data if df not provided.
        """
        try:
            # get data if not provided
            if df is None or len(df) < self.cfg["min_candles"]:
                if self.market_data and hasattr(self.market_data, "get_ohlcv"):
                    try:
                        df = self.market_data.get_ohlcv(self.symbol, bars=self.cfg["lookback"])
                    except Exception:
                        return None
                else:
                    return None

            df = df.copy().tail(self.cfg["lookback"])
            ind = self.compute_indicators(df)
            if ind.empty:
                return None

            # detections
            bos_action, bos_price = self.detect_bos(ind)
            fvg_zones = self.detect_fvg(ind)
            order_blocks = self.detect_order_blocks(ind)
            liq = self.detect_liquidity_sweep(ind)
            smt_score = self.detect_smt_score(ind)

            # decide action from BOS primarily, fallback to wick sweep + order block / fvg context
            action = None
            if bos_action:
                action = bos_action
            elif liq:
                action = liq["side"]
            else:
                # check most recent OB near price
                last_close = float(ind["close"].iloc[-1])
                for ob in reversed(order_blocks):
                    # if price within OB zone, choose the opposite (rejection) or same (break) heuristics
                    if ob["low"] - 1e-9 <= last_close <= ob["high"] + 1e-9:
                        action = "BUY" if ob["type"] == "demand" else "SELL"
                        break

            if action is None:
                return None

            # confidence heuristic
            atr = float(ind["atr"].iloc[-1])
            gap = abs(float(ind["ema_8"].iloc[-1] - ind["ema_21"].iloc[-1]))
            base_conf = float(min(1.0, (gap / (atr + 1e-9)) * 0.6 + 0.4))
            # boost if FVG in direction or OB confirm
            fvg_bonus = 0.12 if any(z["type"] == ("bullish" if action == "BUY" else "bearish") for z in fvg_zones[-3:]) else 0.0
            ob_bonus = 0.12 if any((ob["type"] == ("demand" if action == "BUY" else "supply")) for ob in order_blocks[-3:]) else 0.0
            liq_bonus = 0.08 if liq and liq["side"] == action else 0.0
            smt_bonus = 0.08 if smt_score < -0.2 and action == "BUY" else (0.08 if smt_score < -0.2 and action == "SELL" else 0.0)

            confidence = float(min(1.0, base_conf + fvg_bonus + ob_bonus + liq_bonus + smt_bonus))

            # gather meta votes from other strategies
            meta_results = {}
            agree = 0
            sum_conf = 0.0
            for strat in self.other_strategies:
                try:
                    out = self._call_other_strategy(strat, ind, timeout=self.cfg["other_strat_timeout"])
                    if out:
                        name = getattr(strat, "__name__", str(type(strat)))
                        a = out.get("action")
                        c = float(out.get("confidence", out.get("conf", 0.0) or 0.0))
                        meta_results[name] = {"action": a, "confidence": c}
                        if a == action:
                            agree += 1
                            sum_conf += c
                except Exception:
                    continue
            meta_avg_conf = (sum_conf / agree) if agree > 0 else 0.0
            if agree > 0:
                confidence = float(min(1.0, (confidence + meta_avg_conf) / 2.0))

            # prepare ai payload
            payload = {
                "symbol": self.symbol,
                "action": action,
                "entry": float(ind["close"].iloc[-1]),
                "confidence": round(confidence, 3),
                "strategy": "ICTConceptsAI",
                "indicators": {
                    "ema_gap": float(gap),
                    "atr": float(atr),
                    "last_vol_spike": float(ind["vol_spike"].iloc[-1]),
                    "fvg_count": len(fvg_zones),
                    "order_block_count": len(order_blocks),
                },
                "fvg_zones": fvg_zones[-3:],
                "order_blocks": order_blocks[-3:],
                "meta_votes": meta_results,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

            # ask AIManager
            ai_res = self._ask_ai(payload)
            ai_votes = ai_res.get("votes") if isinstance(ai_res, dict) else []
            ai_approved = bool(ai_res.get("approved")) if isinstance(ai_res, dict) else False

            # consensus rules: require either AI approval or simple majority from meta or high confidence
            consensus_ok = False
            if ai_approved:
                consensus_ok = True
            elif agree > 0 and (agree / max(1, len(self.other_strategies))) >= 0.5 and confidence >= self.cfg["min_confidence"]:
                consensus_ok = True
            elif confidence >= 0.85:
                consensus_ok = True

            if not consensus_ok:
                logger.debug("[%s] ICT consensus rejected (action=%s conf=%.3f ai_ok=%s meta_agree=%d)",
                             self.symbol, action, confidence, ai_approved, agree)
                return None

            # final TP/SL
            entry = float(ind["close"].iloc[-1])
            sl_dist = atr * 1.2
            tp_dist = atr * 2.6
            if action == "BUY":
                sl = entry - sl_dist
                tp = entry + tp_dist
            else:
                sl = entry + sl_dist
                tp = entry - tp_dist

            # lot suggestion
            lot = self._suggest_lot(confidence, smt_score)

            # dedupe
            if not self._dedupe(action, entry):
                return None

            # build signal
            sig = Signal(
                symbol=self.symbol,
                action=action,
                confidence=round(confidence, 4),
                entry=round(entry, 6),
                tp=round(tp, 6),
                sl=round(sl, 6),
                lot_recommendation=lot,
                timestamp=datetime.utcnow().isoformat() + "Z",
                strategy="ICTConceptsAI",
                indicators=payload["indicators"],
                fvg_zones=payload["fvg_zones"],
                order_blocks=payload["order_blocks"],
                smt_score=round(smt_score, 4),
                meta_votes=meta_results,
                ai_votes=ai_votes or [],
                reason=f"consensus ai_ok={ai_approved} agree={agree}"
            )

            # persist and async send
            self._signal_history.append(sig.to_dict())
            try:
                self.executor.submit(self._send_socket, {"type": "trade_signal", "strategy": "ICTConceptsAI", "signals": [sig.to_dict()], "timestamp": datetime.utcnow().isoformat()})
            except Exception:
                logger.debug("ICT: async send queue failed")

            logger.info("[%s] ICTConceptsAI -> %s conf=%.3f lot=%s fvg=%d ob=%d ai_ok=%s",
                        self.symbol, action, confidence, lot, len(fvg_zones), len(order_blocks), ai_approved)
            return sig

        except Exception as e:
            logger.exception("ICTConceptsAI generate_signal exception: %s", e)
            return None

    def _send_socket(self, payload: Dict[str, Any]) -> None:
        try:
            self.client.send_request(payload)
        except Exception as e:
            logger.debug("ICT socket send failed: %s", e)
