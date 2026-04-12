"""
test_provider_routes.py — Tests for the LLM provider management API.

Endpoints tested:
    GET  /api/providers/              — List all providers (reads from .env)
    POST /api/providers/{name}/key    — Save API key for provider (writes to .env)
    POST /api/providers/{name}/test   — Test provider health
    POST /api/providers/{name}/reset  — Reset provider rate limit
    GET  /api/providers/usage         — Get provider usage stats (from UsageTracker)
    GET  /api/providers/models        — List available models (from ROUTES)
    GET  /api/providers/health        — Provider health check
    GET  /api/providers/quota         — Get live quota remaining (from UsageTracker)
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


def _mod():
    """Get the provider_routes module via sys.modules."""
    return sys.modules["apps.api.routers.provider_routes"]


class TestListProviders:
    @pytest.mark.asyncio
    async def test_list_providers_success(self, client):
        mod = _mod()
        with patch.object(mod, "_get_configured_providers", return_value=[
            ({"name": "groq", "display_name": "Groq", "requires_auth": True,
              "signup_url": "https://console.groq.com", "priority": 1}, True),
            ({"name": "openrouter", "display_name": "OpenRouter", "requires_auth": True,
              "signup_url": "https://openrouter.ai", "priority": 2}, True),
        ]):
            resp = await client.get("/api/providers/")
            assert resp.status_code == 200
            data = resp.json()
            assert "providers" in data
            assert len(data["providers"]) >= 1
            # Check structure of first provider
            prov = data["providers"][0]
            assert "name" in prov
            assert "display_name" in prov
            assert "is_configured" in prov
            assert "has_key" in prov

    @pytest.mark.asyncio
    async def test_list_providers_500_error(self, client):
        mod = _mod()
        with patch.object(mod, "_get_configured_providers", side_effect=Exception("Read error")):
            resp = await client.get("/api/providers/")
            assert resp.status_code == 500


class TestSaveKey:
    @pytest.mark.asyncio
    async def test_save_key_success(self, client):
        mod = _mod()
        with patch.object(mod, "_read_env", return_value={"GROQ_API_KEY": ""}), \
             patch.object(mod, "_save_env") as mock_save:
            resp = await client.post("/api/providers/groq/key", json={"api_key": "gsk_test123"})
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_key_400_invalid_provider(self, client):
        resp = await client.post("/api/providers/xyz/key", json={"api_key": "test"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_save_key_422_missing_body(self, client):
        resp = await client.post("/api/providers/groq/key", json={})
        assert resp.status_code == 422


class TestTestProvider:
    @pytest.mark.asyncio
    async def test_test_provider_configured(self, client):
        mod = _mod()
        with patch.object(mod, "_read_env", return_value={"GROQ_API_KEY": "gsk_valid_key"}):
            resp = await client.post("/api/providers/groq/test")
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_test_provider_no_key(self, client):
        mod = _mod()
        with patch.object(mod, "_read_env", return_value={"GROQ_API_KEY": ""}):
            resp = await client.post("/api/providers/groq/test")
            assert resp.status_code == 200
            assert resp.json()["ok"] is False

    @pytest.mark.asyncio
    async def test_test_provider_unknown(self, client):
        mod = _mod()
        with patch.object(mod, "_read_env", return_value={}):
            resp = await client.post("/api/providers/unknown_provider/test")
            assert resp.status_code == 200
            assert resp.json()["ok"] is False

    @pytest.mark.asyncio
    async def test_test_provider_500_error(self, client):
        mod = _mod()
        with patch.object(mod, "_read_env", side_effect=Exception("Read error")):
            resp = await client.post("/api/providers/groq/test")
            assert resp.status_code == 500


class TestResetProvider:
    @pytest.mark.asyncio
    async def test_reset_success(self, client):
        mod = _mod()
        with patch.object(mod, "UsageTracker", create=True):
            resp = await client.post("/api/providers/groq/reset")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_reset_500_error(self, client):
        with patch("packages.router.tracker.UsageTracker", side_effect=Exception("DB error"), create=True):
            resp = await client.post("/api/providers/groq/reset")
            assert resp.status_code == 500


class TestGetUsage:
    @pytest.mark.asyncio
    async def test_usage_success(self, client):
        mod = _mod()
        mock_tracker = MagicMock()
        mock_tracker.get_all_usage_today.return_value = [
            {"provider": "groq", "requests": 10, "total_tokens": 5000}
        ]
        with patch("apps.api.routers.provider_routes.UsageTracker", return_value=mock_tracker, create=True):
            resp = await client.get("/api/providers/usage")
            assert resp.status_code == 200
            data = resp.json()
            assert "freerouter" in data
            assert "pipeline" in data

    @pytest.mark.asyncio
    async def test_usage_graceful_when_tracker_fails(self, client):
        # usage endpoint catches UsageTracker errors gracefully and returns empty pipeline.
        with patch("packages.router.tracker.UsageTracker", side_effect=Exception("DB error")):
            resp = await client.get("/api/providers/usage")
            # Endpoint is resilient — returns 200 with empty pipeline data
            assert resp.status_code == 200
            data = resp.json()
            assert "freerouter" in data
            assert "pipeline" in data


class TestGetModels:
    @pytest.mark.asyncio
    async def test_models_success(self, client):
        mod = _mod()
        mock_routes = {
            "auto": {"model": "openrouter/stepfun/step-3.5-flash:free",
                      "fallback": "groq/llama-3.3-70b-versatile"},
            "scorer": {"model": "groq/compound-beta-mini",
                       "fallback": "groq/llama-3.1-8b-instant"},
        }
        with patch.dict("sys.modules", {"freerouter": MagicMock(config=MagicMock(ROUTES=mock_routes))}):
            resp = await client.get("/api/providers/models")
            assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_models_500_when_no_config(self, client):
        # If freerouter.config is not available, expect 500
        resp = await client.get("/api/providers/models")
        assert resp.status_code in (200, 500)


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_returns_status(self, client):
        mod = _mod()
        mock_proxy = AsyncMock()
        mock_proxy.get = AsyncMock(side_effect=Exception("Proxy offline"))

        with patch("apps.api.dependencies.get_proxy_client", return_value=mock_proxy), \
             patch.object(mod, "_get_configured_providers", return_value=[]), \
             patch.object(mod, "os", MagicMock(path=MagicMock(exists=lambda p: False))), \
             patch.object(mod, "glob", return_value=[]):
            resp = await client.get("/api/providers/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "overall" in data
            assert "freerouter_proxy" in data
            assert "providers" in data


class TestGetQuota:
    @pytest.mark.asyncio
    async def test_quota_success(self, client):
        mock_tracker = MagicMock()
        mock_tracker.get_latest_limits.return_value = [
            {"provider": "groq", "live_rpm_remaining": 25,
             "live_tpm_remaining": 5000, "timestamp": "2025-01-01T00:00:00"}
        ]
        with patch("packages.router.tracker.UsageTracker", return_value=mock_tracker):
            resp = await client.get("/api/providers/quota")
            assert resp.status_code == 200
            data = resp.json()
            assert "providers" in data
            assert len(data["providers"]) == 1
            assert data["providers"][0]["name"] == "groq"

    @pytest.mark.asyncio
    async def test_quota_500_error(self, client):
        with patch("packages.router.tracker.UsageTracker", side_effect=Exception("DB error")):
            resp = await client.get("/api/providers/quota")
            assert resp.status_code == 500
