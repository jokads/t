"""
Rate Limiter - Token Bucket Algorithm

Async-safe rate limiting per (account_id, symbol) to prevent:
- Burst trading
- Broker API rate limit violations
- Excessive risk exposure
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Tuple

from bot_mt5.utils.config import RateLimitConfig, get_config


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.

    Tokens are added at a constant rate (refill_rate).
    Each request consumes 1 token.
    Max tokens = burst_size.
    """

    capacity: int  # Max tokens (burst size)
    refill_rate: float  # Tokens per second
    tokens: float = 0.0  # Current tokens
    last_refill_time: float = 0.0  # Last refill timestamp

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill_time = time.time()

    def refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill_time

        # Add tokens based on refill rate
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill_time = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Returns:
            True if tokens consumed, False if not enough tokens
        """
        self.refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: int = 1) -> float:
        """
        Calculate time until enough tokens are available.

        Returns:
            Seconds to wait, or 0.0 if tokens available now
        """
        self.refill()

        if self.tokens >= tokens:
            return 0.0

        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """
    Async rate limiter with token bucket per (account_id, symbol).

    Features:
    - Per-account and per-symbol limits
    - Configurable burst size
    - Async-safe with locks
    - Automatic cleanup of old buckets
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or get_config().rate_limit
        self.buckets: Dict[Tuple[str, str], TokenBucket] = {}
        self.locks: Dict[Tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)
        self._cleanup_task: asyncio.Task | None = None

        # Calculate refill rate from orders per minute
        self.refill_rate = self.config.orders_per_minute / 60.0

    async def start(self):
        """Start the rate limiter (starts cleanup task)"""
        if self._cleanup_task:
            return

        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """Stop the rate limiter"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def acquire(
        self,
        account_id: str,
        symbol: str,
        tokens: int = 1,
        timeout: float | None = None,
    ) -> bool:
        """
        Acquire tokens for rate limiting.

        Args:
            account_id: MT5 account ID
            symbol: Trading symbol
            tokens: Number of tokens to acquire (default: 1)
            timeout: Max time to wait for tokens (None = wait forever)

        Returns:
            True if tokens acquired, False if timeout
        """
        if not self.config.enabled:
            return True

        key = (account_id, symbol)

        # Get or create bucket
        async with self.locks[key]:
            if key not in self.buckets:
                self.buckets[key] = TokenBucket(
                    capacity=self.config.burst_size,
                    refill_rate=self.refill_rate,
                )

            bucket = self.buckets[key]

        # Try to consume tokens
        start_time = time.time()

        while True:
            async with self.locks[key]:
                if bucket.consume(tokens):
                    return True

                # Calculate wait time
                wait_time = bucket.time_until_available(tokens)

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False

                # Don't wait longer than timeout
                wait_time = min(wait_time, timeout - elapsed)

            # Wait for tokens to refill
            await asyncio.sleep(wait_time)

    async def check_available(
        self, account_id: str, symbol: str, tokens: int = 1
    ) -> bool:
        """
        Check if tokens are available without consuming.

        Args:
            account_id: MT5 account ID
            symbol: Trading symbol
            tokens: Number of tokens to check

        Returns:
            True if tokens available, False otherwise
        """
        if not self.config.enabled:
            return True

        key = (account_id, symbol)

        async with self.locks[key]:
            if key not in self.buckets:
                return True  # No bucket = no limit yet

            bucket = self.buckets[key]
            bucket.refill()
            return bucket.tokens >= tokens

    async def get_wait_time(
        self, account_id: str, symbol: str, tokens: int = 1
    ) -> float:
        """
        Get time to wait until tokens are available.

        Args:
            account_id: MT5 account ID
            symbol: Trading symbol
            tokens: Number of tokens to check

        Returns:
            Seconds to wait, or 0.0 if available now
        """
        if not self.config.enabled:
            return 0.0

        key = (account_id, symbol)

        async with self.locks[key]:
            if key not in self.buckets:
                return 0.0

            bucket = self.buckets[key]
            return bucket.time_until_available(tokens)

    async def reset(self, account_id: str, symbol: str):
        """
        Reset rate limit for a specific account/symbol.

        Args:
            account_id: MT5 account ID
            symbol: Trading symbol
        """
        key = (account_id, symbol)

        async with self.locks[key]:
            if key in self.buckets:
                del self.buckets[key]

    async def reset_all(self):
        """Reset all rate limits"""
        # Acquire all locks
        for key in list(self.buckets.keys()):
            async with self.locks[key]:
                pass

        self.buckets.clear()

    async def _cleanup_loop(self):
        """Cleanup old buckets periodically"""
        while True:
            try:
                await asyncio.sleep(300.0)  # Cleanup every 5 minutes

                now = time.time()
                keys_to_remove = []

                # Find buckets that haven't been used in 10 minutes
                for key, bucket in list(self.buckets.items()):
                    async with self.locks[key]:
                        if now - bucket.last_refill_time > 600.0:
                            keys_to_remove.append(key)

                # Remove old buckets
                for key in keys_to_remove:
                    async with self.locks[key]:
                        if key in self.buckets:
                            del self.buckets[key]

                if keys_to_remove:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(
                        f"Cleaned up {len(keys_to_remove)} old rate limit buckets"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.exception(f"Error in rate limiter cleanup: {e}")
