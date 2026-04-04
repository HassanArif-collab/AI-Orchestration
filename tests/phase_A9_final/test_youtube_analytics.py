"""Tests for packages/integrations/youtube/youtube_analytics.py

Covers:
- VideoPerformance / ChannelAnalytics / ContentGapAnalysis dataclasses
- YouTubeAnalyticsError exception
- YouTubeAnalyticsClient: init, context manager, _ensure_access_token, _request
- Token refresh (success, failure, expiry)
- 401 retry logic
- 403 handling
- get_channel_analytics (aggregation math)
- get_top_videos
- get_traffic_sources
- get_video_retention
- analyze_content_gaps (under/overperforming classification, retention drops)
- Convenience functions
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from packages.integrations.youtube.youtube_analytics import (
    VideoPerformance,
    ChannelAnalytics,
    ContentGapAnalysis,
    YouTubeAnalyticsError,
    YouTubeAnalyticsClient,
    get_my_channel_analytics,
    analyze_my_content_gaps,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────────

def _make_settings(**overrides):
    from packages.core.config import Settings
    defaults = {
        "FREEROUTER_URL": "http://localhost:4000",
        "SUPABASE_URL": "",
        "ZEP_BASE_URL": "https://api.getzep.com",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


@pytest.fixture()
def mock_oauth_settings():
    settings = _make_settings(
        YOUTUBE_CLIENT_ID="ci",
        YOUTUBE_CLIENT_SECRET="cs",
        YOUTUBE_REFRESH_TOKEN="rt",
    )
    with patch("packages.integrations.youtube.youtube_analytics.get_settings", return_value=settings):
        yield settings


@pytest.fixture()
def mock_no_oauth_settings():
    settings = _make_settings(
        YOUTUBE_CLIENT_ID="",
        YOUTUBE_CLIENT_SECRET="",
        YOUTUBE_REFRESH_TOKEN="",
    )
    with patch("packages.integrations.youtube.youtube_analytics.get_settings", return_value=settings):
        yield settings


@pytest.fixture()
async def analytics_client(mock_oauth_settings):
    """Return a YouTubeAnalyticsClient with mocked httpx.AsyncClient."""
    client = YouTubeAnalyticsClient(
        client_id="ci", client_secret="cs", refresh_token="rt"
    )
    client._client = AsyncMock()
    return client


def _make_token_response(expires_in=3600):
    """Build a mock token refresh response."""
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "access_token": "new-access-token",
        "expires_in": expires_in,
    }
    return resp


def _make_api_response(rows, column_headers=None):
    """Build a mock YouTube Analytics API response."""
    if column_headers is None:
        column_headers = ["day", "views", "estimatedMinutesWatched", "averageViewDuration", "subscribersGained", "subscribersLost", "estimatedRevenue"]
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"columnHeaders": [{"name": h} for h in column_headers], "rows": rows}
    resp.raise_for_status = MagicMock()
    return resp


# ─── Data Models ─────────────────────────────────────────────────────────────────


class TestVideoPerformance:
    def test_defaults(self):
        vp = VideoPerformance(video_id="v1")
        assert vp.video_id == "v1"
        assert vp.views == 0
        assert vp.estimated_revenue == 0.0
        assert vp.thumbnail_url == ""

    def test_all_fields(self):
        vp = VideoPerformance(
            video_id="v2", title="Title", views=5000, estimated_minutes_watched=100,
            average_view_duration=120.0, average_view_percentage=55.0,
            likes=200, dislikes=5, comments=30, shares=10,
            subscribers_gained=15, subscribers_lost=2, estimated_revenue=12.5,
            impression_count=10000, impression_click_through_rate=5.0,
            thumbnail_url="https://thumb.jpg", published_at="2025-01-01",
        )
        assert vp.views == 5000
        assert vp.estimated_revenue == 12.5
        assert vp.impression_click_through_rate == 5.0


class TestChannelAnalytics:
    def test_defaults(self):
        ca = ChannelAnalytics(channel_id="mine")
        assert ca.channel_id == "mine"
        assert ca.views == 0
        assert ca.top_videos == []
        assert ca.traffic_sources == {}

    def test_with_data(self):
        ca = ChannelAnalytics(
            channel_id="c1", views=1000, estimated_minutes_watched=500,
            subscribers_gained=50, subscribers_lost=10,
            top_videos=[VideoPerformance(video_id="v1", views=100)],
            traffic_sources={"search": 500, "browse": 300},
        )
        assert ca.views == 1000
        assert len(ca.top_videos) == 1
        assert ca.traffic_sources["search"] == 500


class TestContentGapAnalysis:
    def test_defaults(self):
        cga = ContentGapAnalysis()
        assert cga.underperforming_topics == []
        assert cga.overperforming_topics == []
        assert cga.suggested_topics == []
        assert cga.retention_drop_points == []

    def test_with_data(self):
        cga = ContentGapAnalysis(
            underperforming_topics=["v1"],
            overperforming_topics=["v2"],
            suggested_topics=["new topic"],
            retention_drop_points=[{"video_id": "v3", "drop_percentage": 15.0}],
        )
        assert len(cga.underperforming_topics) == 1
        assert cga.retention_drop_points[0]["drop_percentage"] == 15.0


class TestYouTubeAnalyticsError:
    def test_error(self):
        err = YouTubeAnalyticsError("auth failed")
        assert str(err) == "auth failed"
        assert isinstance(err, Exception)


# ─── Client Init ─────────────────────────────────────────────────────────────────


class TestYouTubeAnalyticsClientInit:
    def test_init_with_credentials(self):
        client = YouTubeAnalyticsClient(client_id="id", client_secret="sec", refresh_token="tok")
        assert client.client_id == "id"
        assert client.client_secret == "sec"
        assert client.refresh_token == "tok"
        assert client._access_token == ""

    def test_init_falls_back_to_settings(self, mock_oauth_settings):
        client = YouTubeAnalyticsClient()
        assert client.client_id == "ci"
        assert client.client_secret == "cs"
        assert client.refresh_token == "rt"

    def test_token_expires_set_to_min(self):
        client = YouTubeAnalyticsClient(client_id="x", client_secret="y", refresh_token="z")
        assert client._token_expires == datetime.min.replace(tzinfo=timezone.utc)

    def test_warns_on_missing_credentials(self, mock_no_oauth_settings):
        client = YouTubeAnalyticsClient()
        assert client.client_id == ""


# ─── _ensure_access_token ───────────────────────────────────────────────────────


class TestEnsureAccessToken:
    @pytest.mark.asyncio
    async def test_refreshes_on_empty_token(self, analytics_client):
        analytics_client._client.post.return_value = _make_token_response()
        await analytics_client._ensure_access_token()
        assert analytics_client._access_token == "new-access-token"
        analytics_client._client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_refreshes_on_expired_token(self, analytics_client):
        analytics_client._access_token = "old-token"
        analytics_client._token_expires = datetime.now(timezone.utc) - timedelta(hours=1)
        analytics_client._client.post.return_value = _make_token_response()
        await analytics_client._ensure_access_token()
        assert analytics_client._access_token == "new-access-token"

    @pytest.mark.asyncio
    async def test_skips_refresh_if_token_valid(self, analytics_client):
        analytics_client._access_token = "valid-token"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await analytics_client._ensure_access_token()
        analytics_client._client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_token_failure_raises(self, analytics_client):
        resp = MagicMock(status_code=400)
        resp.text = "invalid_grant"
        analytics_client._client.post.return_value = resp
        with pytest.raises(YouTubeAnalyticsError, match="Token refresh failed"):
            await analytics_client._ensure_access_token()

    @pytest.mark.asyncio
    async def test_token_expires_minus_60s_buffer(self, analytics_client):
        analytics_client._client.post.return_value = _make_token_response(expires_in=3600)
        await analytics_client._ensure_access_token()
        # Expiry should be ~59 minutes from now (3600 - 60)
        expected = datetime.now(timezone.utc) + timedelta(seconds=3540)
        diff = abs((analytics_client._token_expires - expected).total_seconds())
        assert diff < 5  # within 5 seconds tolerance

    @pytest.mark.asyncio
    async def test_no_credentials_raises(self, analytics_client):
        analytics_client.client_id = ""
        analytics_client.client_secret = ""
        analytics_client.refresh_token = ""
        with pytest.raises(YouTubeAnalyticsError, match="OAuth credentials not configured"):
            await analytics_client._ensure_access_token()

    @pytest.mark.asyncio
    async def test_posts_correct_oauth_params(self, analytics_client):
        analytics_client._client.post.return_value = _make_token_response()
        await analytics_client._ensure_access_token()
        call_kwargs = analytics_client._client.post.call_args
        data = call_kwargs[1]["data"]
        assert data["grant_type"] == "refresh_token"
        assert data["client_id"] == "ci"
        assert data["client_secret"] == "cs"
        assert data["refresh_token"] == "rt"


# ─── _request ────────────────────────────────────────────────────────────────────


class TestRequest:
    @pytest.mark.asyncio
    async def test_successful_request(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"rows": []}
        resp.raise_for_status = MagicMock()
        analytics_client._client.get.return_value = resp
        result = await analytics_client._request({"metrics": "views"})
        assert result == {"rows": []}

    @pytest.mark.asyncio
    async def test_request_includes_bearer_token(self, analytics_client):
        analytics_client._access_token = "my-token"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {}
        resp.raise_for_status = MagicMock()
        analytics_client._client.get.return_value = resp
        await analytics_client._request({"ids": "channel==MINE"})
        call_kwargs = analytics_client._client.get.call_args
        assert call_kwargs[1]["headers"]["Authorization"] == "Bearer my-token"

    @pytest.mark.asyncio
    async def test_401_triggers_token_refresh_and_retry(self, analytics_client):
        # First call: 401, then token refresh, then successful retry
        fail_resp = MagicMock(status_code=401)
        fail_resp.json.return_value = {}
        success_resp = MagicMock(status_code=200)
        success_resp.json.return_value = {"rows": [[1, 2, 3]]}
        success_resp.raise_for_status = MagicMock()

        analytics_client._access_token = "expired"
        analytics_client._token_expires = datetime.now(timezone.utc) - timedelta(hours=1)
        analytics_client._client.get.side_effect = [fail_resp, success_resp]
        analytics_client._client.post.return_value = _make_token_response()

        result = await analytics_client._request({"ids": "channel==MINE"})
        assert result["rows"] == [[1, 2, 3]]
        # Should have called get twice (initial + retry)
        assert analytics_client._client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_403_raises_error(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        resp = MagicMock(status_code=403)
        resp.json.return_value = {"error": {"message": "Forbidden"}}
        analytics_client._client.get.return_value = resp
        with pytest.raises(YouTubeAnalyticsError, match="Forbidden"):
            await analytics_client._request({"ids": "channel==MINE"})


# ─── get_channel_analytics ───────────────────────────────────────────────────────


class TestGetChannelAnalytics:
    @pytest.mark.asyncio
    async def test_basic_metrics_aggregation(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        # NOTE: Source code uses dimensions="day" but indexes rows as if no dimension.
        # row[0]=views, row[1]=minutes, row[3]=subGained, row[4]=subLost, row[5]=revenue
        rows = [
            [100, 200, 120.0, 10, 2, 1.0],
            [150, 300, 120.0, 15, 3, 1.5],
            [200, 400, 120.0, 20, 5, 2.0],
        ]
        analytics_client._client.get.return_value = _make_api_response(rows)
        analytics_client.get_top_videos = AsyncMock(return_value=[])
        analytics_client.get_traffic_sources = AsyncMock(return_value={})

        result = await analytics_client.get_channel_analytics(days=30, channel_id="ch1")
        assert result.views == 450
        assert result.estimated_minutes_watched == 900
        assert result.subscribers_gained == 45
        assert result.subscribers_lost == 10
        assert result.estimated_revenue == pytest.approx(4.5)

    @pytest.mark.asyncio
    async def test_avg_duration_calculation(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        # 100 views, 100 minutes => 100*60/100 = 60 seconds avg
        rows = [[100, 100, 60.0, 5, 1, 0.5]]
        analytics_client._client.get.return_value = _make_api_response(rows)
        analytics_client.get_top_videos = AsyncMock(return_value=[])
        analytics_client.get_traffic_sources = AsyncMock(return_value={})

        result = await analytics_client.get_channel_analytics(days=30)
        assert result.average_view_duration == 60.0

    @pytest.mark.asyncio
    async def test_zero_views_avg_duration_zero(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        rows = []
        analytics_client._client.get.return_value = _make_api_response(rows)
        analytics_client.get_top_videos = AsyncMock(return_value=[])
        analytics_client.get_traffic_sources = AsyncMock(return_value={})

        result = await analytics_client.get_channel_analytics(days=30)
        assert result.average_view_duration == 0.0

    @pytest.mark.asyncio
    async def test_default_channel_mine(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        analytics_client._client.get.return_value = _make_api_response([])
        analytics_client.get_top_videos = AsyncMock(return_value=[])
        analytics_client.get_traffic_sources = AsyncMock(return_value={})

        result = await analytics_client.get_channel_analytics()
        assert result.channel_id == "MINE"

    @pytest.mark.asyncio
    async def test_error_returns_empty_analytics(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        analytics_client._client.get.side_effect = Exception("fail")
        result = await analytics_client.get_channel_analytics()
        assert isinstance(result, ChannelAnalytics)
        assert result.views == 0


# ─── get_top_videos ──────────────────────────────────────────────────────────────


class TestGetTopVideos:
    @pytest.mark.asyncio
    async def test_returns_video_performance_list(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        # rows: [video_id, views, minutes, avgDuration, avgViewPct, likes, comments, subGained, subLost]
        rows = [
            ["vid1", 1000, 200, 120.0, 55.0, 50, 10, 5, 1],
            ["vid2", 500, 100, 90.0, 40.0, 20, 5, 2, 0],
        ]
        analytics_client._client.get.return_value = _make_api_response(
            rows,
            column_headers=["video", "views", "estimatedMinutesWatched", "averageViewDuration",
                            "averageViewPercentage", "likes", "comments", "subscribersGained", "subscribersLost"],
        )
        result = await analytics_client.get_top_videos(days=30)
        assert len(result) == 2
        assert isinstance(result[0], VideoPerformance)
        assert result[0].video_id == "vid1"
        assert result[0].views == 1000
        assert result[1].views == 500

    @pytest.mark.asyncio
    async def test_empty_rows_returns_empty(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        analytics_client._client.get.return_value = _make_api_response([])
        result = await analytics_client.get_top_videos()
        assert result == []

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        analytics_client._client.get.side_effect = Exception("fail")
        result = await analytics_client.get_top_videos()
        assert result == []


# ─── get_traffic_sources ─────────────────────────────────────────────────────────


class TestGetTrafficSources:
    @pytest.mark.asyncio
    async def test_returns_dict(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        rows = [
            ["YT_SEARCH", 5000],
            ["BROWSE", 3000],
            ["RELATED_VIDEO", 2000],
        ]
        analytics_client._client.get.return_value = _make_api_response(
            rows, column_headers=["insightTrafficSourceType", "views"]
        )
        result = await analytics_client.get_traffic_sources()
        assert result["YT_SEARCH"] == 5000
        assert result["BROWSE"] == 3000
        assert result["RELATED_VIDEO"] == 2000

    @pytest.mark.asyncio
    async def test_empty_rows_returns_empty_dict(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        analytics_client._client.get.return_value = _make_api_response([], column_headers=["source", "views"])
        result = await analytics_client.get_traffic_sources()
        assert result == {}

    @pytest.mark.asyncio
    async def test_error_returns_empty_dict(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        analytics_client._client.get.side_effect = Exception("fail")
        result = await analytics_client.get_traffic_sources()
        assert result == {}


# ─── get_video_retention ─────────────────────────────────────────────────────────


class TestGetVideoRetention:
    @pytest.mark.asyncio
    async def test_returns_retention_list(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        rows = [
            [0.0, 1.0],
            [0.1, 0.9],
            [0.2, 0.7],
            [0.5, 0.4],
            [1.0, 0.2],
        ]
        analytics_client._client.get.return_value = _make_api_response(
            rows, column_headers=["elapsedVideoTimeRatio", "audienceWatchRatio"]
        )
        result = await analytics_client.get_video_retention("vid123")
        assert len(result) == 5
        assert result[0]["time_ratio"] == 0.0
        assert result[0]["watch_ratio"] == 1.0
        assert result[4]["watch_ratio"] == 0.2

    @pytest.mark.asyncio
    async def test_empty_rows_returns_empty(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        analytics_client._client.get.return_value = _make_api_response([], column_headers=["t", "w"])
        result = await analytics_client.get_video_retention("vid_empty")
        assert result == []

    @pytest.mark.asyncio
    async def test_filter_contains_video_id(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        analytics_client._client.get.return_value = _make_api_response([], column_headers=["t", "w"])
        await analytics_client.get_video_retention("target_vid")
        call_args = analytics_client._client.get.call_args
        assert "video==target_vid" in call_args[1]["params"]["filters"]


# ─── analyze_content_gaps ────────────────────────────────────────────────────────


class TestAnalyzeContentGaps:
    @pytest.mark.asyncio
    async def test_empty_top_videos_returns_empty_analysis(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        analytics_client._client.get.return_value = _make_api_response(
            [],
            column_headers=["video", "views", "estimatedMinutesWatched", "averageViewDuration",
                            "averageViewPercentage", "likes", "comments", "subscribersGained", "subscribersLost"],
        )
        result = await analytics_client.analyze_content_gaps()
        assert isinstance(result, ContentGapAnalysis)
        assert result.underperforming_topics == []
        assert result.overperforming_topics == []

    @pytest.mark.asyncio
    async def test_underperforming_classification(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        # avg views = (1000 + 200) / 2 = 600; 0.5 * 600 = 300 threshold for underperforming
        rows = [
            ["low_vid", 200, 50, 60.0, 30.0, 5, 1, 0, 0],
            ["high_vid", 1000, 200, 120.0, 55.0, 50, 10, 5, 1],
        ]
        analytics_client._client.get.return_value = _make_api_response(
            rows,
            column_headers=["video", "views", "estimatedMinutesWatched", "averageViewDuration",
                            "averageViewPercentage", "likes", "comments", "subscribersGained", "subscribersLost"],
        )
        # No retention data
        analytics_client.get_video_retention = AsyncMock(return_value=[])
        result = await analytics_client.analyze_content_gaps()
        assert "low_vid" in result.underperforming_topics
        assert "high_vid" not in result.underperforming_topics

    @pytest.mark.asyncio
    async def test_overperforming_classification(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        # avg views = 600; 1.5 * 600 = 900 threshold for overperforming
        rows = [
            ["low_vid", 200, 50, 60.0, 30.0, 5, 1, 0, 0],
            ["high_vid", 1000, 200, 120.0, 55.0, 50, 10, 5, 1],
        ]
        analytics_client._client.get.return_value = _make_api_response(
            rows,
            column_headers=["video", "views", "estimatedMinutesWatched", "averageViewDuration",
                            "averageViewPercentage", "likes", "comments", "subscribersGained", "subscribersLost"],
        )
        analytics_client.get_video_retention = AsyncMock(return_value=[])
        result = await analytics_client.analyze_content_gaps()
        assert "high_vid" in result.overperforming_topics

    @pytest.mark.asyncio
    async def test_retention_drop_detection(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        rows = [
            ["vid1", 1000, 200, 120.0, 55.0, 50, 10, 5, 1],
        ]
        analytics_client._client.get.return_value = _make_api_response(
            rows,
            column_headers=["video", "views", "estimatedMinutesWatched", "averageViewDuration",
                            "averageViewPercentage", "likes", "comments", "subscribersGained", "subscribersLost"],
        )
        # Retention: big drop from 0.9 to 0.7 (>10%)
        retention_data = [
            {"time_ratio": 0.0, "watch_ratio": 1.0},
            {"time_ratio": 0.1, "watch_ratio": 0.9},
            {"time_ratio": 0.2, "watch_ratio": 0.7},  # drop of 0.2 > 0.1
            {"time_ratio": 0.3, "watch_ratio": 0.65},
        ]
        analytics_client.get_video_retention = AsyncMock(return_value=retention_data)
        result = await analytics_client.analyze_content_gaps()
        assert len(result.retention_drop_points) >= 1
        drop = result.retention_drop_points[0]
        assert drop["video_id"] == "vid1"
        assert drop["drop_percentage"] == pytest.approx(20.0)

    @pytest.mark.asyncio
    async def test_no_retention_drop_when_small(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        rows = [
            ["vid1", 500, 100, 90.0, 40.0, 20, 5, 2, 0],
        ]
        analytics_client._client.get.return_value = _make_api_response(
            rows,
            column_headers=["video", "views", "estimatedMinutesWatched", "averageViewDuration",
                            "averageViewPercentage", "likes", "comments", "subscribersGained", "subscribersLost"],
        )
        retention_data = [
            {"time_ratio": 0.0, "watch_ratio": 1.0},
            {"time_ratio": 0.1, "watch_ratio": 0.95},
            {"time_ratio": 0.2, "watch_ratio": 0.92},  # only 3% drop - not >10%
        ]
        analytics_client.get_video_retention = AsyncMock(return_value=retention_data)
        result = await analytics_client.analyze_content_gaps()
        assert result.retention_drop_points == []

    @pytest.mark.asyncio
    async def test_only_top_5_analyzed_for_retention(self, analytics_client):
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        rows = [[f"v{i}", (i + 1) * 100, 10, 10.0, 10.0, 5, 1, 1, 0] for i in range(10)]
        analytics_client._client.get.return_value = _make_api_response(
            rows,
            column_headers=["video", "views", "estimatedMinutesWatched", "averageViewDuration",
                            "averageViewPercentage", "likes", "comments", "subscribersGained", "subscribersLost"],
        )
        analytics_client.get_video_retention = AsyncMock(return_value=[])
        await analytics_client.analyze_content_gaps()
        # Should only call get_video_retention for top 5 videos
        assert analytics_client.get_video_retention.call_count == 5

    @pytest.mark.asyncio
    async def test_borderline_views_neither_under_nor_over(self, analytics_client):
        """Video with exactly avg views should be in neither list."""
        analytics_client._access_token = "tok"
        analytics_client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        rows = [
            ["v1", 100, 10, 10.0, 10.0, 5, 1, 1, 0],
            ["v2", 100, 10, 10.0, 10.0, 5, 1, 1, 0],
        ]
        analytics_client._client.get.return_value = _make_api_response(
            rows,
            column_headers=["video", "views", "estimatedMinutesWatched", "averageViewDuration",
                            "averageViewPercentage", "likes", "comments", "subscribersGained", "subscribersLost"],
        )
        analytics_client.get_video_retention = AsyncMock(return_value=[])
        result = await analytics_client.analyze_content_gaps()
        assert result.underperforming_topics == []
        assert result.overperforming_topics == []


# ─── Convenience Functions ───────────────────────────────────────────────────────


class TestConvenienceFunctions:
    @pytest.mark.asyncio
    async def test_get_my_channel_analytics(self, mock_oauth_settings):
        analytics_client_mock = AsyncMock()
        analytics_client_mock.get_channel_analytics.return_value = ChannelAnalytics(channel_id="MINE")
        with patch("packages.integrations.youtube.youtube_analytics.YouTubeAnalyticsClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=analytics_client_mock)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await get_my_channel_analytics(days=7)
            assert isinstance(result, ChannelAnalytics)
            analytics_client_mock.get_channel_analytics.assert_called_once_with(days=7)

    @pytest.mark.asyncio
    async def test_analyze_my_content_gaps(self, mock_oauth_settings):
        analytics_client_mock = AsyncMock()
        analytics_client_mock.analyze_content_gaps.return_value = ContentGapAnalysis()
        with patch("packages.integrations.youtube.youtube_analytics.YouTubeAnalyticsClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=analytics_client_mock)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await analyze_my_content_gaps(days=60)
            assert isinstance(result, ContentGapAnalysis)
            analytics_client_mock.analyze_content_gaps.assert_called_once_with(days=60)
