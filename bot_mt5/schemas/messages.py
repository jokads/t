"""
Pydantic schemas for MT5 socket messages

All messages exchanged between Python backend and MT5 EA are validated
using these schemas for type safety and security.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class SignalPayload(BaseModel):
    """Payload for trading signal"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "account_id": "12345",
                "strategy": "SuperTrend",
                "symbol": "EURUSD",
                "action": "BUY",
                "lot": 0.01,
                "stop_loss": 1.0850,
                "take_profit": 1.0900,
                "confidence": 0.75,
                "price": 1.0870,
            }
        }
    )

    account_id: str = Field(..., description="MT5 account ID")
    strategy: str = Field(..., description="Strategy name that generated signal")
    symbol: str = Field(
        ..., pattern=r"^[A-Z]{6}$", description="Trading symbol (e.g., EURUSD)"
    )
    action: Literal["BUY", "SELL", "HOLD"] = Field(..., description="Trading action")
    lot: float = Field(..., gt=0.0, le=100.0, description="Lot size")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Signal confidence score"
    )
    price: Optional[float] = Field(None, description="Current market price")

    @field_validator("symbol", mode="before")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase"""
        return v.upper()


class SignalCreate(BaseModel):
    """Request to create a trading signal (from EA to Python)"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "signal.create",
                "timestamp": "2026-02-11T20:30:00Z",
                "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "payload": {
                    "account_id": "12345",
                    "strategy": "SuperTrend",
                    "symbol": "EURUSD",
                    "action": "BUY",
                    "lot": 0.01,
                    "stop_loss": 1.0850,
                    "take_profit": 1.0900,
                    "confidence": 0.75,
                    "price": 1.0870,
                },
            }
        }
    )

    type: Literal["signal.create"] = "signal.create"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    auth_token: str = Field(..., description="JWT authentication token")
    payload: SignalPayload


class OrderExecute(BaseModel):
    """Response with order execution details (from Python to EA)"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "order.execute",
                "timestamp": "2026-02-11T20:30:01Z",
                "success": True,
                "order_id": "987654321",
                "payload": {
                    "account_id": "12345",
                    "strategy": "SuperTrend",
                    "symbol": "EURUSD",
                    "action": "BUY",
                    "lot": 0.01,
                    "stop_loss": 1.0850,
                    "take_profit": 1.0900,
                    "confidence": 0.75,
                    "price": 1.0870,
                },
                "latency_ms": 125.5,
            }
        }
    )

    type: Literal["order.execute"] = "order.execute"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    success: bool = Field(..., description="Whether order was executed successfully")
    order_id: Optional[str] = Field(None, description="MT5 order ticket ID")
    payload: Optional[SignalPayload] = Field(
        None, description="Executed signal payload"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    latency_ms: Optional[float] = Field(
        None, description="Processing latency in milliseconds"
    )


class Heartbeat(BaseModel):
    """Heartbeat message to keep connection alive"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "heartbeat.ping",
                "timestamp": "2026-02-11T20:30:00Z",
                "sender": "ea",
            }
        }
    )

    type: Literal["heartbeat.ping", "heartbeat.pong"]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    sender: Literal["ea", "python"] = Field(..., description="Who sent the heartbeat")


class ErrorMessage(BaseModel):
    """Error message for failed operations"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "error",
                "timestamp": "2026-02-11T20:30:00Z",
                "error_code": "AI_TIMEOUT",
                "error_message": "AI model timed out after 8.0 seconds",
                "trace_id": "abc123",
                "details": {"model": "mistral-7b", "timeout": 8.0},
            }
        }
    )

    type: Literal["error"] = "error"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    error_code: str = Field(
        ..., description="Error code (e.g., TIMEOUT, VALIDATION_ERROR)"
    )
    error_message: str = Field(..., description="Human-readable error message")
    trace_id: Optional[str] = Field(None, description="Trace ID for debugging")
    details: Optional[dict] = Field(None, description="Additional error details")


class AuthRequest(BaseModel):
    """Authentication request from EA"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "auth.request",
                "timestamp": "2026-02-11T20:30:00Z",
                "account_id": "12345",
                "api_key": "sk_live_abc123...",
            }
        }
    )

    type: Literal["auth.request"] = "auth.request"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    account_id: str = Field(..., description="MT5 account ID")
    api_key: str = Field(..., description="API key for authentication")


class AuthResponse(BaseModel):
    """Authentication response from Python"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "auth.response",
                "timestamp": "2026-02-11T20:30:00Z",
                "success": True,
                "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_in": 3600,
            }
        }
    )

    type: Literal["auth.response"] = "auth.response"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    success: bool = Field(..., description="Whether authentication succeeded")
    auth_token: Optional[str] = Field(None, description="JWT token if successful")
    expires_in: Optional[int] = Field(None, description="Token expiration in seconds")
    error: Optional[str] = Field(None, description="Error message if failed")
