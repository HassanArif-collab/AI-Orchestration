"""
retry.py — Retry logic with exponential backoff for resilient operations.

Provides a decorator for automatic retry with configurable backoff strategies.
Used by integrations (Notion, YouTube) to handle transient failures.

Usage:
    from packages.core.retry import retry_with_backoff
    import httpx

    @retry_with_backoff(max_attempts=3, base_delay=2.0, exceptions=(httpx.HTTPStatusError,))
    async def my_api_call():
        ...

Imports: asyncio, random, functools
Imported by: packages/integrations/
"""

import asyncio
import random
from functools import wraps
from typing import Callable, ParamSpec, TypeVar, Awaitable

from packages.core.logger import get_logger

log = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry decorator with exponential backoff for async functions.

    Retries the decorated async function on specified exceptions with
    exponentially increasing delays between attempts. Includes jitter
    to prevent thundering herd problems.

    Args:
        max_attempts: Maximum number of retry attempts (default 3).
        base_delay: Initial delay in seconds (default 1.0).
        max_delay: Maximum delay cap in seconds (default 30.0).
        exceptions: Tuple of exception types to retry on (default all exceptions).

    Returns:
        Decorated async function with retry logic.

    Example:
        @retry_with_backoff(max_attempts=3, base_delay=2.0, exceptions=(httpx.HTTPStatusError,))
        async def fetch_data():
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    Note:
        - Delays have 50-100% jitter added for distributed systems
        - Logs warning on each retry attempt
        - Logs error when all retries exhausted
        - Re-raises the last exception after all retries fail
    """
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        log.error(
                            f"retry_exhausted: func={func.__name__} attempts={max_attempts}",
                            extra={"error": str(e), "error_type": type(e).__name__}
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    # Add jitter (50% to 100% of calculated delay)
                    delay = delay * (0.5 + random.random())

                    log.warning(
                        f"retry_attempt: func={func.__name__} attempt={attempt}/{max_attempts} delay={delay:.2f}s",
                        extra={"error": str(e), "error_type": type(e).__name__}
                    )

                    await asyncio.sleep(delay)

            # This should never be reached, but satisfies type checker
            if last_exception:
                raise last_exception
            raise RuntimeError(f"retry logic error in {func.__name__}")

        return wrapper
    return decorator


def retry_with_backoff_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry decorator with exponential backoff for sync functions.

    Same as retry_with_backoff but for synchronous functions.

    Args:
        max_attempts: Maximum number of retry attempts (default 3).
        base_delay: Initial delay in seconds (default 1.0).
        max_delay: Maximum delay cap in seconds (default 30.0).
        exceptions: Tuple of exception types to retry on (default all exceptions).

    Returns:
        Decorated sync function with retry logic.
    """
    import time

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        log.error(
                            f"retry_exhausted: func={func.__name__} attempts={max_attempts}",
                            extra={"error": str(e), "error_type": type(e).__name__}
                        )
                        raise

                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay = delay * (0.5 + random.random())

                    log.warning(
                        f"retry_attempt: func={func.__name__} attempt={attempt}/{max_attempts} delay={delay:.2f}s",
                        extra={"error": str(e), "error_type": type(e).__name__}
                    )

                    time.sleep(delay)

            if last_exception:
                raise last_exception
            raise RuntimeError(f"retry logic error in {func.__name__}")

        return wrapper
    return decorator
