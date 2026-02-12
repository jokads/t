"""
FallbackStrategy - Rule-Based Strategy (Conservative)

🔥 HARDCORE FIX: Estratégia de fallback quando AI falha

OBJETIVO:
- Funcionar SEMPRE (sem dependência de AI)
- Sinais conservadores baseados em indicadores técnicos
- Usado quando AI retorna HOLD ou falha

LÓGICA:
1. EMA 20/50 crossover (trend)
2. RSI oversold/overbought (reversal)
3. Bollinger Bands squeeze (volatility)
4. Combinar sinais (votação)

RESULTADO:
- BUY: EMA bullish + RSI não overbought + BB não overbought
- SELL: EMA bearish + RSI não oversold + BB não oversold
- HOLD: Sinais conflitantes
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class FallbackStrategy:
    """
    Estratégia conservadora rule-based para fallback quando AI falha.
    """
    
    def __init__(self):
        self.name = "FallbackStrategy"
        self.ema_fast_period = 20
        self.ema_slow_period = 50
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.bb_period = 20
        self.bb_std = 2.0
        
    def analyze(self, symbol: str, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Analisa mercado e retorna sinal.
        
        Args:
            symbol: Par de moedas (ex: EURUSD)
            data: DataFrame com OHLCV
            
        Returns:
            {
                "action": "BUY" | "SELL" | "HOLD",
                "confidence": float (0.0-1.0),
                "price": float,
                "take_profit": float,
                "stop_loss": float,
                "reason": str
            }
        """
        try:
            if data is None or len(data) < max(self.ema_slow_period, self.bb_period):
                return self._hold_signal("insufficient_data")
            
            # Garantir que data é DataFrame
            if not isinstance(data, pd.DataFrame):
                try:
                    data = pd.DataFrame(data)
                except Exception:
                    return self._hold_signal("invalid_data_format")
            
            # Calcular indicadores
            ema_signal = self._ema_crossover(data)
            rsi_signal = self._rsi_extreme(data)
            bb_signal = self._bollinger_squeeze(data)
            
            # Combinar sinais
            decision, confidence, reason = self._combine_signals(
                ema_signal, rsi_signal, bb_signal
            )
            
            # Calcular preços
            current_price = float(data['close'].iloc[-1])
            atr = self._calculate_atr(data, period=14)
            
            # SL/TP baseado em ATR
            sl_distance = atr * 1.5
            tp_distance = atr * 3.0
            
            if decision == "BUY":
                stop_loss = current_price - sl_distance
                take_profit = current_price + tp_distance
            elif decision == "SELL":
                stop_loss = current_price + sl_distance
                take_profit = current_price - tp_distance
            else:
                stop_loss = current_price
                take_profit = current_price
            
            return {
                "action": decision,
                "confidence": confidence,
                "price": current_price,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "reason": reason,
                "indicators": {
                    "ema_signal": ema_signal,
                    "rsi_signal": rsi_signal,
                    "bb_signal": bb_signal
                }
            }
            
        except Exception as e:
            logger.error(f"FallbackStrategy.analyze failed: {e}", exc_info=True)
            return self._hold_signal(f"exception: {str(e)[:50]}")
    
    def _ema_crossover(self, data: pd.DataFrame) -> str:
        """
        Detecta EMA crossover.
        
        Returns:
            "BUY" | "SELL" | "NEUTRAL"
        """
        try:
            close = data['close'].values
            
            # Calcular EMAs
            ema_fast = self._calculate_ema(close, self.ema_fast_period)
            ema_slow = self._calculate_ema(close, self.ema_slow_period)
            
            # Crossover recente (últimos 3 candles)
            if ema_fast[-1] > ema_slow[-1] and ema_fast[-3] <= ema_slow[-3]:
                return "BUY"
            elif ema_fast[-1] < ema_slow[-1] and ema_fast[-3] >= ema_slow[-3]:
                return "SELL"
            
            # Trend atual (sem crossover)
            if ema_fast[-1] > ema_slow[-1]:
                return "BUY"
            elif ema_fast[-1] < ema_slow[-1]:
                return "SELL"
            
            return "NEUTRAL"
            
        except Exception as e:
            logger.debug(f"EMA crossover failed: {e}")
            return "NEUTRAL"
    
    def _rsi_extreme(self, data: pd.DataFrame) -> str:
        """
        Detecta RSI oversold/overbought.
        
        Returns:
            "BUY" | "SELL" | "NEUTRAL"
        """
        try:
            close = data['close'].values
            rsi = self._calculate_rsi(close, self.rsi_period)
            
            current_rsi = rsi[-1]
            
            if current_rsi < self.rsi_oversold:
                return "BUY"  # Oversold → reversal para cima
            elif current_rsi > self.rsi_overbought:
                return "SELL"  # Overbought → reversal para baixo
            
            return "NEUTRAL"
            
        except Exception as e:
            logger.debug(f"RSI extreme failed: {e}")
            return "NEUTRAL"
    
    def _bollinger_squeeze(self, data: pd.DataFrame) -> str:
        """
        Detecta Bollinger Bands squeeze/breakout.
        
        Returns:
            "BUY" | "SELL" | "NEUTRAL"
        """
        try:
            close = data['close'].values
            
            # Calcular Bollinger Bands
            sma = self._calculate_sma(close, self.bb_period)
            std = self._calculate_std(close, self.bb_period)
            
            upper_band = sma + (self.bb_std * std)
            lower_band = sma - (self.bb_std * std)
            
            current_price = close[-1]
            
            # Breakout para cima
            if current_price > upper_band[-1]:
                return "BUY"
            # Breakout para baixo
            elif current_price < lower_band[-1]:
                return "SELL"
            
            return "NEUTRAL"
            
        except Exception as e:
            logger.debug(f"Bollinger squeeze failed: {e}")
            return "NEUTRAL"
    
    def _combine_signals(self, ema: str, rsi: str, bb: str) -> tuple:
        """
        Combina sinais de múltiplos indicadores.
        
        Returns:
            (decision, confidence, reason)
        """
        signals = {"BUY": 0, "SELL": 0, "NEUTRAL": 0}
        
        # Votar
        signals[ema] += 1
        signals[rsi] += 1
        signals[bb] += 1
        
        # Decisão por maioria
        if signals["BUY"] >= 2:
            confidence = 0.50 + (signals["BUY"] / 6.0)  # 0.50-0.67
            reason = f"fallback_buy (ema={ema}, rsi={rsi}, bb={bb})"
            return "BUY", confidence, reason
        elif signals["SELL"] >= 2:
            confidence = 0.50 + (signals["SELL"] / 6.0)  # 0.50-0.67
            reason = f"fallback_sell (ema={ema}, rsi={rsi}, bb={bb})"
            return "SELL", confidence, reason
        else:
            confidence = 0.30
            reason = f"fallback_hold (conflicting: ema={ema}, rsi={rsi}, bb={bb})"
            return "HOLD", confidence, reason
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calcula Exponential Moving Average."""
        return pd.Series(data).ewm(span=period, adjust=False).mean().values
    
    def _calculate_sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calcula Simple Moving Average."""
        return pd.Series(data).rolling(window=period).mean().values
    
    def _calculate_std(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calcula Standard Deviation."""
        return pd.Series(data).rolling(window=period).std().values
    
    def _calculate_rsi(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calcula Relative Strength Index."""
        deltas = np.diff(data)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(data)
        rsi[:period] = 100.0 - 100.0 / (1.0 + rs)
        
        for i in range(period, len(data)):
            delta = deltas[i - 1]
            if delta > 0:
                upval = delta
                downval = 0.0
            else:
                upval = 0.0
                downval = -delta
            
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            
            rs = up / down if down != 0 else 0
            rsi[i] = 100.0 - 100.0 / (1.0 + rs)
        
        return rsi
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calcula Average True Range."""
        try:
            high = data['high'].values
            low = data['low'].values
            close = data['close'].values
            
            tr = np.maximum(
                high[1:] - low[1:],
                np.maximum(
                    np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:] - close[:-1])
                )
            )
            
            atr = np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
            return float(atr)
            
        except Exception:
            return 0.0001  # Fallback mínimo
    
    def _hold_signal(self, reason: str) -> Dict[str, Any]:
        """Retorna sinal HOLD padrão."""
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "price": 0.0,
            "take_profit": 0.0,
            "stop_loss": 0.0,
            "reason": reason
        }


# Para compatibilidade com trading_bot_core.py
def analyze_market(symbol: str, data: pd.DataFrame) -> Dict[str, Any]:
    """Wrapper para compatibilidade."""
    strategy = FallbackStrategy()
    return strategy.analyze(symbol, data)
