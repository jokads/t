"""
HybridStrategy - Combina Múltiplas Estratégias com Votação Ponderada

🔥 HARDCORE FIX: Estratégia híbrida que combina sinais de múltiplas estratégias

OBJETIVO:
- Combinar SuperTrend, EMA, RSI, Bollinger, ICT
- Votação ponderada por performance histórica
- Reduzir falsos positivos
- Aumentar confidence de sinais válidos

LÓGICA:
1. Executar todas as estratégias
2. Coletar votos (BUY/SELL/HOLD)
3. Aplicar pesos configuráveis
4. Decisão por maioria ponderada
5. Confidence agregada

PESOS PADRÃO:
- SuperTrend: 30% (trend following)
- EMA Crossover: 20% (momentum)
- RSI: 20% (reversal)
- Bollinger: 15% (volatility)
- ICT: 15% (smart money)
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import logging
import os

logger = logging.getLogger(__name__)


class HybridStrategy:
    """
    Estratégia híbrida que combina múltiplas estratégias com votação ponderada.
    """
    
    def __init__(self):
        self.name = "HybridStrategy"
        
        # Pesos configuráveis via env vars
        self.weights = {
            "supertrend": float(os.getenv("WEIGHT_SUPERTREND", "0.30")),
            "ema": float(os.getenv("WEIGHT_EMA", "0.20")),
            "rsi": float(os.getenv("WEIGHT_RSI", "0.20")),
            "bollinger": float(os.getenv("WEIGHT_BOLLINGER", "0.15")),
            "ict": float(os.getenv("WEIGHT_ICT", "0.15"))
        }
        
        # Normalizar pesos (garantir soma = 1.0)
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            self.weights = {k: v / total_weight for k, v in self.weights.items()}
        
        # Threshold mínimo para executar trade
        self.min_confidence = float(os.getenv("HYBRID_MIN_CONFIDENCE", "0.40"))
        
        # Lazy load de estratégias
        self._strategies = {}
        
    def analyze(self, symbol: str, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Analisa mercado combinando múltiplas estratégias.
        
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
                "reason": str,
                "votes": List[Dict]
            }
        """
        try:
            if data is None or len(data) < 50:
                return self._hold_signal("insufficient_data")
            
            # Garantir DataFrame
            if not isinstance(data, pd.DataFrame):
                try:
                    data = pd.DataFrame(data)
                except Exception:
                    return self._hold_signal("invalid_data_format")
            
            # Coletar votos de todas as estratégias
            votes = []
            
            # SuperTrend
            if "supertrend" in self.weights:
                vote = self._vote_supertrend(data)
                if vote:
                    votes.append({**vote, "strategy": "supertrend", "weight": self.weights["supertrend"]})
            
            # EMA Crossover
            if "ema" in self.weights:
                vote = self._vote_ema(data)
                if vote:
                    votes.append({**vote, "strategy": "ema", "weight": self.weights["ema"]})
            
            # RSI
            if "rsi" in self.weights:
                vote = self._vote_rsi(data)
                if vote:
                    votes.append({**vote, "strategy": "rsi", "weight": self.weights["rsi"]})
            
            # Bollinger Bands
            if "bollinger" in self.weights:
                vote = self._vote_bollinger(data)
                if vote:
                    votes.append({**vote, "strategy": "bollinger", "weight": self.weights["bollinger"]})
            
            # ICT Concepts
            if "ict" in self.weights:
                vote = self._vote_ict(data)
                if vote:
                    votes.append({**vote, "strategy": "ict", "weight": self.weights["ict"]})
            
            # Agregar votos
            decision, confidence, reason = self._aggregate_votes(votes)
            
            # Calcular preços
            current_price = float(data['close'].iloc[-1])
            
            # SL/TP agregado (média ponderada dos votos)
            tp_values = [(v["take_profit"], v["weight"]) for v in votes if v.get("take_profit")]
            sl_values = [(v["stop_loss"], v["weight"]) for v in votes if v.get("stop_loss")]
            
            take_profit = self._weighted_average(tp_values) if tp_values else current_price
            stop_loss = self._weighted_average(sl_values) if sl_values else current_price
            
            return {
                "action": decision,
                "confidence": confidence,
                "price": current_price,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "reason": reason,
                "votes": votes
            }
            
        except Exception as e:
            logger.error(f"HybridStrategy.analyze failed: {e}", exc_info=True)
            return self._hold_signal(f"exception: {str(e)[:50]}")
    
    def _vote_supertrend(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Voto da estratégia SuperTrend."""
        try:
            # Lazy load
            if "supertrend" not in self._strategies:
                from strategies.supertrend_strategy import SuperTrendStrategy
                self._strategies["supertrend"] = SuperTrendStrategy()
            
            result = self._strategies["supertrend"].analyze("", data)
            if result and result.get("action") != "HOLD":
                return {
                    "decision": result["action"],
                    "confidence": result.get("confidence", 0.5),
                    "take_profit": result.get("take_profit", 0.0),
                    "stop_loss": result.get("stop_loss", 0.0)
                }
        except Exception as e:
            logger.debug(f"SuperTrend vote failed: {e}")
        return None
    
    def _vote_ema(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Voto da estratégia EMA Crossover."""
        try:
            if "ema" not in self._strategies:
                from strategies.ema_crossover import EMACrossoverStrategy
                self._strategies["ema"] = EMACrossoverStrategy()
            
            result = self._strategies["ema"].analyze("", data)
            if result and result.get("action") != "HOLD":
                return {
                    "decision": result["action"],
                    "confidence": result.get("confidence", 0.5),
                    "take_profit": result.get("take_profit", 0.0),
                    "stop_loss": result.get("stop_loss", 0.0)
                }
        except Exception as e:
            logger.debug(f"EMA vote failed: {e}")
        return None
    
    def _vote_rsi(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Voto da estratégia RSI."""
        try:
            if "rsi" not in self._strategies:
                from strategies.rsi_strategy import RSIStrategy
                self._strategies["rsi"] = RSIStrategy()
            
            result = self._strategies["rsi"].analyze("", data)
            if result and result.get("action") != "HOLD":
                return {
                    "decision": result["action"],
                    "confidence": result.get("confidence", 0.5),
                    "take_profit": result.get("take_profit", 0.0),
                    "stop_loss": result.get("stop_loss", 0.0)
                }
        except Exception as e:
            logger.debug(f"RSI vote failed: {e}")
        return None
    
    def _vote_bollinger(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Voto da estratégia Bollinger Bands."""
        try:
            # Implementação simplificada (pode usar estratégia dedicada se existir)
            close = data['close'].values
            sma = pd.Series(close).rolling(window=20).mean().values
            std = pd.Series(close).rolling(window=20).std().values
            
            upper_band = sma + (2.0 * std)
            lower_band = sma - (2.0 * std)
            
            current_price = close[-1]
            atr = self._calculate_atr(data)
            
            # Breakout para cima
            if current_price > upper_band[-1]:
                return {
                    "decision": "BUY",
                    "confidence": 0.55,
                    "take_profit": current_price + (atr * 3.0),
                    "stop_loss": current_price - (atr * 1.5)
                }
            # Breakout para baixo
            elif current_price < lower_band[-1]:
                return {
                    "decision": "SELL",
                    "confidence": 0.55,
                    "take_profit": current_price - (atr * 3.0),
                    "stop_loss": current_price + (atr * 1.5)
                }
        except Exception as e:
            logger.debug(f"Bollinger vote failed: {e}")
        return None
    
    def _vote_ict(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Voto da estratégia ICT Concepts."""
        try:
            if "ict" not in self._strategies:
                from strategies.ict_concepts import ICTStrategy
                self._strategies["ict"] = ICTStrategy()
            
            result = self._strategies["ict"].analyze("", data)
            if result and result.get("action") != "HOLD":
                return {
                    "decision": result["action"],
                    "confidence": result.get("confidence", 0.5),
                    "take_profit": result.get("take_profit", 0.0),
                    "stop_loss": result.get("stop_loss", 0.0)
                }
        except Exception as e:
            logger.debug(f"ICT vote failed: {e}")
        return None
    
    def _aggregate_votes(self, votes: List[Dict[str, Any]]) -> tuple:
        """
        Agrega votos com pesos.
        
        Returns:
            (decision, confidence, reason)
        """
        if not votes:
            return "HOLD", 0.0, "no_votes"
        
        # Calcular scores ponderados
        buy_score = sum(
            v["confidence"] * v["weight"]
            for v in votes if v["decision"] == "BUY"
        )
        sell_score = sum(
            v["confidence"] * v["weight"]
            for v in votes if v["decision"] == "SELL"
        )
        
        # Decisão por maior score
        if buy_score > sell_score and buy_score >= self.min_confidence:
            strategies = [v["strategy"] for v in votes if v["decision"] == "BUY"]
            reason = f"hybrid_buy (score={buy_score:.2f}, strategies={strategies})"
            return "BUY", buy_score, reason
        elif sell_score > buy_score and sell_score >= self.min_confidence:
            strategies = [v["strategy"] for v in votes if v["decision"] == "SELL"]
            reason = f"hybrid_sell (score={sell_score:.2f}, strategies={strategies})"
            return "SELL", sell_score, reason
        else:
            reason = f"hybrid_hold (buy={buy_score:.2f}, sell={sell_score:.2f}, min={self.min_confidence})"
            return "HOLD", max(buy_score, sell_score), reason
    
    def _weighted_average(self, values: List[tuple]) -> float:
        """Calcula média ponderada."""
        total_weight = sum(w for _, w in values)
        if total_weight == 0:
            return 0.0
        return sum(v * w for v, w in values) / total_weight
    
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
            return 0.0001
    
    def _hold_signal(self, reason: str) -> Dict[str, Any]:
        """Retorna sinal HOLD padrão."""
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "price": 0.0,
            "take_profit": 0.0,
            "stop_loss": 0.0,
            "reason": reason,
            "votes": []
        }


# Para compatibilidade com trading_bot_core.py
def analyze_market(symbol: str, data: pd.DataFrame) -> Dict[str, Any]:
    """Wrapper para compatibilidade."""
    strategy = HybridStrategy()
    return strategy.analyze(symbol, data)
