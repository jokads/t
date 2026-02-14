"""
Tests for rate limiter
"""

import asyncio
import pytest

from bot_mt5.utils.rate_limiter import RateLimiter, TokenBucket
from bot_mt5.utils.config import RateLimitConfig


class TestTokenBucket:
    """Test TokenBucket class"""

    def test_initial_tokens(self):
        """Test bucket starts with full capacity"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.tokens == 10.0

    def test_consume_tokens(self):
        """Test consuming tokens"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # Consume 5 tokens
        assert bucket.consume(5) is True
        assert 4.9 <= bucket.tokens <= 5.1  # Allow small variance

        # Consume 5 more
        assert bucket.consume(5) is True
        assert bucket.tokens < 0.1  # Near zero

        # Try to consume when empty
        assert bucket.consume(1) is False

    def test_refill(self):
        """Test token refill"""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens/sec

        # Consume all
        bucket.consume(10)
        assert bucket.tokens < 0.1

        # Wait 0.5 seconds
        import time

        time.sleep(0.5)

        # Refill should add ~5 tokens
        bucket.refill()
        assert 4.0 <= bucket.tokens <= 6.0  # Allow some variance

    def test_max_capacity(self):
        """Test tokens don't exceed capacity"""
        bucket = TokenBucket(capacity=10, refill_rate=100.0)

        # Wait and refill
        import time

        time.sleep(0.5)
        bucket.refill()

        # Should not exceed capacity
        assert bucket.tokens <= 10.0


@pytest.mark.asyncio
class TestRateLimiter:
    """Test RateLimiter class"""

    async def test_acquire_success(self, mock_config):
        """Test successful token acquisition"""
        config = RateLimitConfig(
            enabled=True,
            orders_per_minute=60,  # 1 per second
            burst_size=10,
        )

        limiter = RateLimiter(config)
        await limiter.start()

        try:
            # Should succeed immediately
            result = await limiter.acquire("12345", "EURUSD", timeout=1.0)
            assert result is True
        finally:
            await limiter.stop()

    async def test_acquire_timeout(self, mock_config):
        """Test timeout when rate limit exceeded"""
        config = RateLimitConfig(
            enabled=True,
            orders_per_minute=6,  # 0.1 per second
            burst_size=2,
        )

        limiter = RateLimiter(config)
        await limiter.start()

        try:
            # Consume all burst tokens
            assert await limiter.acquire("12345", "EURUSD", timeout=0.1) is True
            assert await limiter.acquire("12345", "EURUSD", timeout=0.1) is True

            # Next should timeout (not enough time to refill)
            result = await limiter.acquire("12345", "EURUSD", timeout=0.1)
            assert result is False
        finally:
            await limiter.stop()

    async def test_per_account_symbol(self, mock_config):
        """Test rate limiting is per (account_id, symbol)"""
        config = RateLimitConfig(
            enabled=True,
            orders_per_minute=60,
            burst_size=2,
        )

        limiter = RateLimiter(config)
        await limiter.start()

        try:
            # Different symbols should have separate limits
            assert await limiter.acquire("12345", "EURUSD", timeout=0.1) is True
            assert await limiter.acquire("12345", "EURUSD", timeout=0.1) is True

            # EURUSD exhausted, but GBPUSD should work
            assert await limiter.acquire("12345", "GBPUSD", timeout=0.1) is True

            # Different account should also work
            assert await limiter.acquire("67890", "EURUSD", timeout=0.1) is True
        finally:
            await limiter.stop()

    async def test_check_available(self, mock_config):
        """Test checking availability without consuming"""
        config = RateLimitConfig(
            enabled=True,
            orders_per_minute=60,
            burst_size=2,
        )

        limiter = RateLimiter(config)
        await limiter.start()

        try:
            # Should be available
            assert await limiter.check_available("12345", "EURUSD") is True

            # Consume all
            await limiter.acquire("12345", "EURUSD")
            await limiter.acquire("12345", "EURUSD")

            # Should not be available
            assert await limiter.check_available("12345", "EURUSD") is False
        finally:
            await limiter.stop()

    async def test_disabled(self, mock_config):
        """Test rate limiter when disabled"""
        config = RateLimitConfig(
            enabled=False,
            orders_per_minute=1,
            burst_size=1,
        )

        limiter = RateLimiter(config)
        await limiter.start()

        try:
            # Should always succeed when disabled
            for _ in range(10):
                result = await limiter.acquire("12345", "EURUSD", timeout=0.1)
                assert result is True
        finally:
            await limiter.stop()

    async def test_reset(self, mock_config):
        """Test resetting rate limit"""
        config = RateLimitConfig(
            enabled=True,
            orders_per_minute=60,
            burst_size=2,
        )

        limiter = RateLimiter(config)
        await limiter.start()

        try:
            # Consume all
            await limiter.acquire("12345", "EURUSD")
            await limiter.acquire("12345", "EURUSD")

            # Should be exhausted
            assert await limiter.check_available("12345", "EURUSD") is False

            # Reset
            await limiter.reset("12345", "EURUSD")

            # Should be available again
            assert await limiter.check_available("12345", "EURUSD") is True
        finally:
            await limiter.stop()
