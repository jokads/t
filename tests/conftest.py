"""
Pytest configuration and fixtures
"""
import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    from bot_mt5.utils.config import (
        AIConfig,
        MT5Config,
        RateLimitConfig,
        LoggingConfig,
        PerformanceConfig,
        BotConfig,
    )
    
    return BotConfig(
        ai=AIConfig(
            model_paths=["/tmp/models"],
            pool_size=1,
            timeout_quick=1.0,
            timeout_deep=2.0,
            max_retries=2,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=5.0,
        ),
        mt5=MT5Config(
            host="127.0.0.1",
            port=18765,
            reconnect_max_attempts=3,
            reconnect_backoff_base=1.5,
            reconnect_backoff_max=10.0,
            heartbeat_interval=5.0,
            heartbeat_timeout=10.0,
            exec_timeout=2.0,
        ),
        rate_limit=RateLimitConfig(
            enabled=True,
            orders_per_minute=10,
            burst_size=5,
        ),
        logging=LoggingConfig(
            level="DEBUG",
            format="text",
            sentry_dsn=None,
        ),
        performance=PerformanceConfig(
            use_uvloop=False,
            use_orjson=False,
        ),
    )
