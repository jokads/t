# strategies/ema_crossover_ai.py
from __future__ import annotations
import pandas as pd
import numpy as np
import time
import logging
import threading
import json
import random
from datetime import datetime
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field

logger = logging.getLogger("EMA_CROSSOVER_AI")
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    logger.addHandler(sh)
logger.setLevel(logging.INFO)


@dataclass
class Signal:
    symbol: str
    action: str                 # "BUY" | "SELL"
    confidence: float           # 0..1
    entry_price: float
    tp: float
    sl: float
    lot_recommendation: float   # suggestion (RiskManager decides final)
    timestamp: str
    strategy: str
    indicators: Dict[str, float] = field(default_factory=dict)
    meta_votes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
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
            "lot_recommendation": self.lot_recommendation,
            "timestamp": self.timestamp,
            "strategy": self.strategy,
            "indicators": self.indicators,
            "meta_votes": self.meta_votes,
            "ai_votes": self.ai_votes,
            "reason": self.reason,
        }


class SocketClient:
    def __init__(self, host="127.0.0.1", port=9090, timeout=0.4, retries=1):
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


class EMA_CrossoverAI:
    DEFAULTS = dict(
        short=5, long=20,
        rsi_period=14, atr_period=14,
        macd_fast=12, macd_slow=26, macd_signal=9,
        vol_multiplier=2.0,
        min_conf=0.50,
        sock_host="127.0.0.1", sock_port=9090, sock_timeout=0.4, sock_retries=1,
        ai_timeout=0.6,
        dedup_interval=1.0, max_seen=200,
        lot_base=0.01, lot_cap=0.10,
        min_bars=60,
        other_strat_timeout=0.2
    )

    def __init__(self, symbol: str, ai_manager: Optional[Any] = None,
                 other_strategies: Optional[List[Any]] = None,
                 market_data: Optional[Any] = None,
                 cfg: Optional[Dict[str, Any]] = None):
        self.symbol = symbol
        self.cfg = {**self.DEFAULTS, **(cfg or {})}
        self.client = SocketClient(self.cfg["sock_host"], self.cfg["sock_port"], self.cfg["sock_timeout"], self.cfg["sock_retries"])
        self.ai_manager = ai_manager
        self.other_strategies = other_strategies or []
        self.market_data = market_data
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._seen_signals: Dict[str, float] = {}
        self._signal_history: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        # registered meta from other strategies (name -> {vote, conf})
        self._registered_meta: Dict[str, Dict[str, Any]] = {}
        logger.info("EMA_CROSSOVER_AI initialized for %s", self.symbol)

    # ----- public API ---------------------------------------------------
    def register_strategy_info(self, strategy_name: str, info: Dict[str, Any]) -> None:
        """Other strategies publish votes/info here: {'vote':'BUY'|'SELL', 'conf':0.6}"""
        with self._lock:
            self._registered_meta[strategy_name] = dict(info)
            logger.debug("[%s] registered meta %s -> %s", self.symbol, strategy_name, info)

    def get_registered_votes(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._registered_meta)

    def clear_registered_info(self):
        with self._lock:
            self._registered_meta.clear()

    def get_status(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "cfg": self.cfg,
            "registered_meta": self.get_registered_votes(),
            "seen_signals_count": len(self._seen_signals),
            "history_len": len(self._signal_history)
        }

    # ----- indicators ---------------------------------------------------
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if len(df) < max(self.cfg["min_bars"], 20):
            return pd.DataFrame()  # clear signal: not enough data

        # EMA
        df["ema_short"] = df["close"].ewm(span=self.cfg["short"], adjust=False).mean()
        df["ema_long"] = df["close"].ewm(span=self.cfg["long"], adjust=False).mean()
        df["ema_diff"] = df["ema_short"] - df["ema_long"]

        # RSI
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        rsi = 100 - (100 / (1 + (gain.rolling(self.cfg["rsi_period"]).mean() / (loss.rolling(self.cfg["rsi_period"]).mean() + 1e-9))))
        df["rsi"] = rsi.fillna(method="bfill")

        # ATR (robust)
        hl = df["high"] - df["low"]
        hc = (df["high"] - df["close"].shift()).abs()
        lc = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df["atr"] = tr.rolling(self.cfg["atr_period"]).mean().fillna(method="bfill").replace(0, 1e-9)

        # MACD
        fast = df["close"].ewm(span=self.cfg["macd_fast"], adjust=False).mean()
        slow = df["close"].ewm(span=self.cfg["macd_slow"], adjust=False).mean()
        macd = fast - slow
        signal = macd.ewm(span=self.cfg["macd_signal"], adjust=False).mean()
        df["macd"] = macd
        df["macd_signal"] = signal
        df["macd_hist"] = macd - signal

        # Volume spike
        if "volume" in df.columns:
            df["vol_spike"] = df["volume"] / (df["volume"].rolling(20).mean().replace(0, np.nan) + 1e-9)
        else:
            df["vol_spike"] = 1.0

        # incorporate small last-known meta features (if any)
        with self._lock:
            for name, info in self._registered_meta.items():
                vote_col = f"meta_{name}_vote"
                conf_col = f"meta_{name}_conf"
                vote_val = 0
                v = info.get("vote")
                if v in ("BUY", "LONG", 1):
                    vote_val = 1
                elif v in ("SELL", "SHORT", -1):
                    vote_val = -1
                df[vote_col] = vote_val
                df[conf_col] = float(info.get("conf", 0.0))

        df = df.replace([np.inf, -np.inf], np.nan).dropna()
        return df

    # ----- other strategies safe call ----------------------------------
    def _call_other_strategy(self, strat, df: pd.DataFrame, timeout: float) -> Optional[Dict[str, Any]]:
        """Attempt to call other strategy safely to get a quick vote/indicator snippet."""
        try:
            # prefer generate_signal if available
            if hasattr(strat, "generate_signal"):
                fut = self.executor.submit(lambda: strat.generate_signal(df))
                try:
                    res = fut.result(timeout=timeout)
                except FuturesTimeout:
                    return None
                if res is None:
                    return None
                # if returns our Signal dataclass
                if hasattr(res, "to_dict"):
                    return res.to_dict()
                # if returns dict-like payload
                if isinstance(res, dict):
                    return res
                # if returns dataclass-like
                try:
                    return dict(res.__dict__)
                except Exception:
                    return None
            # else try compute_indicators to extract a quick vote
            elif hasattr(strat, "compute_indicators"):
                fut = self.executor.submit(lambda: strat.compute_indicators(df))
                try:
                    subdf = fut.result(timeout=timeout)
                except FuturesTimeout:
                    return None
                # try to infer a quick vote from subdf last row if possible
                if isinstance(subdf, (pd.DataFrame,)):
                    last = subdf.iloc[-1] if len(subdf) > 0 else None
                    if last is not None:
                        # heuristic: if meta has 'action' column use it
                        if "action" in last:
                            return {"action": last["action"], "confidence": float(last.get("confidence", 0.0))}
                return None
        except Exception as e:
            logger.debug("Other strat call failed: %s", e)
            return None

    # ----- AI manager ask (safe) ---------------------------------------
    def _ask_ai(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.ai_manager:
            return {}
        try:
            fut = self.executor.submit(lambda: self.ai_manager.evaluate_signal(payload, timeout=self.cfg["ai_timeout"]))
            return fut.result(timeout=self.cfg["ai_timeout"] + 0.2)
        except FuturesTimeout:
            logger.warning("[%s] AIManager timeout", self.symbol)
            return {"error": "timeout"}
        except Exception as e:
            logger.debug("[%s] AIManager call failed: %s", self.symbol, e)
            return {"error": str(e)}

    # ----- dedupe ------------------------------------------------------
    def _dedupe_check(self, action: str, price: float) -> bool:
        sig_id = f"{self.symbol}-{action}-{int(price*1e5)}"
        now = time.time()
        with self._lock:
            last = self._seen_signals.get(sig_id, 0.0)
            if now - last < float(self.cfg["dedup_interval"]):
                return False
            self._seen_signals[sig_id] = now
        return True

    # ----- lot suggestion ----------------------------------------------
    def _suggest_lot(self, confidence: float, ai_approved: bool) -> float:
        base = float(self.cfg["lot_base"])
        cap = float(self.cfg["lot_cap"])
        if confidence < 0.55:
            return base
        if confidence < 0.70:
            target = base * 2
        elif confidence < 0.85:
            target = base * 3
        else:
            target = base * 5
        if target > base * 2 and not ai_approved:
            target = base * 2
        return round(min(target, cap), 4)

    # ----- main generator ---------------------------------------------
    def generate_signal(self, df: Optional[pd.DataFrame]) -> Optional[Signal]:
        try:
            # try to fetch data if not provided
            if df is None or len(df) < self.cfg["min_bars"]:
                if self.market_data and hasattr(self.market_data, "get_ohlcv"):
                    try:
                        df = self.market_data.get_ohlcv(self.symbol, bars=self.cfg["min_bars"])
                    except Exception:
                        return None
                else:
                    return None

            df = df.tail(max(self.cfg["min_bars"], 50)).copy()
            df_ind = self.compute_indicators(df)
            if df_ind.empty:
                return None

            last = df_ind.iloc[-1]
            price = float(last["close"])
            action = "HOLD"
            conf = 0.0

            # crossover base
            if float(last["ema_short"]) > float(last["ema_long"]):
                action = "BUY"
            elif float(last["ema_short"]) < float(last["ema_long"]):
                action = "SELL"

            # filters: RSI, MACD, volume
            if action == "BUY":
                if last["rsi"] > 70 or last["macd_hist"] < 0 or last["vol_spike"] > self.cfg["vol_multiplier"] * 3:
                    action = "HOLD"
            elif action == "SELL":
                if last["rsi"] < 30 or last["macd_hist"] > 0 or last["vol_spike"] > self.cfg["vol_multiplier"] * 3:
                    action = "HOLD"

            if action == "HOLD":
                return None

            # baseline confidence (normalized by ema gap / atr)
            gap = abs(float(last["ema_diff"]))
            atr = max(float(last["atr"]) if not np.isnan(last["atr"]) else 1e-9, 1e-9)
            conf = float(min(1.0, (gap / (atr + 1e-9)) * 0.5 + 0.5))  # heuristic mapping

            # volume spike increases confidence
            if float(last.get("vol_spike", 1.0)) > self.cfg["vol_multiplier"]:
                conf = min(1.0, conf + 0.12)

            # gather meta votes from other strategies (safe calls)
            meta_results = {}
            agree = 0
            sum_conf = 0.0
            if self.other_strategies:
                for strat in self.other_strategies:
                    try:
                        out = self._call_other_strategy(strat, df_ind, timeout=self.cfg["other_strat_timeout"])
                        if out:
                            # try to extract action/conf
                            a = out.get("action") or out.get("action", None)
                            c = float(out.get("confidence", out.get("conf", 0.0) or 0.0))
                            meta_results[getattr(strat, "__name__", str(type(strat)))] = {"action": a, "confidence": c}
                            if a == action:
                                agree += 1
                                sum_conf += c
                    except Exception:
                        continue
            meta_avg_conf = (sum_conf / agree) if agree > 0 else 0.0
            if agree > 0:
                conf = float(min(1.0, (conf + meta_avg_conf) / 2.0))

            # ask AIManager
            ai_payload = {
                "symbol": self.symbol,
                "action": action,
                "price": price,
                "confidence": round(conf, 3),
                "strategy": "EMA_CROSSOVER_AI",
                "indicators": {
                    "ema_short": float(last["ema_short"]),
                    "ema_long": float(last["ema_long"]),
                    "rsi": float(last["rsi"]),
                    "macd_hist": float(last["macd_hist"]),
                    "atr": float(last["atr"]),
                    "vol_spike": float(last.get("vol_spike", 1.0)),
                },
                "meta_votes": meta_results,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            ai_res = self._ask_ai(ai_payload)
            ai_votes = ai_res.get("votes") if isinstance(ai_res, dict) else []
            ai_approved = bool(ai_res.get("approved")) if isinstance(ai_res, dict) else False

            # final consensus rules
            meta_total = len(meta_results)
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
            elif meta_total > 0 and meta_fraction >= 0.5 and conf >= self.cfg["min_conf"]:
                consensus_ok = True
            elif ai_vote_majority and conf >= self.cfg["min_conf"]:
                consensus_ok = True
            elif meta_total == 0 and conf >= 0.8:
                consensus_ok = True

            if not consensus_ok:
                logger.debug("[%s] consensus failed: action=%s conf=%.3f meta_frac=%.2f ai_ok=%s", self.symbol, action, conf, meta_fraction, ai_approved)
                return None

            # TP/SL logic
            if action == "BUY":
                tp = price + 2.5 * atr
                sl = price - 1.0 * atr
            else:
                tp = price - 2.5 * atr
                sl = price + 1.0 * atr

            # lot suggestion
            lot = self._suggest_lot(conf, ai_approved)

            # dedupe and build final signal
            if not self._dedupe_check(action, price):
                return None

            sig = Signal(
                symbol=self.symbol,
                action=action,
                confidence=round(float(conf), 4),
                entry_price=price,
                tp=round(float(tp), 6),
                sl=round(float(sl), 6),
                lot_recommendation=lot,
                timestamp=datetime.utcnow().isoformat() + "Z",
                strategy="EMA_CROSSOVER_AI",
                indicators={k: float(ai_payload["indicators"][k]) for k in ai_payload["indicators"]},
                meta_votes=meta_results,
                ai_votes=ai_votes or [],
                reason=f"consensus ai_approved={ai_approved} meta_frac={meta_fraction:.2f}"
            )

            # persist history + async send
            with self._lock:
                self._signal_history.append(sig.to_dict())

            try:
                self.executor.submit(self._send_signal_socket, sig.to_dict())
            except Exception:
                logger.debug("[%s] failed to queue socket send", self.symbol)

            logger.info("[%s] EMA_CROSSOR generated %s conf=%.3f lot=%s", self.symbol, action, conf, lot)
            return sig

        except Exception as e:
            logger.exception("[%s] generate_signal exception: %s", self.symbol, e)
            return None

    # ----- socket send -------------------------------------------------
    def _send_signal_socket(self, payload: Dict[str, Any]) -> None:
        try:
            self.client.send_request({
                "type": "trade_signal",
                "strategy": "EMA_CROSSOVER_AI",
                "signals": [payload],
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.debug("[%s] socket send exception: %s", self.symbol, e)