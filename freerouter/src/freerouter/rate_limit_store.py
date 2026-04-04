"""
rate_limit_store.py — Abstract rate limit storage backends.

Context: Provides pluggable storage backends for rate limit tracking.
Supports in-memory (default) and Redis backends for multi-process
and distributed deployments.

Environment Variables:
    RATE_LIMIT_BACKEND: Storage backend type ("memory" or "redis")
    REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)

Imports: nothing internal
Imported by: providers.py
"""

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import logging

logger = logging.getLogger("freerouter.rate_limit_store")


@dataclass
class ProviderUsage:
    """Rate limit usage tracking for a provider."""
    name: str
    requests_limit: int = 0
    requests_remaining: int = -1
    tokens_limit: int = 0
    tokens_remaining: int = -1
    last_updated: float = field(default_factory=time.time)
    is_soft_limited: bool = False
    is_hard_limited: bool = False
    hard_limited_at: float = 0.0

    @property
    def requests_used_pct(self) -> Optional[float]:
        """Calculate percentage of requests used."""
        if self.requests_limit > 0 and self.requests_remaining >= 0:
            return 1.0 - (self.requests_remaining / self.requests_limit)
        return None

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "name": self.name,
            "requests_limit": self.requests_limit,
            "requests_remaining": self.requests_remaining,
            "tokens_limit": self.tokens_limit,
            "tokens_remaining": self.tokens_remaining,
            "last_updated": self.last_updated,
            "is_soft_limited": self.is_soft_limited,
            "is_hard_limited": self.is_hard_limited,
            "hard_limited_at": self.hard_limited_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProviderUsage":
        """Deserialize from dictionary."""
        return cls(
            name=data.get("name", ""),
            requests_limit=data.get("requests_limit", 0),
            requests_remaining=data.get("requests_remaining", -1),
            tokens_limit=data.get("tokens_limit", 0),
            tokens_remaining=data.get("tokens_remaining", -1),
            last_updated=data.get("last_updated", time.time()),
            is_soft_limited=data.get("is_soft_limited", False),
            is_hard_limited=data.get("is_hard_limited", False),
            hard_limited_at=data.get("hard_limited_at", 0.0),
        )


class RateLimitStore(ABC):
    """Abstract base class for rate limit storage backends.

    Provides a common interface for storing and retrieving provider
    rate limit usage data. Implementations can use in-memory storage,
    Redis, or other distributed storage systems.
    """

    @abstractmethod
    def get_usage(self, name: str) -> ProviderUsage:
        """Get usage data for a provider.

        Args:
            name: Provider name

        Returns:
            ProviderUsage object (creates new if not exists)
        """
        pass

    @abstractmethod
    def set_usage(self, usage: ProviderUsage) -> None:
        """Save usage data for a provider.

        Args:
            usage: ProviderUsage object to save
        """
        pass

    @abstractmethod
    def get_all_usage(self) -> dict[str, ProviderUsage]:
        """Get usage data for all providers.

        Returns:
            Dict mapping provider names to their usage data
        """
        pass

    @abstractmethod
    def reset_provider(self, name: str) -> None:
        """Reset rate limit state for a provider.

        Args:
            name: Provider name to reset
        """
        pass

    def update_from_headers(
        self,
        name: str,
        headers: dict,
        soft_limit_threshold: float = 0.90,
    ) -> ProviderUsage:
        """Update usage data from HTTP response headers.

        Args:
            name: Provider name
            headers: HTTP response headers
            soft_limit_threshold: Threshold for soft limiting (default: 0.90)

        Returns:
            Updated ProviderUsage object
        """
        usage = self.get_usage(name)

        def _get_int(key: str) -> Optional[int]:
            for k, v in headers.items():
                if k.lower() == key.lower():
                    try:
                        return int(v)
                    except (ValueError, TypeError):
                        pass
            return None

        rem = _get_int("x-ratelimit-remaining-requests")
        lim = _get_int("x-ratelimit-limit-requests")
        if rem is not None:
            usage.requests_remaining = rem
        if lim is not None:
            usage.requests_limit = lim

        tok_rem = _get_int("x-ratelimit-remaining-tokens")
        tok_lim = _get_int("x-ratelimit-limit-tokens")
        if tok_rem is not None:
            usage.tokens_remaining = tok_rem
        if tok_lim is not None:
            usage.tokens_limit = tok_lim

        usage.last_updated = time.time()
        pct = usage.requests_used_pct
        usage.is_soft_limited = (pct is not None and pct >= soft_limit_threshold)

        # Clear hard limit on successful response with remaining requests
        if rem is not None and rem > 0:
            usage.is_hard_limited = False
            usage.hard_limited_at = 0.0

        self.set_usage(usage)
        return usage

    def mark_hard_limited(self, name: str) -> ProviderUsage:
        """Mark a provider as hard limited.

        Args:
            name: Provider name

        Returns:
            Updated ProviderUsage object
        """
        usage = self.get_usage(name)
        usage.is_hard_limited = True
        usage.requests_remaining = 0
        usage.hard_limited_at = time.time()
        self.set_usage(usage)
        return usage

    def should_skip(
        self,
        name: str,
        reset_seconds: int = 60,
    ) -> bool:
        """Check if provider should be skipped due to rate limits.

        Args:
            name: Provider name
            reset_seconds: Seconds before auto-resetting hard limit

        Returns:
            True if provider should be skipped
        """
        usage = self.get_usage(name)

        # Auto-reset hard limits after the window expires
        if usage.is_hard_limited and usage.hard_limited_at > 0:
            if time.time() - usage.hard_limited_at > reset_seconds:
                usage.is_hard_limited = False
                usage.hard_limited_at = 0.0
                self.set_usage(usage)
                return False

        return usage.is_hard_limited or usage.is_soft_limited


