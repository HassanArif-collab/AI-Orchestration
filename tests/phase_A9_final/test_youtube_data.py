"""Tests for packages/integrations/youtube/youtube_data.py

Covers:
- YouTubeVideo / TrendingVideo dataclasses
- QuotaExceededError / YouTubeAPIError exceptions
- YouTubeDataClient: init, context manager, _request, _parse_video
- get_trending_videos (ranking, category filter, region)
- search (filters, order, fallback on empty results)
- get_videos_by_ids
- get_categories
- get_channel_info
- Convenience functions fetch_trending_for_region / search_youtube
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from packages.integrations.youtube.youtube_data import (
    YouTubeVideo,
    TrendingVideo,
    YouTubeAPIError,
    QuotaExceededError,
    YouTubeDataClient,
    fetch_trending_for_region,
    search_youtube,
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
def mock_settings():
    settings = _make_settings(YOUTUBE_API_KEY="fake-yt-key")
    with patch("packages.integrations.youtube.youtube_data.get_settings", return_value=settings):
        yield settings


@pytest.fixture()
def mock_no_key_settings():
    settings = _make_settings(YOUTUBE_API_KEY="")  # uses valid defaults for other fields
    with patch("packages.integrations.youtube.youtube_data.get_settings", return_value=settings):
        yield settings


@pytest.fixture()
async def data_client(mock_settings):
    """Return a YouTubeDataClient with a mocked httpx.AsyncClient."""
    client = YouTubeDataClient(api_key="fake-yt-key")
    mock_http = AsyncMock()
    client._client = mock_http
    return client


def _sample_video_item(vid="abc123", title="Test Video", views=1000, likes=50, comments=10):
    """Build a raw API video item dict for _parse_video."""
    return {
        "id": vid,
        "snippet": {
            "title": title,
            "description": "A test video",
            "channelTitle": "TestChannel",
            "channelId": "ch001",
            "publishedAt": "2025-01-15T10:00:00Z",
            "categoryId": "22",
            "tags": ["tag1", "tag2"],
            "thumbnails": {
                "maxres": {"url": "https://img.maxres/abc"},
                "high": {"url": "https://img.high/abc"},
                "default": {"url": "https://img.default/abc"},
            },
        },
        "statistics": {
            "viewCount": str(views),
            "likeCount": str(likes),
            "commentCount": str(comments),
        },
        "contentDetails": {
            "duration": "PT5M30S",
        },
    }


# ─── Data Models ─────────────────────────────────────────────────────────────────


class TestYouTubeVideo:
    """YouTubeVideo dataclass tests."""

    def test_basic_fields(self):
        v = YouTubeVideo(
            video_id="x1", title="T", description="D", channel_title="C",
            channel_id="c1", published_at="2025-01-01T00:00:00Z",
            view_count=100, like_count=10, comment_count=5,
            thumbnail_url="https://img/x", category_id="22",
            tags=["a"], duration="PT5M",
        )
        assert v.video_id == "x1"
        assert v.view_count == 100
        assert v.tags == ["a"]

    def test_url_property(self):
        v = YouTubeVideo(
            video_id="dQw4w9", title="", description="", channel_title="",
            channel_id="", published_at="", view_count=0, like_count=0,
            comment_count=0, thumbnail_url="", category_id="", tags=[], duration="",
        )
        assert v.url == "https://youtube.com/watch?v=dQw4w9"

    def test_default_tags(self):
        v = YouTubeVideo(
            video_id="z", title="", description="", channel_title="",
            channel_id="", published_at="", view_count=0, like_count=0,
            comment_count=0, thumbnail_url="", category_id="", tags=[], duration="",
        )
        assert v.tags == []


class TestTrendingVideo:
    """TrendingVideo dataclass (extends YouTubeVideo)."""

    def test_inherits_fields(self):
        tv = TrendingVideo(
            video_id="t1", title="Trending", description="D", channel_title="C",
            channel_id="c1", published_at="2025-01-01T00:00:00Z",
            view_count=5000, like_count=200, comment_count=50,
            thumbnail_url="https://img/t", category_id="10",
            tags=["trending"], duration="PT10M",
            trending_rank=1, trending_region="PK", fetched_at="2025-06-01T00:00:00Z",
        )
        assert tv.video_id == "t1"
        assert tv.trending_rank == 1
        assert tv.trending_region == "PK"
        assert tv.fetched_at == "2025-06-01T00:00:00Z"

    def test_defaults(self):
        tv = TrendingVideo(
            video_id="t2", title="", description="", channel_title="",
            channel_id="", published_at="", view_count=0, like_count=0,
            comment_count=0, thumbnail_url="", category_id="", tags=[], duration="",
        )
        assert tv.trending_rank == 0
        assert tv.trending_region == ""
        assert tv.fetched_at == ""


class TestExceptions:
    """YouTubeAPIError / QuotaExceededError tests."""

    def test_youtube_api_error(self):
        err = YouTubeAPIError("Bad request")
        assert str(err) == "Bad request"

    def test_quota_exceeded_is_youtube_api_error(self):
        err = QuotaExceededError("quota exceeded")
        assert isinstance(err, YouTubeAPIError)
        assert isinstance(err, Exception)

    def test_quota_exceeded_message(self):
        err = QuotaExceededError("YouTube API quota exceeded")
        assert "quota" in str(err).lower()


# ─── YouTubeDataClient Init ──────────────────────────────────────────────────────


class TestYouTubeDataClientInit:
    def test_init_with_api_key(self):
        client = YouTubeDataClient(api_key="my-key")
        assert client.api_key == "my-key"

    def test_init_falls_back_to_settings(self, mock_settings):
        client = YouTubeDataClient()
        assert client.api_key == "fake-yt-key"

    def test_init_warns_on_missing_key(self, mock_no_key_settings):
        client = YouTubeDataClient()
        assert client.api_key == ""


class TestYouTubeDataClientContextManager:
    """__aenter__ / __aexit__ tests."""

    @pytest.mark.asyncio
    async def test_aenter_creates_client(self):
        client = YouTubeDataClient(api_key="k")
        with patch("packages.integrations.youtube.youtube_data.httpx.AsyncClient") as MockAsync:
            MockAsync.return_value.aclose = AsyncMock()
            async with client:
                assert hasattr(client, "_client")


# ─── _parse_video ────────────────────────────────────────────────────────────────


class TestParseVideo:
    def test_full_item(self):
        client = YouTubeDataClient.__new__(YouTubeDataClient)
        item = _sample_video_item()
        video = client._parse_video(item)
        assert isinstance(video, YouTubeVideo)
        assert video.video_id == "abc123"
        assert video.title == "Test Video"
        assert video.view_count == 1000
        assert video.like_count == 50
        assert video.comment_count == 10
        assert video.duration == "PT5M30S"
        assert video.category_id == "22"
        assert video.tags == ["tag1", "tag2"]
        assert video.channel_title == "TestChannel"
        assert video.channel_id == "ch001"

    def test_thumbnail_priority_maxres(self):
        client = YouTubeDataClient.__new__(YouTubeDataClient)
        item = _sample_video_item()
        video = client._parse_video(item)
        assert video.thumbnail_url == "https://img.maxres/abc"

    def test_thumbnail_fallback_to_high(self):
        client = YouTubeDataClient.__new__(YouTubeDataClient)
        item = _sample_video_item()
        del item["snippet"]["thumbnails"]["maxres"]
        video = client._parse_video(item)
        assert video.thumbnail_url == "https://img.high/abc"

    def test_thumbnail_fallback_to_default(self):
        client = YouTubeDataClient.__new__(YouTubeDataClient)
        item = _sample_video_item()
        del item["snippet"]["thumbnails"]["maxres"]
        del item["snippet"]["thumbnails"]["high"]
        video = client._parse_video(item)
        assert video.thumbnail_url == "https://img.default/abc"

    def test_empty_thumbnail(self):
        client = YouTubeDataClient.__new__(YouTubeDataClient)
        item = _sample_video_item()
        item["snippet"]["thumbnails"] = {}
        video = client._parse_video(item)
        assert video.thumbnail_url == ""

    def test_missing_fields_default_to_empty(self):
        client = YouTubeDataClient.__new__(YouTubeDataClient)
        item = {"id": "empty"}
        video = client._parse_video(item)
        assert video.video_id == "empty"
        assert video.title == ""
        assert video.view_count == 0
        assert video.tags == []
        assert video.duration == ""

    def test_stats_as_strings(self):
        client = YouTubeDataClient.__new__(YouTubeDataClient)
        item = _sample_video_item(views="9999", likes="888", comments="77")
        video = client._parse_video(item)
        assert video.view_count == 9999
        assert video.like_count == 888
        assert video.comment_count == 77


# ─── _request ────────────────────────────────────────────────────────────────────


class TestRequest:
    @pytest.mark.asyncio
    async def test_successful_request(self, data_client):
        data_client._client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": []}),
        )
        data_client._client.get.return_value.raise_for_status = MagicMock()
        result = await data_client._request("videos", {"part": "snippet"})
        assert result == {"items": []}

    @pytest.mark.asyncio
    async def test_request_adds_api_key(self, data_client):
        data_client._client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={}),
        )
        data_client._client.get.return_value.raise_for_status = MagicMock()
        await data_client._request("videos", {"part": "snippet"})
        call_args = data_client._client.get.call_args
        assert "key" in call_args[1]["params"]
        assert call_args[1]["params"]["key"] == "fake-yt-key"

    @pytest.mark.asyncio
    async def test_quota_exceeded_raises(self, data_client):
        error_resp = MagicMock(status_code=403)
        error_resp.json.return_value = {
            "error": {"errors": [{"reason": "quotaExceeded"}]}
        }
        data_client._client.get.return_value = error_resp
        with pytest.raises(QuotaExceededError):
            await data_client._request("videos", {})

    @pytest.mark.asyncio
    async def test_403_non_quota_raises_youtube_api_error(self, data_client):
        error_resp = MagicMock(status_code=403)
        error_resp.json.return_value = {
            "error": {"errors": [{"reason": "forbidden"}]}
        }
        data_client._client.get.return_value = error_resp
        with pytest.raises(YouTubeAPIError, match="Forbidden"):
            await data_client._request("videos", {})

    @pytest.mark.asyncio
    async def test_400_raises_bad_request(self, data_client):
        error_resp = MagicMock(status_code=400)
        error_resp.json.return_value = {"error": {"message": "bad"}}
        data_client._client.get.return_value = error_resp
        with pytest.raises(YouTubeAPIError, match="Bad request"):
            await data_client._request("videos", {})

    @pytest.mark.asyncio
    async def test_500_raises_http_error(self, data_client):
        error_resp = MagicMock(status_code=500)
        error_resp.json.return_value = {}
        error_resp.raise_for_status.side_effect = Exception("Server error")
        data_client._client.get.return_value = error_resp
        with pytest.raises(Exception, match="Server error"):
            await data_client._request("videos", {})


# ─── get_trending_videos ─────────────────────────────────────────────────────────


class TestGetTrendingVideos:
    @pytest.mark.asyncio
    async def test_returns_trending_list(self, data_client):
        data_client._client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": [_sample_video_item("v1"), _sample_video_item("v2")]}),
        )
        data_client._client.get.return_value.raise_for_status = MagicMock()
        results = await data_client.get_trending_videos("PK")
        assert len(results) == 2
        assert all(isinstance(v, TrendingVideo) for v in results)

    @pytest.mark.asyncio
    async def test_trending_ranking(self, data_client):
        data_client._client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": [_sample_video_item("a"), _sample_video_item("b"), _sample_video_item("c")]}),
        )
        data_client._client.get.return_value.raise_for_status = MagicMock()
        results = await data_client.get_trending_videos("US")
        assert results[0].trending_rank == 1
        assert results[1].trending_rank == 2
        assert results[2].trending_rank == 3

    @pytest.mark.asyncio
    async def test_trending_region_set(self, data_client):
        data_client._client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": [_sample_video_item()]}),
        )
        data_client._client.get.return_value.raise_for_status = MagicMock()
        results = await data_client.get_trending_videos("IN")
        assert results[0].trending_region == "IN"

    @pytest.mark.asyncio
    async def test_fetched_at_is_set(self, data_client):
        data_client._client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": [_sample_video_item()]}),
        )
        data_client._client.get.return_value.raise_for_status = MagicMock()
        results = await data_client.get_trending_videos()
        assert results[0].fetched_at != ""

    @pytest.mark.asyncio
    async def test_category_id_param(self, data_client):
        data_client._client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": []}),
        )
        data_client._client.get.return_value.raise_for_status = MagicMock()
        await data_client.get_trending_videos("PK", category_id="10")
        call_args = data_client._client.get.call_args
        assert call_args[1]["params"]["videoCategoryId"] == "10"

    @pytest.mark.asyncio
    async def test_no_category_id_omitted(self, data_client):
        data_client._client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": []}),
        )
        data_client._client.get.return_value.raise_for_status = MagicMock()
        await data_client.get_trending_videos("PK")
        call_args = data_client._client.get.call_args
        assert "videoCategoryId" not in call_args[1]["params"]

    @pytest.mark.asyncio
    async def test_empty_items_returns_empty_list(self, data_client):
        data_client._client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": []}),
        )
        data_client._client.get.return_value.raise_for_status = MagicMock()
        results = await data_client.get_trending_videos()
        assert results == []

    @pytest.mark.asyncio
    async def test_api_error_returns_empty_list(self, data_client):
        data_client._client.get.side_effect = Exception("Network error")
        results = await data_client.get_trending_videos()
        assert results == []


# ─── search ──────────────────────────────────────────────────────────────────────


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_videos(self, data_client):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = {
            "items": [
                {"id": {"videoId": "vid1"}, "snippet": {}},
                {"id": {"videoId": "vid2"}, "snippet": {}},
            ]
        }
        search_resp.raise_for_status = MagicMock()
        video_resp = MagicMock(status_code=200)
        video_resp.json.return_value = {"items": [_sample_video_item("vid1"), _sample_video_item("vid2")]}
        video_resp.raise_for_status = MagicMock()
        data_client._client.get.side_effect = [search_resp, video_resp]
        results = await data_client.search("test query")
        assert len(results) == 2
        assert results[0].video_id == "vid1"

    @pytest.mark.asyncio
    async def test_search_empty_items_returns_empty(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"items": []}
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        results = await data_client.search("nothing")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_duration_filter(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"items": []}
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        await data_client.search("short videos", video_duration="short")
        call_args = data_client._client.get.call_args
        assert call_args[1]["params"]["videoDuration"] == "short"

    @pytest.mark.asyncio
    async def test_search_with_published_after(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"items": []}
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        await data_client.search("recent", published_after="2025-01-01T00:00:00Z")
        call_args = data_client._client.get.call_args
        assert call_args[1]["params"]["publishedAfter"] == "2025-01-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_search_order_param(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"items": []}
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        await data_client.search("views", order="viewCount")
        call_args = data_client._client.get.call_args
        assert call_args[1]["params"]["order"] == "viewCount"

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, data_client):
        data_client._client.get.side_effect = Exception("fail")
        results = await data_client.search("broken")
        assert results == []


# ─── get_videos_by_ids ───────────────────────────────────────────────────────────


class TestGetVideosByIds:
    @pytest.mark.asyncio
    async def test_returns_videos(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"items": [_sample_video_item("id1"), _sample_video_item("id2")]}
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        results = await data_client.get_videos_by_ids(["id1", "id2"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty(self, data_client):
        results = await data_client.get_videos_by_ids([])
        assert results == []
        data_client._client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_ids_joined_with_comma(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"items": []}
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        await data_client.get_videos_by_ids(["a", "b", "c"])
        call_args = data_client._client.get.call_args
        assert call_args[1]["params"]["id"] == "a,b,c"

    @pytest.mark.asyncio
    async def test_max_50_ids_truncated(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"items": []}
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        ids = [f"v{i}" for i in range(60)]
        await data_client.get_videos_by_ids(ids)
        call_args = data_client._client.get.call_args
        joined = call_args[1]["params"]["id"]
        # Should be at most 50 IDs
        assert joined.count(",") == 49

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, data_client):
        data_client._client.get.side_effect = Exception("fail")
        results = await data_client.get_videos_by_ids(["x1"])
        assert results == []


# ─── get_categories ──────────────────────────────────────────────────────────────


class TestGetCategories:
    @pytest.mark.asyncio
    async def test_returns_category_dict(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "items": [
                {"id": "22", "snippet": {"title": "People & Blogs"}},
                {"id": "24", "snippet": {"title": "Entertainment"}},
            ]
        }
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        cats = await data_client.get_categories("US")
        assert cats["22"] == "People & Blogs"
        assert cats["24"] == "Entertainment"

    @pytest.mark.asyncio
    async def test_empty_items_returns_empty_dict(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"items": []}
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        cats = await data_client.get_categories()
        assert cats == {}

    @pytest.mark.asyncio
    async def test_error_returns_empty_dict(self, data_client):
        data_client._client.get.side_effect = Exception("fail")
        cats = await data_client.get_categories()
        assert cats == {}


# ─── get_channel_info ────────────────────────────────────────────────────────────


class TestGetChannelInfo:
    @pytest.mark.asyncio
    async def test_returns_channel_dict(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "items": [{
                "snippet": {
                    "title": "My Channel",
                    "description": "A cool channel",
                    "thumbnails": {"default": {"url": "https://thumb.jpg"}},
                },
                "statistics": {
                    "subscriberCount": "5000",
                    "viewCount": "100000",
                    "videoCount": "120",
                },
            }]
        }
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        info = await data_client.get_channel_info("ch123")
        assert info["channel_id"] == "ch123"
        assert info["title"] == "My Channel"
        assert info["subscriber_count"] == 5000
        assert info["view_count"] == 100000
        assert info["video_count"] == 120
        assert info["thumbnail"] == "https://thumb.jpg"

    @pytest.mark.asyncio
    async def test_empty_items_returns_none(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"items": []}
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        info = await data_client.get_channel_info("nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_error_returns_none(self, data_client):
        data_client._client.get.side_effect = Exception("fail")
        info = await data_client.get_channel_info("broken")
        assert info is None

    @pytest.mark.asyncio
    async def test_default_values_for_missing_stats(self, data_client):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "items": [{
                "snippet": {"title": "New Channel", "description": "", "thumbnails": {}},
                "statistics": {},
            }]
        }
        resp.raise_for_status = MagicMock()
        data_client._client.get.return_value = resp
        info = await data_client.get_channel_info("ch_empty")
        assert info["subscriber_count"] == 0
        assert info["view_count"] == 0
        assert info["thumbnail"] == ""


# ─── Convenience Functions ───────────────────────────────────────────────────────


class TestConvenienceFunctions:
    @pytest.mark.asyncio
    async def test_fetch_trending_for_region_no_key(self, mock_no_key_settings):
        result = await fetch_trending_for_region("PK")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_youtube_no_key(self, mock_no_key_settings):
        result = await search_youtube("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_trending_delegates_to_client(self, mock_settings):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"items": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("packages.integrations.youtube.youtube_data.httpx.AsyncClient") as MockAC:
            MockAC.return_value.get.return_value = mock_resp
            MockAC.return_value.aclose = AsyncMock()
            result = await fetch_trending_for_region("PK", max_results=5)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_youtube_delegates_to_client(self, mock_settings):
        search_resp = MagicMock(status_code=200)
        search_resp.json.return_value = {"items": []}
        search_resp.raise_for_status = MagicMock()
        with patch("packages.integrations.youtube.youtube_data.httpx.AsyncClient") as MockAC:
            MockAC.return_value.get.return_value = search_resp
            MockAC.return_value.aclose = AsyncMock()
            result = await search_youtube("hello")
            assert isinstance(result, list)
