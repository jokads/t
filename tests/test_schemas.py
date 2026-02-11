"""
Tests for pydantic schemas
"""
import pytest
from pydantic import ValidationError

from bot_mt5.schemas.messages import (
    SignalPayload,
    SignalCreate,
    OrderExecute,
    Heartbeat,
    ErrorMessage,
    AuthRequest,
    AuthResponse,
)


class TestSignalPayload:
    """Test SignalPayload schema"""
    
    def test_valid_payload(self):
        """Test valid signal payload"""
        payload = SignalPayload(
            account_id="12345",
            strategy="SuperTrend",
            symbol="EURUSD",
            action="BUY",
            lot=0.01,
            stop_loss=1.0850,
            take_profit=1.0900,
            confidence=0.75,
            price=1.0870,
        )
        
        assert payload.account_id == "12345"
        assert payload.symbol == "EURUSD"
        assert payload.action == "BUY"
        assert payload.confidence == 0.75
    
    def test_symbol_uppercase(self):
        """Test symbol is converted to uppercase"""
        payload = SignalPayload(
            account_id="12345",
            strategy="Test",
            symbol="eurusd",  # lowercase
            action="BUY",
            lot=0.01,
            confidence=0.5,
        )
        
        assert payload.symbol == "EURUSD"  # Should be uppercase
    
    def test_invalid_symbol(self):
        """Test invalid symbol format"""
        with pytest.raises(ValidationError):
            SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EUR",  # Too short
                action="BUY",
                lot=0.01,
                confidence=0.5,
            )
    
    def test_invalid_action(self):
        """Test invalid action"""
        with pytest.raises(ValidationError):
            SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="INVALID",  # Not BUY/SELL/HOLD
                lot=0.01,
                confidence=0.5,
            )
    
    def test_confidence_range(self):
        """Test confidence must be 0-1"""
        # Valid
        payload = SignalPayload(
            account_id="12345",
            strategy="Test",
            symbol="EURUSD",
            action="BUY",
            lot=0.01,
            confidence=0.5,
        )
        assert payload.confidence == 0.5
        
        # Invalid - too high
        with pytest.raises(ValidationError):
            SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=1.5,
            )
        
        # Invalid - negative
        with pytest.raises(ValidationError):
            SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=-0.1,
            )
    
    def test_lot_validation(self):
        """Test lot size validation"""
        # Valid
        payload = SignalPayload(
            account_id="12345",
            strategy="Test",
            symbol="EURUSD",
            action="BUY",
            lot=0.01,
            confidence=0.5,
        )
        assert payload.lot == 0.01
        
        # Invalid - zero
        with pytest.raises(ValidationError):
            SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.0,
                confidence=0.5,
            )
        
        # Invalid - too large
        with pytest.raises(ValidationError):
            SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=101.0,
                confidence=0.5,
            )


class TestSignalCreate:
    """Test SignalCreate schema"""
    
    def test_valid_signal_create(self):
        """Test valid signal create message"""
        signal = SignalCreate(
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
        
        assert signal.type == "signal.create"
        assert signal.auth_token == "test_token"
        assert signal.payload.symbol == "EURUSD"
    
    def test_timestamp_auto_generated(self):
        """Test timestamp is auto-generated"""
        signal = SignalCreate(
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
        
        assert signal.timestamp is not None
        assert isinstance(signal.timestamp, str)


class TestOrderExecute:
    """Test OrderExecute schema"""
    
    def test_success_response(self):
        """Test successful order execution response"""
        response = OrderExecute(
            success=True,
            order_id="123456",
            payload=SignalPayload(
                account_id="12345",
                strategy="Test",
                symbol="EURUSD",
                action="BUY",
                lot=0.01,
                confidence=0.5,
            ),
            latency_ms=125.5,
        )
        
        assert response.type == "order.execute"
        assert response.success is True
        assert response.order_id == "123456"
        assert response.latency_ms == 125.5
    
    def test_error_response(self):
        """Test error response"""
        response = OrderExecute(
            success=False,
            error="Timeout",
        )
        
        assert response.success is False
        assert response.error == "Timeout"
        assert response.order_id is None


class TestHeartbeat:
    """Test Heartbeat schema"""
    
    def test_ping(self):
        """Test heartbeat ping"""
        ping = Heartbeat(
            type="heartbeat.ping",
            sender="ea",
        )
        
        assert ping.type == "heartbeat.ping"
        assert ping.sender == "ea"
    
    def test_pong(self):
        """Test heartbeat pong"""
        pong = Heartbeat(
            type="heartbeat.pong",
            sender="python",
        )
        
        assert pong.type == "heartbeat.pong"
        assert pong.sender == "python"


class TestErrorMessage:
    """Test ErrorMessage schema"""
    
    def test_error_message(self):
        """Test error message"""
        error = ErrorMessage(
            error_code="TIMEOUT",
            error_message="Request timed out",
            trace_id="abc123",
            details={"timeout": 5.0},
        )
        
        assert error.type == "error"
        assert error.error_code == "TIMEOUT"
        assert error.error_message == "Request timed out"
        assert error.trace_id == "abc123"
        assert error.details["timeout"] == 5.0


class TestAuthMessages:
    """Test authentication messages"""
    
    def test_auth_request(self):
        """Test auth request"""
        request = AuthRequest(
            account_id="12345",
            api_key="sk_test_123",
        )
        
        assert request.type == "auth.request"
        assert request.account_id == "12345"
        assert request.api_key == "sk_test_123"
    
    def test_auth_response_success(self):
        """Test successful auth response"""
        response = AuthResponse(
            success=True,
            auth_token="jwt_token",
            expires_in=3600,
        )
        
        assert response.type == "auth.response"
        assert response.success is True
        assert response.auth_token == "jwt_token"
        assert response.expires_in == 3600
    
    def test_auth_response_failure(self):
        """Test failed auth response"""
        response = AuthResponse(
            success=False,
            error="Invalid API key",
        )
        
        assert response.success is False
        assert response.error == "Invalid API key"
        assert response.auth_token is None
