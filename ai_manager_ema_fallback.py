# 🔥 ULTIMATE FIX: EMA Crossover Fallback Method
# Add this method to AIManager class in ai_manager.py

def _ema_crossover_fallback(self, market_df, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fallback rule-based strategy: EMA crossover (9/21)
    Usado quando TODOS os modelos AI retornam HOLD 0.0
    
    Returns:
        dict com keys: action, confidence, tp, sl
        ou None se não houver sinal
    """
    import pandas as pd
    import numpy as np
    
    try:
        # Convert to DataFrame if needed
        if isinstance(market_df, dict):
            df = pd.DataFrame([market_df])
        elif isinstance(market_df, str):
            return None  # Can't process string
        else:
            df = market_df
        
        if df is None or len(df) < 21:
            return None
        
        # Calculate EMAs
        close = df['close'].values if 'close' in df.columns else df['Close'].values
        
        ema_fast = pd.Series(close).ewm(span=9, adjust=False).mean()
        ema_slow = pd.Series(close).ewm(span=21, adjust=False).mean()
        
        # Current and previous values
        fast_curr = float(ema_fast.iloc[-1])
        slow_curr = float(ema_slow.iloc[-1])
        fast_prev = float(ema_fast.iloc[-2])
        slow_prev = float(ema_slow.iloc[-2])
        
        # Detect crossover
        bullish_cross = (fast_prev <= slow_prev) and (fast_curr > slow_curr)
        bearish_cross = (fast_prev >= slow_prev) and (fast_curr < slow_curr)
        
        if bullish_cross:
            # Calculate ATR for SL/TP
            high = df['high'].values if 'high' in df.columns else df['High'].values
            low = df['low'].values if 'low' in df.columns else df['Low'].values
            
            tr = np.maximum(high[1:] - low[1:], 
                           np.maximum(np.abs(high[1:] - close[:-1]), 
                                     np.abs(low[1:] - close[:-1])))
            atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else float(np.mean(tr))
            
            # Convert ATR to pips (assuming 4-digit broker)
            price = float(close[-1])
            point = 0.0001 if price < 100 else 0.01  # Forex vs indices
            atr_pips = atr / point
            
            return {
                "action": "BUY",
                "confidence": 0.65,  # Medium confidence for rule-based
                "tp": max(100.0, atr_pips * 2.0),
                "sl": max(50.0, atr_pips * 1.5),
                "reason": "EMA_9_21_bullish_crossover"
            }
        
        elif bearish_cross:
            # Calculate ATR
            high = df['high'].values if 'high' in df.columns else df['High'].values
            low = df['low'].values if 'low' in df.columns else df['Low'].values
            
            tr = np.maximum(high[1:] - low[1:], 
                           np.maximum(np.abs(high[1:] - close[:-1]), 
                                     np.abs(low[1:] - close[:-1])))
            atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else float(np.mean(tr))
            
            price = float(close[-1])
            point = 0.0001 if price < 100 else 0.01
            atr_pips = atr / point
            
            return {
                "action": "SELL",
                "confidence": 0.65,
                "tp": max(100.0, atr_pips * 2.0),
                "sl": max(50.0, atr_pips * 1.5),
                "reason": "EMA_9_21_bearish_crossover"
            }
        
        else:
            # No crossover - check if strongly trending
            distance = abs(fast_curr - slow_curr) / slow_curr
            
            if distance > 0.005:  # 0.5% separation
                if fast_curr > slow_curr:
                    # Strong uptrend
                    high = df['high'].values if 'high' in df.columns else df['High'].values
                    low = df['low'].values if 'low' in df.columns else df['Low'].values
                    tr = np.maximum(high[1:] - low[1:], 
                                   np.maximum(np.abs(high[1:] - close[:-1]), 
                                             np.abs(low[1:] - close[:-1])))
                    atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else float(np.mean(tr))
                    price = float(close[-1])
                    point = 0.0001 if price < 100 else 0.01
                    atr_pips = atr / point
                    
                    return {
                        "action": "BUY",
                        "confidence": 0.55,  # Lower confidence (no crossover)
                        "tp": max(100.0, atr_pips * 2.0),
                        "sl": max(50.0, atr_pips * 1.5),
                        "reason": "EMA_9_21_strong_uptrend"
                    }
                else:
                    # Strong downtrend
                    high = df['high'].values if 'high' in df.columns else df['High'].values
                    low = df['low'].values if 'low' in df.columns else df['Low'].values
                    tr = np.maximum(high[1:] - low[1:], 
                                   np.maximum(np.abs(high[1:] - close[:-1]), 
                                             np.abs(low[1:] - close[:-1])))
                    atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else float(np.mean(tr))
                    price = float(close[-1])
                    point = 0.0001 if price < 100 else 0.01
                    atr_pips = atr / point
                    
                    return {
                        "action": "SELL",
                        "confidence": 0.55,
                        "tp": max(100.0, atr_pips * 2.0),
                        "sl": max(50.0, atr_pips * 1.5),
                        "reason": "EMA_9_21_strong_downtrend"
                    }
            
            # No clear signal
            return None
    
    except Exception as e:
        log = getattr(self, "logger", logging.getLogger(__name__))
        log.debug(f"EMA fallback exception: {e}")
        return None
