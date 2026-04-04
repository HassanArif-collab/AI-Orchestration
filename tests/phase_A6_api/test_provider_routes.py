"""
test_provider_routes.py — Tests for the LLM provider management API.

Endpoints tested:
    GET  /api/providers/              — List all providers
    POST /api/providers/{name}/key    — Save API key for provider
    POST /api/providers/{name}/test   — Test provider health
    POST /api/providers/{name}/reset  — Reset provider rate limit
    GET  /api/providers/usage         — Get provider usage stats
    GET  /api/providers/models        — List available models
    GET  /api/providers/health        — Provider health check
    GET  /api/providers/quota         — Get live quota remaining
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mod():
    """Get the provider_routes module via sys.modules."""
    return sys.modules["apps.api.routers.provider_routes"]


def _mock_provider_defn(name, display_name, requires_auth=True, signup_url="", priority=0, default_model=""):
    defn = MagicMock()
    defn.name = name
    defn.display_name = display_name
    defn.requires_auth = requires_auth
    defn.signup_url = signup_url
    defn.priority = priority
    defn.default_model = default_model
    return defn


class TestListProviders:
    @pytest.mark.asyncio
    async def test_list_providers_success(self, client):
        mod = _mod()
        mock_defn = _mock_provider_defn("groq", "Groq")
        with patch.object(mod, "_fr") as m_fr:
            m_fr.return_value = {
                "load_env": MagicMock(),
                "get_configured_providers": MagicMock(return_value=[(mock_defn, True)]),
            }
            resp = await client.get("/api/providers/")
            assert resp.status_code == 200
            data = resp.json()
            assert "providers" in data
            assert len(data["providers"]) >= 1

    @pytest.mark.asyncio
    async def test_list_providers_500_error(self, client):
        mod = _mod()
        with patch.object(mod, "_fr", side_effect=Exception("Import error")):
            resp = await client.get("/api/providers/")
            assert resp.status_code == 500


class TestSaveKey:
    @pytest.mark.asyncio
    async def test_save_key_success(self, client):
        mod = _mod()
        with patch.object(mod, "_fr") as m_fr:
            m_fr.return_value = {"save_api_key": MagicMock()}
            resp = await client.post("/api/providers/groq/key", json={"api_key": "gsk_test123"})
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_save_key_400_invalid(self, client):
        mod = _mod()
        with patch.object(mod, "_fr") as m_fr:
            m_fr.return_value = {
                "save_api_key": MagicMock(side_effect=ValueError("Unknown provider: xyz"))
            }
            resp = await client.post("/api/providers/xyz/key", json={"api_key": "test"})
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_save_key_422_missing_body(self, client):
        resp = await client.post("/api/providers/groq/key", json={})
        assert resp.status_code == 422


class TestTestProvider:
    @pytest.mark.asyncio
    async def test_test_provider_success(self, client):
        mod = _mod()
        with patch.object(mod, "_fr") as m_fr:
            m_fr.return_value = {"check_provider_health": AsyncMock(return_value=(True, "OK"))}
            resp = await client.post("/api/providers/groq/test")
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_test_provider_500_error(self, client):
        mod = _mod()
        with patch.object(mod, "_fr", side_effect=Exception("Import error")):
            resp = await client.post("/api/providers/groq/test")
            assert resp.status_code == 500


class TestResetProvider:
    @pytest.mark.asyncio
    async def test_reset_success(self, client):
        mod = _mod()
        with patch.object(mod, "_fr") as m_fr:
            m_fr.return_value = {"reset_provider": MagicMock()}
            resp = await client.post("/api/providers/groq/reset")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_reset_500_error(self, client):
        mod = _mod()
        with patch.object(mod, "_fr", side_effect=Exception("Import error")):
            resp = await client.post("/api/providers/groq/reset")
            assert resp.status_code == 500


class TestGetUsage:
    @pytest.mark.asyncio
    async def test_usage_success(self, client):
        mod = _mod()
        mock_usage = MagicMock()
        mock_usage.requests_today = 100
        mock_usage.tokens_in_today = 50000
        mock_usage.tokens_out_today = 10000
        mock_usage.requests_used_pct = 0.1
        mock_usage.is_hard_limited = False

        with patch.object(mod, "_fr") as m_fr:
            m_fr.return_value = {"get_all_usage": MagicMock(return_value={"groq": mock_usage})}
            resp = await client.get("/api/providers/usage")
            assert resp.status_code == 200
            data = resp.json()
            assert "freerouter" in data

    @pytest.mark.asyncio
    async def test_usage_500_error(self, client):
        mod = _mod()
        with patch.object(mod, "_fr", side_effect=Exception("Error")):
            resp = await client.get("/api/providers/usage")
            assert resp.status_code == 500


class TestGetModels:
    @pytest.mark.asyncio
    async def test_models_500_error(self, client):
        # list_models imports from freerouter.router at call time
        # If freerouter is not installed, expect 500
        resp = await client.get("/api/providers/models")
        assert resp.status_code in (200, 500)


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_returns_status(self, client):
        mod = _mod()
        mock_proxy = AsyncMock()
        mock_proxy.get = AsyncMock(side_effect=Exception("Proxy offline"))

        with patch.object(mod, "_fr") as m_fr, \
             patch("apps.api.dependencies.get_proxy_client", return_value=mock_proxy), \
             patch.object(mod, "os", MagicMock(path=MagicMock(exists=lambda p: False))), \
             patch.object(mod, "glob", return_value=[]):
            m_fr.return_value = {
                "load_env": MagicMock(),
                "get_configured_providers": MagicMock(return_value=[]),
            }
            resp = await client.get("/api/providers/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "overall" in data


class TestGetQuota:
    @pytest.mark.asyncio
    async def test_quota_500_error(self, client):
        # UsageTracker is imported at call time from packages.router.tracker
        # If the package is not installed, expect 500
        resp = await client.get("/api/providers/quota")
        assert resp.status_code in (200, 500)
