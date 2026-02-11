# strategies/supertrend_hardcore_v2.py — SuperTrend Ultra-Hardcore (AI-integrated)
from __future__ import annotations
import json
import socket
import uuid
import time
import threading
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List, Union, Mapping
import numpy as np
import pandas as pd

logger = logging.getLogger("supertrend_strategy")
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s"))
    logger.addHandler(sh)
logger.setLevel(logging.INFO)

DEFAULT_MT5_HOST = "127.0.0.1"
DEFAULT_MT5_PORT = 9090
MIN_VOLUME = 0.01


# ---------------------------
# Module helpers (volume handling / utils)
# ---------------------------

def _find_volume_column(cols) -> Optional[str]:
    """Return a best-guess volume column name from df.columns (case-insensitive)."""
    if cols is None:
        return None
    candidates = ["volume", "tick_volume", "real_volume", "vol", "size"]
    lc = {str(c).lower(): c for c in cols}
    for cand in candidates:
        if cand in lc:
            return lc[cand]
    # any column containing 'vol'
    for c in cols:
        if "vol" in str(c).lower():
            return c
    return None


def _coerce_volume_series(series: pd.Series, min_volume: float = MIN_VOLUME) -> pd.Series:
    """Convert to numeric, fill NaNs and enforce minimum volume."""
    try:
        s = pd.to_numeric(series, errors="coerce").astype(float)
        s = s.fillna(min_volume).clip(lower=min_volume)
        return s
    except Exception:
        # fallback: create constant min volume
        return pd.Series([min_volume] * len(series), index=getattr(series, 'index', range(len(series))))


