# strategies/risk_manager.py – Ultra Hardcore Production Version v6
from __future__ import annotations
import math
import os
import json
import time
import logging
import threading
from typing import Optional, Dict, Any, List, Tuple

# try to import your domain models — keep compatibility if names differ at runtime
try:
    from strategies.models import TradeSignal, TradeDirection, OrderType, AccountInfo
except Exception:
    TradeSignal = None
    TradeDirection = type("TradeDirection", (), {"BUY": "BUY", "SELL": "SELL", "HOLD": "HOLD"})
    OrderType = type("OrderType", (), {"MARKET": "MARKET"})

# =========================
# Logger
# =========================
logger = logging.getLogger("risk_manager")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | RISK | %(levelname)s | %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)

# file log
_log_path = os.getenv("RISK_MANAGER_LOG", "risk_manager.log")
try:
    fh_file = logging.FileHandler(_log_path)
    fh_file.setFormatter(logging.Formatter("%(asctime)s | RISK | %(levelname)s | %(message)s"))
    logger.addHandler(fh_file)
except Exception:
    logger.debug("Could not create file handler for risk_manager.log")

# =========================
# Utils
# =========================
def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def round_down_to_step(value: float, step: float) -> float:
    """Round down to nearest step (safe for lots)."""
    if step <= 0:
        return value
    return math.floor(value / step) * step

