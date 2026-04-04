"""
test_health_routes_advanced.py — Tests for the 3 UNCOVERED health endpoints.

Endpoints tested:
    GET /api/health/freerouter       — FreeRouter proxy health via httpx
    GET /api/health/services         — Comprehensive service status check
    GET /api/health/circuit-breakers — Circuit breaker status summary

Uses an isolated FastAPI app (no middleware) to avoid auth issues.

CRITICAL: get_settings and ServiceStatus are lazily imported INSIDE
function bodies in health_routes.py, so we must patch at the SOURCE
module level (packages.core.config), not at the router module level.
"""

from __future__ import annotations

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from starlette.testclient import TestClient


# ─── Build isolated app once at module level (avoids middleware) ─────────
from apps.api.routers.health_routes import router as health_router

_isolated_app = FastAPI()
_isolated_app.include_router(health_router)


def _get_health_module():
    """Get the health_routes module via sys.modules for patching."""
    key = "apps.api.routers.health_routes"
    if key not in sys.modules:
        __import__(key)
    return sys.modules[key]


def _make_httpx_client(response_status=200, error=None):
    """Build a mock httpx.AsyncClient constructor.

    httpx.AsyncClient(timeout=3.0) is a normal constructor call (not async),
    but its result is used as an async context manager. We return a MagicMock
    whose return_value is an object with async __aenter__/__aexit__.

    Args:
        response_status: HTTP status code for the response.
        error: If set, the constructor raises this error instead.
    """
    if error is not None:
        mock_ctor = MagicMock()
        mock_ctor.side_effect = error
        return mock_ctor

    mock_response = MagicMock()
    mock_response.status_code = response_status

    mock_instance = MagicMock()
    mock_instance.get = AsyncMock(return_value=mock_response)
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=False)

    mock_ctor = MagicMock(return_value=mock_instance)
    return mock_ctor


# ═══════════════════════════════════════════════════════════════════════
# FreeRouter Health
# ═══════════════════════════════════════════════════════════════════════

class TestFreeRouterHealth:
    """Tests for GET /api/health/freerouter.

    This endpoint does a live httpx request to the FreeRouter URL
    obtained from settings. We mock httpx and get_settings.
    """

    def test_healthy_when_freerouter_returns_200(self):
        """FreeRouter returns HTTP 200 → healthy=True."""
        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("httpx.AsyncClient", _make_httpx_client(200)):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/freerouter")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] is True
        assert data["url"] == "http://localhost:4000"

    def test_unhealthy_when_connection_error(self):
        """FreeRouter connection error → healthy=False."""
        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("httpx.AsyncClient", _make_httpx_client(error=Exception("Connection refused"))):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/freerouter")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] is False
        assert data["url"] == "http://localhost:4000"

    def test_unhealthy_when_non_200_status(self):
        """FreeRouter returns HTTP 502 → healthy=False."""
        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("httpx.AsyncClient", _make_httpx_client(502)):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/freerouter")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] is False

    def test_settings_url_returned(self):
        """The FREEROUTER_URL from settings appears in the response."""
        custom_url = "http://custom-router:9999"
        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = custom_url

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("httpx.AsyncClient", _make_httpx_client(error=Exception("unreachable"))):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/freerouter")
        assert resp.json()["url"] == custom_url


# ═══════════════════════════════════════════════════════════════════════
# Service Health Check
# ═══════════════════════════════════════════════════════════════════════

