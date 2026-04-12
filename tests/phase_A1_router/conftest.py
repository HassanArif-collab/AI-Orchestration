"""
conftest.py — Shared fixtures for Phase A.1 Router Client tests.

Provides mocked settings, circuit breaker reset, shared client reset,
and HTTP client mocks so router tests run in complete isolation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.core.config import Settings


def make_settings(**overrides):
    """Create a Settings instance without reading the .env file.

    This is the ONLY way to reliably test Settings in isolation —
    monkeypatch.setenv alone does NOT override .env file values
    because pydantic-settings reads the .env file directly.
    """
    return Settings(_env_file=None, **overrides)


@pytest.fixture()
def mock_settings(monkeypatch):
    """Patch get_settings() to return a controlled Settings instance.

    Sets FREEROUTER_URL, empty FALLBACK_ROUTER_URL, and disables
    FREEROUTER_STARTUP_CHECK so no real health checks run.
    """
    settings = make_settings(
        FREEROUTER_URL="http://localhost:4000",
        FALLBACK_ROUTER_URL="",
        FREEROUTER_STARTUP_CHECK=False,
    )
    monkeypatch.setattr("packages.router.client.get_settings", lambda: settings)
    monkeypatch.setattr("packages.core.config.get_settings", lambda: settings)
    return settings


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset RouterClient._circuit_breaker before each test."""
    from packages.router.client import RouterClient
    RouterClient.reset_circuit_breaker()
    yield
    RouterClient.reset_circuit_breaker()


@pytest.fixture(autouse=True)
def reset_shared_client():
    """Reset RouterClient._shared_client before each test."""
    from packages.router.client import RouterClient
    RouterClient._shared_client = None
    RouterClient._shared_client_refcount = 0
    yield
    # Cleanup after test — use asyncio.run() to avoid deprecation warning
    if RouterClient._shared_client is not None and not RouterClient._shared_client.is_closed:
        import asyncio
        try:
            asyncio.run(RouterClient._shared_client.aclose())
        except RuntimeError:
            pass
    RouterClient._shared_client = None
    RouterClient._shared_client_refcount = 0


@pytest.fixture()
def mock_http_client():
    """Provide an AsyncMock-based HTTP client for RouterClient.

    Returns a tuple of (mock_http, mock_post, mock_get) where:
      - mock_http: a MagicMock with AsyncMock .post and .get methods
      - mock_post: the AsyncMock for .post()
      - mock_get: the AsyncMock for .get()
    """
    mock_post = AsyncMock()
    mock_get = AsyncMock()
    mock_http = MagicMock()
    mock_http.post = mock_post
    mock_http.get = mock_get
    mock_http.is_closed = False
    return mock_http, mock_post, mock_get
