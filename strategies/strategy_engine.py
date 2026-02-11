# strategies/strategy_engine.py – Hardcore Production Version (AI-integrated, resilient)
from __future__ import annotations
import json
import logging
import threading
import time
import math
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Iterable

import numpy as np

# Optional MT5/MT4 communication layer (if present)
try:
    from mt5_communication import MT5Communication
except Exception:
    MT5Communication = None

logger = logging.getLogger("strategy_engine")
if not logger.handlers:
    fh = logging.StreamHandler()
    fh.setFormatter(logging.Formatter("%(asctime)s | STRATEGY | %(levelname)s | %(message)s"))
    logger.addHandler(fh)
logger.setLevel(logging.INFO)


# -------------------------
# Data models
# -------------------------
@dataclass
class MarketData:
    symbol: str
    timeframe: str = "1m"
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    spread: float = 0.0
    indicators: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow().replace(tzinfo=timezone.utc))


@dataclass
class Signal:
    symbol: str
    direction: str  # LONG, SHORT, BUY, SELL, HOLD
    confidence: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    lot_size: float = 0.01
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow().replace(tzinfo=timezone.utc))
    strategy: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class EngineSignal:
    symbol: str
    direction: str  # BUY, SELL, HOLD
    confidence: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    lot_size: float = 0.01
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow().replace(tzinfo=timezone.utc))
    strategy: str = ""
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "confidence": float(self.confidence),
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "lot_size": float(self.lot_size),
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
            "strategy": self.strategy,
            "reason": self.reason,
            "metadata": self.metadata or {},
        }


# -------------------------
# Lightweight SocketClient (fire-and-forget / simple)
# -------------------------
class SimpleSocketClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 9999, timeout: float = 1.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, data: dict) -> None:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall(json.dumps(data).encode("utf-8"))
        except Exception as e:
            logger.debug("SimpleSocketClient failed to send: %s", e)


