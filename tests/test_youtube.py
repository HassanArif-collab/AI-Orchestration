"""Tests for YouTubeClient and AnalyticsTracker.

Tests verify graceful degradation - all methods return empty/default values
when YouTube API is unavailable, and no exceptions are raised.
"""

import pytest
from unittest.mock import MagicMock, patch
import tempfile
import json
import os


class TestYouTubeClient:
    """Tests for YouTubeClient."""

    def test_no_exception_when_api_key_empty(self):
        """YouTubeClient should not crash when api_key is empty."""
        from packages.integrations.youtube.client import YouTubeClient

        # Should not raise any exception
        client = YouTubeClient(api_key="")
        assert client._service is None

    def test_no_exception_when_api_key_none(self):
        """YouTubeClient should not crash when api_key is None."""
        from packages.integrations.youtube.client import YouTubeClient

        # Should not raise any exception
        client = YouTubeClient(api_key=None)
        assert client._service is None

    def test_get_channel_stats_returns_default_dict_when_service_none(self):
        """get_channel_stats should return default dict when service is None."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        result = client.get_channel_stats("UC_test_channel")

        assert isinstance(result, dict)
        assert result["subscriber_count"] == 0
        assert result["total_views"] == 0
        assert result["video_count"] == 0
        assert result["channel_id"] == "UC_test_channel"

    def test_get_recent_videos_returns_empty_list_when_service_none(self):
        """get_recent_videos should return [] when service is None."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        result = client.get_recent_videos("UC_test_channel")
        assert result == []

    def test_get_video_details_returns_empty_dict_when_service_none(self):
        """get_video_details should return {} when service is None."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        result = client.get_video_details("video_id_123")
        assert result == {}

    def test_search_trending_returns_empty_list_when_service_none(self):
        """search_trending should return [] when service is None."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        result = client.search_trending("AI technology")
        assert result == []

    def test_get_competitor_videos_returns_empty_list_when_service_none(self):
        """get_competitor_videos should return [] when service is None."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        result = client.get_competitor_videos(["UC_channel_1", "UC_channel_2"])
        assert result == []

    def test_methods_handle_exceptions_gracefully(self):
        """All methods should catch exceptions and return default values."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="fake_key")

        # Mock the service to raise an exception
        client._service = MagicMock()
        client._service.channels.return_value.list.return_value.execute.side_effect = Exception("API Error")
        client._service.playlistItems.return_value.list.return_value.execute.side_effect = Exception("API Error")
        client._service.videos.return_value.list.return_value.execute.side_effect = Exception("API Error")
        client._service.search.return_value.list.return_value.execute.side_effect = Exception("API Error")

        # All should return defaults without raising
        result = client.get_channel_stats("UC_test")
        assert result["subscriber_count"] == 0

        result = client.get_recent_videos("UC_test")
        assert result == []

        result = client.get_video_details("video_id")
        assert result == {}

        result = client.search_trending("query")
        assert result == []

        result = client.get_competitor_videos(["UC_test"])
        assert result == []


class TestAnalyticsTracker:
    """Tests for AnalyticsTracker."""

    def test_pull_weekly_stats_returns_proper_structure(self):
        """pull_weekly_stats should return properly structured dict even on failure."""
        from packages.integrations.youtube.analytics import AnalyticsTracker

        tracker = AnalyticsTracker(api_key="")
        result = tracker.pull_weekly_stats("UC_test_channel")

        assert isinstance(result, dict)
        assert "channel_id" in result
        assert "timestamp" in result
        assert "channel_stats" in result
        assert "video_stats" in result
        assert result["channel_id"] == "UC_test_channel"

    def test_compare_videos_returns_empty_list_on_failure(self):
        """compare_videos should return [] on API failure."""
        from packages.integrations.youtube.analytics import AnalyticsTracker

        tracker = AnalyticsTracker(api_key="")
        result = tracker.compare_videos(["video_id_1", "video_id_2"])
        assert isinstance(result, list)

    def test_find_best_performers_returns_empty_list_on_failure(self):
        """find_best_performers should return [] on API failure."""
        from packages.integrations.youtube.analytics import AnalyticsTracker

        tracker = AnalyticsTracker(api_key="")
        result = tracker.find_best_performers("UC_test_channel")
        assert isinstance(result, list)

    def test_save_snapshot_saves_to_file(self):
        """save_snapshot should save data to a JSON file."""
        from packages.integrations.youtube.analytics import AnalyticsTracker

        tracker = AnalyticsTracker(api_key="")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_snapshot.json")
            result_path = tracker.save_snapshot({"test": "data", "count": 42}, filepath)

            assert result_path == filepath
            assert os.path.exists(filepath)

            with open(filepath, "r") as f:
                loaded = json.load(f)

            assert loaded["test"] == "data"
            assert loaded["count"] == 42
            assert "_snapshot_metadata" in loaded

    def test_save_snapshot_creates_directory_if_needed(self):
        """save_snapshot should create the analytics directory if it doesn't exist."""
        from packages.integrations.youtube.analytics import AnalyticsTracker

        tracker = AnalyticsTracker(api_key="")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_data_dir = os.path.join(tmpdir, "test_data", "analytics")

            # Ensure directory doesn't exist
            assert not os.path.exists(test_data_dir)

            # Save snapshot to that location
            filepath = os.path.join(test_data_dir, "snapshot.json")
            tracker.save_snapshot({"test": "data"}, filepath)

            # Verify file was created
            assert os.path.exists(filepath)

    def test_calculate_engagement(self):
        """_calculate_engagement should compute correct engagement rate."""
        from packages.integrations.youtube.analytics import AnalyticsTracker

        tracker = AnalyticsTracker(api_key="")

        # Test with typical values
        video = {"views": 1000, "likes": 50, "comments": 25}
        engagement = tracker._calculate_engagement(video)

        # Engagement = (likes + comments) / views * 100
        expected = round((50 + 25) / 1000 * 100, 2)
        assert engagement == expected

        # Test with zero views
        video_zero = {"views": 0, "likes": 10, "comments": 5}
        assert tracker._calculate_engagement(video_zero) == 0.0