def safe_get(d: Any, key: str, default=None):
    """Works with dict-like or object-like."""
    try:
        if d is None:
            return default
        if isinstance(d, dict):
            return d.get(key, default)
        return getattr(d, key, default)
    except Exception:
        return default

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# =========================
# RiskManager Hardcore
# =========================
class RiskManager:
    """
    Institutional-grade Risk Manager (AI-aware, multi-strategy)
    - Aggregates signals, computes lot sizing safely
    - Exposure tracking per-symbol with atomic operations
    - Audit trail (jsonl)
    - Optional decay of exposures over time
    """

    DEFAULTS = {
        "base_risk": 0.0025,          # 0.25% account risk per trade
        "risk_min": 0.001,            # 0.1%
        "risk_max": 0.01,             # 1%
        "max_symbol_exposure": 1.0,   # max lots per symbol active
        "consensus_required": 0.6,    # 60% signals agreement to aggregate
        "min_lot_absolute": 0.01,     # minimum lot to allow
        "max_lot_absolute": 0.10,     # maximum lot allowed by risk manager
        "exposure_persist_file": "exposures.json",
        "exposure_persist_interval": 30.0,  # seconds
        "exposure_decay_enabled": True,
        "exposure_decay_window": 3600.0,    # seconds after which exposure decays
        "exposure_decay_rate": 0.5,         # fraction to reduce exposure after window
    }

    def __init__(self, mt5_comm: Any, ai_manager: Any, config: Optional[Dict[str, Any]] = None):
        if mt5_comm is None or ai_manager is None:
            raise RuntimeError("RiskManager requires mt5_comm and ai_manager")
        self.mt5_comm = mt5_comm
        self.ai_manager = ai_manager
        self.cfg = dict(self.DEFAULTS)
        if config:
            self.cfg.update(config)

        self.symbol_exposure: Dict[str, float] = {}
        self.symbol_last_exec_ts: Dict[str, float] = {}
        self._exposure_lock = threading.RLock()
        self._persist_lock = threading.RLock()

        # load persisted exposures if present
        self._load_exposures()

        # background persist thread
        self._stop_event = threading.Event()
        self._p_thread = threading.Thread(target=self._persist_loop, daemon=True)
        self._p_thread.start()

        logger.info("RiskManager initialized (AI-aware)")

    # -------------------------
    # Persistence
    # -------------------------
    def _persist_loop(self):
        interval = float(self.cfg.get("exposure_persist_interval", 30.0))
        while not self._stop_event.is_set():
            try:
                time.sleep(interval)
                self._save_exposures()
                if self.cfg.get("exposure_decay_enabled"):
                    self._decay_exposures_if_needed()
            except Exception as e:
                logger.debug("RiskManager persist loop exception: %s", e)

    def _load_exposures(self):
        p = self.cfg.get("exposure_persist_file")
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    with self._exposure_lock:
                        self.symbol_exposure.update({k: float(v) for k, v in data.get("symbol_exposure", {}).items()})
                        self.symbol_last_exec_ts.update({k: float(v) for k, v in data.get("symbol_last_exec_ts", {}).items()})
                logger.info("RiskManager loaded exposures from %s", p)
        except Exception as e:
            logger.debug("RiskManager load exposures failed: %s", e)

    def _save_exposures(self):
        p = self.cfg.get("exposure_persist_file")
        payload = {
            "symbol_exposure": self.symbol_exposure,
            "symbol_last_exec_ts": self.symbol_last_exec_ts,
            "ts": now_iso()
        }
        try:
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
            logger.debug("RiskManager saved exposures to %s", p)
        except Exception as e:
            logger.debug("RiskManager save exposures failed: %s", e)

    def shutdown(self):
        self._stop_event.set()
        try:
            self._p_thread.join(timeout=2.0)
        except Exception:
            pass
        self._save_exposures()

    # -------------------------
    # Signal aggregation
    # -------------------------
    def aggregate_signals(self, signals: List[Any]) -> Optional[Any]:
        """
        Accepts a list of TradeSignal-like objects and attempts to produce a single aggregated signal.
        Defensive: works with dicts/objects — uses safe_get to access attributes.
        """
        if not signals:
            return None

        # normalize into small dicts
        normalized = []
        for s in signals:
            try:
                sym = safe_get(s, "symbol", None) or safe_get(s, "symbol", None)
                direction = safe_get(s, "direction", safe_get(s, "action", None))
                # unify enums/strings
                if hasattr(direction, "name"):
                    direction = getattr(direction, "name")
                if isinstance(direction, str):
                    direction = direction.upper()
                    if direction in ("BUY", "SELL"):
                        pass
                confidence = float(safe_get(s, "confidence", 0.0) or 0.0)
                entry = float(safe_get(s, "entry_price", safe_get(s, "entry", 0.0) or 0.0))
                sl = safe_get(s, "sl", None)
                tp = safe_get(s, "tp", None)
                strategy = safe_get(s, "strategy", safe_get(s, "source", None) or getattr(s, "strategy", None))
                normalized.append({"symbol": sym, "direction": direction, "confidence": confidence, "entry": entry, "sl": sl, "tp": tp, "strategy": strategy})
            except Exception:
                continue

        if not normalized:
            return None

        symbol = normalized[0]["symbol"]
        # group by direction
        groups = {"BUY": [], "SELL": []}
        for n in normalized:
            d = n.get("direction")
            if d in ("BUY", "SELL"):
                groups[d].append(n)

        total_votes = sum(len(v) for v in groups.values())
        if total_votes == 0:
            return None

        active_groups = {k:v for k,v in groups.items() if len(v)>0}
        if not active_groups:
            return None
        winner = max(active_groups.keys(), key=lambda k: len(active_groups[k]))
        consensus = len(active_groups[winner])/sum(len(v) for v in active_groups.values())

        chosen = groups[winner]
        # aggregate entry by confidence-weighted average
        sum_conf = sum(float(x["confidence"]) for x in chosen) or 1.0
        entry = sum(float(x["entry"]) * float(x["confidence"]) for x in chosen) / sum_conf
        # conservative SL/TP selection
        if winner == "BUY":
            sl_candidates = [float(x["sl"]) for x in chosen if x.get("sl") is not None]
            tp_candidates = [float(x["tp"]) for x in chosen if x.get("tp") is not None]
            sl = min(sl_candidates) if sl_candidates else None
            tp = max(tp_candidates) if tp_candidates else None
        else:
            sl_candidates = [float(x["sl"]) for x in chosen if x.get("sl") is not None]
            tp_candidates = [float(x["tp"]) for x in chosen if x.get("tp") is not None]
            sl = max(sl_candidates) if sl_candidates else None
            tp = min(tp_candidates) if tp_candidates else None

        # build a minimal TradeSignal-like dict
        agg = {
            "symbol": symbol,
            "direction": winner,
            "order_type": safe_get(signals[0], "order_type", OrderType.MARKET if OrderType else "MARKET"),
            "entry_price": entry,
            "sl": sl,
            "tp": tp,
            "lot_size": 0.0,
            "confidence": float(sum_conf / len(chosen)),
            "strategy": "AGGREGATED",
            "sources": [x.get("strategy") for x in chosen]
        }
        return agg

    # -------------------------
    # Risk evaluation & lot sizing
    # -------------------------
    def evaluate_risk(self, signal: Any, account: Any) -> Optional[float]:
        """
        Compute lot for a single aggregated signal (dict-like or object-like).
        Returns lot (float) or None if not allowed.
        """
        try:
            # defensive extraction
            symbol = (safe_get(signal, "symbol") or "").upper()
            if not symbol:
                logger.error("evaluate_risk: missing symbol on signal")
                return None

            direction = safe_get(signal, "direction", safe_get(signal, "action", None))
            entry = float(safe_get(signal, "entry_price", safe_get(signal, "entry", 0.0) or 0.0))
            sl = safe_get(signal, "sl")
            if sl is None or entry <= 0:
                logger.error("evaluate_risk: missing sl/entry for %s", symbol)
                return None
            sl = float(sl)

            # symbol info (mt5_comm wrapper may return dict or object)
            info = None
            try:
                info = self.mt5_comm.get_symbol_info(symbol)
            except Exception:
                try:
                    info = self.mt5_comm.symbol_info(symbol)
                except Exception:
                    info = None
            if not info:
                logger.error("evaluate_risk: symbol info not available for %s", symbol)
                return None

            # read fields defensively
            tick_size = float(safe_get(info, "tick_size", safe_get(info, "point", 0.00001) or 0.00001))
            tick_value = float(safe_get(info, "tick_value", safe_get(info, "contract_size", 1.0) or 1.0))
            vol_min = float(safe_get(info, "volume_min", 0.01) or 0.01)
            vol_max = float(safe_get(info, "volume_max", self.cfg.get("max_lot_absolute", 0.1)) or self.cfg.get("max_lot_absolute", 0.1))
            vol_step = float(safe_get(info, "volume_step", 0.01) or 0.01)

            # sl distance and ticks
            sl_distance = abs(entry - sl)
            sl_ticks = sl_distance / (tick_size or 1e-9)
            if sl_ticks <= 0:
                logger.warning("evaluate_risk: sl distance too small for %s", symbol)
                return None

            # base risk
            base_risk = float(self.cfg.get("base_risk", 0.0025))
            try:
                # ask AI for risk multiplier: safe wrapper
                ai_payload = {
                    "symbol": symbol,
                    "entry": entry,
                    "sl": sl,
                    "tp": safe_get(signal, "tp", None),
                    "confidence": float(safe_get(signal, "confidence", 0.0) or 0.0),
                    "strategy": safe_get(signal, "strategy", "unknown")
                }
                ai_res = getattr(self.ai_manager, "assess_risk", lambda p, a=None: {})(ai_payload, getattr(account, "to_dict", lambda: {})())
                multiplier = float(ai_res.get("risk_multiplier", 1.0)) if isinstance(ai_res, dict) else 1.0
                multiplier = clamp(multiplier, 0.5, 1.5)
            except Exception:
                multiplier = 1.0

            risk = clamp(base_risk * multiplier, float(self.cfg["risk_min"]), float(self.cfg["risk_max"]))

            # compute money risk and loss/lots
            account_balance = float(safe_get(account, "balance", getattr(account, "equity", 0.0) or 0.0))
            if account_balance <= 0:
                logger.error("evaluate_risk: invalid account balance")
                return None

            risk_money = account_balance * risk
            loss_per_lot = sl_ticks * tick_value
            if loss_per_lot <= 0:
                logger.error("evaluate_risk: invalid loss per lot for %s", symbol)
                return None

            raw_lot = risk_money / loss_per_lot

            # exposure cap
            with self._exposure_lock:
                current_exp = float(self.symbol_exposure.get(symbol, 0.0))
            max_allowed = max(float(self.cfg.get("min_lot_absolute", 0.01)), float(self.cfg.get("max_symbol_exposure", 0.20)) - current_exp)
            raw_lot = clamp(raw_lot, 0.0, max_allowed)

            # step and clamp
            stepped = round_down_to_step(raw_lot, vol_step)
            lot = clamp(stepped, max(vol_min, float(self.cfg.get("min_lot_absolute", 0.01))), min(vol_max, float(self.cfg.get("max_lot_absolute", 0.10))))

            # final guard rails
            if lot < float(self.cfg.get("min_lot_absolute", 0.01)):
                logger.info("evaluate_risk: computed lot below minimum for %s (%.4f)", symbol, lot)
                return None

            # Audit log
            audit = {
                "ts": now_iso(),
                "symbol": symbol,
                "entry": entry,
                "sl": sl,
                "tp": safe_get(signal, "tp", None),
                "raw_lot": raw_lot,
                "final_lot": lot,
                "vol_step": vol_step,
                "risk_pct": risk,
                "account_balance": account_balance,
                "ai_multiplier": multiplier,
                "current_exposure": current_exp,
                "sources": safe_get(signal, "sources", safe_get(signal, "strategy", None))
            }
            try:
                with open("risk_audit.jsonl", "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(audit, ensure_ascii=False) + "\n")
            except Exception:
                logger.debug("Could not write risk_audit.jsonl")

            logger.info("RiskManager evaluate | %s lot=%.4f risk=%.3f%% (ai_mul=%.2f) current_exp=%.2f",
                        symbol, lot, risk*100.0, multiplier, current_exp)
            return round(lot, 4)

        except Exception as e:
            logger.exception("evaluate_risk exception: %s", e)
            return None

    # -------------------------
    # Register and release executions
    # -------------------------
    def register_execution(self, symbol: str, lot: float):
        symbol = symbol.upper()
        with self._exposure_lock:
            prev = float(self.symbol_exposure.get(symbol, 0.0))
            self.symbol_exposure[symbol] = prev + float(lot)
            self.symbol_last_exec_ts[symbol] = time.time()
        logger.info("Registered execution %s lot=%.4f -> exposure=%.4f", symbol, lot, self.symbol_exposure[symbol])
        # persist soon
        try:
            self._save_exposures()
        except Exception:
            pass

    def release_execution(self, symbol: str, lot: float):
        symbol = symbol.upper()
        with self._exposure_lock:
            prev = float(self.symbol_exposure.get(symbol, 0.0))
            new = max(0.0, prev - float(lot))
            self.symbol_exposure[symbol] = new
            self.symbol_last_exec_ts[symbol] = time.time()
        logger.info("Released execution %s lot=%.4f -> exposure=%.4f", symbol, lot, self.symbol_exposure[symbol])
        try:
            self._save_exposures()
        except Exception:
            pass

    # -------------------------
    # Exposure decay (optional)
    # -------------------------
    def _decay_exposures_if_needed(self):
        now = time.time()
        window = float(self.cfg.get("exposure_decay_window", 3600.0))
        rate = float(self.cfg.get("exposure_decay_rate", 0.5))
        changed = False
        with self._exposure_lock:
            for sym, ts in list(self.symbol_last_exec_ts.items()):
                if now - ts > window:
                    old = self.symbol_exposure.get(sym, 0.0)
                    new = old * (1.0 - rate)
                    self.symbol_exposure[sym] = round(max(0.0, new), 6)
                    self.symbol_last_exec_ts[sym] = now
                    changed = True
                    logger.debug("Decayed exposure %s: %.4f -> %.4f", sym, old, new)
        if changed:
            try:
                self._save_exposures()
            except Exception:
                pass

    # -------------------------
    # Helper: pretty status
    # -------------------------
    def status(self) -> Dict[str, Any]:
        with self._exposure_lock:
            return {
                "symbols": dict(self.symbol_exposure),
                "last_exec": dict(self.symbol_last_exec_ts),
                "cfg": self.cfg
            }