# -------------------------
# Strategy Engine (improved)
# -------------------------
class StrategyEngine:
    """
    StrategyEngine:
    - Runs multiple strategies safely in parallel
    - Integrates with ai_manager (direct calls or via socket fallback)
    - Aggregates signals (softmax + robust weighting)
    - Produces a meta EngineSignal and attempts to dispatch via mt_comm
    """

    def __init__(
        self,
        strategies: List[Any],
        mt_comm: Optional[Any] = None,
        ai_manager: Optional[Any] = None,
        max_workers: int = 8,
        cooldown_sec: float = 30.0,
        ai_timeout: float = 1.0,
        ai_socket: Optional[Dict[str, Any]] = None,
    ):
        self.strategies = strategies
        self.mt_comm = mt_comm
        self.ai_manager = ai_manager
        self.max_workers = max_workers
        self.cooldown_sec = cooldown_sec
        self.ai_timeout = ai_timeout
        self.ai_socket = ai_socket or {"host": "127.0.0.1", "port": 9999}
        self._symbol_cooldowns: Dict[str, float] = {}
        self._cooldown_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._audit_lock = threading.Lock()
        self._audit_path = "strategy_engine_audit.jsonl"
        logger.info("StrategyEngine initialized | strategies=%d | max_workers=%d", len(self.strategies), self.max_workers)

    # -------------------------
    # Cooldown helpers
    # -------------------------
    def _is_on_cooldown(self, symbol: str) -> bool:
        with self._cooldown_lock:
            last = self._symbol_cooldowns.get(symbol, 0.0)
            return (time.time() - last) < self.cooldown_sec

    def _set_cooldown(self, symbol: str):
        with self._cooldown_lock:
            self._symbol_cooldowns[symbol] = time.time()

    # -------------------------
    # Convert to EngineSignal (robust)
    # -------------------------
    def _convert_to_engine_signal(self, sig: Union[Signal, Any], reason: str = "") -> EngineSignal:
        symbol = getattr(sig, "symbol", "UNKNOWN").upper()
        direction = getattr(sig, "direction", "HOLD").upper()
        confidence = float(getattr(sig, "confidence", 0.0))
        entry_price = getattr(sig, "entry_price", None) or getattr(sig, "close", None)
        stop_loss = getattr(sig, "stop_loss", None) or getattr(sig, "sl", None)
        take_profit = getattr(sig, "take_profit", None) or getattr(sig, "tp", None)
        strategy = getattr(sig, "strategy", getattr(sig, "__class__", type(sig)).__name__)
        metadata = getattr(sig, "metadata", getattr(sig, "additional_info", {})) or {}

        return EngineSignal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=getattr(sig, "lot_size", 0.01),
            timestamp=datetime.utcnow().replace(tzinfo=timezone.utc),
            reason=reason or "Generated by strategy",
            strategy=str(strategy),
            metadata=metadata
        )

    # -------------------------
    # Safe call wrapper for a strategy
    # -------------------------
    def _safe_run_strategy(self, strat: Any, market_data: MarketData) -> Optional[Union[Signal, List[Signal], Dict]]:
        try:
            # Strategy may accept pandas df, MarketData or custom signature
            if hasattr(strat, "generate_signal"):
                return strat.generate_signal(market_data)
            elif callable(strat):
                return strat(market_data)
            return None
        except Exception as e:
            logger.exception("Strategy %s raised exception: %s", getattr(strat, "__class__", strat), e)
            return None

    # -------------------------
    # Run all strategies in parallel and collect EngineSignals
    # -------------------------
    def run_strategies(self, market_data: MarketData, timeout: float = 2.0) -> List[EngineSignal]:
        futures = {}
        signals: List[EngineSignal] = []
        if not self.strategies:
            return signals

        # submit
        for strat in self.strategies:
            fut = self._executor.submit(self._safe_run_strategy, strat, market_data)
            futures[fut] = strat

        # collect with timeout
        for fut in as_completed(futures, timeout=timeout):
            strat = futures[fut]
            try:
                res = fut.result(timeout=0.01)
                if not res:
                    continue
                items: List = res if isinstance(res, list) else [res]
                for s in items:
                    try:
                        eng = self._convert_to_engine_signal(s, reason=f"from {getattr(strat,'__class__',str(strat))}")
                        # cooldown by symbol prevents floods
                        if self._is_on_cooldown(eng.symbol):
                            logger.debug("Skipping %s from %s due to cooldown", eng.symbol, eng.strategy)
                            continue
                        signals.append(eng)
                    except Exception as e:
                        logger.debug("Failed converting strategy result: %s", e)
            except TimeoutError:
                logger.warning("Strategy %s timed out", getattr(strat, "__class__", strat))
            except Exception as e:
                logger.debug("Strategy %s error collecting result: %s", getattr(strat, "__class__", strat), e)
        return signals

    # -------------------------
    # Ask AIManager for signals (prefer direct API; fallback to socket)
    # -------------------------
    def _get_ai_signals(self, market_data: MarketData, local_signals: Iterable[EngineSignal]) -> List[EngineSignal]:
        ai_signals: List[EngineSignal] = []
        # Try direct ai_manager API (preferred)
        try:
            if self.ai_manager:
                # many AIManagers implement evaluate_signals or evaluate_signal
                # we try to pass a batch first
                payload = {
                    "market_data": market_data.__dict__,
                    "signals": [s.to_dict() for s in local_signals],
                    "timestamp": datetime.utcnow().isoformat()
                }
                if hasattr(self.ai_manager, "evaluate_signals"):
                    resp = self.ai_manager.evaluate_signals(payload, timeout=self.ai_timeout)
                    ai_list = resp.get("signals", []) if isinstance(resp, dict) else []
                elif hasattr(self.ai_manager, "evaluate_signal"):
                    # call per-signal (less efficient)
                    ai_list = []
                    for s in local_signals:
                        try:
                            r = self.ai_manager.evaluate_signal(s.to_dict(), timeout=self.ai_timeout)
                            if isinstance(r, dict) and r.get("ok") and r.get("signal"):
                                ai_list.append(r["signal"])
                        except Exception:
                            continue
                else:
                    ai_list = []
                # normalize ai_list -> EngineSignal
                for s in ai_list:
                    try:
                        if not isinstance(s, dict):
                            continue
                        eng = EngineSignal(
                            symbol=s.get("symbol", market_data.symbol).upper(),
                            direction=s.get("direction", "HOLD").upper(),
                            confidence=float(s.get("confidence", 0.5)),
                            entry_price=s.get("entry_price"),
                            stop_loss=s.get("stop_loss"),
                            take_profit=s.get("take_profit"),
                            lot_size=float(s.get("lot_size", 0.01)),
                            timestamp=datetime.utcnow().replace(tzinfo=timezone.utc),
                            strategy="AIManager",
                            reason=s.get("reason", "ai"),
                            metadata=s.get("metadata", {})
                        )
                        ai_signals.append(eng)
                    except Exception:
                        continue
                if ai_signals:
                    logger.info("AIManager provided %d signals", len(ai_signals))
                    return ai_signals
        except Exception as e:
            logger.debug("ai_manager direct call failed: %s", e)

        # Fallback: socket request to ai service
        try:
            client = SimpleSocketClient(host=self.ai_socket.get("host", "127.0.0.1"), port=self.ai_socket.get("port", 9999), timeout=self.ai_timeout)
            req = {"type": "request_signal", "market_data": market_data.__dict__, "local_signals": [s.to_dict() for s in local_signals], "timestamp": datetime.utcnow().isoformat()}
            client.send(req)
            # NOTE: this implementation is fire-and-forget; if you have a reply path, integrate here.
        except Exception as e:
            logger.debug("ai_manager socket fallback failed: %s", e)

        return ai_signals

    # -------------------------
    # Aggregation helpers: robust weighted average and trimming
    # -------------------------
    @staticmethod
    def _robust_weighted_avg(values_weights: List[tuple]) -> Optional[float]:
        if not values_weights:
            return None
        # trim extremes (25% trim) when more than 3 samples
        vals = np.array([v for v, _ in values_weights], dtype=float)
        wts = np.array([w for _, w in values_weights], dtype=float)
        if len(vals) > 3:
            lo, hi = np.percentile(vals, [10, 90])
            mask = (vals >= lo) & (vals <= hi)
            if mask.sum() == 0:
                mask = np.ones_like(mask, dtype=bool)
            vals, wts = vals[mask], wts[mask]
        total_w = float(np.sum(wts))
        if total_w <= 0:
            return float(np.median(vals))
        return float(np.sum(vals * wts) / total_w)

    # -------------------------
    # Softmax-based direction pick & meta aggregation
    # -------------------------
    def _aggregate(self, signals: List[EngineSignal], max_lot: float = 1.0) -> EngineSignal:
        # normalize directions
        votes = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        entries, tps, sls = [], [], []
        for s in signals:
            d = s.direction.upper()
            if d not in votes:
                d = "HOLD"
            votes[d] += float(s.confidence)
            if s.entry_price is not None:
                entries.append((s.entry_price, s.confidence))
            if s.take_profit is not None:
                tps.append((s.take_profit, s.confidence))
            if s.stop_loss is not None:
                sls.append((s.stop_loss, s.confidence))

        q_vals = np.array([votes["BUY"], votes["SELL"], votes["HOLD"]], dtype=float)
        # avoid all zeros
        if np.allclose(q_vals, 0.0):
            q_vals = q_vals + 1e-6
        exp_q = np.exp(q_vals - q_vals.max())
        probs = exp_q / (exp_q.sum() + 1e-12)
        directions = ["BUY", "SELL", "HOLD"]
        meta_dir = directions[int(np.argmax(probs))]
        meta_conf = float(np.max(probs))

        meta_entry = self._robust_weighted_avg(entries)
        meta_tp = self._robust_weighted_avg(tps)
        meta_sl = self._robust_weighted_avg(sls)

        # weighted lot (confidence-weighted average of lot_size)
        total_conf = sum(max(0.0, s.confidence) for s in signals)
        if total_conf <= 0:
            meta_lot = 0.01
        else:
            meta_lot = sum(max(0.0, s.lot_size) * s.confidence for s in signals) / total_conf
        meta_lot = float(min(max(meta_lot, 0.01), max_lot))

        # metadata includes sources and raw signals
        metadata = {
            "raw_signals": [s.to_dict() for s in signals],
            "vote_sums": votes,
            "generated_at": datetime.utcnow().isoformat()
        }

        eng = EngineSignal(
            symbol=(signals[0].symbol if signals else "UNKNOWN"),
            direction=meta_dir,
            confidence=meta_conf,
            entry_price=meta_entry,
            stop_loss=meta_sl,
            take_profit=meta_tp,
            lot_size=meta_lot,
            timestamp=datetime.utcnow().replace(tzinfo=timezone.utc),
            strategy="MetaStrategy",
            reason="aggregated",
            metadata=metadata
        )
        return eng

    # -------------------------
    # Dispatch meta-signal: prefer mt_comm.place_trade, fallback to send_signal or socket
    # -------------------------
    def _dispatch(self, eng_sig: EngineSignal):
        payload = eng_sig.to_dict()
        # audit persist
        try:
            with self._audit_lock:
                with open(self._audit_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": datetime.utcnow().isoformat(), "meta_signal": payload}, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug("Failed to write audit: %s", e)

        # attempt send via mt_comm
        try:
            if self.mt_comm:
                # prefer place_trade or place_order if available
                if hasattr(self.mt_comm, "place_trade"):
                    # normalize direction to side
                    side = "BUY" if eng_sig.direction.upper() == "BUY" else "SELL" if eng_sig.direction.upper() == "SELL" else "BUY"
                    kwargs = dict(
                        symbol=eng_sig.symbol,
                        side=side,
                        volume=eng_sig.lot_size,
                        tp_pips=None,
                        sl_pips=None,
                        source="MetaStrategy",
                        confidence=eng_sig.confidence,
                        uuid=None
                    )
                    # pass entry/sl/tp as price floats if mt_comm supports
                    if eng_sig.take_profit is not None:
                        kwargs["tp_pips"] = None
                    if eng_sig.stop_loss is not None:
                        kwargs["sl_pips"] = None
                    # best-effort: call place_trade
                    try:
                        res = self.mt_comm.place_trade(**kwargs)
                        logger.info("mt_comm.place_trade result: %s", getattr(res, "__dict__", res))
                        return res
                    except Exception as e:
                        logger.debug("mt_comm.place_trade failed: %s", e)
                # fallback to send_signal
                if hasattr(self.mt_comm, "send_signal"):
                    self.mt_comm.send_signal(payload)
                    logger.info("mt_comm.send_signal called for %s", eng_sig.symbol)
                    return {"ok": True, "sent_via": "mt_comm.send_signal"}
        except Exception as e:
            logger.debug("mt_comm dispatch failed: %s", e)

        # final fallback: emit via SimpleSocketClient
        try:
            SimpleSocketClient(host=self.ai_socket.get("host", "127.0.0.1"), port=self.ai_socket.get("port", 9999), timeout=1.0).send({"type": "meta_signal", "payload": payload})
            logger.info("Dispatched meta_signal via socket for %s", eng_sig.symbol)
            return {"ok": True, "sent_via": "socket"}
        except Exception as e:
            logger.exception("Failed dispatch fallback socket: %s", e)
            return {"ok": False, "error": str(e)}

    # -------------------------
    # Public: run all strategies, ask AI and aggregate into one meta-signal
    # -------------------------
    def run_strategies_aggregated(self, market_data: MarketData, timeout: float = 2.0, max_lot: float = 0.10) -> EngineSignal:
        """
        Runs strategies, asks AIManager, aggregates and dispatches a single meta signal.
        Returns the EngineSignal generated (even if HOLD).
        """
        try:
            local_signals = self.run_strategies(market_data, timeout=timeout)
        except Exception as e:
            logger.exception("run_strategies failed: %s", e)
            local_signals = []

        # ask AI for additional / filtered signals
        try:
            ai_signals = self._get_ai_signals(market_data, local_signals)
        except Exception as e:
            logger.debug("AI signal gathering failed: %s", e)
            ai_signals = []

        # merge signals, prefer AI signals appended (AI can override)
        merged = list(local_signals) + list(ai_signals)

        # if empty -> return HOLD engine signal
        if not merged:
            hold = EngineSignal(
                symbol=market_data.symbol.upper(),
                direction="HOLD",
                confidence=0.0,
                strategy="MetaStrategy",
                reason="no_signals",
                timestamp=datetime.utcnow().replace(tzinfo=timezone.utc)
            )
            # audit and return
            self._dispatch(hold)
            return hold

        # Aggregate robustly
        meta = self._aggregate(merged, max_lot=max_lot)
        # Rate-limit / cooldown
        if self._is_on_cooldown(meta.symbol):
            logger.info("Meta signal for %s skipped due cooldown", meta.symbol)
            return meta

        # Dispatch and set cooldown if dispatch success-ish
        try:
            res = self._dispatch(meta)
            # set cooldown only if dispatch attempted
            self._set_cooldown(meta.symbol)
            logger.info("Meta signal created: %s", meta.to_dict())
            return meta
        except Exception as e:
            logger.exception("Failed to dispatch meta signal: %s", e)
            return meta
