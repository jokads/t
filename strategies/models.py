# strategies/models.py – Hardcore Production Socket Models
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import json, uuid
import logging

logger = logging.getLogger("models")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | MODELS | %(levelname)s | %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)

# =========================
# Utils
# =========================
def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def clamp(v: float, lo: float, hi: float) -> float:
    """Clamp a value between lo and hi"""
    return max(lo, min(hi, v))

def parse_ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
        s = str(v)
        if s.endswith("Z"): s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return utc_now()

def f(v: Any, d: float = 0.0) -> float:
    try: return float(v)
    except: return float(d)

def safe_json(obj: Any) -> Any:
    if obj is None: return None
    if isinstance(obj, (str, int, float, bool)): return obj
    if isinstance(obj, datetime): return obj.isoformat()
    if isinstance(obj, dict): return {k: safe_json(v) for k,v in obj.items()}
    if isinstance(obj, (list, tuple)): return [safe_json(x) for x in obj]
    try: return str(obj)
    except: return None

# =========================
# Enums
# =========================
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

class OrderType(Enum):
    MARKET="MARKET"; LIMIT="LIMIT"; STOP="STOP"
    @classmethod
    def from_any(cls,v:Any)->"OrderType":
        if isinstance(v,cls): return v
        if v is None: return cls.MARKET
        s=str(v).strip().upper()
        if s in ("MARKET","MKT"): return cls.MARKET
        if s in ("LIMIT","LMT"): return cls.LIMIT
        if s in ("STOP",): return cls.STOP
        return cls.MARKET

class SocketMessageType(Enum):
    TRADE_SIGNAL="TRADE_SIGNAL"; TRADE_RESULT="TRADE_RESULT"
    ACCOUNT_INFO="ACCOUNT_INFO"; HEARTBEAT="HEARTBEAT"

# =========================
# Socket Message
# =========================
@dataclass
class SocketMessage:
    type: SocketMessageType
    payload: Dict[str, Any]
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    protocol: str = "MT5_SOCKET_V1"
    timestamp: datetime = field(default_factory=utc_now)
    def to_dict(self) -> Dict[str,Any]:
        return {
            "protocol":self.protocol,
            "request_id":self.request_id,
            "type":self.type.value,
            "timestamp":parse_ts(self.timestamp).isoformat(),
            "payload":safe_json(self.payload)
        }
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

# =========================
# Trade Signal
# =========================
@dataclass
class TradeSignal:
    symbol: str
    direction: TradeDirection
    lot_size: float
    order_type: OrderType = OrderType.MARKET
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    strategy: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        # =========================
        # Timestamp
        # =========================
        self.timestamp = parse_ts(self.timestamp)

        # =========================
        # Lote seguro (Hardcore Max)
        # =========================
        max_default_lot = 0.20
        raw_lot = f(self.lot_size, 0.0)
        self.lot_size = clamp(raw_lot, 0.0, max_default_lot)
        if raw_lot > max_default_lot:
            logger.warning(f"[HARDCORE] Lot size {raw_lot} truncated to {max_default_lot} for symbol {getattr(self, 'symbol', '?')}")

        # =========================
        # Entry, SL, TP
        # =========================
        self.entry_price = None if self.entry_price is None else f(self.entry_price)
        self.sl = None if self.sl is None else f(self.sl)
        self.tp = None if self.tp is None else f(self.tp)

        # Evita SL = Entry (divisão por zero em risk manager)
        if self.sl is not None and self.entry_price is not None and self.sl == self.entry_price:
            self.sl += 1e-5
            logger.debug(f"[HARDCORE] SL adjusted slightly to avoid zero distance for {getattr(self, 'symbol', '?')}")

        # =========================
        # Confidence
        # =========================
        if self.confidence is not None:
            try:
                c = f(self.confidence)
                if c > 1.0:  # se vier em percentual (>100)
                    c = min(1.0, c / 100.0)
                self.confidence = clamp(c, 0.0, 1.0)
                if self.confidence > 0.95:
                    logger.debug(f"[HARDCORE] High confidence {self.confidence:.2f} detected for {getattr(self, 'symbol', '?')}")
            except Exception:
                self.confidence = None

        # =========================
        # Direction e OrderType
        # =========================
        self.direction = TradeDirection.from_any(self.direction)
        self.order_type = OrderType.from_any(self.order_type)

        # =========================
        # Metadata seguro
        # =========================
        if not isinstance(self.metadata, dict):
            try:
                self.metadata = dict(self.metadata)
            except Exception:
                self.metadata = {"raw": str(self.metadata)}

    def is_valid(self) -> bool:
        return bool(self.symbol) and self.direction != TradeDirection.HOLD

    def to_payload(self)->Dict[str,Any]:
        p={
            "symbol":self.symbol,
            "direction":self.direction.value,
            "order_type":self.order_type.value,
            "lot_size":self.lot_size,
            "entry_price":self.entry_price,
            "sl":self.sl,
            "tp":self.tp,
            "strategy":self.strategy,
            "confidence":self.confidence,
            "metadata":safe_json(self.metadata),
            "timestamp":self.timestamp.isoformat()
        }
        return {k:v for k,v in p.items() if v is not None}

    def to_socket_message(self)->SocketMessage:
        return SocketMessage(type=SocketMessageType.TRADE_SIGNAL,payload=self.to_payload())

    def to_json(self)->str:
        return json.dumps(self.to_payload(),ensure_ascii=False,default=str)

    @classmethod
    def from_dict(cls,d:Dict[str,Any])->"TradeSignal":
        symbol=d.get("symbol") or d.get("ticker") or d.get("pair") or d.get("instrument")
        direction=d.get("direction") or d.get("action") or d.get("decision") or d.get("signal")
        lot_raw = d.get("lot_size") or d.get("lots") or d.get("volume") or d.get("size")
        lot = 0.0  # forçar avaliação segura pelo RiskManager

        order_type=d.get("order_type") or d.get("type")
        entry=d.get("entry_price") or d.get("price") or d.get("level")
        sl=d.get("sl") or d.get("stop_loss")
        tp=d.get("tp") or d.get("take_profit")
        strategy=d.get("strategy") or d.get("source")
        confidence=d.get("confidence") or d.get("conf") or d.get("score")
        metadata=d.get("metadata") or {k:v for k,v in d.items() if k not in ("symbol","direction","action","decision","signal","lot_size","lots","volume","size","order_type","type","entry_price","price","level","sl","stop_loss","tp","take_profit","strategy","source","confidence","conf","score","timestamp")}
        ts=d.get("timestamp") or d.get("ts") or d.get("time")
        return cls(symbol=symbol,direction=direction,lot_size=f(lot,0.0),order_type=order_type or OrderType.MARKET,
                   entry_price=None if entry is None else f(entry),sl=None if sl is None else f(sl),tp=None if tp is None else f(tp),
                   strategy=strategy,confidence=None if confidence is None else float(confidence),metadata=metadata,timestamp=parse_ts(ts) if ts else utc_now())

