"""
Phase 14 — FreeRouter / LLM Integration Tests

Tests the full LLM routing stack:
  - RouterClient (HTTP client for FreeRouter proxy at localhost:4000)
  - FreeRouter provider system (providers.py, router.py)
  - Capability mapping (capabilities.py)
  - Usage tracking (tracker.py — SQLite)
  - SSRF prevention (client.py — validate_health_check_url, is_private_ip)
  - Service validation (config.py — Settings.validate_service)

All tests use REAL credentials and services. Tests that require a running
FreeRouter instance will PASS gracefully when it is unavailable, reporting
what was missing — AND will test actual error-handling behaviour (circuit
breaker, error types, connection refusal) rather than using assert True.

NO pytest.mark.skip is used anywhere.

Run:
    pytest tests/integration/test_freerouter_integration.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# ─── sys.path setup ─────────────────────────────────────────────────────────────
# Ensure freerouter package is importable (it lives outside the normal packages/)
REPO_ROOT = Path(__file__).resolve().parents[2]
FREEROUTER_SRC = str(REPO_ROOT / "freerouter" / "src")
if FREEROUTER_SRC not in sys.path:
    sys.path.insert(0, FREEROUTER_SRC)

# ─── Load freerouter/.env so provider API keys are available ────────────────────
from dotenv import load_dotenv
_freerouter_env_path = REPO_ROOT / "freerouter" / ".env"
if _freerouter_env_path.exists():
    load_dotenv(_freerouter_env_path, override=True)

# ─── Imports ────────────────────────────────────────────────────────────────────

from packages.core.config import Settings, ServiceStatus, get_settings
from packages.core.errors import LLMClientError, RateLimitError, PipelineException
from packages.core.circuit_breaker import CircuitBreaker, CircuitState
from packages.router.client import (
    RouterClient,
    is_private_ip,
    validate_health_check_url,
)
from packages.router.capabilities import (
    CAPABILITY_MODELS,
    get_model_for_capability,
    list_capabilities,
)
from packages.router.tracker import UsageTracker


# ═══════════════════════════════════════════════════════════════════════════════
# Helper fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def freerouter_url() -> str:
    """Return the configured FreeRouter URL from env or default."""
    return os.getenv("FREEROUTER_URL", "http://localhost:4000")


@pytest.fixture()
def temp_db_path(tmp_path: Path) -> Path:
    """Return a temporary database path for UsageTracker tests."""
    return tmp_path / "test_usage.db"


@pytest.fixture()
def tracker(temp_db_path: Path) -> UsageTracker:
    """Provide a UsageTracker with a temporary database."""
    return UsageTracker(db_path=temp_db_path)


@pytest.fixture()
def freerouter_available(freerouter_url: str) -> bool:
    """Check if FreeRouter is reachable. Returns True if up, False if down."""
    import httpx
    try:
        resp = httpx.get(f"{freerouter_url}/health", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture()
def has_any_provider_key() -> bool:
    """Check whether at least one LLM provider API key is set.

    NOTE: freerouter/.env is loaded at module level above, so these env vars
    are available in os.environ.
    """
    providers = [
        "GROQ_API_KEY", "OPENROUTER_API_KEY", "MISTRAL_API_KEY",
        "TOGETHER_API_KEY", "SAMBANOVA_API_KEY", "DEEPINFRA_API_KEY",
        "CEREBRAS_API_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN",
        "ANTHROPIC_API_KEY", "APIFREELLM_API_KEY", "ZAI_API_KEY",
    ]
    return any(os.getenv(p, "").strip() for p in providers)


# ═══════════════════════════════════════════════════════════════════════════════
# A. RouterClient Connection Tests (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouterClientConnection:
    """Test RouterClient initialization and health-check behaviour."""

    @pytest.mark.asyncio
    async def test_router_client_health_check(
        self, freerouter_url: str, freerouter_available: bool
    ):
        """If FreeRouter is running, health_check returns healthy=True.

        If FreeRouter is NOT running, test that health_check correctly reports
        healthy=False instead of using assert True pass-through.
        """
        if freerouter_available:
            client = RouterClient(base_url=freerouter_url, startup_check=False)
            try:
                result = await client.health_check()
                assert isinstance(result, dict), "health_check should return a dict"
                assert "healthy" in result, "result must contain 'healthy' key"
                assert result["healthy"] is True, (
                    f"Expected healthy=True but got {result}"
                )
            finally:
                await client.close()
        else:
            # FreeRouter not running — test that RouterClient correctly detects
            # this instead of using assert True pass-through
            client = RouterClient(base_url=freerouter_url, startup_check=False)
            try:
                result = await client.health_check()
                assert isinstance(result, dict), (
                    "health_check should still return a dict when service is down"
                )
                assert result["healthy"] is False, (
                    f"Expected healthy=False when FreeRouter unreachable, "
                    f"got {result}. This tests that the client correctly detects "
                    f"service unavailability."
                )
            finally:
                await client.close()

    @pytest.mark.asyncio
    async def test_router_client_health_check_latency(
        self, freerouter_url: str, freerouter_available: bool
    ):
        """Verify latency_ms when FreeRouter is healthy; verify None when down."""
        client = RouterClient(base_url=freerouter_url, startup_check=False)
        try:
            result = await client.health_check()
            assert isinstance(result, dict)
            assert "latency_ms" in result

            if freerouter_available:
                assert result["healthy"] is True
                latency = result["latency_ms"]
                assert latency is not None, "latency_ms should not be None when healthy"
                assert isinstance(latency, (int, float)), (
                    f"latency_ms should be numeric, got {type(latency)}"
                )
                assert latency > 0, f"latency_ms should be > 0, got {latency}"
            else:
                # When service is down, latency should be None
                assert result["latency_ms"] is None, (
                    "latency_ms should be None when FreeRouter is unreachable"
                )
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_router_client_unavailable(self):
        """If FreeRouter is NOT running, health_check returns healthy=False gracefully."""
        # Use a deliberately unreachable URL
        fake_url = "http://127.0.0.1:19999"
        client = RouterClient(base_url=fake_url, startup_check=False)
        try:
            result = await client.health_check()
            assert isinstance(result, dict)
            assert result["healthy"] is False
            assert result["latency_ms"] is None
            # is_healthy property should reflect the same
            assert client.is_healthy is False
        finally:
            await client.close()

    def test_router_client_init_with_custom_url(self):
        """Init with explicit URL works and stores it correctly."""
        custom_url = "http://custom-host:9999"
        client = RouterClient(base_url=custom_url, startup_check=False)
        assert client.base_url == custom_url
        assert client.timeout == 90.0  # default


# ═══════════════════════════════════════════════════════════════════════════════
# B. RouterClient Completion Tests (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouterClientCompletion:
    """Test end-to-end LLM completion through RouterClient → FreeRouter.

    When FreeRouter is running: test real LLM calls with assertions on response.
    When FreeRouter is NOT running: test that the client raises LLMClientError
    and that the circuit breaker records failures correctly.
    """

    @pytest.mark.asyncio
    async def test_complete_text_simple(
        self, freerouter_url: str, freerouter_available: bool, has_any_provider_key: bool
    ):
        """Send 'Say hello' and verify response contains text.

        If FreeRouter is down, verify that LLMClientError is raised.
        """
        RouterClient.reset_circuit_breaker()

        if not freerouter_available:
            # Test that the client correctly raises an error when service is down
            client = RouterClient(base_url=freerouter_url, startup_check=False)
            client._healthy = True
            try:
                with pytest.raises(LLMClientError):
                    await client.complete_text(
                        "Reply with exactly: Hello World",
                        model="auto",
                        max_tokens=50,
                        retries=0,  # No retries — fail fast
                    )
            finally:
                await client.close()
            return

        if not has_any_provider_key:
            # FreeRouter up but no provider keys — should also raise error
            client = RouterClient(base_url=freerouter_url, startup_check=False)
            client._healthy = True
            try:
                with pytest.raises(LLMClientError):
                    await client.complete_text(
                        "Reply with exactly: Hello World",
                        model="auto",
                        max_tokens=50,
                        retries=0,
                    )
            finally:
                await client.close()
            return

        # FreeRouter is running with keys — make real LLM call
        client = RouterClient(base_url=freerouter_url, startup_check=False)
        client._healthy = True
        try:
            text = await client.complete_text(
                "Reply with exactly: Hello World",
                model="auto",
                max_tokens=50,
            )
            assert isinstance(text, str), "complete_text should return a string"
            assert len(text) > 0, "Response should not be empty"
            assert any(c.isalpha() for c in text), (
                "Response should contain alphabetic characters"
            )
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(
        self, freerouter_url: str, freerouter_available: bool, has_any_provider_key: bool
    ):
        """Send system prompt + user message; verify response follows instructions.

        If FreeRouter is down, verify error handling.
        """
        RouterClient.reset_circuit_breaker()

        if not freerouter_available or not has_any_provider_key:
            # Test error handling when FreeRouter is unreachable or no keys
            client = RouterClient(base_url=freerouter_url, startup_check=False)
            client._healthy = True
            try:
                with pytest.raises(LLMClientError):
                    await client.complete_text(
                        "Name one color.",
                        system="You MUST reply with ONLY the word RED and nothing else.",
                        model="auto",
                        max_tokens=50,
                        retries=0,
                    )
            finally:
                await client.close()
            return

        client = RouterClient(base_url=freerouter_url, startup_check=False)
        client._healthy = True
        try:
            text = await client.complete_text(
                "Name one color.",
                system="You MUST reply with ONLY the word RED and nothing else.",
                model="auto",
                max_tokens=50,
                retries=1,
            )
            assert isinstance(text, str)
            assert len(text) > 0
            assert "RED" in text.upper(), (
                f"System prompt not followed. Expected RED, got: {text}"
            )
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_complete_returns_usage_data(
        self, freerouter_url: str, freerouter_available: bool, has_any_provider_key: bool
    ):
        """Verify usage dict has prompt_tokens and completion_tokens.

        If FreeRouter is down, verify error + circuit breaker state.
        """
        RouterClient.reset_circuit_breaker()

        if not freerouter_available or not has_any_provider_key:
            # When FreeRouter is down or no keys, verify error is raised
            client = RouterClient(base_url=freerouter_url, startup_check=False)
            client._healthy = True
            try:
                await client.complete(
                    messages=[{"role": "user", "content": "Say OK"}],
                    model="auto",
                    max_tokens=10,
                    retries=0,
                )
                pytest.fail("Expected LLMClientError when FreeRouter is unavailable")
            except LLMClientError as exc:
                # Error message should be meaningful
                err_str = str(exc)
                assert len(err_str) > 0, "Error message should not be empty"
            finally:
                await client.close()
            return

        client = RouterClient(base_url=freerouter_url, startup_check=False)
        client._healthy = True
        try:
            result = await client.complete(
                messages=[{"role": "user", "content": "Say OK"}],
                model="auto",
                max_tokens=10,
                retries=1,
            )
            assert isinstance(result, dict)
            assert "usage" in result, "Result must contain 'usage' key"
            usage = result["usage"]
            assert isinstance(usage, dict), "usage should be a dict"
            assert "prompt_tokens" in usage, "usage must have prompt_tokens"
            assert "completion_tokens" in usage, "usage must have completion_tokens"
            assert isinstance(usage["prompt_tokens"], int)
            assert isinstance(usage["completion_tokens"], int)
            assert usage["prompt_tokens"] >= 0
            assert usage["completion_tokens"] >= 0
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_complete_returns_provider_info(
        self, freerouter_url: str, freerouter_available: bool, has_any_provider_key: bool
    ):
        """Verify response includes 'provider' and 'model' keys.

        If FreeRouter is down, verify error is raised (not a silent pass).
        """
        RouterClient.reset_circuit_breaker()

        if not freerouter_available or not has_any_provider_key:
            client = RouterClient(base_url=freerouter_url, startup_check=False)
            client._healthy = True
            try:
                with pytest.raises(LLMClientError):
                    await client.complete(
                        messages=[{"role": "user", "content": "Say OK"}],
                        model="auto",
                        max_tokens=10,
                        retries=0,
                    )
            finally:
                await client.close()
            return

        client = RouterClient(base_url=freerouter_url, startup_check=False)
        client._healthy = True
        try:
            result = await client.complete(
                messages=[{"role": "user", "content": "Say OK"}],
                model="auto",
                max_tokens=10,
                retries=1,
            )
            assert isinstance(result, dict)
            assert "provider" in result, "Result must contain 'provider'"
            assert "model" in result, "Result must contain 'model'"
            assert isinstance(result["provider"], str)
            assert len(result["provider"]) > 0, "provider should not be empty"
            assert isinstance(result["model"], str)
            assert len(result["model"]) > 0, "model should not be empty"
        finally:
            await client.close()


# ═══════════════════════════════════════════════════════════════════════════════
# C. Provider System Tests (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderSystem:
    """Test FreeRouter's provider definitions, configuration, and timeouts."""

    def test_get_configured_providers(self):
        """get_configured_providers returns list of tuples with is_configured flag."""
        from freerouter.providers import get_configured_providers

        result = get_configured_providers()
        assert isinstance(result, list), "Should return a list"
        assert len(result) > 0, "Should have at least one provider definition"
        for item in result:
            assert isinstance(item, tuple), "Each item should be a tuple"
            assert len(item) == 2, "Each tuple should have (ProviderDefinition, bool)"
            provider_def, is_configured = item
            assert hasattr(provider_def, "name"), "First element needs .name"
            assert isinstance(is_configured, bool), (
                f"is_configured should be bool for {provider_def.name}"
            )

    def test_get_configured_providers_detects_real_keys(self):
        """At least one provider should show as configured with real API keys.

        The freerouter/.env is loaded at module level; this test verifies that
        the provider detection actually picks up the keys from that file.
        """
        from freerouter.providers import get_configured_providers

        result = get_configured_providers()
        configured = [defn.name for defn, is_configured in result if is_configured]
        assert len(configured) >= 1, (
            f"Expected at least 1 configured provider from freerouter/.env, "
            f"but none found. Configured: {configured}"
        )

    def test_provider_definitions_exist(self):
        """All expected providers are present in KNOWN_PROVIDERS."""
        from freerouter.providers import KNOWN_PROVIDERS

        expected_names = [
            "ollama", "groq", "openrouter", "together", "mistral",
            "sambanova", "deepinfra", "cerebras", "openai", "github",
            "anthropic", "apifreellm", "zai",
        ]
        actual_names = [p.name for p in KNOWN_PROVIDERS]
        for expected in expected_names:
            assert expected in actual_names, (
                f"Expected provider '{expected}' not found in KNOWN_PROVIDERS. "
                f"Available: {actual_names}"
            )

    def test_default_models_defined(self):
        """DEFAULT_MODELS has entries for all defined providers."""
        from freerouter.providers import KNOWN_PROVIDERS, DEFAULT_MODELS

        provider_names = {p.name for p in KNOWN_PROVIDERS}
        model_keys = set(DEFAULT_MODELS.keys())
        missing = provider_names - model_keys
        assert not missing, (
            f"DEFAULT_MODELS missing entries for providers: {missing}"
        )

    def test_get_provider_timeouts(self):
        """get_provider_timeouts returns (connect_timeout, read_timeout) with positive values."""
        from freerouter.providers import get_provider_timeouts, PROVIDER_MAP

        # Test with a known provider
        for name in ["groq", "openrouter", "ollama"]:
            if name in PROVIDER_MAP:
                connect, read = get_provider_timeouts(name)
                assert isinstance(connect, (int, float)), (
                    f"connect_timeout for {name} should be numeric"
                )
                assert isinstance(read, (int, float)), (
                    f"read_timeout for {name} should be numeric"
                )
                assert connect > 0, f"connect_timeout for {name} should be > 0, got {connect}"
                assert read > 0, f"read_timeout for {name} should be > 0, got {read}"

        # Test with unknown provider — should return defaults
        connect, read = get_provider_timeouts("nonexistent_provider")
        assert connect > 0
        assert read > 0

    def test_provider_priority_ordering(self):
        """Providers are sorted by priority (lower number = higher priority)."""
        from freerouter.providers import get_configured_providers

        result = get_configured_providers()
        priorities = [defn.priority for defn, _ in result]
        assert priorities == sorted(priorities), (
            f"Providers should be sorted by priority. Got: {priorities}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# D. Capabilities System Tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCapabilities:
    """Test model capability mapping system."""

    def test_get_model_for_capability_research(self):
        """get_model_for_capability('research') returns a valid model string."""
        result = get_model_for_capability("research")
        assert isinstance(result, str), "Should return a string"
        assert len(result) > 0, "Should not be empty"
        # Without override file, should match the default
        override_path = Path(__file__).resolve().parents[2] / "packages" / "capabilities.yaml"
        if not override_path.exists():
            assert result == "groq/llama-3.3-70b-versatile", (
                f"Expected 'groq/llama-3.3-70b-versatile' for research (no override file), "
                f"got '{result}'."
            )

    def test_get_model_for_capability_unknown(self):
        """get_model_for_capability returns 'auto' for unknown capability."""
        result = get_model_for_capability("totally_fake_capability_xyz")
        assert result == "auto", (
            f"Unknown capability should return 'auto', got '{result}'"
        )

    def test_list_capabilities(self):
        """list_capabilities returns list with at least research, scripting, creative."""
        caps = list_capabilities()
        assert isinstance(caps, list), "Should return a list"
        assert len(caps) > 0, "Should have at least one capability"
        required = {"research", "scripting", "creative"}
        actual_set = set(caps)
        missing = required - actual_set
        assert not missing, (
            f"Missing expected capabilities: {missing}. "
            f"Available: {actual_set}"
        )
        # Verify all CAPABILITY_MODELS keys are represented
        assert set(caps) == set(CAPABILITY_MODELS.keys()), (
            "list_capabilities should return exactly the keys from CAPABILITY_MODELS"
        )

    def test_all_capabilities_return_valid_strings(self):
        """Every capability should return a non-empty string with provider/model format."""
        for cap in list_capabilities():
            model = get_model_for_capability(cap)
            assert isinstance(model, str), f"Capability '{cap}' should return string"
            assert len(model) > 0, f"Capability '{cap}' should not return empty string"
            if model != "auto":
                assert "/" in model, (
                    f"Model '{model}' for capability '{cap}' should contain '/' "
                    f"(format: provider/model)"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# E. Usage Tracker Tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestUsageTracker:
    """Test SQLite-backed usage tracking with isolated temp database."""

    def test_usage_tracker_record_call(self, tracker: UsageTracker):
        """Record a call and verify get_daily_usage returns it."""
        tracker.record_call(
            provider="groq",
            model="llama-3.3-70b-versatile",
            tokens_in=100,
            tokens_out=200,
            latency_ms=450,
            success=True,
        )
        usage = tracker.get_daily_usage("groq")
        assert isinstance(usage, dict)
        assert usage["provider"] == "groq"
        assert usage["requests"] == 1, f"Expected 1 request, got {usage['requests']}"
        assert usage["total_tokens"] == 300, (
            f"Expected 300 total tokens, got {usage['total_tokens']}"
        )
        assert usage["avg_latency_ms"] == 450, (
            f"Expected 450ms latency, got {usage['avg_latency_ms']}"
        )

    def test_usage_tracker_all_usage_today(self, tracker: UsageTracker):
        """Record multiple calls across providers, verify aggregation."""
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 200, True)
        tracker.record_call("groq", "llama-3.3-70b", 30, 50, 300, True)
        tracker.record_call("openrouter", "step-3.5-flash", 80, 150, 500, True)
        tracker.record_call("groq", "llama-3.3-70b", 10, 20, 100, False)  # failed

        all_usage = tracker.get_all_usage_today()
        assert isinstance(all_usage, list)
        assert len(all_usage) == 2, (
            f"Expected 2 providers, got {len(all_usage)}: {all_usage}"
        )

        groq_entry = next((u for u in all_usage if u["provider"] == "groq"), None)
        assert groq_entry is not None, "groq should be in usage"
        assert groq_entry["requests"] == 2, (
            f"groq should have 2 successful requests, got {groq_entry['requests']}"
        )
        assert groq_entry["total_tokens"] == 230, (
            f"groq should have 230 total tokens (50+100+30+50), "
            f"got {groq_entry['total_tokens']}"
        )

        openrouter_entry = next(
            (u for u in all_usage if u["provider"] == "openrouter"), None
        )
        assert openrouter_entry is not None
        assert openrouter_entry["requests"] == 1
        assert openrouter_entry["total_tokens"] == 230

    def test_usage_tracker_latest_limits(self, tracker: UsageTracker):
        """Record call with rpm/tpm remaining, verify retrieval."""
        tracker.record_call(
            provider="groq",
            model="llama-3.3-70b",
            tokens_in=100,
            tokens_out=200,
            latency_ms=300,
            success=True,
            rpm_remaining=25,
            tpm_remaining=5000,
        )
        limits = tracker.get_latest_limits()
        assert isinstance(limits, list)
        assert len(limits) >= 1

        groq_limit = next((l for l in limits if l["provider"] == "groq"), None)
        assert groq_limit is not None, "groq should have rate limit data"
        assert groq_limit["live_rpm_remaining"] == 25, (
            f"Expected rpm_remaining=25, got {groq_limit['live_rpm_remaining']}"
        )
        assert groq_limit["live_tpm_remaining"] == 5000, (
            f"Expected tpm_remaining=5000, got {groq_limit['live_tpm_remaining']}"
        )
        assert "timestamp" in groq_limit, "Should include timestamp"


# ═══════════════════════════════════════════════════════════════════════════════
# F. SSRF Prevention Tests (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSSRFPrevention:
    """Test SSRF protection in health check URL validation."""

    def test_validate_health_check_url_private_ip_blocked(self):
        """Private IPs (10.x, 192.168.x, 172.16.x) should be rejected."""
        private_urls = [
            "http://10.0.0.1/health",
            "http://192.168.1.100/health",
            "http://172.16.0.1/health",
            "http://169.254.1.1/health",  # link-local
        ]
        for url in private_urls:
            is_valid, error_msg = validate_health_check_url(url)
            assert is_valid is False, (
                f"URL {url} should be rejected as a private IP. "
                f"Got valid=True, error='{error_msg}'"
            )
            assert len(error_msg) > 0, (
                f"Error message should not be empty for {url}"
            )

    def test_validate_health_check_url_localhost_allowed(self):
        """localhost and 127.0.0.1 should be allowed (development/testing)."""
        allowed_urls = [
            "http://localhost:4000/health",
            "http://localhost/health",
            "http://127.0.0.1:4000/health",
            "http://127.0.0.1/health",
            "https://localhost:4000/health",
        ]
        for url in allowed_urls:
            is_valid, error_msg = validate_health_check_url(url)
            assert is_valid is True, (
                f"URL {url} should be allowed. Got valid=False, error='{error_msg}'"
            )

    def test_is_private_ip_helper(self):
        """Test the is_private_ip helper function directly."""
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("169.254.1.1") is True
        assert is_private_ip("8.8.8.8") is False  # Google DNS
        assert is_private_ip("1.1.1.1") is False  # Cloudflare
        assert is_private_ip("not-an-ip") is False  # invalid input

    def test_validate_health_check_url_empty_and_bad_scheme(self):
        """Empty URLs and non-http schemes should be rejected."""
        # Empty URL
        is_valid, msg = validate_health_check_url("")
        assert is_valid is False
        assert "empty" in msg.lower()

        # Bad scheme
        is_valid, msg = validate_health_check_url("ftp://localhost/file")
        assert is_valid is False
        assert "scheme" in msg.lower()

    def test_validate_health_check_url_custom_allowed_hosts(self):
        """Custom allowed_hosts parameter should allow additional hosts."""
        # 10.0.0.1 is normally blocked
        is_valid, _ = validate_health_check_url("http://10.0.0.1/health")
        assert is_valid is False

        # But allowed via custom hosts list
        is_valid, _ = validate_health_check_url(
            "http://10.0.0.1/health", allowed_hosts={"10.0.0.1"}
        )
        assert is_valid is True, "Custom allowed hosts should override private IP block"


# ═══════════════════════════════════════════════════════════════════════════════
# G. Service Validation Tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceValidation:
    """Test Settings.validate_service and get_service_status."""

    def test_validate_service_freerouter(self):
        """validate_service('freerouter') returns AVAILABLE when FREEROUTER_URL is set."""
        settings = get_settings()
        result = settings.validate_service("freerouter")

        assert isinstance(result, ServiceStatus)
        assert settings.FREEROUTER_URL, "FREEROUTER_URL should not be empty"
        assert result == ServiceStatus.AVAILABLE, (
            f"Expected AVAILABLE, got {result}. FREEROUTER_URL='{settings.FREEROUTER_URL}'"
        )

    def test_get_service_status(self):
        """get_service_status returns dict with all expected service keys."""
        settings = get_settings()
        status = settings.get_service_status()
        assert isinstance(status, dict)

        expected_services = {"zep", "youtube", "notion", "freerouter", "supabase", "exa"}
        actual_services = set(status.keys())
        assert actual_services == expected_services, (
            f"Missing services: {expected_services - actual_services}. "
            f"Extra: {actual_services - expected_services}"
        )

        # All values should be valid ServiceStatus enum values
        valid_values = {s.value for s in ServiceStatus}
        for service, value in status.items():
            assert value in valid_values, (
                f"Status for {service} is '{value}', expected one of {valid_values}"
            )

    def test_validate_service_freerouter_with_empty_url(self):
        """validate_service('freerouter') returns NOT_CONFIGURED when URL is empty.

        NOTE: The field_validator on FREEROUTER_URL prevents instantiating Settings
        with an empty string. This test uses object.__setattr__ to bypass the
        validator and verify the validate_service logic directly.

        PRODUCTION BUG: The FREEROUTER_URL field validator makes the
        NOT_CONFIGURED branch for freerouter unreachable in normal operation,
        because an empty string is rejected before validate_service is ever
        called. This means validate_service("freerouter") will always return
        AVAILABLE (or MISCONFIGURED) — never NOT_CONFIGURED.
        """
        settings = get_settings()
        original_url = settings.FREEROUTER_URL
        try:
            object.__setattr__(settings, "FREEROUTER_URL", "")
            result = settings.validate_service("freerouter")
            assert result == ServiceStatus.NOT_CONFIGURED, (
                f"Expected NOT_CONFIGURED with empty URL, got {result}"
            )
        finally:
            object.__setattr__(settings, "FREEROUTER_URL", original_url)


# ═══════════════════════════════════════════════════════════════════════════════
# H. Circuit Breaker Integration Tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCircuitBreakerIntegration:
    """Test the circuit breaker used by RouterClient."""

    def test_circuit_breaker_resets_on_router_client_reset(self):
        """RouterClient.reset_circuit_breaker() resets the class-level breaker."""
        RouterClient.reset_circuit_breaker()  # Start clean
        # Record enough failures to trip the breaker (threshold=10)
        for _ in range(10):
            RouterClient._circuit_breaker.record_failure()

        assert RouterClient._circuit_breaker.state == CircuitState.OPEN, (
            "Circuit breaker should be OPEN after 10 failures"
        )

        # Reset should close it
        RouterClient.reset_circuit_breaker()
        assert RouterClient._circuit_breaker.state == CircuitState.CLOSED, (
            "Circuit breaker should be CLOSED after reset"
        )

    def test_circuit_breaker_get_status_comprehensive(self):
        """CircuitBreaker.get_status() returns a complete status dict."""
        cb = CircuitBreaker(
            name="test-cb",
            failure_threshold=3,
            recovery_timeout=60,
        )
        status = cb.get_status()
        assert isinstance(status, dict)
        required_keys = {
            "name", "state", "failure_count", "last_failure_time",
            "recovery_timeout", "time_until_recovery", "total_successes",
            "total_failures", "failure_threshold", "half_open_max_calls",
        }
        assert set(status.keys()) == required_keys, (
            f"Missing keys: {required_keys - set(status.keys())}"
        )
        assert status["name"] == "test-cb"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0

    def test_circuit_breaker_blocks_requests_when_open(self):
        """When OPEN, circuit breaker should reject requests via allow_request."""
        cb = CircuitBreaker(
            name="block-test",
            failure_threshold=2,
            recovery_timeout=9999,  # Long recovery so it stays OPEN
        )
        # Trip the breaker
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Should reject requests
        assert cb.allow_request() is False, (
            "Circuit breaker should block requests when OPEN"
        )

        # Reset should allow requests again
        cb.reset()
        assert cb.allow_request() is True

    def test_circuit_breaker_recovers_after_success_in_half_open(self):
        """After recovery_timeout, HALF_OPEN allows 1 request; success closes it."""
        cb = CircuitBreaker(
            name="recover-test",
            failure_threshold=2,
            recovery_timeout=0.01,  # Almost instant recovery
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout to transition to HALF_OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN, (
            "Should transition to HALF_OPEN after recovery_timeout"
        )

        # Half-open allows one request
        assert cb.allow_request() is True
        # A second call should be blocked while the first is in-flight
        assert cb.allow_request() is False, (
            "HALF_OPEN should only allow 1 request at a time"
        )

        # Success should close the circuit
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.get_status()["failure_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# I. Error Types Tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorTypes:
    """Test that error types are properly structured."""

    def test_llm_client_error_properties(self):
        """LLMClientError has correct error_code and is catchable."""
        err = LLMClientError("FreeRouter not running")
        assert str(err) == "FreeRouter not running"
        assert err.error_code == "LLM_UNAVAILABLE"
        assert err.get_error_code() == "LLM_UNAVAILABLE"
        assert isinstance(err, PipelineException)

    def test_rate_limit_error_inherits_llm_client_error(self):
        """RateLimitError inherits from LLMClientError with its own code."""
        err = RateLimitError("All providers rate limited")
        assert isinstance(err, LLMClientError)
        assert err.error_code == "LLM_RATE_LIMIT"
        assert err.get_error_code() == "LLM_RATE_LIMIT"
        # Should also be catchable as PipelineException
        assert isinstance(err, PipelineException)

    def test_error_code_override(self):
        """Instance-level error_code takes precedence over class-level."""
        err = LLMClientError("custom error", error_code="CUSTOM_CODE")
        assert err.get_error_code() == "CUSTOM_CODE"

    def test_error_raised_and_caught(self):
        """LLMClientError can be raised and caught correctly."""
        with pytest.raises(LLMClientError) as exc_info:
            raise LLMClientError("test error")
        assert exc_info.value.error_code == "LLM_UNAVAILABLE"

        # Catch as parent
        with pytest.raises(PipelineException):
            raise LLMClientError("test error")

        # RateLimitError catchable as LLMClientError
        with pytest.raises(LLMClientError):
            raise RateLimitError("rate limited")


# ═══════════════════════════════════════════════════════════════════════════════
# J. Router Provider Map Consistency Tests (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouterProviderMap:
    """Test FreeRouter's Router class and provider map consistency."""

    def test_provider_map_matches_known_providers(self):
        """PROVIDER_MAP should have entries for all KNOWN_PROVIDERS."""
        from freerouter.providers import KNOWN_PROVIDERS, PROVIDER_MAP

        known_names = {p.name for p in KNOWN_PROVIDERS}
        map_names = set(PROVIDER_MAP.keys())
        missing = known_names - map_names
        assert not missing, (
            f"PROVIDER_MAP missing entries for: {missing}"
        )

    def test_router_resolve_model_auto(self):
        """Router._resolve_model with 'auto' returns provider's default model."""
        from freerouter.router import Router
        from freerouter.providers import DEFAULT_MODELS

        router = Router()
        for provider_name, default_model in DEFAULT_MODELS.items():
            resolved = router._resolve_model(provider_name, "auto")
            assert resolved == default_model, (
                f"auto for {provider_name} should resolve to {default_model}, "
                f"got {resolved}"
            )

    def test_router_resolve_model_with_prefix(self):
        """Router._resolve_model strips correct provider prefix."""
        from freerouter.router import Router

        router = Router()
        # "groq/llama-3.3-70b" with provider=groq should return "llama-3.3-70b"
        resolved = router._resolve_model("groq", "groq/llama-3.3-70b-versatile")
        assert resolved == "llama-3.3-70b-versatile", (
            f"Expected 'llama-3.3-70b-versatile', got '{resolved}'"
        )

        # Wrong provider prefix should fall back to provider default
        resolved = router._resolve_model("openrouter", "groq/llama-3.3-70b")
        assert resolved == "stepfun/step-3.5-flash:free", (
            f"Wrong provider prefix should return openrouter default, got '{resolved}'"
        )

    def test_router_ordered_providers(self):
        """Router._get_ordered_providers() returns a list with real configured providers."""
        from freerouter.router import Router

        router = Router()
        providers = router._get_ordered_providers()
        assert isinstance(providers, list), "_get_ordered_providers should return a list"
        # With real keys loaded, should have at least 1 provider
        assert len(providers) >= 1, (
            f"Expected at least 1 provider with real API keys. "
            f"Got: {providers}. Check that freerouter/.env is loaded."
        )
        # All returned names should be strings
        for p in providers:
            assert isinstance(p, str), f"Provider name should be str, got {type(p)}"


# ═══════════════════════════════════════════════════════════════════════════════
# K. Proxy Server Tests (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestProxyServer:
    """Test the FastAPI proxy server factory and format converters."""

    def test_create_proxy_app_returns_fastapi(self):
        """create_proxy_app returns a FastAPI application."""
        from freerouter.proxy_server import create_proxy_app

        app = create_proxy_app(api_key=None)
        assert hasattr(app, "routes"), "FastAPI app should have .routes"
        assert hasattr(app, "add_middleware"), "FastAPI app should have .add_middleware"

    def test_proxy_app_has_health_route(self):
        """Proxy app should have /health and /v1/health routes."""
        from freerouter.proxy_server import create_proxy_app

        app = create_proxy_app(api_key=None)
        route_paths = [r.path for r in app.routes]
        assert "/health" in route_paths, (
            f"/health route missing. Available: {route_paths}"
        )
        assert "/v1/health" in route_paths, (
            f"/v1/health route missing. Available: {route_paths}"
        )

    def test_proxy_app_has_chat_completions_route(self):
        """Proxy app should have /v1/chat/completions route."""
        from freerouter.proxy_server import create_proxy_app

        app = create_proxy_app(api_key=None)
        route_paths = [r.path for r in app.routes]
        assert "/v1/chat/completions" in route_paths, (
            f"/v1/chat/completions route missing. Available: {route_paths}"
        )

    def test_proxy_app_has_anthropic_messages_route(self):
        """Proxy app should have /v1/messages (Anthropic-compatible) route."""
        from freerouter.proxy_server import create_proxy_app

        app = create_proxy_app(api_key=None)
        route_paths = [r.path for r in app.routes]
        assert "/v1/messages" in route_paths, (
            f"/v1/messages route missing. Available: {route_paths}"
        )

    def test_proxy_app_has_models_route(self):
        """Proxy app should have /v1/models route."""
        from freerouter.proxy_server import create_proxy_app

        app = create_proxy_app(api_key=None)
        route_paths = [r.path for r in app.routes]
        assert "/v1/models" in route_paths, (
            f"/v1/models route missing. Available: {route_paths}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# L. Format Converter Tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatConverters:
    """Test message format conversion between Anthropic and OpenAI."""

    def test_anthropic_to_openai_messages_with_system(self):
        """Convert Anthropic messages with system prompt to OpenAI format."""
        from freerouter.proxy_server import _anthropic_to_openai_messages

        anthropic_msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        openai_msgs = _anthropic_to_openai_messages(anthropic_msgs, system="Be brief.")
        assert isinstance(openai_msgs, list)
        assert len(openai_msgs) == 3  # system + 2 messages
        assert openai_msgs[0]["role"] == "system"
        assert openai_msgs[0]["content"] == "Be brief."
        assert openai_msgs[1]["role"] == "user"
        assert openai_msgs[2]["role"] == "assistant"

    def test_anthropic_to_openai_content_blocks(self):
        """Handle Anthropic content blocks (list of dicts with type='text')."""
        from freerouter.proxy_server import _anthropic_to_openai_messages

        anthropic_msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "First part"},
                    {"type": "text", "text": "Second part"},
                ],
            },
        ]
        openai_msgs = _anthropic_to_openai_messages(anthropic_msgs)
        assert len(openai_msgs) == 1
        assert "First part" in openai_msgs[0]["content"]
        assert "Second part" in openai_msgs[0]["content"]

    def test_openai_to_anthropic_response(self):
        """Convert OpenAI response format to Anthropic format."""
        from freerouter.proxy_server import _openai_to_anthropic_response

        openai_resp = {
            "id": "chatcmpl-123",
            "choices": [
                {"message": {"content": "Hello!", "role": "assistant"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        anthropic_resp = _openai_to_anthropic_response(openai_resp, "groq/llama-3.3")
        assert anthropic_resp["role"] == "assistant"
        assert anthropic_resp["model"] == "groq/llama-3.3"
        assert anthropic_resp["type"] == "message"
        assert isinstance(anthropic_resp["content"], list)
        assert any(b.get("text") == "Hello!" for b in anthropic_resp["content"])

    def test_anthropic_to_openai_without_system(self):
        """Convert Anthropic messages without system prompt — no system message added."""
        from freerouter.proxy_server import _anthropic_to_openai_messages

        anthropic_msgs = [
            {"role": "user", "content": "Hello"},
        ]
        openai_msgs = _anthropic_to_openai_messages(anthropic_msgs)
        assert len(openai_msgs) == 1
        assert openai_msgs[0]["role"] == "user"
        assert openai_msgs[0]["content"] == "Hello"


# ═══════════════════════════════════════════════════════════════════════════════
# M. Usage Tracker Edge Cases (2 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestUsageTrackerEdgeCases:
    """Test edge cases in UsageTracker."""

    def test_usage_tracker_empty_database(self, tracker: UsageTracker):
        """get_daily_usage and get_all_usage_today return empty/zeros when no data."""
        usage = tracker.get_daily_usage("groq")
        assert usage["requests"] == 0
        assert usage["total_tokens"] == 0
        assert usage["avg_latency_ms"] == 0

        all_usage = tracker.get_all_usage_today()
        assert all_usage == []

    def test_usage_tracker_is_near_limit_with_unlimited(self, tracker: UsageTracker):
        """is_near_limit returns False for provider with unlimited quota (-1)."""
        tracker.record_call(
            provider="ollama",
            model="llama3.2",
            tokens_in=50,
            tokens_out=100,
            latency_ms=200,
            success=True,
            rpm_remaining=-1,  # unlimited
            tpm_remaining=-1,  # unlimited
        )
        assert tracker.is_near_limit("ollama") is False, (
            "Ollama (unlimited) should not be near limit"
        )

    def test_usage_tracker_failed_calls_not_counted(self, tracker: UsageTracker):
        """Failed calls should not appear in get_all_usage_today aggregation."""
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 200, False)
        tracker.record_call("groq", "llama-3.3-70b", 30, 50, 300, False)
        tracker.record_call("groq", "llama-3.3-70b", 10, 20, 100, True)

        all_usage = tracker.get_all_usage_today()
        assert len(all_usage) == 1, (
            f"Should have 1 provider (groq), got {len(all_usage)}"
        )
        groq_entry = all_usage[0]
        assert groq_entry["requests"] == 1, (
            "Only the successful call should be counted"
        )
        assert groq_entry["total_tokens"] == 30, (
            "Only successful call tokens (10+20) should be counted"
        )

    def test_usage_tracker_multiple_providers_isolated(self, tracker: UsageTracker):
        """Usage from different providers is correctly isolated."""
        tracker.record_call("groq", "model-a", 100, 200, 300, True)
        tracker.record_call("openrouter", "model-b", 50, 150, 400, True)

        groq_usage = tracker.get_daily_usage("groq")
        assert groq_usage["total_tokens"] == 300
        assert groq_usage["requests"] == 1

        openrouter_usage = tracker.get_daily_usage("openrouter")
        assert openrouter_usage["total_tokens"] == 200
        assert openrouter_usage["requests"] == 1

        # Non-existent provider
        missing_usage = tracker.get_daily_usage("nonexistent")
        assert missing_usage["requests"] == 0
        assert missing_usage["total_tokens"] == 0
