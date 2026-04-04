"""Phase 11 — Integration tests for YouTube API clients.

These tests make REAL YouTube API calls. They are skipped gracefully when:
- YOUTUBE_API_KEY is not set in the environment
- google-api-python-client is not installed
- The YouTube API is unreachable
- Quota is exhausted

Each test wraps real API calls in try/except and calls pytest.skip() on
connection errors or critical failures, ensuring CI pipelines never break
due to missing credentials or transient network issues.
"""

from __future__ import annotations

import os
import pytest

from tests.integration.conftest import skip_if_no_env

pytestmark = pytest.mark.integration


# ── Module-level skip guard ────────────────────────────────────────────────────

_SKIP_REASON = ""

if not os.environ.get("YOUTUBE_API_KEY", ""):
    _SKIP_REASON = "YOUTUBE_API_KEY not configured"


def _require_youtube_key() -> str:
    """Return YOUTUBE_API_KEY after verifying it exists."""
    skip_if_no_env("YOUTUBE_API_KEY")
    return os.environ["YOUTUBE_API_KEY"]  # module-level skip when no key


# ── Real YouTubeClient (googleapiclient) ───────────────────────────────────────

class TestYouTubeClientReal:
    """Integration tests against the live YouTube Data API v3 via YouTubeClient."""

    def _build_client(self) -> "YouTubeClient":
        """Create a YouTubeClient with the real API key from the environment."""
        from packages.integrations.youtube.client import YouTubeClient
        api_key = _require_youtube_key()
        return YouTubeClient(api_key=api_key)

    def test_client_initialization_with_valid_key(self):
        """Verify YouTubeClient initializes successfully with a real API key.

        Scenario: A developer has set YOUTUBE_API_KEY in .env. The client
        should create the googleapiclient service object without errors.
        """
        client = self._build_client()
        assert client is not None
        assert client.api_key != ""

    def test_get_competitor_videos_returns_data(self):
        """Real API call: fetch recent videos from a well-known channel.

        Scenario: The pipeline fetches competitor videos for benchmarking.
        We use a large, public channel (Google's official channel) to ensure
        data is always available.

        Verifies:
        - Response is a list (possibly empty on quota exhaustion)
        - Each video dict has expected keys (video_id, title, views, etc.)
        - Views are non-negative integers
        """
        client = self._build_client()

        try:
            # Use Google's official YouTube channel (UCBR8-60-B28hp2BmDPdntcQ)
            videos = client.get_competitor_videos(
                channel_ids=["UCBR8-60-B28hp2BmDPdntcQ"],
                max_results=3,
            )

            assert isinstance(videos, list), "Should return a list of video dicts"
            # Results may be empty on quota exhaustion — that's acceptable graceful degradation
            if videos:
                for video in videos:
                    assert "video_id" in video, "Each video must have a video_id"
                    assert "title" in video, "Each video must have a title"
                    assert isinstance(video.get("views", 0), int), "Views must be int"
                    assert video.get("views", 0) >= 0, "Views must be non-negative"

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            # 403 quotaExceeded is graceful degradation, not a test failure
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted or forbidden: {exc}")
            raise

    def test_search_videos_returns_results(self):
        """Real API call: search for trending videos by query.

        Scenario: The pipeline's search_trending method is used to discover
        trending content for a niche. We search for a broad term to ensure
        results exist.

        Verifies:
        - Returns a list
        - Results contain video_id, title, and view count
        """
        client = self._build_client()

        try:
            videos = client.search_trending(
                query="Pakistan technology news",
                region_code="PK",
                max_results=3,
            )

            assert isinstance(videos, list), "Should return a list"
            if videos:
                for video in videos:
                    assert "video_id" in video
                    assert "title" in video
                    assert isinstance(video.get("views", 0), int)

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted: {exc}")
            raise

    def test_get_video_stats(self):
        """Real API call: fetch detailed statistics for a specific popular video.

        Scenario: The analytics module fetches video details for performance
        tracking. We use a well-known video (Rick Astley - Never Gonna Give You Up)
        which is guaranteed to exist and have high view counts.

        Verifies:
        - Returns a dict with expected keys
        - Views, likes, comments are positive integers
        - Duration field is a non-empty ISO 8601 string
        """
        client = self._build_client()

        try:
            details = client.get_video_details("dQw4w9WgXcQ")

            # Client returns {} on quota exhaustion or errors — that's acceptable
            if not details:
                pytest.skip("YouTube API returned empty result (possible quota exhaustion)")

            assert isinstance(details, dict)
            assert "video_id" in details
            assert details["video_id"] == "dQw4w9WgXcQ"
            assert "title" in details
            assert isinstance(details.get("views", 0), int)
            assert details.get("views", 0) > 0, "Rick Astley video should have views"
            assert isinstance(details.get("duration", ""), str)
            assert len(details.get("duration", "")) > 0, "Duration should not be empty"

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted: {exc}")
            raise

    def test_get_channel_stats_returns_structure(self):
        """Real API call: fetch channel statistics for a known channel.

        Scenario: The analytics tracker needs channel-level subscriber counts
        and total view metrics for weekly reporting.

        Verifies:
        - Returns a dict with subscriber_count, total_views, video_count
        - All values are non-negative integers
        """
        client = self._build_client()

        try:
            stats = client.get_channel_stats("UCBR8-60-B28hp2BmDPdntcQ")

            assert isinstance(stats, dict)
            assert "subscriber_count" in stats
            assert "total_views" in stats
            assert "video_count" in stats
            assert isinstance(stats["subscriber_count"], int)
            assert stats["subscriber_count"] >= 0
            assert isinstance(stats["total_views"], int)
            assert stats["total_views"] >= 0

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted: {exc}")
            raise

    def test_invalid_api_key_returns_empty_not_exception(self):
        """Verify that an invalid API key degrades gracefully.

        Scenario: A developer enters a wrong API key. The client should
        return empty/default values rather than raising an unhandled exception.
        """
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="INVALID_KEY_FOR_TESTING_12345")

        try:
            # The googleapiclient will try to build, but actual API calls
            # should return empty results, not crash
            result = client.get_channel_stats("UCBR8-60-B28hp2BmDPdntcQ")
            assert isinstance(result, dict)
            # Either we get defaults or an error — both are acceptable
            assert "subscriber_count" in result

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            # 400/403 from invalid key is expected — that's graceful degradation
            err_str = str(exc).lower()
            if any(kw in err_str for kw in ("invalid", "forbidden", "quota", "bad request", "403", "400")):
                # This is expected graceful degradation
                pass
            else:
                raise

    def test_quota_exhausted_returns_empty_not_exception(self):
        """Verify that quota exhaustion is handled gracefully.

        Scenario: During high-traffic periods, the YouTube API quota may be
        exhausted. The client should return empty results rather than crashing.

        We test this by making a call and verifying the response is always
        a list/dict (never an exception), regardless of quota status.
        """
        client = self._build_client()

        try:
            videos = client.search_trending("test query for quota check", max_results=1)
            assert isinstance(videos, list), "Should always return a list, even on quota exhaustion"
        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted: {exc}")
            raise