class InMemoryRateLimitStore(RateLimitStore):
    """In-memory rate limit storage (default implementation).

    Uses a process-local dictionary to store rate limit data.
    Suitable for single-process deployments.

    Note: Data is lost on process restart. For multi-process or
    distributed deployments, use RedisRateLimitStore.
    """

    def __init__(self):
        """Initialize the in-memory store."""
        self._usage: dict[str, ProviderUsage] = {}

    def get_usage(self, name: str) -> ProviderUsage:
        """Get usage data for a provider."""
        if name not in self._usage:
            self._usage[name] = ProviderUsage(name=name)
        return self._usage[name]

    def set_usage(self, usage: ProviderUsage) -> None:
        """Save usage data for a provider."""
        self._usage[usage.name] = usage

    def get_all_usage(self) -> dict[str, ProviderUsage]:
        """Get usage data for all providers."""
        return dict(self._usage)

    def reset_provider(self, name: str) -> None:
        """Reset rate limit state for a provider."""
        if name in self._usage:
            self._usage[name].is_hard_limited = False
            self._usage[name].is_soft_limited = False
            self._usage[name].hard_limited_at = 0.0
            self._usage[name].requests_remaining = -1


class RedisRateLimitStore(RateLimitStore):
    """Redis-backed rate limit storage.

    Uses Redis for atomic operations and cross-process sharing.
    Suitable for multi-process and distributed deployments.

    Features:
        - Atomic read-modify-write operations
        - Automatic fallback to in-memory on Redis errors
        - JSON serialization for complex data
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        key_prefix: str = "freerouter:ratelimit:",
    ):
        """Initialize the Redis store.

        Args:
            redis_url: Redis connection URL (default: from REDIS_URL env var)
            key_prefix: Key prefix for namespacing (default: "freerouter:ratelimit:")
        """
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._key_prefix = key_prefix
        self._redis = None
        self._fallback_store = InMemoryRateLimitStore()
        self._redis_available = False

    async def _get_redis(self):
        """Get Redis connection (lazy initialization)."""
        if self._redis is not None:
            return self._redis

        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._redis.ping()
            self._redis_available = True
            logger.info(f"Redis rate limit store connected: {self._redis_url}")
            return self._redis
        except Exception as e:
            logger.warning(
                f"Redis connection failed, using in-memory fallback: {e}"
            )
            self._redis_available = False
            return None

    def _get_key(self, name: str) -> str:
        """Get Redis key for a provider."""
        return f"{self._key_prefix}{name}"

    def get_usage(self, name: str) -> ProviderUsage:
        """Get usage data for a provider (synchronous wrapper).

        Note: This uses the fallback store for sync access.
        For async operations, use get_usage_async.
        """
        return self._fallback_store.get_usage(name)

    async def get_usage_async(self, name: str) -> ProviderUsage:
        """Get usage data for a provider (async).

        Args:
            name: Provider name

        Returns:
            ProviderUsage object
        """
        redis = await self._get_redis()
        if redis and self._redis_available:
            try:
                data = await redis.get(self._get_key(name))
                if data:
                    import json
                    return ProviderUsage.from_dict(json.loads(data))
            except Exception as e:
                logger.warning(f"Redis get failed, using fallback: {e}")

        return self._fallback_store.get_usage(name)

    def set_usage(self, usage: ProviderUsage) -> None:
        """Save usage data for a provider (synchronous wrapper).

        Note: This uses the fallback store for sync access.
        For async operations, use set_usage_async.
        """
        self._fallback_store.set_usage(usage)

    async def set_usage_async(self, usage: ProviderUsage) -> None:
        """Save usage data for a provider (async).

        Args:
            usage: ProviderUsage object to save
        """
        # Always update fallback for read consistency
        self._fallback_store.set_usage(usage)

        redis = await self._get_redis()
        if redis and self._redis_available:
            try:
                import json
                await redis.set(
                    self._get_key(usage.name),
                    json.dumps(usage.to_dict()),
                )
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")

    def get_all_usage(self) -> dict[str, ProviderUsage]:
        """Get usage data for all providers (sync, uses fallback)."""
        return self._fallback_store.get_all_usage()

    async def get_all_usage_async(self) -> dict[str, ProviderUsage]:
        """Get usage data for all providers (async).

        Returns:
            Dict mapping provider names to their usage data
        """
        redis = await self._get_redis()
        if redis and self._redis_available:
            try:
                keys = await redis.keys(f"{self._key_prefix}*")
                if keys:
                    import json
                    result = {}
                    for key in keys:
                        data = await redis.get(key)
                        if data:
                            usage = ProviderUsage.from_dict(json.loads(data))
                            result[usage.name] = usage
                    return result
            except Exception as e:
                logger.warning(f"Redis keys scan failed: {e}")

        return self._fallback_store.get_all_usage()

    def reset_provider(self, name: str) -> None:
        """Reset rate limit state for a provider (sync)."""
        self._fallback_store.reset_provider(name)

    async def reset_provider_async(self, name: str) -> None:
        """Reset rate limit state for a provider (async).

        Args:
            name: Provider name to reset
        """
        self._fallback_store.reset_provider(name)

        redis = await self._get_redis()
        if redis and self._redis_available:
            try:
                usage = await self.get_usage_async(name)
                usage.is_hard_limited = False
                usage.is_soft_limited = False
                usage.hard_limited_at = 0.0
                usage.requests_remaining = -1
                await self.set_usage_async(usage)
            except Exception as e:
                logger.warning(f"Redis reset failed: {e}")

    async def atomic_update(
        self,
        name: str,
        update_fn,
    ) -> ProviderUsage:
        """Atomically update usage data.

        Uses Redis WATCH/MULTI/EXEC for atomic read-modify-write.
        Falls back to in-memory if Redis unavailable.

        Args:
            name: Provider name
            update_fn: Function that takes ProviderUsage and returns modified version

        Returns:
            Updated ProviderUsage object
        """
        redis = await self._get_redis()
        if redis and self._redis_available:
            try:
                key = self._get_key(name)
                # Use Redis transaction for atomic update
                async with redis.pipeline() as pipe:
                    while True:
                        try:
                            await pipe.watch(key)
                            data = await redis.get(key)
                            import json
                            usage = (
                                ProviderUsage.from_dict(json.loads(data))
                                if data
                                else ProviderUsage(name=name)
                            )
                            updated = update_fn(usage)
                            pipe.multi()
                            await pipe.set(key, json.dumps(updated.to_dict()))
                            await pipe.execute()
                            # Update fallback
                            self._fallback_store.set_usage(updated)
                            return updated
                        except Exception as watch_error:
                            # Retry on watch error
                            logger.debug(f"Retrying atomic update: {watch_error}")
                            continue
            except Exception as e:
                logger.warning(f"Atomic update failed, using fallback: {e}")

        # Fallback to non-atomic update
        usage = self._fallback_store.get_usage(name)
        updated = update_fn(usage)
        self._fallback_store.set_usage(updated)
        return updated


# Factory function for creating the appropriate store
_store: Optional[RateLimitStore] = None


def get_rate_limit_store() -> RateLimitStore:
    """Get the configured rate limit store singleton.

    Returns:
        RateLimitStore instance based on RATE_LIMIT_BACKEND env var
    """
    global _store
    if _store is not None:
        return _store

    backend = os.getenv("RATE_LIMIT_BACKEND", "memory").lower()

    if backend == "redis":
        try:
            _store = RedisRateLimitStore()
            logger.info("Using Redis rate limit store")
        except Exception as e:
            logger.warning(
                f"Failed to initialize Redis store, falling back to memory: {e}"
            )
            _store = InMemoryRateLimitStore()
    else:
        _store = InMemoryRateLimitStore()
        logger.info("Using in-memory rate limit store")

    return _store


def reset_rate_limit_store() -> None:
    """Reset the rate limit store singleton (for testing)."""
    global _store
    _store = None
