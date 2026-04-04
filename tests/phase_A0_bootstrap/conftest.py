"""
conftest.py — Shared fixtures for Phase A.0 Bootstrap tests.

These fixtures provide test utilities for the bootstrap test suite.
They mock or configure external dependencies so tests can run
in isolation without real services (Supabase, Zep, FreeRouter, etc.).
"""

import os
import pytest


@pytest.fixture(autouse=True)
def _prevent_litellm_remote_call():
    """Ensure LiteLLM never makes a remote HTTP call during tests."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    yield


@pytest.fixture(autouse=True)
def _mock_get_settings_env(monkeypatch):
    """Patch get_settings so it uses test env vars, not the real .env file.

    We set a minimal set of env vars that let Settings() instantiate
    without errors. Individual test modules can override specific
    keys via monkeypatch or the `settings_env` fixture below.
    """
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
