"""
conftest.py — Shared fixtures for Phase A.5 Exa Client tests.

Provides a make_settings helper and common mock utilities so
Exa tests run in isolation without real API keys or services.
"""

from packages.core.config import Settings


def make_settings(**overrides):
    """Create a Settings instance without reading the .env file.

    This is the ONLY way to reliably test Settings in isolation —
    monkeypatch.setenv alone does NOT override .env file values
    because pydantic-settings reads the .env file directly.

    Usage:
        from tests.phase_A5_exa.conftest import make_settings
        s = make_settings(EXA_API_KEY="test-key")
    """
    return Settings(_env_file=None, **overrides)
