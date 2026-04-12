"""
test_router_client.py — Phase A.1: Comprehensive unit tests for RouterClient.

Tests are organized into classes:
  - TestRouterInit: Client construction and shared client pooling
  - TestParseProviderLimits: Rate limit header parsing across providers
  - TestSSRFPrevention: SSRF protection via is_private_ip and validate_health_check_url
  - TestCircuitBreaker: Circuit breaker state transitions on RouterClient
  - TestCompleteMethod: The complete() method with retries, fallbacks, and errors

All tests use mocking — no real network calls.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import httpx
import pytest

from packages.core.circuit_breaker import CircuitState
from packages.core.errors import LLMClientError
from packages.router.client import (
    RouterClient,
    _parse_provider_limits,
    is_private_ip,
    validate_health_check_url,
    DEFAULT_ALLOWED_HOSTS,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_mock_response(
    status_code: int = 200,
    body: dict | None = None,
    headers: dict | None = None,
):
    """Create a mock HTTP response object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = httpx.Headers(headers or {})
    resp.json.return_value = body or {
        "choices": [{"message": {"content": "OK"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    return resp


def _make_success_response():
    """Create a standard 200 success response with full headers."""
    return _make_mock_response(
        status_code=200,
        headers={
            "x-freerouter-provider": "groq",
            "x-freerouter-model": "llama-3.3-70b-versatile",
            "x-ratelimit-remaining-requests": "500",
            "x-ratelimit-remaining-tokens": "10000",
        },
    )


# ─── TestRouterInit ───────────────────────────────────────────────────────────

class TestRouterInit:
    """Tests for RouterClient initialization."""

    def test_router_init_default_url(self, mock_settings):
        """RouterClient uses FREEROUTER_URL from patched settings."""
        client = RouterClient(startup_check=False)
        assert client.base_url == "http://localhost:4000"

    def test_router_init_custom_url(self, mock_settings):
        """Custom base_url overrides config."""
        client = RouterClient(base_url="http://custom:5000", startup_check=False)
        assert client.base_url == "http://custom:5000"

    def test_router_init_no_startup_check(self, mock_settings):
        """startup_check=False disables health check."""
        client = RouterClient(startup_check=False)
        assert client._startup_check_enabled is False

    def test_shared_client_connection_pool(self, mock_settings):
        """Multiple RouterClient instances share the same _shared_client."""
        client_a = RouterClient(startup_check=False)
        client_b = RouterClient(startup_check=False)
        assert RouterClient._shared_client is not None
        assert client_a._http is client_b._http
        assert RouterClient._shared_client_refcount == 2


# ─── TestParseProviderLimits ──────────────────────────────────────────────────

class TestParseProviderLimits:
    """Tests for _parse_provider_limits module-level function."""

    def test_parse_provider_limits_standard(self):
        """Correctly parses x-ratelimit-remaining-requests and x-ratelimit-remaining-tokens."""
        headers = httpx.Headers({
            "x-ratelimit-remaining-requests": "500",
            "x-ratelimit-remaining-tokens": "10000",
        })
        result = _parse_provider_limits(headers, "groq")
        assert result["rpm_remaining"] == 500
        assert result["tpm_remaining"] == 10000
        assert result["provider"] == "groq"
        assert "timestamp" in result

    def test_parse_provider_limits_ollama(self):
        """Returns -1 for rpm/tpm when no rate limit headers (Ollama)."""
        headers = httpx.Headers({})
        result = _parse_provider_limits(headers, "ollama")
        assert result["rpm_remaining"] == -1
        assert result["tpm_remaining"] == -1
        assert result["provider"] == "ollama"

    def test_parse_provider_limits_partial(self):
        """Returns -1 for missing tpm header only."""
        headers = httpx.Headers({
            "x-ratelimit-remaining-requests": "100",
        })
        result = _parse_provider_limits(headers, "openrouter")
        assert result["rpm_remaining"] == 100
        assert result["tpm_remaining"] == -1


# ─── TestSSRFPrevention ───────────────────────────────────────────────────────

class TestSSRFPrevention:
    """Tests for is_private_ip and validate_health_check_url."""

    def test_is_private_ip_loopback(self):
        """Detects 127.0.0.1, ::1 as private."""
        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("127.0.0.100") is True
        assert is_private_ip("::1") is True

    def test_is_private_ip_rfc1918(self):
        """Detects 10.x, 172.16.x, 192.168.x as private."""
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("10.255.255.255") is True
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("172.31.255.255") is True
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("192.168.0.1") is True

    def test_is_private_ip_public(self):
        """8.8.8.8, 1.1.1.1 are NOT private."""
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False
        assert is_private_ip("203.0.113.1") is False

    def test_validate_url_allowed_host(self):
        """localhost and 127.0.0.1 pass validation (they're in DEFAULT_ALLOWED_HOSTS)."""
        valid, msg = validate_health_check_url("http://localhost/health")
        assert valid is True
        assert msg == ""

        valid, msg = validate_health_check_url("http://127.0.0.1/health")
        assert valid is True

    def test_validate_url_private_ip_blocked(self):
        """URL resolving to 192.168.1.1 is rejected (mock socket.getaddrinfo)."""
        with patch(
            "socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("192.168.1.1", 80))],
        ):
            valid, msg = validate_health_check_url("http://evil.com/health")
            assert valid is False
            assert "private" in msg.lower()

    def test_validate_url_invalid_scheme(self):
        """ftp:// scheme rejected."""
        valid, msg = validate_health_check_url("ftp://localhost/file")
        assert valid is False
        assert "scheme" in msg.lower()

    def test_validate_url_empty(self):
        """Empty URL returns (False, 'URL is empty')."""
        valid, msg = validate_health_check_url("")
        assert valid is False
        assert msg == "URL is empty"


# ─── TestCircuitBreaker ───────────────────────────────────────────────────────

class TestCircuitBreaker:
    """Tests for the class-level circuit breaker on RouterClient."""

    def test_circuit_breaker_opens(self):
        """After 10 failures, circuit breaker rejects (allow_request returns False)."""
        cb = RouterClient._circuit_breaker
        # Record 10 failures to meet the threshold
        for _ in range(10):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_circuit_breaker_resets(self):
        """reset() sets breaker back to CLOSED."""
        cb = RouterClient._circuit_breaker
        for _ in range(10):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_circuit_breaker_half_open(self):
        """After recovery_timeout, transitions to HALF_OPEN."""
        cb = RouterClient._circuit_breaker
        for _ in range(10):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Simulate time passing beyond recovery_timeout (30s)
        cb._last_failure_time = time.time() - 31
        # Accessing .state or calling allow_request triggers transition
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True


# ─── TestCompleteMethod ───────────────────────────────────────────────────────

class TestCompleteMethod:
    """Tests for the RouterClient.complete() method with retries and fallback."""

    @pytest.mark.asyncio
    async def test_complete_429_retry(self, mock_settings, mock_http_client):
        """On 429, retry with backoff then succeed."""
        mock_http, mock_post, _ = mock_http_client

        fail_429 = _make_mock_response(status_code=429)
        success = _make_success_response()

        call_count = 0

        async def fake_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fail_429
            return success

        mock_post.side_effect = fake_post

        client = RouterClient(startup_check=False)
        client._http = mock_http

        # Patch asyncio.sleep to avoid real delays
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client.complete(
                [{"role": "user", "content": "hi"}],
                retries=3,
            )

        assert result["content"] == "OK"
        assert call_count == 2
        # First retry should sleep with backoff (2^0 + 1 = 2s)
        mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_complete_503_fallback_to_auto(self, mock_settings, mock_http_client):
        """On 503 with specific model, retry with model='auto'."""
        mock_http, mock_post, _ = mock_http_client

        fail_503 = _make_mock_response(status_code=503)
        success = _make_success_response()

        call_count = 0

        async def fake_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fail_503
            return success

        mock_post.side_effect = fake_post

        client = RouterClient(startup_check=False)
        client._http = mock_http

        result = await client.complete(
            [{"role": "user", "content": "hi"}],
            model="groq/llama-3.3-70b-versatile",
        )

        assert result["content"] == "OK"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_complete_all_retries_fail(self, mock_settings, mock_http_client):
        """After all retries exhausted, raises LLMClientError."""
        mock_http, mock_post, _ = mock_http_client

        fail_resp = _make_mock_response(status_code=500)
        mock_post.return_value = fail_resp

        client = RouterClient(startup_check=False)
        client._http = mock_http

        with pytest.raises(LLMClientError, match="LLM call failed after 3 attempts"):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await client.complete(
                    [{"role": "user", "content": "hi"}],
                    retries=3,
                )

    @pytest.mark.asyncio
    async def test_fallback_router_on_primary_fail(
        self, mock_settings, mock_http_client, monkeypatch
    ):
        """When primary fails and FALLBACK_ROUTER_URL set, tries fallback."""
        mock_http, mock_post, _ = mock_http_client

        # Primary always fails with 500
        fail_resp = _make_mock_response(status_code=500)
        mock_post.return_value = fail_resp

        client = RouterClient(startup_check=False)
        client._http = mock_http

        # Set up fallback settings with a fallback URL
        fallback_settings = mock_settings.__class__(
            _env_file=None,
            FREEROUTER_URL="http://localhost:4000",
            FALLBACK_ROUTER_URL="http://fallback:5000",
            FREEROUTER_STARTUP_CHECK=False,
        )

        # Patch get_settings to return settings with fallback URL AFTER init
        monkeypatch.setattr(
            "packages.router.client.get_settings", lambda: fallback_settings
        )

        # Create the fallback response
        fallback_success = _make_mock_response(
            status_code=200,
            headers={
                "x-freerouter-provider": "fallback",
                "x-freerouter-model": "auto",
                "x-ratelimit-remaining-requests": "100",
                "x-ratelimit-remaining-tokens": "5000",
            },
            body={
                "choices": [{"message": {"content": "Fallback worked!"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            },
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("httpx.AsyncClient") as MockAsyncClient:
                mock_fallback_instance = MagicMock()
                mock_fallback_instance.post = AsyncMock(return_value=fallback_success)
                mock_fallback_instance.__aenter__ = AsyncMock(return_value=mock_fallback_instance)
                mock_fallback_instance.__aexit__ = AsyncMock(return_value=False)
                MockAsyncClient.return_value = mock_fallback_instance

                result = await client.complete(
                    [{"role": "user", "content": "hi"}],
                    retries=2,
                )

        assert result["content"] == "Fallback worked!"
        assert result["provider"] == "fallback"

    @pytest.mark.asyncio
    async def test_complete_success(self, mock_settings, mock_http_client):
        """Successful completion returns dict with content, model, provider, usage, limits keys."""
        mock_http, mock_post, _ = mock_http_client
        mock_post.return_value = _make_success_response()

        client = RouterClient(startup_check=False)
        client._http = mock_http

        # Patch UsageTracker to avoid DB side effects
        with patch("packages.router.tracker.UsageTracker"):
            result = await client.complete(
                [{"role": "user", "content": "hello"}],
            )

        assert "content" in result
        assert result["content"] == "OK"
        assert "model" in result
        assert result["model"] == "llama-3.3-70b-versatile"
        assert "provider" in result
        assert result["provider"] == "groq"
        assert "usage" in result
        assert result["usage"]["total_tokens"] == 15
        assert "limits" in result
        assert result["limits"]["rpm_remaining"] == 500
        assert result["limits"]["tpm_remaining"] == 10000
