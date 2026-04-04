"""
test_visual_routes.py — Tests for the visual asset management API.

Endpoints tested:
    GET /api/visual/manifests              — List asset manifests
    GET /api/visual/radiant/shaders        — List radiant shaders
    GET /api/visual/radiant/preview/{name} — Preview a shader
    GET /api/visual/radiant/moods          — List mood-to-shader mappings
    GET /api/visual/remotion/compositions  — List Remotion compositions
    GET /api/visual/remotion/templates     — List Remotion templates
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def _mod():
    """Get the visual_routes module via sys.modules."""
    return sys.modules["apps.api.routers.visual_routes"]


class TestListManifests:
    """Tests for GET /api/visual/manifests."""

    @pytest.mark.asyncio
    async def test_manifests_empty(self, client):
        mod = _mod()
        with patch.object(mod, "glob", return_value=[]):
            resp = await client.get("/api/visual/manifests")
            assert resp.status_code == 200
            assert resp.json() == []

    @pytest.mark.asyncio
    async def test_manifests_returns_data(self, client):
        mod = _mod()
        mock_manifest = MagicMock()
        mock_manifest.video_title = "Test Video"
        mock_manifest.summary.return_value = {"total_assets": 5}
        mock_asset_cls = MagicMock()
        mock_asset_cls.load.return_value = mock_manifest

        # Patch glob.glob (the function), not the module
        with patch("glob.glob", return_value=["test.manifest.json"]), \
             patch("packages.visual.manifest.AssetManifest", mock_asset_cls):
            resp = await client.get("/api/visual/manifests")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["video_title"] == "Test Video"

    @pytest.mark.asyncio
    async def test_manifests_skips_invalid(self, client):
        mod = _mod()
        with patch.object(mod, "glob", return_value=["bad.manifest.json"]):
            resp = await client.get("/api/visual/manifests")
            assert resp.status_code == 200
            assert resp.json() == []


class TestListShaders:
    """Tests for GET /api/visual/radiant/shaders."""

    @pytest.mark.asyncio
    async def test_shaders_no_manager(self, client):
        mod = _mod()
        with patch.object(mod, "get_radiant_manager", return_value=None):
            resp = await client.get("/api/visual/radiant/shaders")
            assert resp.status_code == 200
            assert resp.json() == []

    @pytest.mark.asyncio
    async def test_shaders_returns_list(self, client):
        mod = _mod()
        mock_mgr = MagicMock()
        mock_mgr.list_shaders.return_value = [
            {"name": "dark_wave", "path": "/data/shaders/dark_wave.html"},
        ]
        with patch.object(mod, "get_radiant_manager", return_value=mock_mgr):
            resp = await client.get("/api/visual/radiant/shaders")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "dark_wave"
            assert "tags" in data[0]

    @pytest.mark.asyncio
    async def test_shaders_empty(self, client):
        mod = _mod()
        mock_mgr = MagicMock()
        mock_mgr.list_shaders.return_value = []
        with patch.object(mod, "get_radiant_manager", return_value=mock_mgr):
            resp = await client.get("/api/visual/radiant/shaders")
            assert resp.status_code == 200
            assert resp.json() == []


class TestPreviewShader:
    """Tests for GET /api/visual/radiant/preview/{shader_name}."""

    @pytest.mark.asyncio
    async def test_preview_404_not_found(self, auth_client):
        mod = _mod()
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path.resolve.return_value = mock_path
        mock_path.__truediv__ = MagicMock(return_value=mock_path)

        original_base = mod.SHADER_BASE_DIR
        try:
            mod.SHADER_BASE_DIR = Path("/fake/shaders")
            resp = await auth_client.get("/api/visual/radiant/preview/test_shader")
            assert resp.status_code == 404
        finally:
            mod.SHADER_BASE_DIR = original_base

    @pytest.mark.asyncio
    async def test_preview_400_invalid_name(self, client):
        # FastAPI Path regex validation rejects special chars
        resp = await client.get("/api/visual/radiant/preview/invalid<name>")
        assert resp.status_code in (404, 422, 307)


class TestListMoods:
    """Tests for GET /api/visual/radiant/moods."""

    @pytest.mark.asyncio
    async def test_moods_returns_mappings(self, client):
        resp = await client.get("/api/visual/radiant/moods")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


class TestListCompositions:
    """Tests for GET /api/visual/remotion/compositions."""

    @pytest.mark.asyncio
    async def test_compositions_not_scaffolded(self, client):
        # Patch only os.path.exists, not the entire os module
        with patch("os.path.exists", return_value=False):
            resp = await client.get("/api/visual/remotion/compositions")
            assert resp.status_code == 200
            data = resp.json()
            assert "error" in data

    @pytest.mark.asyncio
    async def test_compositions_returns_list(self, client):
        mod = _mod()
        # Patch only os.path.exists, not the entire os module
        with patch("os.path.exists", return_value=True), \
             patch("glob.glob", return_value=["visual-engine/src/compositions/bar_chart.tsx"]):
            resp = await client.get("/api/visual/remotion/compositions")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "bar_chart"


class TestListTemplates:
    """Tests for GET /api/visual/remotion/templates."""

    @pytest.mark.asyncio
    async def test_templates_returns_list(self, client):
        resp = await client.get("/api/visual/remotion/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert "bar_chart" in data
        assert len(data) == 7