def _merge_external_volume(df: pd.DataFrame, external_vol: Any, timeframe_minutes: Optional[int] = None) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Merge external volume into df.

    external_vol can be:
      - pd.Series indexed by timestamps
      - dict mapping ISO timestamp -> value
      - list/array same length as df (aligned by position)
      - DataFrame with a volume column
    Returns (df, source_tag)
    """
    if external_vol is None:
        return df, None

    # If external_vol is a DataFrame with a volume-like column
    if isinstance(external_vol, pd.DataFrame):
        vol_col = _find_volume_column(external_vol.columns)
        if vol_col:
            s = external_vol[vol_col]
            return _merge_external_volume(df, s, timeframe_minutes)

    # Series-like
    if isinstance(external_vol, pd.Series):
        s = external_vol.copy()
        # try convert index to datetime if possible
        if not isinstance(s.index, pd.DatetimeIndex):
            try:
                s.index = pd.to_datetime(s.index)
            except Exception:
                pass

        # if both df and s have DatetimeIndex -> align by nearest within tolerance
        if isinstance(df.index, pd.DatetimeIndex) and isinstance(s.index, pd.DatetimeIndex) and len(s) > 0:
            # ensure sorted
            s = s.sort_index()
            # tolerance: bar duration in minutes (fallback 1 minute)
            tol = pd.Timedelta(minutes=(timeframe_minutes or 1))
            try:
                # use asof-like behavior via reindex(method='nearest') with tolerance
                merged = s.reindex(df.index, method='nearest', tolerance=tol)
                # if many NaNs, try forward/backfill
                merged = merged.fillna(method='ffill').fillna(method='bfill')
                df['volume'] = _coerce_volume_series(merged, MIN_VOLUME)
                return df, 'external_series_nearest'
            except Exception:
                pass

        # if lengths match, align by position
        if len(s) == len(df):
            df['volume'] = _coerce_volume_series(pd.Series(s).values, MIN_VOLUME)
            return df, 'external_array_aligned'

        # try resampling ticks -> per-bar sum if s is tick-level
        try:
            if isinstance(s.index, pd.DatetimeIndex) and isinstance(df.index, pd.DatetimeIndex):
                # infer bar duration
                if len(df.index) >= 2:
                    # compute approximate bar duration
                    delta = (df.index[-1] - df.index[-2])
                    minutes = max(1, int(delta.total_seconds() // 60))
                else:
                    minutes = timeframe_minutes or 1
                vol_per_bar = s.resample(f"{minutes}T").sum()
                vol_per_bar = vol_per_bar.reindex(df.index, method='nearest', tolerance=pd.Timedelta(minutes=minutes))
                vol_per_bar = vol_per_bar.fillna(method='ffill').fillna(method='bfill')
                df['volume'] = _coerce_volume_series(vol_per_bar, MIN_VOLUME)
                return df, 'external_ticks_resampled'
        except Exception:
            pass

    # mapping/dict-like
    if isinstance(external_vol, Mapping):
        try:
            s = pd.Series(external_vol)
            s.index = pd.to_datetime(s.index)
            return _merge_external_volume(df, s, timeframe_minutes)
        except Exception:
            pass

    # list/array same length fallback
    if hasattr(external_vol, '__len__') and len(external_vol) == len(df):
        try:
            df['volume'] = _coerce_volume_series(pd.Series(external_vol), MIN_VOLUME)
            return df, 'external_array'
        except Exception:
            pass

    return df, None


# ---------------------------
# Strategy class
# ---------------------------
class SuperTrendStrategy:
    """
    SuperTrend ultrahardcore v2 — refatorado e hardenizado.
    """

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: int = 15,
        atr_period: int = 10,
        multiplier: float = 3.0,
        trend_filter_period: int = 50,
        cooldown_sec: float = 60.0,
        volume_filter: bool = True,
        mt5_host: str = DEFAULT_MT5_HOST,
        mt5_port: int = DEFAULT_MT5_PORT,
        ai_manager: Optional[Any] = None,
        strategy_engine: Optional[Any] = None,
        audit_path: str = "supertrend_signals.jsonl",
        min_bars: int = 30,
        max_recent_signals: int = 6,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.name = "SuperTrend"
        self.atr_period = max(1, int(atr_period))
        self.multiplier = float(multiplier)
        self.trend_filter_period = max(1, int(trend_filter_period))
        self.cooldown_sec = max(0.1, float(cooldown_sec))
        self.volume_filter = bool(volume_filter)
        self.mt5_host = mt5_host
        self.mt5_port = mt5_port
        self.ai_manager = ai_manager
        self.strategy_engine = strategy_engine
        self.audit_path = audit_path
        self.min_bars = max(10, int(min_bars))
        self._recent_signals: List[float] = []
        self._recent_lock = threading.Lock()
        self._last_signal_ts = 0.0
        self._max_recent = max_recent_signals
        logger.info("SuperTrendStrategy v2 inicializada para %s (%dm)", self.symbol, self.timeframe)

    # ---------------------------
    # Helpers
    # ---------------------------
    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _adaptive_cooldown(self) -> float:
        with self._recent_lock:
            n = len([t for t in self._recent_signals if time.time() - t < 3600])
        factor = 1.0 + (n / max(1, self._max_recent))
        return min(self.cooldown_sec * factor, self.cooldown_sec * 5.0)

    def _on_cooldown(self) -> bool:
        cd = self._adaptive_cooldown()
        return (time.time() - self._last_signal_ts) < cd

    def _record_signal_ts(self, ts: Optional[float] = None) -> None:
        with self._recent_lock:
            self._recent_signals.append(ts or time.time())
            if len(self._recent_signals) > self._max_recent:
                self._recent_signals = self._recent_signals[-self._max_recent:]
        self._last_signal_ts = ts or time.time()

    def _audit_write(self, payload: Dict[str, Any]) -> None:
        try:
            with open(self.audit_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            logger.debug("Audit write failed", exc_info=True)

    def _safe_socket_send(self, payload: dict, host: Optional[str] = None, port: Optional[int] = None, timeout: float = 0.8, retries: int = 2) -> Dict[str, Any]:
        host = host or self.mt5_host
        port = port or self.mt5_port
        b = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        attempt = 0
        while attempt <= retries:
            try:
                with socket.create_connection((host, port), timeout=timeout) as s:
                    s.settimeout(timeout)
                    s.sendall(b)
                    try:
                        ack = s.recv(4096)
                        if ack:
                            return {"ok": True, "ack": ack.decode("utf-8", errors="ignore")}
                        return {"ok": True}
                    except socket.timeout:
                        return {"ok": True, "ack": None}
            except Exception as e:
                logger.debug("socket send failed (attempt %d/%d): %s", attempt + 1, retries + 1, e)
                attempt += 1
                time.sleep(0.1 * attempt)
        return {"ok": False}

    # ---------------------------
    # ATR & SuperTrend
    # ---------------------------
    def calculate_atr(self, data: pd.DataFrame, period: Optional[int] = None) -> pd.Series:
        period = int(period or self.atr_period)
        high, low, close = data["high"], data["low"], data["close"]
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        return tr.rolling(window=period, min_periods=1).mean()

    def calculate_supertrend(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        if len(data) < max(3, self.atr_period + 2):
            return pd.Series(dtype=float, index=data.index), pd.Series(dtype=int, index=data.index)

        atr = self.calculate_atr(data)
        hl2 = (data["high"] + data["low"]) / 2.0
        upper_band = hl2 + (self.multiplier * atr)
        lower_band = hl2 - (self.multiplier * atr)

        st = pd.Series(index=data.index, dtype=float)
        dir_series = pd.Series(index=data.index, dtype=int)

        # safe initialization using first valid index
        first_idx = 0
        try:
            final_upper = float(upper_band.iat[first_idx])
            final_lower = float(lower_band.iat[first_idx])
            dir_series.iat[first_idx] = 1 if float(data["close"].iat[first_idx]) > final_upper else -1
            st.iat[first_idx] = final_lower if dir_series.iat[first_idx] == 1 else final_upper
        except Exception:
            # fallback: fill with defaults
            st[:] = np.nan
            dir_series[:] = 0

        for i in range(max(1, first_idx + 1), len(data)):
            try:
                cur_close = float(data["close"].iat[i])
                u, l = float(upper_band.iat[i]), float(lower_band.iat[i])
                prev_close = float(data["close"].iat[i - 1])

                final_upper = u if (u < final_upper) or (prev_close > final_upper) else final_upper
                final_lower = l if (l > final_lower) or (prev_close < final_lower) else final_lower

                prev_dir = int(dir_series.iat[i - 1])
                if prev_dir == -1 and cur_close > final_upper:
                    dir_series.iat[i] = 1
                elif prev_dir == 1 and cur_close < final_lower:
                    dir_series.iat[i] = -1
                else:
                    dir_series.iat[i] = prev_dir

                st.iat[i] = final_lower if dir_series.iat[i] == 1 else final_upper
            except Exception:
                # keep previous values
                dir_series.iat[i] = int(dir_series.iat[i - 1]) if i - 1 >= 0 else 0
                st.iat[i] = st.iat[i - 1] if i - 1 >= 0 else np.nan

        return st, dir_series

    # ---------------------------
    # Normalize market data (accept DataFrame or MarketData-like)
    # ---------------------------
    def _normalize_df(self, market_data: Union[pd.DataFrame, Any]) -> Optional[pd.DataFrame]:
        if market_data is None:
            return None

        # conversion
        if isinstance(market_data, pd.DataFrame):
            df = market_data.copy()
        else:
            try:
                # allow dict with 'data' key containing the ohlc rows
                if isinstance(market_data, dict) and "data" in market_data:
                    df = pd.DataFrame(market_data.get("data"))
                else:
                    df = pd.DataFrame(market_data)
                if "close" not in df.columns and hasattr(market_data, "__dict__"):
                    df = pd.DataFrame([vars(market_data)])
            except Exception as e:
                logger.debug("normalize_df failed to convert market_data: %s", e)
                return None

        # ensure index is datetime if possible (use provided 'timestamp' column or index)
        if "timestamp" in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df["timestamp"])
            except Exception:
                pass
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                # leave as-is; some callers don't use datetime index
                pass

        # required columns
        required_cols = ("open", "high", "low", "close")
        for c in required_cols:
            if c not in df.columns:
                logger.warning("market_data missing column %s", c)
                return None

        # VOLUME handling: try detect column, then external sources, then fallback
        vol_col = _find_volume_column(df.columns)
        volume_source = None
        if vol_col:
            df["volume"] = _coerce_volume_series(df[vol_col], MIN_VOLUME)
            volume_source = f"col:{vol_col}"
        else:
            # try to extract external volume if provided by contract
            external_vol = None
            if isinstance(market_data, dict):
                external_vol = market_data.get("external_volume") or market_data.get("volume_series") or market_data.get("volume_override")
            if external_vol is None and hasattr(market_data, "volume_series"):
                external_vol = getattr(market_data, "volume_series", None)

            df, ext_src = _merge_external_volume(df, external_vol, timeframe_minutes=self.timeframe)
            if ext_src:
                volume_source = ext_src

        if "volume" not in df.columns or df["volume"].isna().all():
            logger.warning("market_data missing column 'volume', criando volume mínimo = %.2f", MIN_VOLUME)
            df["volume"] = MIN_VOLUME
            volume_source = volume_source or "synthetic_min"

        # final cleaning
        df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=False)
        # keep volume_source as attribute for auditing
        df.attrs["volume_source"] = volume_source
        try:
            # if reset_index produced a timestamp column, keep it as index for later resample logic
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
                df.set_index("timestamp", inplace=True)
        except Exception:
            pass

        return df

    # ---------------------------
    # Ask AI Manager with timeout & safe handling
    # ---------------------------
    def _ask_ai(self, signal_payload: Dict[str, Any], timeout: float = 0.8) -> Dict[str, Any]:
        if not self.ai_manager:
            return {"ok": False, "reason": "no_ai_manager"}
        try:
            # try preferred sync methods
            for name in ("evaluate_signal", "assess_signal", "submit_signal", "ingest_signal"):
                if hasattr(self.ai_manager, name):
                    fn = getattr(self.ai_manager, name)
                    try:
                        # call in thread with timeout
                        from concurrent.futures import ThreadPoolExecutor, TimeoutError
                        with ThreadPoolExecutor(max_workers=1) as ex:
                            fut = ex.submit(fn, signal_payload)
                            try:
                                resp = fut.result(timeout=timeout)
                                return resp if isinstance(resp, dict) else {"ok": True, "response": resp}
                            except TimeoutError:
                                logger.debug("ai_manager %s TIMEOUT after %.3fs", name, timeout)
                                return {"ok": False, "reason": "timeout"}
                    except TypeError:
                        # try without payload
                        try:
                            resp = fn()
                            return resp if isinstance(resp, dict) else {"ok": True, "response": resp}
                        except Exception:
                            continue
            # fallback: if ai_manager exposes async call
            if hasattr(self.ai_manager, "chat"):
                try:
                    # try to call synchronously if possible
                    res = self.ai_manager.chat(signal_payload)
                    return res if isinstance(res, dict) else {"ok": True, "response": res}
                except Exception:
                    pass
            # best-effort: fire-and-forget over socket
            payload = {"type": "request_signal", "payload": signal_payload, "ts": self._now_iso()}
            try:
                self._safe_socket_send(payload)
            except Exception:
                pass
        except Exception as e:
            logger.debug("ai_manager call failed: %s", e)
        return {"ok": False}

    # ---------------------------
    # Generate signal
    # ---------------------------
    def generate_signal(self, market_data: Union[pd.DataFrame, Any]) -> Optional[Dict[str, Any]]:
        df = self._normalize_df(market_data)
        if df is None or len(df) < max(self.min_bars, self.atr_period + 5):
            return None

        if self._on_cooldown():
            logger.debug("Cooldown ativo (adaptive) para %s", self.symbol)
            return None

        st, dir_series = self.calculate_supertrend(df)
        if st.empty or dir_series.empty:
            return None

        last_dir = int(dir_series.iat[-1]) if len(dir_series) > 0 else 0
        price = float(df["close"].iat[-1]) if "close" in df.columns and len(df) > 0 else None
        if price is None:
            return None

        atr = float(self.calculate_atr(df).iat[-1]) if len(df) >= self.atr_period else float((df["high"] - df["low"]).iloc[-1])
        base_conf = 0.5 + 0.25 * (1.0 if last_dir != 0 else 0.0)

        # trend filter
        try:
            trend_slow = df["close"].rolling(self.trend_filter_period).mean().iloc[-1]
            trend_ok = (last_dir == 1 and price >= trend_slow) or (last_dir == -1 and price <= trend_slow)
        except Exception:
            trend_ok = True

        if not trend_ok:
            logger.debug("Trend filter blocked signal for %s", self.symbol)
            return None

        default_sig = {
            "direction": "BUY" if last_dir == 1 else "SELL",
            "confidence": base_conf,
            "price": price,
            "sl": round(price - (atr * 1.5), 6) if last_dir == 1 else round(price + (atr * 1.5), 6),
            "tp": round(price + (atr * 3.0), 6) if last_dir == 1 else round(price - (atr * 3.0), 6),
            "source": self.name,
        }

        # strategy engine signals
        other_signals: List[Dict[str, Any]] = []
        if self.strategy_engine:
            try:
                res = self.strategy_engine.run_strategies_aggregated(market_data=df, timeout=1.0)
                if isinstance(res, dict):
                    other_signals = res.get("metadata", {}).get("aggregated_signals", []) or res.get("aggregated_signals", [])
                else:
                    other_signals = getattr(res, "metadata", {}).get("aggregated_signals", []) if res else []
            except Exception as e:
                logger.debug("strategy_engine gather failed: %s", e)

        # ai candidate
        ai_candidate = dict(default_sig)
        ai_candidate["symbol"] = self.symbol
        ai_candidate["timestamp"] = self._now_iso()
        ai_response = self._ask_ai(ai_candidate, timeout=0.8)
        ai_signals: List[Dict[str, Any]] = []
        if isinstance(ai_response, dict):
            if ai_response.get("ok") and "signals" in ai_response:
                ai_signals = ai_response.get("signals", [])
            elif ai_response.get("ok") and ai_response.get("signal"):
                ai_signals = [ai_response.get("signal")]
            elif ai_response.get("approved") is True:
                ai_signals = [ai_candidate]

        all_signals = [default_sig] + (other_signals or []) + (ai_signals or [])

        # aggregate
        vote_counter = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        weighted_entry, weighted_tp, weighted_sl = [], [], []
        origins = []
        for s in all_signals:
            dir_ = (s.get("direction") or s.get("action") or "HOLD").upper()
            conf_ = float(s.get("confidence", 0.5)) if s.get("confidence") is not None else 0.5
            vote_counter[dir_] = vote_counter.get(dir_, 0.0) + conf_
            p = s.get("price")
            tp = s.get("tp") or s.get("take_profit")
            sl = s.get("sl") or s.get("stop_loss")
            if p is not None:
                try:
                    weighted_entry.append((float(p), conf_))
                except Exception:
                    pass
            if tp is not None:
                try:
                    weighted_tp.append((float(tp), conf_))
                except Exception:
                    pass
            if sl is not None:
                try:
                    weighted_sl.append((float(sl), conf_))
                except Exception:
                    pass
            origins.append(s.get("source", s.get("strategy", "unknown")))

        q_vals = np.array([vote_counter.get("BUY", 0.0), vote_counter.get("SELL", 0.0), vote_counter.get("HOLD", 0.0)], dtype=float)
        if np.allclose(q_vals, 0.0):
            q_vals += 1e-6
        exp_q = np.exp(q_vals - q_vals.max())
        probs = exp_q / (exp_q.sum() + 1e-12)
        dirs = ["BUY", "SELL", "HOLD"]
        meta_dir = dirs[int(np.argmax(probs))]
        meta_conf = float(np.max(probs))

        def _robust_avg(lst: List[tuple]) -> Optional[float]:
            if not lst:
                return None
            vals = np.array([v for v, _ in lst], dtype=float)
            wts = np.array([w for _, w in lst], dtype=float)
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

        entry_price = _robust_avg(weighted_entry) or price
        take_profit = _robust_avg(weighted_tp) or default_sig["tp"]
        stop_loss = _robust_avg(weighted_sl) or default_sig["sl"]

        # extra filters
        vol_ok = True
        try:
            recent_vol_mean = float(df["volume"].rolling(20).mean().iloc[-1])
            last_vol = float(df["volume"].iloc[-1])
            if self.volume_filter and recent_vol_mean > 0 and (last_vol / (recent_vol_mean + 1e-9)) > 6.0:
                vol_ok = False
                logger.debug("Volume spike -> ignoring (last_vol/mean=%.2f) for %s", last_vol / (recent_vol_mean + 1e-9), self.symbol)
        except Exception:
            pass

        if not vol_ok:
            return None

        # build final payload
        sig = {
            "action": meta_dir,
            "price": round(float(entry_price), 6) if entry_price is not None else None,
            "stop_loss": round(float(stop_loss), 6) if stop_loss is not None else None,
            "take_profit": round(float(take_profit), 6) if take_profit is not None else None,
            "confidence": round(float(meta_conf), 3),
            "timestamp": self._now_iso(),
            "reason": f"SuperTrend ultrahardcore v2 aggregated ({self.name})",
            "meta": {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "origins": origins,
                "ai_ok": bool(ai_signals),
                "atr": round(float(atr), 6),
                "computed_at": self._now_iso(),
                "uuid": str(uuid.uuid4())[:8],
                # volume debug
                "volume_source": getattr(df, 'attrs', {}).get('volume_source', None),
                "volume_mean": float(df['volume'].mean()) if 'volume' in df.columns else None,
            },
        }

        # record + adaptive cooldown + audit
        self._record_signal_ts()
        try:
            self._audit_write({"ts": self._now_iso(), "signal": sig})
        except Exception:
            logger.debug("audit failed", exc_info=True)

        logger.info("Signal gerado %s: %s", self.name, sig)
        # notify ai_manager asynchronously (best-effort)
        try:
            threading.Thread(target=self._ask_ai, args=(dict(sig), 0.5), daemon=True).start()
        except Exception:
            pass

        # attempt deliver to MT5 socket async
        payload = {
            "type": "trade_signal",
            "source": self.name,
            "symbol": self.symbol,
            "action": sig["action"],
            "price": sig["price"],
            "stop_loss": sig["stop_loss"],
            "take_profit": sig["take_profit"],
            "confidence": sig["confidence"],
            "reason": sig["reason"],
            "timestamp": sig["timestamp"],
            "meta": sig["meta"],
        }
        threading.Thread(target=self._safe_socket_send, args=(payload, self.mt5_host, self.mt5_port, 0.8, 2), daemon=True).start()

        return sig