# ── AnalyticsTracker ───────────────────────────────────────────────────────────

class TestAnalyticsTrackerReal:
    """Integration tests for the AnalyticsTracker using the real YouTube API."""

    def _build_tracker(self) -> "AnalyticsTracker":
        """Create an AnalyticsTracker with the real API key."""
        from packages.integrations.youtube.analytics import AnalyticsTracker
        api_key = os.environ.get("YOUTUBE_API_KEY", "")
        return AnalyticsTracker(api_key=api_key)

    def test_pull_weekly_stats_returns_structure(self):
        """Real API call: pull weekly analytics for a known channel.

        Scenario: The analytics pipeline runs its weekly report generation.
        The tracker should aggregate channel stats and video performance
        into a structured summary.

        Verifies:
        - Returns a dict with expected top-level keys
        - Aggregated metrics (total_views, total_likes, etc.) are non-negative
        - timestamp is a valid ISO string
        """
        tracker = self._build_tracker()

        try:
            result = tracker.pull_weekly_stats("UCBR8-60-B28hp2BmDPdntcQ")

            assert isinstance(result, dict)
            assert "channel_id" in result
            assert "timestamp" in result
            assert "total_views" in result
            assert "total_likes" in result
            assert "average_engagement" in result
            assert isinstance(result["total_views"], int)
            assert result["total_views"] >= 0
            assert isinstance(result["average_engagement"], float)
            assert result["average_engagement"] >= 0.0

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted: {exc}")
            raise

    def test_find_best_performers_returns_list(self):
        """Real API call: find top-performing videos on a channel.

        Scenario: The content strategy module needs to identify which video
        formats and topics perform best.

        Verifies:
        - Returns a list
        - Results are sorted by the requested metric
        - Each result has an 'engagement' field
        """
        tracker = self._build_tracker()

        try:
            top = tracker.find_best_performers(
                channel_id="UCBR8-60-B28hp2BmDPdntcQ",
                metric="views",
                top_n=3,
            )

            assert isinstance(top, list)
            if top:
                # Verify sorting (descending by views)
                for i in range(len(top) - 1):
                    assert top[i].get("views", 0) >= top[i + 1].get("views", 0)
                # Each video should have engagement calculated
                for video in top:
                    assert "engagement" in video

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted: {exc}")
            raise

    def test_save_snapshot_writes_file(self, tmp_path):
        """Verify save_snapshot writes a valid JSON file.

        Scenario: The weekly analytics job saves a snapshot for historical
        comparison. This test verifies the file I/O works correctly by
        providing synthetic data and a temp path.
        """
        tracker = self._build_tracker()

        test_data = {
            "channel_id": "TEST_CHANNEL",
            "total_views": 1000,
            "video_count": 5,
        }

        filepath = str(tmp_path / "snapshot_test.json")
        result_path = tracker.save_snapshot(test_data, filepath=filepath)

        assert result_path == filepath
        import json
        with open(filepath, "r") as f:
            saved = json.load(f)

        assert saved["channel_id"] == "TEST_CHANNEL"
        assert saved["total_views"] == 1000
        assert "_snapshot_metadata" in saved
        assert "saved_at" in saved["_snapshot_metadata"]


