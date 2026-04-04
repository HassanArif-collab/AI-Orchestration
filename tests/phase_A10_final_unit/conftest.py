"""
conftest.py — Shared fixtures for Phase A.10 Final Unit tests.

Provides make_settings() helper and environment isolation for testing
notion colors, advanced health routes, and config edge cases.
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
def _clear_settings_cache():
    """Clear the cached Settings singleton so each test starts fresh."""
    yield
    try:
        from packages.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass
