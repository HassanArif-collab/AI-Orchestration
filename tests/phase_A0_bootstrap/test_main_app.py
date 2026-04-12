"""
test_main_app.py — Phase A.0: Tests for apps/api/main.py (FastAPI bootstrap)

Covers:
  - FastAPI app creation (app instance exists and is configured)
  - Router registration (all expected prefixes are mounted)
  - CORS middleware present
  - Auth middleware present
  - Static files mounted at root
  - Lifespan function signature
  - SSE endpoint route registered
  - Health endpoint accessible without auth
  - App title and version metadata
"""

import pytest
from fastapi.testclient import TestClient


# ─── Import app (may fail if heavy deps missing; that's an informative failure) ───

def _get_app():
    """Import and return the FastAPI app instance.

    This may raise ImportError if dependencies are not installed.
    The tests below use this to provide clear error messages.
    """
    from apps.api.main import app
    return app


@pytest.fixture(scope="module")
def app():
    return _get_app()


@pytest.fixture(scope="module")
def client(app):
    # Disable auth for these tests
    import os
    os.environ["API_AUTH_ENABLED"] = "false"
    os.environ["API_KEYS"] = ""
    return TestClient(app, raise_server_exceptions=False)


class TestAppCreation:
    """Verify the FastAPI app is created correctly."""

    def test_app_exists(self, app):
        assert app is not None
        assert hasattr(app, "routes")

    def test_app_title(self, app):
        assert app.title == "YouTube Pipeline Dashboard"

    def test_app_version(self, app):
        assert app.version == "1.0.0"

    def test_app_description(self, app):
        assert app.description is not None


class TestRouterRegistration:
    """Verify all expected API routers are mounted."""

    def test_pipeline_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert any("/api/pipeline" in r for r in routes), "Pipeline routes not found"

    def test_provider_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert any("/api/providers" in r for r in routes), "Provider routes not found"

    def test_chat_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert any("/api/chat" in r for r in routes), "Chat routes not found"

    def test_memory_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert any("/api/memory" in r for r in routes), "Memory routes not found"

    def test_analytics_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert any("/api/analytics" in r for r in routes), "Analytics routes not found"

    def test_visual_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert any("/api/visual" in r for r in routes), "Visual routes not found"

    def test_settings_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert any("/api/settings" in r for r in routes), "Settings routes not found"

    def test_topic_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert any("/api/topics" in r for r in routes), "Topic routes not found"

    def test_kanban_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert any("/api/kanban" in r for r in routes), "Kanban routes not found"

    def test_dlq_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        # DLQ routes may not have a prefix, check for dlq in path
        assert any("dlq" in r.lower() for r in routes), "DLQ routes not found"

    def test_sse_endpoint_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert "/api/events" in routes, "SSE events endpoint not found"

    def test_health_routes_mounted(self, app):
        routes = [r.path for r in app.routes]
        assert "/health" in routes or "/api/health" in routes


class TestMiddleware:
    """Verify middleware is configured."""

    def test_middleware_count(self, app):
        """App should have at least CORS + Auth middleware."""
        assert len(app.user_middleware) >= 2

    def test_cors_middleware_present(self, app):
        from starlette.middleware.cors import CORSMiddleware
        middleware_classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middleware_classes

    def test_auth_middleware_present(self, app):
        from apps.api.middleware.auth import AuthMiddleware
        middleware_classes = [m.cls for m in app.user_middleware]
        assert AuthMiddleware in middleware_classes


class TestHealthEndpoints:
    """Test health check endpoints via TestClient."""

    def test_basic_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_detailed_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_has_timestamp(self, client):
        response = client.get("/health")
        data = response.json()
        assert "timestamp" in data

    def test_health_has_service_name(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["service"] == "youtube-pipeline-dashboard"

    def test_config_health_endpoint(self, client):
        response = client.get("/api/health/config")
        assert response.status_code == 200
        data = response.json()
        assert "critical" in data
        assert "optional" in data
        assert "summary" in data

    def test_config_health_has_all_critical_keys(self, client):
        response = client.get("/api/health/config")
        data = response.json()
        assert "FREEROUTER_URL" in data["critical"]

    def test_config_health_has_all_optional_keys(self, client):
        response = client.get("/api/health/config")
        data = response.json()
        expected_optional = {"NOTION_API_KEY", "ZEP_API_KEY", "EXA_API_KEY", "SUPABASE_URL", "YOUTUBE_API_KEY"}
        assert expected_optional.issubset(set(data["optional"].keys()))


class TestStaticFiles:
    """Verify static files are served."""

    def test_root_serves_index(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_nonexistent_static_returns_404(self, client):
        response = client.get("/nonexistent-page.html")
        assert response.status_code == 404


class TestOpenAPI:
    """Verify OpenAPI docs are available."""

    def test_openapi_schema(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "YouTube Pipeline Dashboard"
        assert data["info"]["version"] == "1.0.0"

    def test_docs_endpoint(self, client):
        response = client.get("/docs")
        assert response.status_code == 200
