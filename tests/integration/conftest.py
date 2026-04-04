"""
conftest.py — Shared fixtures for integration tests (Phases 11-17).

Integration tests hit REAL services (Supabase, Zep, FreeRouter, YouTube, etc.)
and require a valid .env file with real credentials.  On startup this conftest
loads the project .env file into os.environ so that skip_if_no_env() can see
the values without requiring the user to manually export them.

Contrast with tests/phase_A0_bootstrap/conftest.py which creates Settings with
_env_file=None to isolate unit tests from the .env file.
"""

import os
from pathlib import Path

import pytest
import httpx


# ---------------------------------------------------------------------------
# Bootstrap: load .env into os.environ for integration tests
# ---------------------------------------------------------------------------

# Walk up from this file to find the project root (where .env lives)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"

if _ENV_FILE.exists():
    from dotenv import load_dotenv

    load_dotenv(_ENV_FILE, override=True)
else:
    # Fallback: try the repo root one level up
    _ENV_FILE_ALT = Path(__file__).resolve().parents[3] / ".env"
    if _ENV_FILE_ALT.exists():
        from dotenv import load_dotenv

        load_dotenv(_ENV_FILE_ALT, override=True)


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

@pytest.fixture(autouse=True)
def _ensure_env_loaded():
    """Re-load .env before every integration test.

    Phase A10 conftest clears env vars for isolation. Integration tests need
    them back. This fixture runs for every test in tests/integration/.
    """
    _ENV_FILE = _PROJECT_ROOT / ".env"
    if _ENV_FILE.exists():
        from dotenv import load_dotenv
        load_dotenv(_ENV_FILE, override=True)
    yield
