"""
conftest.py — Shared fixtures for Phase A.0 Bootstrap tests.

These fixtures provide test utilities for the bootstrap test suite.
They mock or configure external dependencies so tests can run
in isolation without real services (Supabase, Zep, FreeRouter, etc.).

CRITICAL FIX: pydantic-settings reads the .env file by default, which
overrides monkeypatch.setenv(). We must pass _env_file=None to Settings()
to prevent the real .env from leaking into tests.
"""

import os
import pytest


def make_settings(**overrides):
    """Create a Settings instance without reading the .env file.

    This is the ONLY way to reliably test Settings in isolation —
    monkeypatch.setenv alone does NOT override .env file values
    because pydantic-settings reads the .env file directly.

    Usage:
        from packages.core.config import Settings
        s = make_settings(FREEROUTER_URL="http://localhost:4000")
    """
    from packages.core.config import Settings
    return Settings(_env_file=None, **overrides)


@pytest.fixture(autouse=True)
def _prevent_litellm_remote_call():
    """Ensure LiteLLM never makes a remote HTTP call during tests."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    yield


@pytest.fixture(autouse=True)
def _mock_get_settings_env(monkeypatch):
    """Set minimal env vars for non-Settings tests (middleware, etc.)."""
    monkeypatch.setenv("FREEROUTER_URL", "http://localhost:4000")
    monkeypatch.setenv("API_AUTH_ENABLED", "false")
    yield


@pytest.fixture()
def settings_env(monkeypatch):
    """Return a helper to set/unset env vars per test.

    Usage:
        settings_env.set("SUPABASE_URL", "https://test.supabase.co")
        settings_env.unset("ZEP_API_KEY")
        # Then clear the cached settings singleton:
        from packages.core.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()

    NOTE: For Settings() creation, prefer make_settings() instead,
    as it bypasses the .env file entirely.
    """
    _overrides: dict[str, str] = {}

    class EnvHelper:
        def set(self, key: str, value: str):
            monkeypatch.setenv(key, value)
            _overrides[key] = value

        def unset(self, key: str):
            monkeypatch.delenv(key, raising=False)
            _overrides.pop(key, None)

        def clear_settings_cache(self):
            """Clear the lru_cache on get_settings so new env vars take effect."""
            from packages.core.config import get_settings
            get_settings.cache_clear()

    return EnvHelper()
