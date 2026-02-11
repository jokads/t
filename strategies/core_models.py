# core_models_hardcore_hardcore.py
from __future__ import annotations
import json, uuid, logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("core_models")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | CORE | %(levelname)s | %(message)s")
    )
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# -------------------------
# Constantes hardcore
# -------------------------
MIN_LOT = 0.001
MIN_PRICE = 0.0001

# -------------------------
# Enums
# -------------------------
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

class SignalSource(str, Enum):
    STRATEGY = "STRATEGY"
    AI_MODEL = "AI_MODEL"
    CONSENSUS = "CONSENSUS"

# -------------------------
# Helpers
# -------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            return default

def parse_direction(v: Any) -> TradeDirection:
    if isinstance(v, TradeDirection):
        return v
    s = str(v).upper()
    if s in ("BUY", "LONG"):
        return TradeDirection.BUY
    if s in ("SELL", "SHORT"):
        return TradeDirection.SELL
    return TradeDirection.HOLD

# -------------------------
# Signal central hardcore
# -------------------------
@dataclass(slots=True)
class Signal:
    uid: str
    symbol: str
    direction: TradeDirection
    confidence: float
    entry: float
    sl: float
    tp: float
    lot: float

    timestamp: datetime = field(default_factory=now_utc)
    strategy: str = ""
    reason: str = ""
    source: SignalSource = SignalSource.STRATEGY
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -------------------------
    # Validação hardcore
    # -------------------------
    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.symbol:
            errors.append("symbol missing")
        if self.direction not in (TradeDirection.BUY, TradeDirection.SELL):
            errors.append(f"invalid direction: {self.direction}")
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence out of range: {self.confidence}")
        if self.lot < MIN_LOT:
            errors.append(f"lot < MIN_LOT ({MIN_LOT})")
        for attr in ["entry", "sl", "tp"]:
            val = getattr(self, attr, 0.0)
            if val < MIN_PRICE:
                errors.append(f"{attr} < MIN_PRICE ({MIN_PRICE})")
        return errors

    # -------------------------
    # Serialização hardcore
    # -------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "symbol": self.symbol,
            "action": self.direction.value,
            "confidence": round(float(self.confidence), 4),
            "entry": float(self.entry),
            "stop_loss": float(self.sl),
            "take_profit": float(self.tp),
            "lot_size": float(self.lot),
            "strategy": self.strategy,
            "reason": self.reason,
            "source": self.source.value,
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
            "metadata": dict(self.metadata) if self.metadata else {},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    # -------------------------
    # Payload MT5/MT4
    # -------------------------
    def to_mt5_payload(self) -> Dict[str, Any]:
        return {"type": "trade_signal", "signal": self.to_dict()}

    # -------------------------
    # Factory robusta
    # -------------------------
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Optional["Signal"]:
        try:
            ts_raw = d.get("timestamp")
            if isinstance(ts_raw, str) and ts_raw.endswith("Z"):
                ts_raw = ts_raw.replace("Z", "+00:00")
            timestamp = datetime.fromisoformat(ts_raw) if ts_raw else now_utc()
            return cls(
                uid=str(d.get("uid") or uuid.uuid4().hex),
                symbol=str(d.get("symbol") or ""),
                direction=parse_direction(d.get("action") or d.get("direction")),
                confidence=to_float(d.get("confidence"), 0.0),
                entry=max(MIN_PRICE, to_float(d.get("entry"), MIN_PRICE)),
                sl=max(MIN_PRICE, to_float(d.get("stop_loss") or d.get("sl"), MIN_PRICE)),
                tp=max(MIN_PRICE, to_float(d.get("take_profit") or d.get("tp"), MIN_PRICE)),
                lot=max(MIN_LOT, to_float(d.get("lot_size") or d.get("lot"), MIN_LOT)),
                timestamp=timestamp,
                strategy=str(d.get("strategy", "")),
                reason=str(d.get("reason", "")),
                source=SignalSource(d.get("source", SignalSource.STRATEGY)),
                metadata=d.get("metadata") or {},
            )
        except Exception:
            logger.exception("Signal.from_dict failed")
            return None

# -------------------------
# CONSENSO hardcore + AI-aware
# -------------------------
def consensus(signals: List[Signal], min_conf: float = 0.6, ai_manager: Optional[Any] = None) -> Optional[Signal]:
    if not signals:
        return None

    buys = [s for s in signals if s.direction == TradeDirection.BUY]
    sells = [s for s in signals if s.direction == TradeDirection.SELL]

    if not buys and not sells:
        return None

    sum_buy = sum(s.confidence for s in buys)
    sum_sell = sum(s.confidence for s in sells)

    if sum_buy >= sum_sell:
        direction = TradeDirection.BUY
        weight = sum_buy / (sum_buy + sum_sell + 1e-9)
        group = buys
    else:
        direction = TradeDirection.SELL
        weight = sum_sell / (sum_buy + sum_sell + 1e-9)
        group = sells

    if weight < min_conf:
        return None

    # WAVG seguro hardcore
    def wavg(attr: str) -> float:
        total_conf = sum(s.confidence for s in group)
        if total_conf <= 0:
            return max(MIN_PRICE, float(getattr(group[0], attr, MIN_PRICE)))
        return max(MIN_PRICE, sum(getattr(s, attr, MIN_PRICE) * s.confidence for s in group) / total_conf)

    signal = Signal(
        uid="cons_" + uuid.uuid4().hex[:8],
        symbol=group[0].symbol,
        direction=direction,
        confidence=min(1.0, weight),
        entry=wavg("entry"),
        sl=wavg("sl"),
        tp=wavg("tp"),
        lot=max(MIN_LOT, wavg("lot")),
        strategy="CONSENSUS",
        reason=f"consensus({len(group)})",
        source=SignalSource.CONSENSUS,
        metadata={"sources": [
            {"strategy": s.strategy, "conf": s.confidence, "entry": s.entry, "sl": s.sl, "tp": s.tp}
            for s in group
        ]},
    )

    # AIManager hardcore
    if ai_manager:
        try:
            result = ai_manager.evaluate_signal(signal.to_dict(), timeout=0.5)
            votes = result.get("votes", [])
            approved = result.get("ok", False) and result.get("approved", False)
            if not approved:
                approved = votes.count("BUY") >= 4 if direction == TradeDirection.BUY else votes.count("SELL") >= 4
            if not approved:
                return None
        except Exception as e:
            logger.debug("AIManager consensus fail: %s", e)
            if signal.confidence < min_conf:
                return None  # fallback conservador

    return signal
