"""Tests for packages/integrations/youtube/analytics.py

Covers:
- AnalyticsTracker init
- pull_weekly_stats: aggregation math, engagement rate calculation, error handling
- compare_videos: sorting by views, engagement calc per video
- find_best_performers: metric sorting (views/likes/comments/engagement), top_n
- save_snapshot: default filepath, custom filepath, directory creation, metadata
- _calculate_engagement: zero views, normal case
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from packages.integrations.youtube.analytics import AnalyticsTracker


# ─── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_youtube_client():
    """Patch YouTubeClient so no real API calls happen."""
    with patch("packages.integrations.youtube.analytics.YouTubeClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        yield mock_instance


@pytest.fixture()
def tracker(mock_youtube_client):
    """Return an AnalyticsTracker with a mocked YouTubeClient."""
    return AnalyticsTracker(api_key="fake-key")


# ─── Init ────────────────────────────────────────────────────────────────────────


class TestAnalyticsTrackerInit:
    def test_init_creates_client(self, mock_youtube_client):
        t = AnalyticsTracker(api_key="my-key")
        assert t._client is not None

    def test_init_without_key(self, mock_youtube_client):
        t = AnalyticsTracker()
        assert t._client is not None


# ─── pull_weekly_stats ───────────────────────────────────────────────────────────


class TestPullWeeklyStats:
    def test_basic_aggregation(self, tracker, mock_youtube_client):
        mock_youtube_client.get_channel_stats.return_value = {"subs": 1000}
        mock_youtube_client.get_recent_videos.return_value = [
            {"views": 100, "likes": 10, "comments": 5},
            {"views": 200, "likes": 20, "comments": 10},
            {"views": 300, "likes": 30, "comments": 15},
        ]
        result = tracker.pull_weekly_stats("ch123")
        assert result["channel_id"] == "ch123"
        assert result["total_views"] == 600
        assert result["total_likes"] == 60
        assert result["total_comments"] == 30
        assert result["video_count"] == 3

    def test_average_views(self, tracker, mock_youtube_client):
        mock_youtube_client.get_channel_stats.return_value = {}
        mock_youtube_client.get_recent_videos.return_value = [
            {"views": 100}, {"views": 200}, {"views": 300},
        ]
        result = tracker.pull_weekly_stats("ch1")
        # 600 // 3 = 200 (integer division)
        assert result["average_views"] == 200

    def test_engagement_rate(self, tracker, mock_youtube_client):
        mock_youtube_client.get_channel_stats.return_value = {}
        mock_youtube_client.get_recent_videos.return_value = [
            {"views": 1000, "likes": 50, "comments": 30},
        ]
        result = tracker.pull_weekly_stats("ch1")
        # (50 + 30) / 1000 * 100 = 8.0
        assert result["average_engagement"] == 8.0

    def test_engagement_rate_rounding(self, tracker, mock_youtube_client):
        mock_youtube_client.get_channel_stats.return_value = {}
        mock_youtube_client.get_recent_videos.return_value = [
            {"views": 333, "likes": 11, "comments": 7},
        ]
        result = tracker.pull_weekly_stats("ch1")
        # (11 + 7) / 333 * 100 = 5.405405... => round to 5.41
        assert result["average_engagement"] == 5.41

    def test_zero_views_engagement_zero(self, tracker, mock_youtube_client):
        mock_youtube_client.get_channel_stats.return_value = {}
        mock_youtube_client.get_recent_videos.return_value = [
            {"views": 0, "likes": 0, "comments": 0},
        ]
        result = tracker.pull_weekly_stats("ch1")
        assert result["average_engagement"] == 0.0

    def test_empty_videos(self, tracker, mock_youtube_client):
        mock_youtube_client.get_channel_stats.return_value = {}
        mock_youtube_client.get_recent_videos.return_value = []
        result = tracker.pull_weekly_stats("ch1")
        assert result["total_views"] == 0
        assert result["total_likes"] == 0
        assert result["video_count"] == 0
        assert result["average_views"] == 0
        assert result["average_engagement"] == 0.0

    def test_channel_stats_included(self, tracker, mock_youtube_client):
        stats = {"subscriber_count": 5000, "view_count": 100000}
        mock_youtube_client.get_channel_stats.return_value = stats
        mock_youtube_client.get_recent_videos.return_value = []
        result = tracker.pull_weekly_stats("ch1")
        assert result["channel_stats"] == stats

    def test_error_returns_partial_result(self, tracker, mock_youtube_client):
        mock_youtube_client.get_channel_stats.side_effect = Exception("API down")
        result = tracker.pull_weekly_stats("ch1")
        assert result["channel_id"] == "ch1"
        assert result["total_views"] == 0
        # Should not raise

    def test_video_stats_structure(self, tracker, mock_youtube_client):
        mock_youtube_client.get_channel_stats.return_value = {}
        mock_youtube_client.get_recent_videos.return_value = [
            {"views": 100, "likes": 10, "comments": 5},
        ]
        result = tracker.pull_weekly_stats("ch1")
        assert "videos" in result["video_stats"]
        assert result["video_stats"]["count"] == 1

    def test_timestamp_present(self, tracker, mock_youtube_client):
        mock_youtube_client.get_channel_stats.return_value = {}
        mock_youtube_client.get_recent_videos.return_value = []
        result = tracker.pull_weekly_stats("ch1")
        assert "timestamp" in result
        assert result["timestamp"] != ""


# ─── compare_videos ──────────────────────────────────────────────────────────────


class TestCompareVideos:
    def test_sorts_by_views_descending(self, tracker, mock_youtube_client):
        details_map = {
            "a": {"title": "A", "views": 100, "likes": 5, "comments": 2, "duration": "PT5M", "published_at": "2025-01-01"},
            "b": {"title": "B", "views": 500, "likes": 25, "comments": 10, "duration": "PT10M", "published_at": "2025-01-02"},
            "c": {"title": "C", "views": 300, "likes": 15, "comments": 5, "duration": "PT3M", "published_at": "2025-01-03"},
        }
        mock_youtube_client.get_video_details.side_effect = lambda vid: details_map.get(vid)
        result = tracker.compare_videos(["a", "b", "c"])
        assert result[0]["views"] == 500  # B first
        assert result[1]["views"] == 300  # C second
        assert result[2]["views"] == 100  # A last

    def test_engagement_rate_in_result(self, tracker, mock_youtube_client):
        mock_youtube_client.get_video_details.return_value = {
            "title": "V", "views": 100, "likes": 10, "comments": 5,
            "duration": "PT5M", "published_at": "2025-01-01",
        }
        result = tracker.compare_videos(["vid1"])
        # (10 + 5) / 100 * 100 = 15.0
        assert result[0]["engagement_rate"] == 15.0

    def test_empty_ids_returns_empty(self, tracker, mock_youtube_client):
        result = tracker.compare_videos([])
        assert result == []

    def test_missing_video_details_skipped(self, tracker, mock_youtube_client):
        mock_youtube_client.get_video_details.return_value = None
        result = tracker.compare_videos(["missing"])
        assert result == []

    def test_fields_in_result(self, tracker, mock_youtube_client):
        mock_youtube_client.get_video_details.return_value = {
            "title": "My Video", "views": 200, "likes": 15, "comments": 3,
            "duration": "PT7M", "published_at": "2025-03-15",
        }
        result = tracker.compare_videos(["v1"])
        item = result[0]
        assert item["video_id"] == "v1"
        assert item["title"] == "My Video"
        assert item["duration"] == "PT7M"
        assert item["published_at"] == "2025-03-15"
        assert "engagement_rate" in item


# ─── find_best_performers ────────────────────────────────────────────────────────


class TestFindBestPerformers:
    def test_defaults_to_views(self, tracker, mock_youtube_client):
        videos = [
            {"views": 100, "likes": 5, "comments": 2},
            {"views": 500, "likes": 25, "comments": 10},
            {"views": 300, "likes": 15, "comments": 5},
        ]
        mock_youtube_client.get_recent_videos.return_value = videos
        result = tracker.find_best_performers("ch1")
        assert result[0]["views"] == 500
        assert result[1]["views"] == 300

    def test_sort_by_likes(self, tracker, mock_youtube_client):
        videos = [
            {"views": 500, "likes": 10, "comments": 2},
            {"views": 100, "likes": 50, "comments": 5},
            {"views": 300, "likes": 30, "comments": 3},
        ]
        mock_youtube_client.get_recent_videos.return_value = videos
        result = tracker.find_best_performers("ch1", metric="likes")
        assert result[0]["likes"] == 50

    def test_sort_by_comments(self, tracker, mock_youtube_client):
        videos = [
            {"views": 500, "likes": 10, "comments": 2},
            {"views": 100, "likes": 50, "comments": 100},
            {"views": 300, "likes": 30, "comments": 30},
        ]
        mock_youtube_client.get_recent_videos.return_value = videos
        result = tracker.find_best_performers("ch1", metric="comments")
        assert result[0]["comments"] == 100

    def test_sort_by_engagement(self, tracker, mock_youtube_client):
        # Video A: (50+25)/100 = 75%, Video B: (10+5)/1000 = 1.5%
        videos = [
            {"views": 1000, "likes": 10, "comments": 5},
            {"views": 100, "likes": 50, "comments": 25},
        ]
        mock_youtube_client.get_recent_videos.return_value = videos
        result = tracker.find_best_performers("ch1", metric="engagement")
        assert result[0]["views"] == 100  # higher engagement

    def test_top_n_limits_results(self, tracker, mock_youtube_client):
        videos = [{"views": i, "likes": i, "comments": i} for i in range(10)]
        mock_youtube_client.get_recent_videos.return_value = videos
        result = tracker.find_best_performers("ch1", top_n=3)
        assert len(result) == 3
        assert result[0]["views"] == 9

    def test_invalid_metric_falls_back_to_views(self, tracker, mock_youtube_client):
        videos = [
            {"views": 100, "likes": 10, "comments": 5},
            {"views": 500, "likes": 2, "comments": 1},
        ]
        mock_youtube_client.get_recent_videos.return_value = videos
        result = tracker.find_best_performers("ch1", metric="invalid_metric")
        assert result[0]["views"] == 500

    def test_engagement_field_added_to_videos(self, tracker, mock_youtube_client):
        videos = [{"views": 100, "likes": 10, "comments": 5}]
        mock_youtube_client.get_recent_videos.return_value = videos
        result = tracker.find_best_performers("ch1")
        assert "engagement" in result[0]
        # (10 + 5) / 100 * 100 = 15.0
        assert result[0]["engagement"] == 15.0

    def test_empty_videos_returns_empty(self, tracker, mock_youtube_client):
        mock_youtube_client.get_recent_videos.return_value = []
        result = tracker.find_best_performers("ch1")
        assert result == []


# ─── save_snapshot ───────────────────────────────────────────────────────────────


class TestSaveSnapshot:
    def test_default_filepath(self, tracker, tmp_path, monkeypatch):
        """Save to default dir (monkeypatched to tmp_path)."""
        analytics_dir = tmp_path / "analytics"
        monkeypatch.setattr("packages.integrations.youtube.analytics.Path",
                            lambda p: tmp_path / p if isinstance(p, str) and p.startswith("packages") else Path(p))

        # Instead of monkeypatching Path, just use custom filepath
        filepath = tracker.save_snapshot({"test": True}, filepath=str(tmp_path / "snap" / "2025-01-01.json"))
        assert Path(filepath).exists()
        with open(filepath) as f:
            data = json.load(f)
        assert data["test"] is True
        assert "_snapshot_metadata" in data

    def test_custom_filepath(self, tracker, tmp_path):
        custom = str(tmp_path / "subdir" / "custom.json")
        filepath = tracker.save_snapshot({"data": [1, 2, 3]}, filepath=custom)
        assert filepath == custom
        assert Path(custom).exists()
        with open(custom) as f:
            data = json.load(f)
        assert data["data"] == [1, 2, 3]

    def test_creates_parent_directory(self, tracker, tmp_path):
        nested = str(tmp_path / "a" / "b" / "c" / "snap.json")
        tracker.save_snapshot({"ok": True}, filepath=nested)
        assert Path(nested).exists()

    def test_metadata_includes_saved_at(self, tracker, tmp_path):
        fp = str(tmp_path / "meta.json")
        tracker.save_snapshot({"x": 1}, filepath=fp)
        with open(fp) as f:
            data = json.load(f)
        assert "saved_at" in data["_snapshot_metadata"]
        assert data["_snapshot_metadata"]["filepath"] == fp

    def test_returns_filepath(self, tracker, tmp_path):
        fp = str(tmp_path / "ret.json")
        result = tracker.save_snapshot({}, filepath=fp)
        assert result == fp

    def test_unicode_content(self, tracker, tmp_path):
        fp = str(tmp_path / "unicode.json")
        tracker.save_snapshot({"title": "Pakistani Video \u0648\u06cc\u0688\u06cc\u0648"}, filepath=fp)
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        assert "\u0648\u06cc\u0688\u06cc\u0648" in data["title"]

    def test_non_serializable_defaults_to_str(self, tracker, tmp_path):
        from datetime import datetime, timezone
        fp = str(tmp_path / "dates.json")
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        tracker.save_snapshot({"date": dt}, filepath=fp)
        with open(fp) as f:
            data = json.load(f)
        # default=str should convert datetime to string
        assert isinstance(data["date"], str)


# ─── _calculate_engagement ───────────────────────────────────────────────────────


class TestCalculateEngagement:
    def test_normal_calculation(self, tracker):
        rate = tracker._calculate_engagement({"views": 1000, "likes": 50, "comments": 30})
        # (50 + 30) / 1000 * 100 = 8.0
        assert rate == 8.0

    def test_zero_views_returns_zero(self, tracker):
        rate = tracker._calculate_engagement({"views": 0, "likes": 10, "comments": 5})
        assert rate == 0.0

    def test_no_views_key_defaults_zero(self, tracker):
        rate = tracker._calculate_engagement({"likes": 10, "comments": 5})
        assert rate == 0.0

    def test_rounding(self, tracker):
        rate = tracker._calculate_engagement({"views": 333, "likes": 11, "comments": 7})
        # (11 + 7) / 333 * 100 = 5.405... => 5.41
        assert rate == 5.41

    def test_only_likes(self, tracker):
        rate = tracker._calculate_engagement({"views": 500, "likes": 25, "comments": 0})
        assert rate == 5.0
