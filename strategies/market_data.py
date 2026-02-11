# strategies/market_data_hardcore.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence, List
import json
import math
import re

# pandas opcional
try:
    import pandas as pd
except ImportError:
    pd = None

# -------------------------
# Helpers internos
# -------------------------
_ISO_Z_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2}[T\s].*)Z$")

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _parse_datetime(val: Any) -> datetime:
    if val is None:
        return _now_utc()
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc) if val.tzinfo else val.replace(tzinfo=timezone.utc)
    s = str(val).strip()
    if not s:
        return _now_utc()
    # epoch int/float
    try:
        f = float(s)
        if f > 1e12:
            return datetime.fromtimestamp(f / 1000.0, tz=timezone.utc)
        if f > 1e9:
            return datetime.fromtimestamp(f, tz=timezone.utc)
    except Exception:
        pass
    # ISO com Z
    m = _ISO_Z_RE.match(s)
    if m:
        s = m.group("date") + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return _now_utc()

def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        try:
            return float(str(v).replace(",", ".").strip())
        except Exception:
            return default

# -------------------------
# MarketData hardcore
# -------------------------
@dataclass
class MarketData:
    symbol: str = ""
    timestamp: datetime = field(default_factory=_now_utc)
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0

    def __post_init__(self) -> None:
        self.timestamp = _parse_datetime(self.timestamp)
        self.open = _to_float(self.open)
        self.high = _to_float(self.high)
        self.low = _to_float(self.low)
        self.close = _to_float(self.close)
        self.volume = _to_float(self.volume)
        self.bid = _to_float(self.bid)
        self.ask = _to_float(self.ask)
        self.spread = _to_float(self.spread)
        self._normalize_ohlc()
        self._normalize_spread()

    def _normalize_ohlc(self) -> None:
        """Garante coerência OHLC"""
        o, h, l, c = self.open, self.high, self.low, self.close
        self.high = max(h, o, c)
        self.low = min(l, o, c)

    def _normalize_spread(self) -> None:
        """Garante spread positivo coerente com bid/ask"""
        if self.ask > 0 and self.bid > 0:
            self.spread = abs(self.ask - self.bid)
        if self.spread < 0: self.spread = 0.0

    def is_valid(self) -> bool:
        try:
            if any(math.isnan(x) for x in (self.open, self.high, self.low, self.close)):
                return False
            if self.high < self.low:
                return False
            if self.high < max(self.open, self.close):
                return False
            if self.low > min(self.open, self.close):
                return False
            return True
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.astimezone(timezone.utc).isoformat()
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "MarketData":
        if not d:
            return cls()
        if isinstance(d.get("candle"), dict):
            d = {**d, **d["candle"]}
        def pick(*keys, default=None):
            for k in keys:
                if k in d and d[k] is not None:
                    return d[k]
            return default
        return cls(
            symbol=str(pick("symbol", "pair", "instrument", default="")),
            timestamp=pick("timestamp", "time", "date"),
            open=pick("open", "o"),
            high=pick("high", "h"),
            low=pick("low", "l"),
            close=pick("close", "c", "price"),
            volume=pick("volume", "v", default=0.0),
            bid=pick("bid", default=0.0),
            ask=pick("ask", default=0.0),
            spread=pick("spread", default=0.0),
        )

    @classmethod
    def from_any(cls, obj: Any) -> "MarketData":
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, dict):
            return cls.from_dict(obj)
        if isinstance(obj, str):
            try:
                return cls.from_dict(json.loads(obj))
            except Exception:
                return cls()
        if isinstance(obj, (list, tuple)):
            try:
                return cls(timestamp=obj[0], open=obj[1], high=obj[2], low=obj[3], close=obj[4], volume=obj[5] if len(obj)>5 else 0.0)
            except Exception:
                return cls()
        return cls()

    @staticmethod
    def list_to_md(seq: Sequence[Any]) -> List["MarketData"]:
        out: List[MarketData] = []
        if not seq:
            return out
        for x in seq:
            try:
                md = MarketData.from_any(x)
                if md.is_valid():
                    out.append(md)
            except Exception:
                continue
        return out

    def to_pandas(self) -> Any:
        if pd is None:
            raise RuntimeError("pandas not available")
        return pd.DataFrame([self.to_dict()])
