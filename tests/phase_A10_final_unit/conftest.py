"""
conftest.py — Shared fixtures for Phase A.10 Final Unit tests.

Provides make_settings() helper and environment isolation for testing
notion colors, advanced health routes, and config edge cases.

CRITICAL: Integration tests (tests/integration/) load the .env file into
os.environ. Phase 10 tests must NOT see those real values, so we snapshot
and clear all known env vars at session scope.
"""

import os
import pytest


# Keys that integration conftest may have loaded from .env — we must
# clear them so Phase 10 tests get true defaults.
_ENV_KEYS_TO_CLEAR = [
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_DB_URL", "ZEP_API_KEY", "ZEP_BASE_URL",
    "YOUTUBE_API_KEY", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_REFRESH_TOKEN", "NOTION_API_KEY", "NOTION_DATABASE_ID",
    "EXA_API_KEY", "FREEROUTER_URL", "GITHUB_TOKEN", "OPENAI_API_KEY",
    "API_KEYS", "DATA_DIR",
]

# Snapshot original values so we can restore them after the session
_ORIGINAL_ENV = {k: os.environ.get(k) for k in _ENV_KEYS_TO_CLEAR}


def _clear_env():
    """Remove all known API keys from os.environ for test isolation."""
    for key in _ENV_KEYS_TO_CLEAR:
        os.environ.pop(key, None)


def _restore_env():
    """Restore original env var values after test session."""
    for key, val in _ORIGINAL_ENV.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


# Clear at import time so module-level checks in test files don't see .env values
_clear_env()


@pytest.fixture(scope="session", autouse=True)
def _restore_env_after_session():
    """Restore env vars after the entire Phase 10 test session."""
    yield
    _restore_env()


def make_settings(**overrides):
    """Create a Settings instance without reading the .env file.

    This is the ONLY way to reliably test Settings in isolation —
    monkeypatch.setenv alone does NOT override .env file values
    because pydantic-settings reads the .env file directly.

    Usage:
        from packages.core.config import Settings
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
    """
    _clear_env()  # Ensure clean state before each Settings creation
    from packages.core.config import Settings
    return Settings(_env_file=None, **overrides)


@pytest.fixture(autouse=True)
def _prevent_litellm_remote_call():
    """Ensure LiteLLM never makes a remote HTTP call during tests."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    _clear_env()  # Clear any env vars leaked by other test sessions
    yield
    _restore_env()  # Restore so integration tests in same session work


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the cached Settings singleton so each test starts fresh."""
    yield
    try:
        from packages.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass
