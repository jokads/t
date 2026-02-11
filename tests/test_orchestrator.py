"""
Integration tests for trading orchestrator
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from bot_mt5.core.orchestrator import TradingOrchestrator
from bot_mt5.schemas.messages import SignalCreate, SignalPayload, OrderExecute, ErrorMessage


@pytest.mark.asyncio
class TestTradingOrchestrator:
    """Test TradingOrchestrator"""
    
    async def test_generate_and_validate_signals_success(self, mock_config):
        """Test successful signal generation pipeline"""
        # Mock AI manager
        ai_manager = AsyncMock()
        ai_manager.ask.return_value = {
            "success": True,
            "parsed": {
                "action": "BUY",
                "confidence": 0.75,
                "lot": 0.01,
                "stop_loss": 1.0850,
                "take_profit": 1.0900,
                "reason": "Strong uptrend"
            },
            "latency_ms": 50.0,
            "model_type": "test",
        }
        
        # Mock MT5 client
        mt5_client = AsyncMock()
        mt5_client.execute_order.return_value = {
            "success": True,
            "order_id": "123456",
        }
        
        # Create orchestrator
        orchestrator = TradingOrchestrator(
            ai_manager=ai_manager,
            mt5_client=mt5_client,
        )
        
        # Create signal request
        signal_request = SignalCreate(
            auth_token="test_token",
            payload=SignalPayload(
                account_id="12345",
                strategy="SuperTrend",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=0.5,
                price=1.0870,
            ),
        )
        
        # Process signal
        result = await orchestrator.generate_and_validate_signals(signal_request)
        
        # Verify result
        assert isinstance(result, OrderExecute)
        assert result.success is True
        assert result.order_id == "123456"
        assert result.latency_ms > 0
        
        # Verify AI was called
        ai_manager.ask.assert_called_once()
    
    async def test_ai_failure(self, mock_config):
        """Test handling of AI failure"""
        # Mock AI manager that fails
        ai_manager = AsyncMock()
        ai_manager.ask.return_value = {
            "success": False,
            "error": "Model timeout",
        }
        
        orchestrator = TradingOrchestrator(ai_manager=ai_manager)
        
        signal_request = SignalCreate(
            auth_token="test_token",
            payload=SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=0.5,
            ),
        )
        
        result = await orchestrator.generate_and_validate_signals(signal_request)
        
        # Should return error message
        assert isinstance(result, ErrorMessage)
        assert result.error_code == "AI_FAILED"
        assert "timeout" in result.error_message.lower()
    
    async def test_invalid_ai_response(self, mock_config):
        """Test handling of invalid AI response"""
        # Mock AI manager with invalid response
        ai_manager = AsyncMock()
        ai_manager.ask.return_value = {
            "success": True,
            "parsed": None,  # Invalid - no parsed data
            "text": "invalid json",
        }
        
        orchestrator = TradingOrchestrator(ai_manager=ai_manager)
        
        signal_request = SignalCreate(
            auth_token="test_token",
            payload=SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=0.5,
            ),
        )
        
        result = await orchestrator.generate_and_validate_signals(signal_request)
        
        assert isinstance(result, ErrorMessage)
        assert result.error_code == "INVALID_AI_RESPONSE"
    
    async def test_risk_rejection(self, mock_config):
        """Test risk manager rejection"""
        # Mock AI with low confidence
        ai_manager = AsyncMock()
        ai_manager.ask.return_value = {
            "success": True,
            "parsed": {
                "action": "BUY",
                "confidence": 0.3,  # Too low
                "lot": 0.01,
            },
        }
        
        orchestrator = TradingOrchestrator(ai_manager=ai_manager)
        
        signal_request = SignalCreate(
            auth_token="test_token",
            payload=SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=0.5,
            ),
        )
        
        result = await orchestrator.generate_and_validate_signals(signal_request)
        
        assert isinstance(result, ErrorMessage)
        assert result.error_code == "RISK_REJECTED"
        assert "confidence" in result.error_message.lower()
    
    async def test_hold_action_rejected(self, mock_config):
        """Test HOLD action is rejected"""
        ai_manager = AsyncMock()
        ai_manager.ask.return_value = {
            "success": True,
            "parsed": {
                "action": "HOLD",  # Should be rejected
                "confidence": 0.8,
                "lot": 0.01,
            },
        }
        
        orchestrator = TradingOrchestrator(ai_manager=ai_manager)
        
        signal_request = SignalCreate(
            auth_token="test_token",
            payload=SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=0.5,
            ),
        )
        
        result = await orchestrator.generate_and_validate_signals(signal_request)
        
        assert isinstance(result, ErrorMessage)
        assert result.error_code == "RISK_REJECTED"
        assert "HOLD" in result.error_message
    
    async def test_execution_failure(self, mock_config):
        """Test handling of execution failure"""
        ai_manager = AsyncMock()
        ai_manager.ask.return_value = {
            "success": True,
            "parsed": {
                "action": "BUY",
                "confidence": 0.75,
                "lot": 0.01,
            },
        }
        
        # Mock MT5 client that fails
        mt5_client = AsyncMock()
        mt5_client.execute_order.return_value = {
            "success": False,
            "error": "Insufficient margin",
        }
        
        orchestrator = TradingOrchestrator(
            ai_manager=ai_manager,
            mt5_client=mt5_client,
        )
        
        signal_request = SignalCreate(
            auth_token="test_token",
            payload=SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=0.5,
            ),
        )
        
        result = await orchestrator.generate_and_validate_signals(signal_request)
        
        assert isinstance(result, ErrorMessage)
        assert result.error_code == "EXECUTION_FAILED"
        assert "margin" in result.error_message.lower()
    
    async def test_timeout(self, mock_config):
        """Test pipeline timeout"""
        # Mock AI that takes too long
        async def slow_ai(*args, **kwargs):
            await asyncio.sleep(10.0)
            return {"success": True, "parsed": {}}
        
        ai_manager = AsyncMock()
        ai_manager.ask = slow_ai
        
        orchestrator = TradingOrchestrator(ai_manager=ai_manager)
        
        signal_request = SignalCreate(
            auth_token="test_token",
            payload=SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=0.5,
            ),
        )
        
        # Use short timeout
        result = await orchestrator.generate_and_validate_signals(
            signal_request,
            timeout=1.0
        )
        
        assert isinstance(result, ErrorMessage)
        assert result.error_code == "PIPELINE_TIMEOUT"
    
    async def test_no_ai_manager(self, mock_config):
        """Test orchestrator without AI manager (passthrough)"""
        orchestrator = TradingOrchestrator(ai_manager=None)
        
        signal_request = SignalCreate(
            auth_token="test_token",
            payload=SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=0.75,  # High enough to pass risk check
                price=1.0870,
            ),
        )
        
        result = await orchestrator.generate_and_validate_signals(signal_request)
        
        # Should succeed with passthrough (no MT5 client = simulation)
        assert isinstance(result, OrderExecute)
        assert result.success is True