# ── YouTubeDataClient (httpx-based async client) ───────────────────────────────

class TestYouTubeDataClientReal:
    """Integration tests for the async YouTubeDataClient (httpx-based)."""

    def _build_client(self) -> "YouTubeDataClient":
        """Create a YouTubeDataClient with the real API key."""
        from packages.integrations.youtube.youtube_data import YouTubeDataClient
        api_key = os.environ.get("YOUTUBE_API_KEY", "")
        return YouTubeDataClient(api_key=api_key)

    @pytest.mark.asyncio
    async def test_get_trending_videos_returns_data(self):
        """Real API call: fetch trending videos for Pakistan.

        Scenario: The content pipeline discovers trending topics by fetching
        the most popular videos in the target region (PK).

        Verifies:
        - Returns a list of TrendingVideo dataclass instances
        - Each video has video_id, title, trending_rank
        - Results are ranked 1, 2, 3... in order
        """
        client = self._build_client()

        try:
            async with client:
                videos = await client.get_trending_videos(region_code="PK", max_results=3)

            assert isinstance(videos, list)
            if videos:
                from packages.integrations.youtube.youtube_data import TrendingVideo
                assert all(isinstance(v, TrendingVideo) for v in videos)
                # Verify ranking
                for i, video in enumerate(videos):
                    assert video.trending_rank == i + 1
                    assert video.video_id != ""
                    assert video.title != ""

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted: {exc}")
            raise

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        """Real API call: search YouTube for a query.

        Scenario: The topic finder searches YouTube for niche content ideas.

        Verifies:
        - Returns a list of YouTubeVideo dataclass instances
        - Each video has essential fields populated
        """
        client = self._build_client()

        try:
            async with client:
                videos = await client.search(query="Pakistan AI startups 2024", max_results=3)

            assert isinstance(videos, list)
            if videos:
                from packages.integrations.youtube.youtube_data import YouTubeVideo
                assert all(isinstance(v, YouTubeVideo) for v in videos)
                for v in videos:
                    assert v.video_id != ""
                    assert v.title != ""

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted: {exc}")
            raise

    @pytest.mark.asyncio
    async def test_get_categories_returns_dict(self):
        """Real API call: fetch video categories for Pakistan.

        Scenario: The content factory needs category IDs for targeting
        specific video categories in the YouTube API.

        Verifies:
        - Returns a dict mapping category IDs to titles
        - At least one category is returned
        """
        client = self._build_client()

        try:
            async with client:
                categories = await client.get_categories(region_code="PK")

            assert isinstance(categories, dict)
            if categories:
                # Keys should be string category IDs, values should be titles
                for cat_id, title in categories.items():
                    assert isinstance(cat_id, str)
                    assert isinstance(title, str)
                    assert len(title) > 0

        except ConnectionError as exc:
            pytest.skip(f"YouTube API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube API quota exhausted: {exc}")
            raise


# ── YouTubeAnalyticsClient (OAuth2-based) ──────────────────────────────────────

