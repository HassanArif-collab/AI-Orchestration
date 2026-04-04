"""
test_auth_middleware.py — Phase A.0: Tests for apps/api/middleware/auth.py

Covers:
  - Public paths bypass authentication
  - Auth disabled bypasses authentication
  - Missing API key returns 401
  - Invalid API key returns 403
  - Valid API key passes through
"""

import pytest
from unittest.mock import AsyncMock, patch
from starlette.requests import Request
from starlette.responses import Response


def _make_request(path: str, headers: dict = None) -> Request:
    """Create a Starlette Request for testing.

    Starlette's Request.url is a read-only property computed from scope.
    We build the scope correctly so request.url.path returns the right value.
    """
    # Build header list as (name_bytes, value_bytes) tuples
    headers_list = []
    if headers:
        for k, v in headers.items():
            headers_list.append((k.lower().encode(), v.encode()))

    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": headers_list,
        "query_string": b"",
        "server": ("localhost", 3000),
    }
    return Request(scope)


class TestPublicPaths:
    """Verify public paths bypass authentication."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("API_AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "test-key-123")
        # Clear settings cache so middleware picks up new env vars
        from packages.core.config import get_settings
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_health_path_is_public(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/health")
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_health_path_is_public(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/api/health")
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_root_path_is_public(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/")
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_favicon_is_public(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/favicon.ico")
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_events_is_public(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/api/events")
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_static_prefix_is_public(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/static/js/app.js")
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200


class TestAuthDisabled:
    """When API_AUTH_ENABLED is false, all paths should pass."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("API_AUTH_ENABLED", "false")
        monkeypatch.setenv("API_KEYS", "test-key-123")
        from packages.core.config import get_settings
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_protected_path_passes_when_auth_disabled(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/api/pipeline/status")
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200
        call_next.assert_called_once()


class TestAuthEnabled:
    """When API_AUTH_ENABLED is true and keys are set, enforce auth."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("API_AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "test-key-123, another-key")
        from packages.core.config import get_settings
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_missing_key_returns_401(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/api/pipeline/status", headers={})
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 401
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_key_returns_403(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request(
            "/api/pipeline/status",
            headers={"X-API-Key": "wrong-key"}
        )
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 403
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_key_first_passes(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request(
            "/api/pipeline/status",
            headers={"X-API-Key": "test-key-123"}
        )
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_key_second_passes(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request(
            "/api/pipeline/status",
            headers={"X-API-Key": "another-key"}
        )
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_401_response_body(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/api/pipeline/status", headers={})
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        body = response.body.decode()
        assert "Unauthorized" in body or "Missing" in body

    @pytest.mark.asyncio
    async def test_403_response_body(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request(
            "/api/pipeline/status",
            headers={"X-API-Key": "wrong"}
        )
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        body = response.body.decode()
        assert "Forbidden" in body or "Invalid" in body


class TestNoKeysConfigured:
    """When API_KEYS is empty, auth should be effectively disabled."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("API_AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "")
        from packages.core.config import get_settings
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_no_keys_means_auth_disabled(self):
        from apps.api.middleware.auth import AuthMiddleware
        mw = AuthMiddleware(app=None)
        request = _make_request("/api/pipeline/status")
        call_next = AsyncMock(return_value=Response("ok"))
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200
        call_next.assert_called_once()
