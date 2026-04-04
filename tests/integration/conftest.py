"""
conftest.py — Shared fixtures for integration tests (Phases 11-17).

Integration tests hit REAL services (Supabase, Zep, FreeRouter, YouTube, etc.)
and require a valid .env file with real credentials.  On startup this conftest
loads ALL .env files into os.environ so that skip_if_no_env() can see
the values without requiring the user to manually export them.

Env files loaded (in order, each overriding the previous):
  1. <project_root>/.env          — main pipeline config (Supabase, Zep, Exa, etc.)
  2. <project_root>/freerouter/.env — FreeRouter provider keys (YouTube OAuth, LLM keys)

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

def _load_env_files():
    """Load all .env files into os.environ.

    Integration tests need credentials from multiple .env files:
    - Main .env: Supabase, Zep, Exa, Notion, YouTube API key
    - freerouter/.env: YouTube OAuth, LLM provider keys (OpenRouter, Groq, etc.)
    """
    _PROJECT_ROOT = Path(__file__).resolve().parents[2]
    env_files = [
        _PROJECT_ROOT / ".env",                    # Main pipeline config
        _PROJECT_ROOT / "freerouter" / ".env",     # FreeRouter provider keys
        Path(__file__).resolve().parents[3] / ".env",  # Repo root fallback
    ]

    for env_file in env_files:
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file, override=True)
            except ImportError:
                pass

_load_env_files()


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
    """Re-load .env files before every integration test.

    Phase A10 conftest clears env vars for isolation. Integration tests need
    them back. This fixture runs for every test in tests/integration/.
    """
    _load_env_files()
    yield