class TestServiceHealthCheck:
    """Tests for GET /api/health/services.

    This endpoint checks 6 services: Zep, Notion, FreeRouter, Supabase,
    Exa, and YouTube. We mock settings.validate_service and any lazy imports.
    """

    def test_all_services_available(self):
        """When all 6 services are AVAILABLE, summary shows all operational."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"
        mock_settings.validate_service.return_value = ServiceStatus.AVAILABLE
        mock_settings.SUPABASE_URL = "https://test.supabase.co"
        mock_settings.SUPABASE_SERVICE_ROLE_KEY = "key"
        mock_settings.EXA_API_KEY = "a" * 20
        mock_settings.YOUTUBE_API_KEY = "b" * 30
        mock_settings.NOTION_API_KEY = "secret_test"
        mock_settings.ZEP_API_KEY = "zep-key"
        mock_settings.NOTION_DATABASE_ID = "db-123"

        mock_notion_client = MagicMock()
        mock_notion_client._client = MagicMock()
        mock_notion_client.database_id = "db-123"

        mock_zep_client = MagicMock()
        mock_zep_client._client = MagicMock()

        mod = _get_health_module()

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus), \
             patch.object(mod, "AsyncZepMemoryClient", return_value=mock_zep_client), \
             patch("packages.integrations.notion.client.NotionScriptClient",
                   return_value=mock_notion_client), \
             patch("httpx.AsyncClient", _make_httpx_client(200)):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] == 6
        assert data["summary"]["operational"] == 6

    def test_zep_not_configured(self):
        """Zep with empty API key → not_configured, unavailable."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"

        def _validate(service):
            if service == "zep":
                return ServiceStatus.NOT_CONFIGURED
            return ServiceStatus.AVAILABLE

        mock_settings.validate_service.side_effect = _validate
        mock_settings.SUPABASE_URL = "https://test.supabase.co"
        mock_settings.SUPABASE_SERVICE_ROLE_KEY = "key"
        mock_settings.EXA_API_KEY = "a" * 20
        mock_settings.YOUTUBE_API_KEY = "b" * 30
        mock_settings.NOTION_API_KEY = "secret_test"
        mock_settings.NOTION_DATABASE_ID = "db-123"

        mock_notion_client = MagicMock()
        mock_notion_client._client = MagicMock()
        mock_notion_client.database_id = "db-123"

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus), \
             patch("packages.integrations.notion.client.NotionScriptClient",
                   return_value=mock_notion_client), \
             patch("httpx.AsyncClient", _make_httpx_client(200)):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        data = resp.json()
        assert data["services"]["zep"]["config_status"] == "not_configured"
        assert data["services"]["zep"]["operational_status"] == "unavailable"

    def test_notion_misconfigured(self):
        """Notion with invalid key prefix → misconfigured, degraded."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"

        def _validate(service):
            if service == "notion":
                return ServiceStatus.MISCONFIGURED
            return ServiceStatus.AVAILABLE

        mock_settings.validate_service.side_effect = _validate
        mock_settings.SUPABASE_URL = "https://test.supabase.co"
        mock_settings.SUPABASE_SERVICE_ROLE_KEY = "key"
        mock_settings.EXA_API_KEY = "a" * 20
        mock_settings.YOUTUBE_API_KEY = "b" * 30
        mock_settings.ZEP_API_KEY = "zep-key"

        mock_zep_client = MagicMock()
        mock_zep_client._client = MagicMock()

        mod = _get_health_module()

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus), \
             patch.object(mod, "AsyncZepMemoryClient", return_value=mock_zep_client), \
             patch("httpx.AsyncClient", _make_httpx_client(200)):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        data = resp.json()
        assert data["services"]["notion"]["config_status"] == "misconfigured"
        assert data["services"]["notion"]["operational_status"] == "degraded"

    def test_freerouter_unreachable(self):
        """FreeRouter available but unreachable → degraded/unavailable."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"
        mock_settings.validate_service.return_value = ServiceStatus.AVAILABLE
        mock_settings.SUPABASE_URL = "https://test.supabase.co"
        mock_settings.SUPABASE_SERVICE_ROLE_KEY = "key"
        mock_settings.EXA_API_KEY = "a" * 20
        mock_settings.YOUTUBE_API_KEY = "b" * 30
        mock_settings.NOTION_API_KEY = "secret_test"
        mock_settings.ZEP_API_KEY = "zep-key"
        mock_settings.NOTION_DATABASE_ID = "db-123"

        mock_notion_client = MagicMock()
        mock_notion_client._client = MagicMock()
        mock_notion_client.database_id = "db-123"
        mock_zep_client = MagicMock()
        mock_zep_client._client = MagicMock()

        mod = _get_health_module()

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus), \
             patch.object(mod, "AsyncZepMemoryClient", return_value=mock_zep_client), \
             patch("packages.integrations.notion.client.NotionScriptClient",
                   return_value=mock_notion_client), \
             patch("httpx.AsyncClient", _make_httpx_client(error=Exception("Connection refused"))):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        data = resp.json()
        assert data["services"]["freerouter"]["operational_status"] == "unavailable"
        assert "not reachable" in data["services"]["freerouter"]["message"].lower()

    def test_supabase_misconfigured(self):
        """Supabase misconfigured → degraded status."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"

        def _validate(service):
            if service == "supabase":
                return ServiceStatus.MISCONFIGURED
            return ServiceStatus.AVAILABLE

        mock_settings.validate_service.side_effect = _validate
        mock_settings.EXA_API_KEY = "a" * 20
        mock_settings.YOUTUBE_API_KEY = "b" * 30
        mock_settings.NOTION_API_KEY = "secret_test"
        mock_settings.ZEP_API_KEY = "zep-key"
        mock_settings.NOTION_DATABASE_ID = "db-123"

        mock_notion_client = MagicMock()
        mock_notion_client._client = MagicMock()
        mock_notion_client.database_id = "db-123"
        mock_zep_client = MagicMock()
        mock_zep_client._client = MagicMock()

        mod = _get_health_module()

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus), \
             patch.object(mod, "AsyncZepMemoryClient", return_value=mock_zep_client), \
             patch("packages.integrations.notion.client.NotionScriptClient",
                   return_value=mock_notion_client), \
             patch("httpx.AsyncClient", _make_httpx_client(200)):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        data = resp.json()
        assert data["services"]["supabase"]["config_status"] == "misconfigured"
        assert data["services"]["supabase"]["operational_status"] == "degraded"

    def test_exa_not_configured(self):
        """Exa with empty key → not_configured, unavailable."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"

        def _validate(service):
            if service == "exa":
                return ServiceStatus.NOT_CONFIGURED
            return ServiceStatus.AVAILABLE

        mock_settings.validate_service.side_effect = _validate
        mock_settings.SUPABASE_URL = "https://test.supabase.co"
        mock_settings.SUPABASE_SERVICE_ROLE_KEY = "key"
        mock_settings.YOUTUBE_API_KEY = "b" * 30
        mock_settings.NOTION_API_KEY = "secret_test"
        mock_settings.ZEP_API_KEY = "zep-key"
        mock_settings.NOTION_DATABASE_ID = "db-123"

        mock_notion_client = MagicMock()
        mock_notion_client._client = MagicMock()
        mock_notion_client.database_id = "db-123"
        mock_zep_client = MagicMock()
        mock_zep_client._client = MagicMock()

        mod = _get_health_module()

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus), \
             patch.object(mod, "AsyncZepMemoryClient", return_value=mock_zep_client), \
             patch("packages.integrations.notion.client.NotionScriptClient",
                   return_value=mock_notion_client), \
             patch("httpx.AsyncClient", _make_httpx_client(200)):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        data = resp.json()
        assert data["services"]["exa"]["operational_status"] == "unavailable"

    def test_youtube_misconfigured(self):
        """YouTube with short key → misconfigured, degraded."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"

        def _validate(service):
            if service == "youtube":
                return ServiceStatus.MISCONFIGURED
            return ServiceStatus.AVAILABLE

        mock_settings.validate_service.side_effect = _validate
        mock_settings.SUPABASE_URL = "https://test.supabase.co"
        mock_settings.SUPABASE_SERVICE_ROLE_KEY = "key"
        mock_settings.EXA_API_KEY = "a" * 20
        mock_settings.NOTION_API_KEY = "secret_test"
        mock_settings.ZEP_API_KEY = "zep-key"
        mock_settings.NOTION_DATABASE_ID = "db-123"

        mock_notion_client = MagicMock()
        mock_notion_client._client = MagicMock()
        mock_notion_client.database_id = "db-123"
        mock_zep_client = MagicMock()
        mock_zep_client._client = MagicMock()

        mod = _get_health_module()

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus), \
             patch.object(mod, "AsyncZepMemoryClient", return_value=mock_zep_client), \
             patch("packages.integrations.notion.client.NotionScriptClient",
                   return_value=mock_notion_client), \
             patch("httpx.AsyncClient", _make_httpx_client(200)):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        data = resp.json()
        assert data["services"]["youtube"]["config_status"] == "misconfigured"
        assert data["services"]["youtube"]["operational_status"] == "degraded"

    def test_summary_counts_are_correct(self):
        """Summary operational+degraded+unavailable adds up to total."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"

        call_count = 0
        statuses = [
            ServiceStatus.AVAILABLE,        # zep
            ServiceStatus.MISCONFIGURED,     # notion
            ServiceStatus.AVAILABLE,         # freerouter
            ServiceStatus.NOT_CONFIGURED,    # supabase
            ServiceStatus.NOT_CONFIGURED,    # exa
            ServiceStatus.NOT_CONFIGURED,    # youtube
        ]

        def _validate(service):
            nonlocal call_count
            result = statuses[call_count % len(statuses)]
            call_count += 1
            return result

        mock_settings.validate_service.side_effect = _validate
        mock_settings.SUPABASE_URL = ""
        mock_settings.EXA_API_KEY = ""
        mock_settings.YOUTUBE_API_KEY = ""
        mock_settings.ZEP_API_KEY = "zep-key"
        mock_settings.NOTION_API_KEY = "bad-prefix"

        mock_zep_client = MagicMock()
        mock_zep_client._client = MagicMock()

        mod = _get_health_module()

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus), \
             patch.object(mod, "AsyncZepMemoryClient", return_value=mock_zep_client), \
             patch("httpx.AsyncClient", _make_httpx_client(200)):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        data = resp.json()
        summary = data["summary"]
        assert summary["total"] == 6
        assert (summary["operational"] + summary["degraded"]
                + summary["unavailable"]) == 6

    def test_response_has_timestamp(self):
        """Response must include an ISO timestamp."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"
        mock_settings.validate_service.return_value = ServiceStatus.NOT_CONFIGURED
        mock_settings.SUPABASE_URL = ""
        mock_settings.EXA_API_KEY = ""
        mock_settings.YOUTUBE_API_KEY = ""

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        data = resp.json()
        assert "timestamp" in data
        assert "T" in data["timestamp"]

    def test_service_names_present(self):
        """All 6 expected service keys must be in the response."""
        from packages.core.config import ServiceStatus

        mock_settings = MagicMock()
        mock_settings.FREEROUTER_URL = "http://localhost:4000"
        mock_settings.validate_service.return_value = ServiceStatus.NOT_CONFIGURED
        mock_settings.SUPABASE_URL = ""
        mock_settings.EXA_API_KEY = ""
        mock_settings.YOUTUBE_API_KEY = ""

        with patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch("packages.core.config.ServiceStatus", ServiceStatus):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/services")
        data = resp.json()
        expected_services = {"zep", "notion", "freerouter", "supabase", "exa", "youtube"}
        assert set(data["services"].keys()) == expected_services


# ═══════════════════════════════════════════════════════════════════════
# Circuit Breaker Status
# ═══════════════════════════════════════════════════════════════════════

class TestCircuitBreakerStatus:
    """Tests for GET /api/health/circuit-breakers.

    This endpoint imports get_all_circuit_breaker_statuses at call time
    and returns a dict of circuit breaker states.
    """

    def test_returns_circuit_breaker_statuses(self):
        """Normal case: returns dict of circuit breaker states."""
        mock_statuses = {
            "freerouter": {
                "name": "freerouter",
                "state": "closed",
                "failure_count": 0,
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "last_failure_time": None,
            }
        }

        with patch(
            "packages.core.circuit_breaker.get_all_circuit_breaker_statuses",
            return_value=mock_statuses,
        ):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/circuit-breakers")
        assert resp.status_code == 200
        data = resp.json()
        assert "circuit_breakers" in data
        assert "timestamp" in data
        assert "freerouter" in data["circuit_breakers"]

    def test_import_fallback_returns_empty(self):
        """If circuit_breaker module can't be imported, returns empty dict.

        The endpoint catches ImportError from the lazy import and returns
        a fallback response with an empty dict and explanatory message.
        """
        import builtins
        original_import = builtins.__import__

        def _failing_import(name, *args, **kwargs):
            if "circuit_breaker" in name:
                raise ImportError("simulated")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_failing_import):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/circuit-breakers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["circuit_breakers"] == {}
        assert "message" in data

    def test_empty_circuit_breaker_registry(self):
        """No circuit breakers registered → returns empty dict."""
        with patch(
            "packages.core.circuit_breaker.get_all_circuit_breaker_statuses",
            return_value={},
        ):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/circuit-breakers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["circuit_breakers"] == {}

    def test_multiple_circuit_breakers(self):
        """Multiple registered circuit breakers all appear in response."""
        mock_statuses = {
            "freerouter": {
                "name": "freerouter",
                "state": "closed",
                "failure_count": 0,
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "last_failure_time": None,
            },
            "youtube_api": {
                "name": "youtube_api",
                "state": "open",
                "failure_count": 5,
                "failure_threshold": 5,
                "recovery_timeout": 30,
                "last_failure_time": "2024-01-01T00:00:00Z",
            },
        }

        with patch(
            "packages.core.circuit_breaker.get_all_circuit_breaker_statuses",
            return_value=mock_statuses,
        ):
            with TestClient(_isolated_app) as tc:
                resp = tc.get("/api/health/circuit-breakers")
        data = resp.json()
        assert len(data["circuit_breakers"]) == 2
        assert data["circuit_breakers"]["youtube_api"]["state"] == "open"
