"""
Unit tests for strategies
"""

import pytest
import pandas as pd
import numpy as np
from strategies.fallback_strategy import FallbackStrategy
from strategies.hybrid_strategy import HybridStrategy


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing."""
    np.random.seed(42)
    n = 100
    
    # Generate realistic price data
    close = 1.0870 + np.cumsum(np.random.randn(n) * 0.0001)
    high = close + np.random.rand(n) * 0.0005
    low = close - np.random.rand(n) * 0.0005
    open_price = close + np.random.randn(n) * 0.0002
    volume = np.random.randint(1000, 10000, n)
    
    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })


class TestFallbackStrategy:
    """Tests for FallbackStrategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = FallbackStrategy()
        assert strategy.name == "FallbackStrategy"
        assert strategy.ema_fast_period == 20
        assert strategy.ema_slow_period == 50
    
    def test_analyze_with_valid_data(self, sample_data):
        """Test analyze with valid data."""
        strategy = FallbackStrategy()
        result = strategy.analyze("EURUSD", sample_data)
        
        assert "action" in result
        assert result["action"] in ["BUY", "SELL", "HOLD"]
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0
        assert "price" in result
        assert "take_profit" in result
        assert "stop_loss" in result
        assert "reason" in result
    
    def test_analyze_with_insufficient_data(self):
        """Test analyze with insufficient data."""
        strategy = FallbackStrategy()
        small_data = pd.DataFrame({
            'close': [1.0870, 1.0871, 1.0872]
        })
        
        result = strategy.analyze("EURUSD", small_data)
        assert result["action"] == "HOLD"
        assert result["reason"] == "insufficient_data"
    
    def test_analyze_with_none_data(self):
        """Test analyze with None data."""
        strategy = FallbackStrategy()
        result = strategy.analyze("EURUSD", None)
        
        assert result["action"] == "HOLD"
        assert "insufficient_data" in result["reason"]
    
    def test_ema_crossover(self, sample_data):
        """Test EMA crossover detection."""
        strategy = FallbackStrategy()
        signal = strategy._ema_crossover(sample_data)
        
        assert signal in ["BUY", "SELL", "NEUTRAL"]
    
    def test_rsi_extreme(self, sample_data):
        """Test RSI extreme detection."""
        strategy = FallbackStrategy()
        signal = strategy._rsi_extreme(sample_data)
        
        assert signal in ["BUY", "SELL", "NEUTRAL"]
    
    def test_bollinger_squeeze(self, sample_data):
        """Test Bollinger Bands squeeze detection."""
        strategy = FallbackStrategy()
        signal = strategy._bollinger_squeeze(sample_data)
        
        assert signal in ["BUY", "SELL", "NEUTRAL"]
    
    def test_combine_signals(self):
        """Test signal combination logic."""
        strategy = FallbackStrategy()
        
        # Test BUY majority
        decision, confidence, reason = strategy._combine_signals("BUY", "BUY", "NEUTRAL")
        assert decision == "BUY"
        assert confidence >= 0.50
        
        # Test SELL majority
        decision, confidence, reason = strategy._combine_signals("SELL", "SELL", "NEUTRAL")
        assert decision == "SELL"
        assert confidence >= 0.50
        
        # Test conflicting signals
        decision, confidence, reason = strategy._combine_signals("BUY", "SELL", "NEUTRAL")
        assert decision == "HOLD"


class TestHybridStrategy:
    """Tests for HybridStrategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = HybridStrategy()
        assert strategy.name == "HybridStrategy"
        assert "supertrend" in strategy.weights
        assert "ema" in strategy.weights
        assert "rsi" in strategy.weights
    
    def test_weights_normalization(self):
        """Test that weights sum to 1.0."""
        strategy = HybridStrategy()
        total_weight = sum(strategy.weights.values())
        assert abs(total_weight - 1.0) < 0.01  # Allow small floating point error
    
    def test_analyze_with_valid_data(self, sample_data):
        """Test analyze with valid data."""
        strategy = HybridStrategy()
        result = strategy.analyze("EURUSD", sample_data)
        
        assert "action" in result
        assert result["action"] in ["BUY", "SELL", "HOLD"]
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0
        assert "votes" in result
        assert isinstance(result["votes"], list)
    
    def test_analyze_with_insufficient_data(self):
        """Test analyze with insufficient data."""
        strategy = HybridStrategy()
        small_data = pd.DataFrame({
            'close': [1.0870, 1.0871]
        })
        
        result = strategy.analyze("EURUSD", small_data)
        assert result["action"] == "HOLD"
    
    def test_aggregate_votes_buy(self):
        """Test vote aggregation for BUY."""
        strategy = HybridStrategy()
        votes = [
            {"decision": "BUY", "confidence": 0.70, "weight": 0.30, "strategy": "supertrend", "take_profit": 1.0900, "stop_loss": 1.0850},
            {"decision": "BUY", "confidence": 0.60, "weight": 0.20, "strategy": "ema", "take_profit": 1.0900, "stop_loss": 1.0850},
            {"decision": "SELL", "confidence": 0.50, "weight": 0.15, "strategy": "rsi", "take_profit": 1.0840, "stop_loss": 1.0880}
        ]
        
        decision, confidence, reason = strategy._aggregate_votes(votes)
        
        # BUY score: 0.70*0.30 + 0.60*0.20 = 0.21 + 0.12 = 0.33
        # SELL score: 0.50*0.15 = 0.075
        # BUY should win but may not meet min_confidence (0.40 default)
        assert decision in ["BUY", "HOLD"]
    
    def test_aggregate_votes_no_votes(self):
        """Test vote aggregation with no votes."""
        strategy = HybridStrategy()
        decision, confidence, reason = strategy._aggregate_votes([])
        
        assert decision == "HOLD"
        assert confidence == 0.0
    
    def test_weighted_average(self):
        """Test weighted average calculation."""
        strategy = HybridStrategy()
        values = [(100.0, 0.5), (200.0, 0.3), (150.0, 0.2)]
        
        avg = strategy._weighted_average(values)
        expected = (100*0.5 + 200*0.3 + 150*0.2) / 1.0
        
        assert abs(avg - expected) < 0.01


# Integration test
def test_strategies_compatibility(sample_data):
    """Test that both strategies work together."""
    fallback = FallbackStrategy()
    hybrid = HybridStrategy()
    
    fallback_result = fallback.analyze("EURUSD", sample_data)
    hybrid_result = hybrid.analyze("EURUSD", sample_data)
    
    # Both should return valid results
    assert fallback_result["action"] in ["BUY", "SELL", "HOLD"]
    assert hybrid_result["action"] in ["BUY", "SELL", "HOLD"]
    
    # Both should have confidence
    assert 0.0 <= fallback_result["confidence"] <= 1.0
    assert 0.0 <= hybrid_result["confidence"] <= 1.0
