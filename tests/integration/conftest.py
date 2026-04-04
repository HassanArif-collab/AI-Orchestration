"""
conftest.py — Shared fixtures for integration tests (Phases 11-16).

Integration tests hit REAL services (Supabase, Zep, FreeRouter, etc.)
and require a valid .env file with real credentials. These helpers
ensure tests are skipped gracefully when services are unavailable
or credentials are missing.

Contrast with tests/phase_A0_bootstrap/conftest.py which creates
Settings with _env_file=None to isolate unit tests from the .env file.
"""

import os
import pytest
import httpx


# ---------------------------------------------------------------------------
# Module-level helper: skip_if_no_env
# ---------------------------------------------------------------------------

def skip_if_no_env(env_var: str):
    """Skip the current test if an environment variable is missing or empty.

    Use at module level or inside test functions:

        skip_if_no_env("SUPABASE_URL")
    """
    val = os.environ.get(env_var, "")
    if not val:
        pytest.skip(
            f"{env_var} not configured in .env — skipping integration test",
            allow_module_level=True,
        )


# ---------------------------------------------------------------------------
# Fixture: require_env
# ---------------------------------------------------------------------------

@pytest.fixture
def require_env(request):
    """Return a function to check env vars and skip if missing.

    Usage::

        def test_supabase_connection(require_env):
            url = require_env("SUPABASE_URL")
            # ... use url ...
    """
    def _check(key: str) -> str:
        val = os.environ.get(key, "")
        if not val:
            pytest.skip(f"{key} not configured in .env — skipping integration test")
        return val
    return _check


# ---------------------------------------------------------------------------
# Async helper: is_service_running
# ---------------------------------------------------------------------------

async def is_service_running(url: str, timeout: float = 5) -> bool:
    """Check whether a service at *url* is reachable.

    Sends a GET request; returns True if the response comes back with a
    status code < 500. Returns False on connection refused or timeout.

    Usage::

        if not await is_service_running("http://localhost:8000/health"):
            pytest.skip("FreeRouter not running — skipping integration test")
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            return resp.status_code < 500
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


# ---------------------------------------------------------------------------
# Session-scoped fixture: _integration_settings
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _integration_settings():
    """Load Settings WITH the real .env file.

    Unlike unit tests which pass ``_env_file=None`` to isolate from the
    environment, integration tests need the real credentials to talk to
    live services.
    """
    from packages.core.config import Settings
    return Settings()