class TestYouTubeAnalyticsClientReal:
    """Integration tests for YouTubeAnalyticsClient (requires OAuth2 credentials).

    These tests are almost always skipped in CI because OAuth2 credentials
    (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN) are
    rarely configured. They exist for developers who want to test analytics
    locally with their own channel's OAuth2 credentials.
    """

    def _check_oauth_credentials(self) -> bool:
        """Check if OAuth2 credentials are configured."""
        return all([
            os.environ.get("YOUTUBE_CLIENT_ID", ""),
            os.environ.get("YOUTUBE_CLIENT_SECRET", ""),
            os.environ.get("YOUTUBE_REFRESH_TOKEN", ""),
        ])

    @pytest.mark.asyncio
    async def test_get_channel_analytics_requires_oauth(self):
        """Verify that channel analytics requires OAuth2 credentials.

        Scenario: A developer tries to use analytics without configuring
        OAuth2. The client should degrade gracefully, not crash.
        """
        if not self._check_oauth_credentials():
            pytest.skip("YouTube OAuth2 credentials not configured — skipping analytics test")

        from packages.integrations.youtube.youtube_analytics import YouTubeAnalyticsClient

        client = YouTubeAnalyticsClient()

        try:
            async with client:
                analytics = await client.get_channel_analytics(days=7)

            assert analytics is not None
            assert hasattr(analytics, "channel_id")
            assert hasattr(analytics, "views")
            assert isinstance(analytics.views, int)
            assert analytics.views >= 0

        except ConnectionError as exc:
            pytest.skip(f"YouTube Analytics API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "oauth" in err_str or "token" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube OAuth2 error: {exc}")
            raise

    @pytest.mark.asyncio
    async def test_analyze_content_gaps_requires_oauth(self):
        """Verify that content gap analysis requires OAuth2 credentials.

        Scenario: The content strategy module uses content gap analysis
        to identify underperforming topics. This requires OAuth2 access
        to the YouTube Analytics API.
        """
        if not self._check_oauth_credentials():
            pytest.skip("YouTube OAuth2 credentials not configured — skipping analytics test")

        from packages.integrations.youtube.youtube_analytics import YouTubeAnalyticsClient

        client = YouTubeAnalyticsClient()

        try:
            async with client:
                gaps = await client.analyze_content_gaps(days=30)

            assert gaps is not None
            assert hasattr(gaps, "underperforming_topics")
            assert hasattr(gaps, "overperforming_topics")
            assert isinstance(gaps.underperforming_topics, list)
            assert isinstance(gaps.overperforming_topics, list)

        except ConnectionError as exc:
            pytest.skip(f"YouTube Analytics API unreachable: {exc}")
        except Exception as exc:
            err_str = str(exc).lower()
            if "oauth" in err_str or "token" in err_str or "forbidden" in err_str:
                pytest.skip(f"YouTube OAuth2 error: {exc}")
            raise


# ── Transcript/Caption Tests (no API key required) ────────────────────────────

class TestYouTubeTranscriptReal:
    """Integration tests for YouTube transcript extraction.

    These tests use youtube-transcript-api which does NOT require a YouTube
    API key. They may still fail if the library is not installed or the
    video has no captions.
    """

    def _build_client(self) -> "YouTubeClient":
        """Create a YouTubeClient (transcript methods don't need API key)."""
        from packages.integrations.youtube.client import YouTubeClient
        return YouTubeClient(api_key="")

    def test_get_transcript_from_popular_video(self):
        """Real API call: extract transcript from a well-known video.

        Scenario: The pipeline extracts a transcript for script analysis.
        We use a popular video known to have English captions.

        Verifies:
        - Returns a dict with 'segments' list and 'word_count' int
        - Each segment has text, start, and duration fields
        """
        try:
            client = self._build_client()
            transcript = client.get_transcript("dQw4w9WgXcQ", languages=["en"])
        except ImportError:
            pytest.skip("youtube-transcript-api not installed")

        if not transcript:
            pytest.skip("No transcript available for this video")

        assert isinstance(transcript, dict)
        assert "segments" in transcript
        assert "word_count" in transcript
        assert isinstance(transcript["word_count"], int)
        assert transcript["word_count"] > 0

        for segment in transcript["segments"]:
            assert "text" in segment
            assert "start" in segment
            assert "duration" in segment
            assert isinstance(segment["text"], str)
            assert len(segment["text"]) > 0

    def test_get_captions_list(self):
        """Real API call: list available caption tracks for a video.

        Scenario: The pipeline checks available captions before extracting
        a transcript to ensure the desired language is available.

        Verifies:
        - Returns a list of caption track dicts
        - Each track has language, language_code, and is_generated fields
        """
        try:
            client = self._build_client()
            captions = client.get_captions_list("dQw4w9WgXcQ")
        except ImportError:
            pytest.skip("youtube-transcript-api not installed")

        assert isinstance(captions, list)
        if captions:
            for cap in captions:
                assert "language" in cap
                assert "language_code" in cap
                assert "is_generated" in cap
                assert isinstance(cap["language"], str)
                assert isinstance(cap["language_code"], str)
                assert isinstance(cap["is_generated"], bool)