# alias
Signal=TradeSignal

# =========================
# Trade Result
# =========================
@dataclass
class TradeResult:
    success: bool
    order_id: Optional[int]=None
    symbol: Optional[str]=None
    filled_price: Optional[float]=None
    filled_lots: Optional[float]=None
    status: Optional[str]=None
    message: Optional[str]=None
    raw: Dict[str,Any]=field(default_factory=dict)
    timestamp: datetime=field(default_factory=utc_now)

    def __post_init__(self):
        self.timestamp=parse_ts(self.timestamp)
        self.filled_price=None if self.filled_price is None else f(self.filled_price)
        self.filled_lots=None if self.filled_lots is None else f(self.filled_lots)

    def to_dict(self)->Dict[str,Any]:
        return {
            "success":bool(self.success),
            "order_id":self.order_id,
            "symbol":self.symbol,
            "filled_price":self.filled_price,
            "filled_lots":self.filled_lots,
            "status":self.status,
            "message":self.message,
            "raw":safe_json(self.raw),
            "timestamp":self.timestamp.isoformat()
        }

    @classmethod
    def from_socket(cls,payload:Dict[str,Any])->"TradeResult":
        return cls(
            success=bool(payload.get("success",False)),
            order_id=payload.get("order_id") or payload.get("ticket"),
            symbol=payload.get("symbol"),
            filled_price=None if payload.get("price") is None else f(payload.get("price")),
            filled_lots=None if payload.get("lots") is None else f(payload.get("lots")),
            status=payload.get("status"),
            message=payload.get("message"),
            raw=payload,
            timestamp=parse_ts(payload.get("timestamp") or payload.get("ts") or utc_now())
        )

# =========================
# Account Info
# =========================
@dataclass
class AccountInfo:
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: Optional[int]=None
    currency: Optional[str]=None
    timestamp: datetime=field(default_factory=utc_now)

    def __post_init__(self):
        self.timestamp=parse_ts(self.timestamp)
        self.balance=f(self.balance)
        self.equity=f(self.equity)
        self.margin=f(self.margin)
        self.free_margin=f(self.free_margin)
        if self.leverage is not None:
            try:self.leverage=int(self.leverage)
            except: self.leverage=None

    def to_dict(self)->Dict[str,Any]:
        return {
            "balance":self.balance,
            "equity":self.equity,
            "margin":self.margin,
            "free_margin":self.free_margin,
            "leverage":self.leverage,
            "currency":self.currency,
            "timestamp":self.timestamp.isoformat()
        }

    @classmethod
    def from_socket(cls,payload:Dict[str,Any])->"AccountInfo":
        return cls(
            balance=payload.get("balance",0.0),
            equity=payload.get("equity",0.0),
            margin=payload.get("margin",0.0),
            free_margin=payload.get("free_margin",payload.get("freeMargin",0.0)),
            leverage=payload.get("leverage"),
            currency=payload.get("currency"),
            timestamp=parse_ts(payload.get("timestamp") or payload.get("ts") or utc_now())
        )
