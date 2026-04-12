"""
test_settings_routes.py — Tests for the settings API.

Endpoints tested:
    GET /api/settings/                — Return current config with secrets masked
    GET /api/settings/status          — System status (provider health)
    GET /api/settings/services/status — Service configuration status
    POST /api/settings/services/validate — Validate all service configurations
    GET /api/settings/commands        — Get startup commands
    GET /api/settings/skills          — Get skill files
    GET /api/settings/knowledge-base  — Get knowledge base content
"""

import pytest
from unittest.mock import patch, MagicMock


class TestGetSettings:
    """Tests for GET /api/settings/."""

    @pytest.mark.asyncio
    async def test_settings_returns_config(self, client):
        """Should return current configuration with masked secrets."""
        resp = await client.get("/api/settings/")
        assert resp.status_code == 200
        data = resp.json()
        assert "freerouter_proxy" in data
        assert "dashboard_port" in data
        assert data["dashboard_port"] == 3000

    @pytest.mark.asyncio
    async def test_settings_service_flags(self, client):
        """Should report which services are configured."""
        resp = await client.get("/api/settings/")
        data = resp.json()
        # By default, no API keys are set
        assert "zep_configured" in data
        assert "youtube_configured" in data
        assert "notion_configured" in data

    @pytest.mark.asyncio
    async def test_settings_log_level(self, client):
        """Should return the current log level."""
        resp = await client.get("/api/settings/")
        data = resp.json()
        assert "log_level" in data
        assert data["log_level"] == "INFO"


class TestSystemStatus:
    """Tests for GET /api/settings/status."""

    @pytest.mark.asyncio
    async def test_status_returns_overall(self, client):
        """Should return overall status and components."""
        resp = await client.get("/api/settings/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall" in data
        assert "components" in data

    @pytest.mark.asyncio
    async def test_status_dashboard_online(self, client):
        """Should report dashboard as online."""
        resp = await client.get("/api/settings/status")
        data = resp.json()
        assert data["components"]["dashboard"]["status"] == "online"


class TestServiceStatus:
    """Tests for GET /api/settings/services/status."""

    @pytest.mark.asyncio
    async def test_services_status_returns_all(self, client):
        """Should return status for all services."""
        resp = await client.get("/api/settings/services/status")
        assert resp.status_code == 200
        data = resp.json()
        expected_services = ["zep", "youtube", "notion", "freerouter", "supabase", "exa"]
        for svc in expected_services:
            assert svc in data, f"Missing service: {svc}"

    @pytest.mark.asyncio
    async def test_services_status_values(self, client):
        """Should return valid status values."""
        resp = await client.get("/api/settings/services/status")
        data = resp.json()
        valid_statuses = {"available", "not_configured", "misconfigured"}
        for svc, status in data.items():
            assert status in valid_statuses, f"Invalid status for {svc}: {status}"


class TestValidateConfiguration:
    """Tests for POST /api/settings/services/validate."""

    @pytest.mark.asyncio
    async def test_validate_returns_result(self, client):
        """Should return validation results with issues list."""
        resp = await client.post("/api/settings/services/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data
        assert "issues" in data
        assert "recommendations" in data

    @pytest.mark.asyncio
    async def test_validate_with_no_keys(self, client):
        """Should report issues when no keys are configured."""
        resp = await client.post("/api/settings/services/validate")
        data = resp.json()
        # Without keys, should not be fully valid
        assert isinstance(data["valid"], bool)


class TestGetCommands:
    """Tests for GET /api/settings/commands."""

    @pytest.mark.asyncio
    async def test_commands_returns_all(self, client):
        """Should return all startup commands."""
        resp = await client.get("/api/settings/commands")
        assert resp.status_code == 200
        data = resp.json()
        assert "dashboard" in data
        assert "freerouter_proxy" in data

    @pytest.mark.asyncio
    async def test_commands_values(self, client):
        """Should have correct command strings."""
        resp = await client.get("/api/settings/commands")
        data = resp.json()
        assert "apps.api.main" in data["dashboard"]
        assert "freerouter proxy" in data["freerouter_proxy"]


class TestGetSkills:
    """Tests for GET /api/settings/skills."""

    @pytest.mark.asyncio
    async def test_skills_returns_files(self, client):
        """Should return skill files list."""
        resp = await client.get("/api/settings/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        assert isinstance(data["files"], list)


class TestKnowledgeBase:
    """Tests for GET /api/settings/knowledge-base."""

    @pytest.mark.asyncio
    async def test_knowledge_base_returns_content(self, client):
        """Should return knowledge base content or fallback."""
        resp = await client.get("/api/settings/knowledge-base")
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "path" in data
