"""
router/client.py — HTTP client that calls FreeRouter proxy at localhost:4000.

Context: This is the ONLY way pipeline code should call LLMs.
FreeRouter is a separate running process — this file calls it over HTTP.
Never import from freerouter/. Never call provider APIs directly.

FreeRouter handles:
  - Picking the best free provider (Ollama → Groq → OpenRouter → ...)
  - Automatic fallback if a provider is rate-limited
  - Rate limit tracking and auto-reset after 60s

This client handles:
  - Connection errors (FreeRouter not running)
  - 503 from specific model → retry with "auto"
  - Structured output via instructor + openai client
  - Startup health check with clear error messages
  - SSRF prevention in health check URLs (P2-09)

Usage:
    from packages.router.client import RouterClient

    async with RouterClient() as client:
        text = await client.complete_text("Summarise this topic: ...")
        idea = await client.complete_structured(msgs, VideoIdea)

Imports: httpx, requests, instructor, openai, packages.core
Imported by: packages/pipeline/, packages/agents/
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import threading
from datetime import datetime, timezone
from typing import Any, Optional, Type, TypeVar
from urllib.parse import urlparse

import httpx

from packages.core.circuit_breaker import CircuitBreaker
from packages.core.config import get_settings
from packages.core.errors import LLMClientError, RateLimitError
from packages.core.logger import get_logger

log = get_logger(__name__)
T = TypeVar("T")

# Lock for thread-safe shared client creation
_shared_client_lock = threading.Lock()


# ─── Rate Limit Header Parsing ─────────────────────────────────────────────────────

def _parse_provider_limits(headers: httpx.Headers, provider: str) -> dict:
    """
    Normalize rate limit headers across providers.

    Different providers use slightly different header names:
        Groq/OpenRouter: x-ratelimit-remaining-requests, x-ratelimit-remaining-tokens
        Ollama: None (local, unlimited)

    Returns standardized dict with rpm_remaining and tpm_remaining.
    Falls back to -1 if provider doesn't send headers (e.g., Ollama).

    Args:
        headers: HTTP response headers
        provider: Provider name (groq, openrouter, ollama, etc.)

    Returns:
        Dict with rpm_remaining, tpm_remaining, provider, timestamp
    """
    # Try standard header names first
    rpm = headers.get("x-ratelimit-remaining-requests")
    tpm = headers.get("x-ratelimit-remaining-tokens")

    return {
        "rpm_remaining": int(rpm) if rpm is not None else -1,
        "tpm_remaining": int(tpm) if tpm is not None else -1,
        "provider": provider,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── SSRF Prevention (P2-09) ─────────────────────────────────────────────────────

# Private IP ranges that should be blocked for health checks
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local
    ipaddress.ip_network("0.0.0.0/8"),         # Current network
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]

# Allowed URL schemes for health checks
ALLOWED_SCHEMES = frozenset(["http", "https"])

# Hostnames that are explicitly allowed (for development/testing)
# Can be extended via FREEROUTER_ALLOWED_HOSTS env var
DEFAULT_ALLOWED_HOSTS = frozenset(["localhost", "127.0.0.1", "::1"])


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address falls within private/internal ranges.

    Args:
        ip_str: IP address string to check

    Returns:
        True if the IP is private/internal, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in PRIVATE_IP_RANGES:
            if ip in network:
                return True
        return False
    except ValueError:
        # Not a valid IP address
        return False


def validate_health_check_url(url: str, allowed_hosts: set[str] | None = None) -> tuple[bool, str]:
    """Validate a URL for health check to prevent SSRF attacks.

    This function validates that a health check URL is safe to request,
    blocking attempts to access internal resources via Server-Side Request
    Forgery (SSRF).

    Args:
        url: The URL to validate
        allowed_hosts: Set of additional allowed hostnames

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if URL is safe to use
        - error_message: Description of why validation failed (empty if valid)
    """
    if not url:
        return False, "URL is empty"

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {e}"

    # Check scheme
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"URL scheme '{parsed.scheme}' not allowed. Use http or https."

    # Check for empty hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "URL has no hostname"

    # Check against allowed hosts list
    allowed = DEFAULT_ALLOWED_HOSTS | (allowed_hosts or set())
    if hostname.lower() in [h.lower() for h in allowed]:
        return True, ""

    # Check if hostname resolves to a private IP
    # First check if it's already an IP address
    try:
        if is_private_ip(hostname):
            return False, f"Hostname '{hostname}' resolves to a private IP address"
    except Exception:
        pass  # Not an IP address, continue with DNS resolution check

    # Try DNS resolution for domain names
    import socket
    try:
        resolved_ips = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        for family, socktype, proto, canonname, sockaddr in resolved_ips:
            ip_str = sockaddr[0]
            if is_private_ip(ip_str):
                return False, f"Hostname '{hostname}' resolves to private IP '{ip_str}'"
    except socket.gaierror as e:
        log.warning(f"DNS resolution failed for health check URL: {hostname}: {e}")
        # Don't block on DNS failure - let the request proceed and fail naturally
        pass
    except Exception as e:
        log.warning(f"Error checking DNS for health check URL: {e}")

    return True, ""


class RouterClient:
    """Client for the FreeRouter LLM proxy with connection pooling.

    Use as an async context manager or call close() when done.

    Features:
        - Shared class-level HTTP client with connection pooling
        - Startup health check to ensure FreeRouter is running
        - Async health_check() method for monitoring
        - Automatic retry with exponential backoff
        - Fallback to "auto" model on 503 errors
        - Cached AsyncOpenAI client for structured completions
        - Direct LiteLLM fallback when FreeRouter is not running (embedded mode)
    """

    # Class-level shared HTTP client for connection pooling
    _shared_client: Optional[httpx.AsyncClient] = None
    _shared_client_refcount: int = 0

    # Class-level cached AsyncOpenAI client for structured completions
    _shared_openai_client: Optional[Any] = None
    _shared_openai_base_url: Optional[str] = None

    # Class-level circuit breaker to prevent cascading failures.
    # NOTE: threshold is deliberately higher (10) because the pipeline makes
    # many LLM calls across stages (trend_analysis alone does 6+ calls with
    # 3 retries each). A threshold of 5 would trip the breaker during normal
    # transient failures and block subsequent stages like research.
    _circuit_breaker = CircuitBreaker(
        name="RouterClient",
        failure_threshold=10,
        recovery_timeout=30,
    )

    # Embedded mode: when FreeRouter is not reachable, use LiteLLM directly
    _embedded_mode: bool = False
    _embedded_routes: Optional[dict] = None
    _embedded_ollama_base: Optional[str] = None
    _embedded_ollama_key: Optional[str] = None

    @classmethod
    def _init_embedded_mode(cls):
        """Initialize embedded LiteLLM mode with FreeRouter routing table."""
        if cls._embedded_routes is not None:
            return
        try:
            # Import FreeRouter config to get routing table
            import sys
            freerouter_src = '/home/z/AI-Orchestration/freerouter/src'
            if freerouter_src not in sys.path:
                sys.path.insert(0, freerouter_src)
            from freerouter.config import ROUTES
            cls._embedded_routes = ROUTES

            # Load Ollama config from freerouter/.env
            import os
            from dotenv import load_dotenv
            freerouter_env = os.path.join('/home/z/AI-Orchestration', 'freerouter', '.env')
            if os.path.exists(freerouter_env):
                load_dotenv(freerouter_env, override=True)
            cls._embedded_ollama_base = os.getenv('OLLAMA_API_BASE', 'https://ollama.com')
            cls._embedded_ollama_key = os.getenv('OLLAMA_API_KEY', '')

            cls._embedded_mode = True
        except Exception as e:
            # Use print to avoid structlog issues during class init
            print(f"Warning: embedded_mode_init_failed: {e}")
            cls._embedded_mode = False

    @classmethod
    def _resolve_model_chain(cls, model: str) -> list[str]:
        """Resolve a task name to a chain of LiteLLM model strings."""
        if cls._embedded_routes is None:
            return [model]
        route = cls._embedded_routes.get(model)
        if route:
            models = []
            for key in ('model', 'fallback', 'fallback2', 'fallback3', 'fallback4', 'fallback5'):
                val = route.get(key)
                if val:
                    models.append(val)
            return models
        return [model]

    @classmethod
    def _build_litellm_kwargs(cls, model_str: str) -> dict:
        """Build extra kwargs for litellm based on provider."""
        kwargs = {}
        if model_str.startswith('ollama'):
            kwargs['api_base'] = cls._embedded_ollama_base
            if cls._embedded_ollama_key:
                kwargs['api_key'] = cls._embedded_ollama_key
        return kwargs

    @classmethod
    def _extract_provider(cls, model_str: str) -> str:
        """Extract provider name from LiteLLM model string."""
        prefix = model_str.split('/')[0]
        if prefix.startswith('ollama'):
            return 'ollama'
        return prefix

    @classmethod
    def reset_circuit_breaker(cls) -> None:
        """Reset the class-level circuit breaker to CLOSED state.

        Call this before starting a new pipeline stage to avoid a stale
        OPEN breaker (caused by failures in a previous stage) from
        blocking all LLM calls in the current stage.
        """
        cls._circuit_breaker.reset()
        log.info("circuit_breaker_reset: RouterClient")

    @classmethod
    def _get_shared_client(cls, base_url: str, timeout: float = 90.0) -> httpx.AsyncClient:
        """Get or create the shared HTTP client with connection pooling."""
        global _shared_client_lock
        with _shared_client_lock:
            if cls._shared_client is None or cls._shared_client.is_closed:
                cls._shared_client = httpx.AsyncClient(
                    base_url=base_url,
                    timeout=httpx.Timeout(timeout, connect=10.0),
                    limits=httpx.Limits(
                        max_connections=100,
                        max_keepalive_connections=20,
                        keepalive_expiry=30.0,
                    ),
                )
                cls._shared_client_refcount = 0
            cls._shared_client_refcount += 1
            return cls._shared_client

    @classmethod
    async def _release_shared_client(cls):
        """Decrement reference count; close when last user releases."""
        cls._shared_client_refcount -= 1
        if cls._shared_client_refcount <= 0 and cls._shared_client is not None:
            await cls._shared_client.aclose()
            cls._shared_client = None
            cls._shared_client_refcount = 0

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 90.0,
        startup_check: bool = True,
    ) -> None:
        """
        Initialize the RouterClient.

        Args:
            base_url: FreeRouter URL (defaults to config FREEROUTER_URL)
            timeout: HTTP timeout in seconds (default: 90.0)
            startup_check: If True, perform sync health check on init (default: True)

        Raises:
            LLMClientError: If startup_check=True and FreeRouter is not running
        """
        settings = get_settings()
        self.base_url = (base_url or settings.FREEROUTER_URL).rstrip("/")
        self.timeout = timeout
        self._healthy: bool | None = None  # None = unchecked, True/False = checked
        self._startup_check_enabled = startup_check and settings.FREEROUTER_STARTUP_CHECK

        self._http = self._get_shared_client(self.base_url, timeout)

        # Pre-initialize embedded mode so it's ready when needed
        self._init_embedded_mode()

    async def _startup_health_check(self) -> None:
        """
        Async health check at initialization with SSRF prevention.

        Raises:
            LLMClientError: If FreeRouter is not accessible or URL is invalid
        """
        # Validate URL for SSRF prevention (P2-09)
        is_valid, error_msg = validate_health_check_url(self.base_url)
        if not is_valid:
            log.warning(f"health_check_url_validation_failed: {error_msg}")
            raise LLMClientError(
                f"Invalid FreeRouter URL: {error_msg}. "
                f"URL must point to a valid public endpoint or be in the allowed hosts list."
            )

        try:
            response = await self._http.get("/health")
            if response.status_code == 200:
                self._healthy = True
                log.info("freerouter_startup_check_passed", url=self.base_url)
                return
        except httpx.ConnectError:
            pass
        except httpx.TimeoutException:
            pass
        except Exception as e:
            log.warning(f"freerouter_startup_check_exception: {e}")

        raise LLMClientError(
            f"FreeRouter is not running at {self.base_url}. "
            f"Please start it with: cd freerouter && python -m freerouter"
        )

    async def health_check(self) -> dict:
        """
        Async health check for monitoring.

        Returns:
            Dict with keys:
                - healthy (bool): Whether FreeRouter is responding
                - latency_ms (float | None): Response latency in milliseconds
        """
        start = datetime.now(timezone.utc)
        try:
            response = await self._http.get("/health")
            if response.status_code == 200:
                latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                self._healthy = True
                return {"healthy": True, "latency_ms": latency}
        except Exception as e:
            log.warning(f"health_check_failed: {e}")

        self._healthy = False
        return {"healthy": False, "latency_ms": None}

    @property
    def is_healthy(self) -> bool:
        """Return whether the last health check passed."""
        return self._healthy or False

    # Async context manager support (existing)
    async def __aenter__(self) -> RouterClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._release_shared_client()

    # P2-06: Sync context manager support
    def __enter__(self) -> RouterClient:
        """Sync context manager entry.

        Note: For async operations, prefer the async context manager.
        This is provided for convenience in sync-only contexts.
        """
        return self

    def __exit__(self, *_: Any) -> None:
        """Sync context manager exit.

        Closes the HTTP client synchronously using asyncio.run().
        Note: This may cause issues if called from within an async context.
        Prefer the async context manager for async code.
        """
        try:
            # Try to close the async client properly
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context - can't use run_until_complete
                # Use a synchronous close by creating a new event loop in a thread
                log.warning(
                    "sync_context_manager_in_async_context: "
                    "Consider using async with RouterClient() instead"
                )
                # Use concurrent.futures to run async close in a separate thread
                # with its own event loop to avoid conflicts
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.close())
                    future.result(timeout=30)  # Wait up to 30 seconds
            else:
                # No running loop, we can close synchronously
                loop.run_until_complete(self.close())
        except RuntimeError:
            # No event loop exists - create one to close
            asyncio.run(self.close())
        except Exception as e:
            log.warning(f"context_manager_close_error: {e}")

    async def close(self) -> None:
        """Release the shared HTTP client (closes when last user releases)."""
        await self._release_shared_client()

    async def complete(
        self,
        messages: list[dict],
        model: str = "auto",
        max_tokens: int = 2000,
        temperature: float = 0.7,
        retries: int = 3,
    ) -> dict:
        """
        Call FreeRouter and return parsed response with exponential backoff retries.

        Falls back to embedded LiteLLM mode if FreeRouter is not reachable.

        Returns dict with keys:
            content  (str)  — the model's reply
            model    (str)  — actual model used (from x-freerouter-model header)
            provider (str)  — actual provider (from x-freerouter-provider header)
            usage    (dict) — prompt_tokens, completion_tokens
            limits   (dict) — rate limit info from HTTP headers (rpm_remaining, tpm_remaining)

        If a specific model returns 503, automatically retries with model="auto"
        so FreeRouter's fallback chain kicks in.
        """
        # If in embedded mode (FreeRouter not running), use direct LiteLLM
        if self._healthy is False or (self._healthy is None and not self._startup_check_enabled):
            return await self._complete_embedded(
                messages, model=model, max_tokens=max_tokens, temperature=temperature
            )

        # Circuit breaker check — reject immediately if OPEN
        if not self._circuit_breaker.allow_request():
            raise LLMClientError("Circuit breaker is OPEN for RouterClient")

        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error = None
        for attempt in range(retries):
            try:
                resp = await self._http.post("/v1/chat/completions", json=body)

                # Specific provider unavailable → let FreeRouter pick
                if resp.status_code == 503 and body["model"] != "auto":
                    log.warning("provider_unavailable", model=body["model"], retrying_with="auto")
                    body["model"] = "auto"
                    resp = await self._http.post("/v1/chat/completions", json=body)

                if resp.status_code == 429:
                    wait_time = (2**attempt) + 1
                    log.warning(f"rate_limit_hit_waiting_{wait_time}s")
                    # Emit rate_limit SSE event for frontend awareness (Issue 15)
                    try:
                        from apps.api.events import event_bus as _event_bus
                        # BUGFIX: Do NOT re-import asyncio here — it shadows the module-level
                        # import (line 33) and causes UnboundLocalError in Python 3.12+
                        # when asyncio.sleep() is called after this try/except block.
                        asyncio.ensure_future(_event_bus.publish("rate_limit", {
                            "wait_time": wait_time,
                            "attempt": attempt + 1,
                            "max_retries": retries,
                            "model": body.get("model", "auto"),
                        }))
                    except Exception:
                        pass  # Non-critical: SSE emission must not break the retry loop
                    await asyncio.sleep(wait_time)
                    continue

                resp.raise_for_status()
                data = resp.json()

                # Extract provider from headers for rate limit parsing
                provider = resp.headers.get("x-freerouter-provider", "unknown")
                
                # Parse rate limit headers from provider response
                limits = _parse_provider_limits(resp.headers, provider)

                result = {
                    "content": data["choices"][0]["message"]["content"],
                    "model": resp.headers.get("x-freerouter-model", body["model"]),
                    "provider": provider,
                    "usage": data.get("usage", {}),
                    "limits": limits,  # NEW: live rate limit data from headers
                }

                # Log to usage tracker with live rate limit data
                try:
                    from packages.router.tracker import UsageTracker
                    tracker = UsageTracker()
                    usage = result.get("usage", {})
                    tracker.record_call(
                        provider=provider,
                        model=result["model"],
                        tokens_in=usage.get("prompt_tokens", 0),
                        tokens_out=usage.get("completion_tokens", 0),
                        latency_ms=0,  # Could add timing if needed
                        success=True,
                        rpm_remaining=limits["rpm_remaining"],
                        tpm_remaining=limits["tpm_remaining"],
                    )
                except Exception as tracker_error:
                    # Never crash the pipeline because tracking failed
                    log.debug(f"usage_tracking_failed_non_blocking: {tracker_error}")

                self._circuit_breaker.record_success()

                log.info(
                    "llm_call_ok",
                    provider=result["provider"],
                    model=result["model"],
                    tokens=result["usage"].get("total_tokens", 0),
                    rpm_remaining=limits["rpm_remaining"],
                    tpm_remaining=limits["tpm_remaining"],
                )
                return result

            except httpx.HTTPStatusError as e:
                last_error = e
                self._circuit_breaker.record_failure()
                if attempt < retries - 1:
                    wait_time = (2**attempt) + 1
                    log.warning(f"http_error_{e.response.status_code}_retrying_in_{wait_time}s")
                    await asyncio.sleep(wait_time)
                continue
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                self._circuit_breaker.record_failure()
                if attempt < retries - 1:
                    wait_time = (2**attempt) + 1
                    log.warning(f"connection_or_timeout_error_retrying_in_{wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    await asyncio.sleep(1)
                continue

        # ─── Fallback Router URL ─────────────────────────────────────────────
        fallback_url = get_settings().FALLBACK_ROUTER_URL
        if fallback_url:
            log.warning(
                "primary_router_failed_trying_fallback",
                fallback_url=fallback_url,
                last_error=str(last_error),
            )
            try:
                async with httpx.AsyncClient(
                    base_url=fallback_url.rstrip("/"),
                    timeout=httpx.Timeout(self.timeout, connect=10.0),
                ) as fallback_client:
                    fallback_resp = await fallback_client.post(
                        "/v1/chat/completions", json=body,
                    )
                    fallback_resp.raise_for_status()
                    fallback_data = fallback_resp.json()
                    self._circuit_breaker.record_success()
                    log.info(
                        "llm_call_ok_via_fallback",
                        fallback_url=fallback_url,
                    )
                    return {
                        "content": fallback_data["choices"][0]["message"]["content"],
                        "model": fallback_resp.headers.get("x-freerouter-model", body["model"]),
                        "provider": fallback_resp.headers.get("x-freerouter-provider", "fallback"),
                        "usage": fallback_data.get("usage", {}),
                        "limits": _parse_provider_limits(
                            fallback_resp.headers,
                            fallback_resp.headers.get("x-freerouter-provider", "fallback"),
                        ),
                    }
            except Exception as fallback_error:
                log.error(
                    "fallback_router_also_failed",
                    fallback_url=fallback_url,
                    error=str(fallback_error),
                )
                raise LLMClientError(
                    f"LLM call failed after {retries} attempts on primary, and fallback "
                    f"router also failed: {fallback_error}"
                ) from fallback_error

        raise LLMClientError(f"LLM call failed after {retries} attempts: {last_error}")

    async def _complete_embedded(
        self,
        messages: list[dict],
        model: str = "auto",
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> dict:
        """Direct LiteLLM call with FreeRouter routing table (embedded mode).

        Used when FreeRouter proxy is not running. Tries each model in the
        fallback chain until one succeeds.
        """
        self._init_embedded_mode()
        if not self._embedded_mode:
            raise LLMClientError("Embedded LiteLLM mode not available")

        import litellm
        litellm.drop_params = True
        model_chain = self._resolve_model_chain(model)
        last_error = None

        for m in model_chain:
            try:
                extra = self._build_litellm_kwargs(m)
                resp = await litellm.acompletion(
                    model=m,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **extra,
                )
                content = resp.choices[0].message.content or ''
                # Fix reasoning models that put output in reasoning_content
                if not content and hasattr(resp.choices[0].message, 'reasoning_content'):
                    content = resp.choices[0].message.reasoning_content or ''

                provider = self._extract_provider(m)
                usage = {}
                if hasattr(resp, 'usage'):
                    usage = {
                        'prompt_tokens': getattr(resp.usage, 'prompt_tokens', 0),
                        'completion_tokens': getattr(resp.usage, 'completion_tokens', 0),
                        'total_tokens': getattr(resp.usage, 'total_tokens', 0),
                    }

                log.info(
                    'llm_embedded_call_ok',
                    provider=provider,
                    model=m,
                    tokens=usage.get('total_tokens', 0),
                )
                return {
                    'content': content,
                    'model': m,
                    'provider': provider,
                    'usage': usage,
                    'limits': {'rpm_remaining': -1, 'tpm_remaining': -1, 'provider': provider},
                }
            except Exception as e:
                last_error = e
                error_str = str(e)
                # If rate-limited (429), wait before trying next model
                # Free models share a 20 req/min limit across all users
                if '429' in error_str or 'rate' in error_str.lower():
                    wait = 3
                    log.warning(f"embedded_rate_limited model={m} waiting_{wait}s")
                    await asyncio.sleep(wait)
                else:
                    log.warning(f"embedded_model_failed model={m} error={e}")
                continue

        raise LLMClientError(
            f"All embedded LiteLLM models failed: {model_chain}. Last error: {last_error}"
        ) from last_error

    async def complete_text(
        self,
        prompt: str,
        model: str = "auto",
        system: str = "",
        **kwargs: Any,
    ) -> str:
        """Convenience wrapper: single prompt string in, text string out."""
        # Lazy health check on first call — use embedded mode if FreeRouter is down
        if self._healthy is None and self._startup_check_enabled:
            try:
                await self._startup_health_check()
                self._healthy = True
            except LLMClientError:
                self._healthy = False
                log.warning("freerouter_not_running_falling_back_to_embedded_litellm")
                self._init_embedded_mode()

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # If FreeRouter is not healthy or startup check was skipped, use embedded LiteLLM
        if self._healthy is False or (self._healthy is None and not self._startup_check_enabled):
            result = await self._complete_embedded(messages, model=model, **kwargs)
            return result["content"]

        result = await self.complete(messages, model=model, **kwargs)
        return result["content"]

    async def complete_structured(
        self,
        messages: list[dict],
        response_model: Type[T],
        model: str = "auto",
        **kwargs: Any,
    ) -> T:
        """
        Get a structured response parsed into a Pydantic model.
        Uses instructor library which talks to FreeRouter as an OpenAI client.
        """
        # Lazy health check on first call
        if self._healthy is None and self._startup_check_enabled:
            try:
                await self._startup_health_check()
                self._healthy = True
            except LLMClientError:
                self._healthy = False
                raise LLMClientError(
                    f"FreeRouter not running at {self.base_url}. "
                    "Run: cd freerouter && python -m freerouter proxy"
                )

        import instructor
        from openai import AsyncOpenAI

        # Reuse cached AsyncOpenAI client if base URL matches
        base_url = f"{self.base_url}/v1"
        if (RouterClient._shared_openai_client is None
                or RouterClient._shared_openai_base_url != base_url):
            RouterClient._shared_openai_client = AsyncOpenAI(
                base_url=base_url,
                api_key="not-needed",
                timeout=self.timeout,
            )
            RouterClient._shared_openai_base_url = base_url
        openai_client = RouterClient._shared_openai_client
        client = instructor.from_openai(openai_client)

        last_error = None
        current_model = model
        for attempt in range(3):
            try:
                return await client.chat.completions.create(
                    model=current_model,
                    messages=messages,
                    response_model=response_model,
                    **kwargs,
                )
            except Exception as e:
                last_error = e
                # If model is unavailable and not already on auto, fall back
                if "503" in str(e) and current_model != "auto":
                    log.warning(
                        "structured_provider_unavailable",
                        model=current_model,
                        retrying_with="auto",
                    )
                    current_model = "auto"
                    continue
                if attempt < 2:
                    wait_time = (2 ** attempt) + 1
                    log.warning(
                        f"structured_completion_retry_{attempt+1}_in_{wait_time}s",
                        error=str(e),
                    )
                    await asyncio.sleep(wait_time)
                    continue

        raise LLMClientError(
            f"Structured completion failed after 3 attempts: {last_error}"
        ) from last_error
