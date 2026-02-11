"""
Configuration management for bot_mt5

Centralized configuration with environment variable support.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field


class AIConfig(BaseModel):
    """AI Manager configuration"""
    
    model_paths: list[str] = Field(
        default_factory=lambda: [
            str(Path.cwd() / "models"),
            str(Path.home() / "models" / "gpt4all"),
        ],
        description="Paths to search for GGUF models"
    )
    pool_size: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Number of worker processes per model"
    )
    timeout_quick: float = Field(
        default=8.0,
        gt=0,
        description="Timeout for quick AI calls (seconds)"
    )
    timeout_deep: float = Field(
        default=30.0,
        gt=0,
        description="Timeout for deep analysis AI calls (seconds)"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Max retries for failed AI calls"
    )
    circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        description="Consecutive failures before circuit opens"
    )
    circuit_breaker_timeout: float = Field(
        default=60.0,
        gt=0,
        description="Seconds to wait before retrying after circuit opens"
    )
    
    @classmethod
    def from_env(cls) -> AIConfig:
        """Load configuration from environment variables"""
        return cls(
            model_paths=os.getenv("AI_MODEL_PATHS", "").split(":") if os.getenv("AI_MODEL_PATHS") else None,
            pool_size=int(os.getenv("AI_POOL_SIZE", "2")),
            timeout_quick=float(os.getenv("AI_TIMEOUT_QUICK", "8.0")),
            timeout_deep=float(os.getenv("AI_TIMEOUT_DEEP", "30.0")),
            max_retries=int(os.getenv("AI_MAX_RETRIES", "3")),
            circuit_breaker_threshold=int(os.getenv("AI_CB_THRESHOLD", "5")),
            circuit_breaker_timeout=float(os.getenv("AI_CB_TIMEOUT", "60.0")),
        )


class MT5Config(BaseModel):
    """MT5 Communication configuration"""
    
    host: str = Field(default="0.0.0.0", description="Socket server host")
    port: int = Field(default=8765, ge=1024, le=65535, description="Socket server port")
    protocol: Literal["socket", "dll"] = Field(default="socket", description="Communication protocol")
    reconnect_max_attempts: int = Field(default=10, ge=1, description="Max reconnection attempts")
    reconnect_backoff_base: float = Field(default=2.0, gt=1.0, description="Exponential backoff base")
    reconnect_backoff_max: float = Field(default=60.0, gt=0, description="Max backoff delay (seconds)")
    heartbeat_interval: float = Field(default=30.0, gt=0, description="Heartbeat interval (seconds)")
    heartbeat_timeout: float = Field(default=60.0, gt=0, description="Heartbeat timeout (seconds)")
    exec_timeout: float = Field(default=5.0, gt=0, description="Order execution timeout (seconds)")
    
    @classmethod
    def from_env(cls) -> MT5Config:
        """Load configuration from environment variables"""
        return cls(
            host=os.getenv("MT5_HOST", "0.0.0.0"),
            port=int(os.getenv("MT5_PORT", "8765")),
            protocol=os.getenv("MT5_PROTOCOL", "socket"),
            reconnect_max_attempts=int(os.getenv("MT5_RECONNECT_MAX", "10")),
            reconnect_backoff_base=float(os.getenv("MT5_BACKOFF_BASE", "2.0")),
            reconnect_backoff_max=float(os.getenv("MT5_BACKOFF_MAX", "60.0")),
            heartbeat_interval=float(os.getenv("MT5_HEARTBEAT_INTERVAL", "30.0")),
            heartbeat_timeout=float(os.getenv("MT5_HEARTBEAT_TIMEOUT", "60.0")),
            exec_timeout=float(os.getenv("MT5_EXEC_TIMEOUT", "5.0")),
        )


class RateLimitConfig(BaseModel):
    """Rate limiter configuration"""
    
    enabled: bool = Field(default=True, description="Enable rate limiting")
    orders_per_minute: int = Field(default=60, ge=1, description="Max orders per minute per account")
    burst_size: int = Field(default=10, ge=1, description="Max burst size")
    
    @classmethod
    def from_env(cls) -> RateLimitConfig:
        """Load configuration from environment variables"""
        return cls(
            enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            orders_per_minute=int(os.getenv("RATE_LIMIT_OPM", "60")),
            burst_size=int(os.getenv("RATE_LIMIT_BURST", "10")),
        )


class LoggingConfig(BaseModel):
    """Logging configuration"""
    
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    format: Literal["json", "text"] = Field(default="json")
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    
    @classmethod
    def from_env(cls) -> LoggingConfig:
        """Load configuration from environment variables"""
        return cls(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format=os.getenv("LOG_FORMAT", "json"),
            sentry_dsn=os.getenv("SENTRY_DSN"),
        )


class PerformanceConfig(BaseModel):
    """Performance optimization configuration"""
    
    use_uvloop: bool = Field(
        default=sys.platform != "win32",
        description="Use uvloop (not available on Windows)"
    )
    use_orjson: bool = Field(default=True, description="Use orjson for JSON serialization")
    
    @classmethod
    def from_env(cls) -> PerformanceConfig:
        """Load configuration from environment variables"""
        use_uvloop = os.getenv("USE_UVLOOP", "auto")
        if use_uvloop == "auto":
            use_uvloop = sys.platform != "win32"
        else:
            use_uvloop = use_uvloop.lower() == "true"
        
        return cls(
            use_uvloop=use_uvloop,
            use_orjson=os.getenv("USE_ORJSON", "true").lower() == "true",
        )


class BotConfig(BaseModel):
    """Main bot configuration"""
    
    ai: AIConfig = Field(default_factory=AIConfig)
    mt5: MT5Config = Field(default_factory=MT5Config)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    
    @classmethod
    def from_env(cls) -> BotConfig:
        """Load all configuration from environment variables"""
        return cls(
            ai=AIConfig.from_env(),
            mt5=MT5Config.from_env(),
            rate_limit=RateLimitConfig.from_env(),
            logging=LoggingConfig.from_env(),
            performance=PerformanceConfig.from_env(),
        )
    
    def validate_config(self) -> list[str]:
        """Validate configuration and return list of warnings"""
        warnings = []
        
        # Check uvloop on Windows
        if self.performance.use_uvloop and sys.platform == "win32":
            warnings.append("uvloop is not supported on Windows, disabling")
            self.performance.use_uvloop = False
        
        # Check model paths exist
        for path in self.ai.model_paths:
            if not Path(path).exists():
                warnings.append(f"Model path does not exist: {path}")
        
        # Check timeout consistency
        if self.ai.timeout_quick >= self.ai.timeout_deep:
            warnings.append("AI timeout_quick should be less than timeout_deep")
        
        return warnings


# Global config instance (lazy loaded)
_config: Optional[BotConfig] = None


def get_config() -> BotConfig:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = BotConfig.from_env()
        warnings = _config.validate_config()
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(f"Config warning: {warning}")
    return _config


def reload_config() -> BotConfig:
    """Reload configuration from environment"""
    global _config
    _config = None
    return get_config()
