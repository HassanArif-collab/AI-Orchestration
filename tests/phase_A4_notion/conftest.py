"""
conftest.py — Shared fixtures for Phase A.4 Notion Client tests.

Provides test utilities for creating NotionScriptClient instances
and Settings objects without reading the real .env file.
"""

import pytest
from unittest.mock import MagicMock, patch


def make_settings(**overrides):
    """Create a Settings instance without reading the .env file.

    This is the ONLY way to reliably test Settings in isolation —
    monkeypatch.setenv alone does NOT override .env file values
    because pydantic-settings reads the .env file directly.

    Usage:
        from packages.core.config import Settings
        s = make_settings(NOTION_API_KEY="secret_test")
    """
    from packages.core.config import Settings
    return Settings(_env_file=None, **overrides)


@pytest.fixture(autouse=True)
def _mock_get_settings(monkeypatch):
    """Patch get_settings to return a clean Settings without .env file.

    Prevents the real .env from leaking into tests and ensures
    NotionScriptClient.__init__ gets predictable defaults.

    We patch both the source and the consumer module because
    `from X import Y` creates a local binding that won't update
    when the source module's attribute is patched.
    """
    clean_settings = make_settings()
    with (
        patch("packages.core.config.get_settings", return_value=clean_settings),
        patch("packages.integrations.notion.client.get_settings", return_value=clean_settings),
    ):
        yield


@pytest.fixture()
def mock_notion_client():
    """Return a MagicMock that acts as the notion_client.Client."""
    return MagicMock()
