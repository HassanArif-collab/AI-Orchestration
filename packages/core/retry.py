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

# Default retryable exceptions - network/timeout related errors that are typically transient
# P2-02: Use specific exception types instead of catching all exceptions
DEFAULT_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    TimeoutError,
    asyncio.TimeoutError,
    OSError,  # Base for network errors
)


def is_retryable_exception(exc: Exception, retryable_types: tuple[type[Exception], ...]) -> bool:
    """Check if an exception should trigger a retry.

    Args:
        exc: The exception that was raised
        retryable_types: Tuple of exception types that should trigger retry

    Returns:
        True if the exception should trigger a retry, False otherwise
    """
    # Check if it's an instance of any retryable type
    if isinstance(exc, retryable_types):
        return True

    # Check for common HTTP/network error patterns by name
    # This handles exceptions from httpx, requests, etc. that may not be in our type tuple
    exc_name = type(exc).__name__
    retryable_names = {
        "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
        "ConnectionError", "ConnectError", "HTTPStatusError",
        "RemoteProtocolError", "LocalProtocolError",
        "SSLError", "ProtocolError",
    }

    # Check if exception name matches known retryable errors
    if exc_name in retryable_names:
        return True

    # Check for status code based retry (5xx server errors)
    if hasattr(exc, 'response') and hasattr(exc.response, 'status_code'):
        status_code = exc.response.status_code
        # Retry on server errors (5xx) and rate limits (429)
        if status_code >= 500 or status_code == 429:
            return True

    return False


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry decorator with exponential backoff for async functions.

    Retries the decorated async function on specified exceptions with
    exponentially increasing delays between attempts. Includes jitter
    to prevent thundering herd problems.

    Args:
        max_attempts: Maximum number of retry attempts (default 3).
        base_delay: Initial delay in seconds (default 1.0).
        max_delay: Maximum delay cap in seconds (default 30.0).
        exceptions: Tuple of exception types to retry on (default: network/timeout errors).
                   Pass None to use DEFAULT_RETRYABLE_EXCEPTIONS.

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
        - P2-02: Only retries on specified exception types, others propagate immediately
    """
    # Use default retryable exceptions if none specified
    retryable_exceptions = exceptions if exceptions is not None else DEFAULT_RETRYABLE_EXCEPTIONS

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # P2-02: Check if this exception should trigger a retry
                    if not is_retryable_exception(e, retryable_exceptions):
                        # Non-retryable exception - log and re-raise immediately
                        log.error(
                            f"non_retryable_exception: func={func.__name__} error_type={type(e).__name__}",
                            extra={"error": str(e)}
                        )
                        raise

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
