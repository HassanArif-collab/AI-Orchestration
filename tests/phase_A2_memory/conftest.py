"""
conftest.py — Shared fixtures for Phase A.2 Memory Client tests.

These fixtures provide test utilities for the memory client test suite.
They mock or configure external dependencies so tests can run
in isolation without real Zep API calls.
"""

import pytest


def make_settings(**overrides):
    """Create a Settings instance without reading the .env file.

    This is the ONLY way to reliably test Settings in isolation —
    monkeypatch.setenv alone does NOT override .env file values
    because pydantic-settings reads the .env file directly.

    Usage:
        from packages.core.config import Settings
        s = make_settings(ZEP_API_KEY="test-key")
    """
    from packages.core.config import Settings
    return Settings(_env_file=None, **overrides)


@pytest.fixture()
def mock_get_settings():
    """Patch packages.memory.client.get_settings to return a controlled Settings.

    Usage:
        def test_something(mock_get_settings):
            mock_get_settings(ZEP_API_KEY="my-key")
            ...
    """
    from unittest.mock import patch

    def _configure(**overrides):
        settings = make_settings(**overrides)
        patcher = patch("packages.memory.client.get_settings", return_value=settings)
        patcher.start()
        return patcher

    return _configure
