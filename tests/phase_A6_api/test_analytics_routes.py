"""
test_analytics_routes.py — Tests for the YouTube analytics API.

Endpoints tested:
    GET  /api/analytics/channel      — Get channel stats
    GET  /api/analytics/videos       — Get recent videos
    GET  /api/analytics/competitors  — Get competitor videos
    POST /api/analytics/repurpose    — Repurpose a competitor video
    POST /api/analytics/snapshot     — Save analytics snapshot
    GET  /api/analytics/snapshots    — List snapshots
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mod():
    key = "apps.api.routers.analytics_routes"
    if key not in sys.modules:
        __import__(key)
    return sys.modules[key]


class TestGetChannelStats:
    @pytest.mark.asyncio
    async def test_channel_stats_no_key(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = ""
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/channel")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_channel_stats_no_client(self, client):
        mod = _mod()
        with patch("apps.api.dependencies.get_youtube_client", return_value=None), \
             patch.object(mod, "get_youtube_client", return_value=None):
            resp = await client.get("/api/analytics/channel")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_channel_stats_with_id(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = "test-key"
        mock_client.get_channel_stats.return_value = {"subscriber_count": 1000}
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/channel?channel_id=UC123")
            assert resp.status_code == 200
            assert resp.json()["subscriber_count"] == 1000

    @pytest.mark.asyncio
    async def test_channel_stats_no_channel_id(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = "test-key"
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/channel")
            assert resp.status_code == 200
            assert resp.json()["subscriber_count"] == 0


class TestGetRecentVideos:
    @pytest.mark.asyncio
    async def test_videos_no_key(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = ""
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/videos")
            assert resp.status_code == 200
            assert resp.json() == []

    @pytest.mark.asyncio
    async def test_videos_with_channel(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = "test-key"
        mock_client.get_recent_videos.return_value = [{"title": "Video 1"}]
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/videos?channel_id=UC123")
            assert resp.status_code == 200
            assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_videos_no_channel(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = "test-key"
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/videos")
            assert resp.status_code == 200
            assert resp.json() == []

    @pytest.mark.asyncio
    async def test_videos_limit_param(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = "test-key"
        mock_client.get_recent_videos.return_value = []
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/videos?channel_id=UC123&limit=5")
            assert resp.status_code == 200


class TestGetCompetitors:
    @pytest.mark.asyncio
    async def test_competitors_no_key(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = ""
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/competitors")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_competitors_returns_videos(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = "test-key"
        mock_client.get_competitor_videos.return_value = [{"title": "Competitor Video 1"}]
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/competitors")
            assert resp.status_code == 200
            assert "videos" in resp.json()

    @pytest.mark.asyncio
    async def test_competitors_limit_param(self, client):
        mod = _mod()
        mock_client = MagicMock()
        mock_client.api_key = "test-key"
        mock_client.get_competitor_videos.return_value = []
        with patch.object(mod, "get_youtube_client", return_value=mock_client):
            resp = await client.get("/api/analytics/competitors?limit=5")
            assert resp.status_code == 200


class TestRepurposeVideo:
    @pytest.mark.asyncio
    async def test_repurpose_success(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.insert.return_value.execute.return_value.data = [{"id": "new-card-id"}]
        mod = _mod()
        with patch.object(mod, "get_supabase", return_value=mock_sb):
            resp = await client.post("/api/analytics/repurpose", json={
                "title": "Competitor's Great Video", "video_id": "abc123",
                "channel": "SomeChannel", "views": 100000,
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "created"

    @pytest.mark.asyncio
    async def test_repurpose_no_data(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        # Configure the insert chain to return None data
        insert_mock = MagicMock()
        insert_mock.execute.return_value.data = None
        mock_table.insert.return_value = insert_mock
        # Patch at the router module level (analytics_routes has module-level import)
        mod = _mod()
        with patch.object(mod, "get_supabase", return_value=mock_sb):
            resp = await client.post("/api/analytics/repurpose", json={
                "title": "Test", "video_id": "abc", "channel": "Ch", "views": 100,
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "error"

    @pytest.mark.asyncio
    async def test_repurpose_supabase_error(self, client):
        mod = _mod()
        # Patch at the router module level (analytics_routes has module-level import)
        with patch.object(mod, "get_supabase", side_effect=Exception("Not configured")):
            resp = await client.post("/api/analytics/repurpose", json={
                "title": "Test", "video_id": "abc", "channel": "Ch", "views": 100,
            })
            assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_repurpose_422_missing_fields(self, client):
        resp = await client.post("/api/analytics/repurpose", json={"title": "Test"})
        assert resp.status_code == 422


class TestSaveSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_success(self, client):
        mock_tracker = MagicMock()
        mock_tracker.pull_weekly_stats.return_value = {"views": 100}
        mock_tracker.save_snapshot.return_value = "packages/data/analytics/2025-01-15.json"
        with patch("packages.integrations.youtube.analytics.AnalyticsTracker", return_value=mock_tracker):
            resp = await client.post("/api/analytics/snapshot?channel_id=UC123")
            assert resp.status_code == 200
            assert resp.json()["status"] == "saved"

    @pytest.mark.asyncio
    async def test_snapshot_error(self, client):
        with patch("packages.integrations.youtube.analytics.AnalyticsTracker", side_effect=Exception("Import error")):
            resp = await client.post("/api/analytics/snapshot")
            assert resp.status_code == 500


class TestListSnapshots:
    @pytest.mark.asyncio
    async def test_snapshots_empty(self, client):
        with patch("glob.glob", return_value=[]):
            resp = await client.get("/api/analytics/snapshots")
            assert resp.status_code == 200
            assert resp.json() == []

    @pytest.mark.asyncio
    async def test_snapshots_returns_list(self, client):
        with patch("glob.glob", return_value=[
            "packages/data/analytics/2025-01-15.json",
            "packages/data/analytics/2025-01-14.json",
        ]):
            resp = await client.get("/api/analytics/snapshots")
            assert resp.status_code == 200
            assert len(resp.json()) == 2
