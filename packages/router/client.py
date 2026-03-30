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
from datetime import datetime, timezone
from typing import Any, Type, TypeVar
from urllib.parse import urlparse

import httpx
import requests

from packages.core.config import get_settings
from packages.core.errors import LLMClientError, RateLimitError
from packages.core.logger import get_logger

log = get_logger(__name__)
T = TypeVar("T")


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
        log.debug(f"DNS resolution failed for health check URL: {hostname}: {e}")
        # Don't block on DNS failure - let the request proceed and fail naturally
        pass
    except Exception as e:
        log.debug(f"Error checking DNS for health check URL: {e}")

    return True, ""


class RouterClient:
    """
    Async HTTP client for FreeRouter proxy.
    Use as an async context manager or call close() when done.

    Features:
        - Startup health check to ensure FreeRouter is running
        - Async health_check() method for monitoring
        - Automatic retry with exponential backoff
        - Fallback to "auto" model on 503 errors
    """

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

        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    def _startup_health_check(self) -> None:
        """
        Synchronous health check at initialization with SSRF prevention.

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
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5.0,
            )
            if response.status_code == 200:
                self._healthy = True
                log.info("freerouter_startup_check_passed", url=self.base_url)
                return
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.Timeout:
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
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                    self._healthy = True
                    return {"healthy": True, "latency_ms": latency}
        except Exception as e:
            log.debug(f"health_check_failed: {e}")

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
        await self.close()

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
                # Schedule the close for later (not ideal but prevents crash)
                log.warning(
                    "sync_context_manager_in_async_context: "
                    "Consider using async with RouterClient() instead"
                )
                # Create a task to close later
                loop.create_task(self._http.aclose())
            else:
                # No running loop, we can close synchronously
                loop.run_until_complete(self._http.aclose())
        except RuntimeError:
            # No event loop exists - create one to close
            asyncio.run(self._http.aclose())
        except Exception as e:
            log.debug(f"context_manager_close_error: {e}")

    async def close(self) -> None:
        """Close the HTTP client connection."""
        await self._http.aclose()

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

        Returns dict with keys:
            content  (str)  — the model's reply
            model    (str)  — actual model used (from x-freerouter-model header)
            provider (str)  — actual provider (from x-freerouter-provider header)
            usage    (dict) — prompt_tokens, completion_tokens
            limits   (dict) — rate limit info from HTTP headers (rpm_remaining, tpm_remaining)

        If a specific model returns 503, automatically retries with model="auto"
        so FreeRouter's fallback chain kicks in.
        """
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
                if attempt < retries - 1:
                    wait_time = (2**attempt) + 1
                    log.warning(f"http_error_{e.response.status_code}_retrying_in_{wait_time}s")
                    await asyncio.sleep(wait_time)
                continue
            except httpx.ConnectError as e:
                raise LLMClientError(
                    f"Cannot connect to FreeRouter at {self.base_url}. "
                    "Start it with: python -m freerouter proxy"
                ) from e
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    await asyncio.sleep(1)
                continue

        raise LLMClientError(f"LLM call failed after {retries} attempts: {last_error}")

    async def complete_text(
        self,
        prompt: str,
        model: str = "auto",
        system: str = "",
        **kwargs: Any,
    ) -> str:
        """Convenience wrapper: single prompt string in, text string out."""
        # Lazy health check on first call
        if self._healthy is None and self._startup_check_enabled:
            try:
                self._startup_health_check()
                self._healthy = True
            except LLMClientError:
                self._healthy = False
                raise LLMClientError(
                    f"FreeRouter not running at {self.base_url}. "
                    "Run: cd freerouter && python -m freerouter proxy"
                )

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
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
                self._startup_health_check()
                self._healthy = True
            except LLMClientError:
                self._healthy = False
                raise LLMClientError(
                    f"FreeRouter not running at {self.base_url}. "
                    "Run: cd freerouter && python -m freerouter proxy"
                )

        try:
            import instructor
            from openai import AsyncOpenAI

            openai_client = AsyncOpenAI(
                base_url=f"{self.base_url}/v1",
                api_key="not-needed",
            )
            client = instructor.from_openai(openai_client)
            return await client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=response_model,
                **kwargs,
            )
        except Exception as e:
            raise LLMClientError(f"Structured completion failed: {e}") from e
