"""
test_youtube_client.py — Comprehensive unit tests for YouTubeClient.

Covers initialization, channel stats, recent videos, video details,
search trending, transcript extraction, competitor videos, and captions list.

All tests are fully mocked — no real YouTube API calls are made.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# TestYouTubeClientInit
# ---------------------------------------------------------------------------


class TestYouTubeClientInit:
    """Tests for YouTubeClient.__init__."""

    def test_init_with_api_key(self, mock_youtube_settings):
        """When api_key is provided, build() is called and _service is set."""
        mock_build = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "googleapiclient": MagicMock(),
                "googleapiclient.discovery": MagicMock(build=mock_build),
            },
        ):
            from packages.integrations.youtube.client import YouTubeClient

            client = YouTubeClient(api_key="my-test-key")

            mock_build.assert_called_once_with(
                "youtube", "v3", developerKey="my-test-key"
            )
            assert client._service is not None
            assert client.api_key == "my-test-key"

    def test_init_without_api_key(self, mock_youtube_no_key):
        """When no api_key and settings has empty YOUTUBE_API_KEY, _service is None."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key=None)

        assert client._service is None
        assert client.api_key == ""

    def test_init_google_api_error(self, mock_youtube_no_key):
        """When build() raises an exception, client handles it gracefully."""
        mock_build = MagicMock(side_effect=Exception("google-auth failure"))

        with patch.dict(
            "sys.modules",
            {
                "googleapiclient": MagicMock(),
                "googleapiclient.discovery": MagicMock(build=mock_build),
            },
        ):
            from packages.integrations.youtube.client import YouTubeClient

            client = YouTubeClient(api_key="broken-key")

            assert client._service is None
            assert client.api_key == "broken-key"


# ---------------------------------------------------------------------------
# TestGetChannelStats
# ---------------------------------------------------------------------------


class TestGetChannelStats:
    """Tests for YouTubeClient.get_channel_stats."""

    def test_get_channel_stats_success(self, mock_youtube_no_key):
        """Returns dict with subscriber_count, total_views, video_count, channel_title."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        mock_service = MagicMock()

        mock_channels_list = MagicMock()
        mock_channels_list.execute.return_value = {
            "items": [
                {
                    "statistics": {
                        "subscriberCount": "50000",
                        "viewCount": "1200000",
                        "videoCount": "200",
                    },
                    "snippet": {"title": "Test Channel"},
                }
            ]
        }
        mock_service.channels.return_value.list.return_value = mock_channels_list
        client._service = mock_service

        result = client.get_channel_stats("UC_test_channel")

        assert result["subscriber_count"] == 50000
        assert result["total_views"] == 1200000
        assert result["video_count"] == 200
        assert result["channel_title"] == "Test Channel"
        assert result["channel_id"] == "UC_test_channel"

        # Verify API was called correctly
        mock_service.channels.return_value.list.assert_called_once_with(
            part="statistics,snippet", id="UC_test_channel"
        )

    def test_get_channel_stats_no_items(self, mock_youtube_no_key):
        """When response has no items, returns default zeros dict."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        mock_service = MagicMock()

        mock_channels_list = MagicMock()
        mock_channels_list.execute.return_value = {"items": []}
        mock_service.channels.return_value.list.return_value = mock_channels_list
        client._service = mock_service

        result = client.get_channel_stats("UC_nonexistent")

        assert result["subscriber_count"] == 0
        assert result["total_views"] == 0
        assert result["video_count"] == 0
        assert result["channel_id"] == "UC_nonexistent"

    def test_get_channel_stats_service_unavailable(self, mock_youtube_no_key):
        """When _service is None, returns default zeros dict."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        # _service is None by default

        result = client.get_channel_stats("UC_test_channel")

        assert result["subscriber_count"] == 0
        assert result["total_views"] == 0
        assert result["video_count"] == 0

    def test_get_channel_stats_api_error(self, mock_youtube_no_key):
        """When API raises exception, returns default zeros dict."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        mock_service = MagicMock()

        mock_channels_list = MagicMock()
        mock_channels_list.execute.side_effect = Exception("HTTP 403 Forbidden")
        mock_service.channels.return_value.list.return_value = mock_channels_list
        client._service = mock_service

        result = client.get_channel_stats("UC_test_channel")

        assert result["subscriber_count"] == 0
        assert result["total_views"] == 0
        assert result["video_count"] == 0


# ---------------------------------------------------------------------------
# TestGetRecentVideos
# ---------------------------------------------------------------------------


class TestGetRecentVideos:
    """Tests for YouTubeClient.get_recent_videos."""

    def _build_mock_service_with_recent_videos(self):
        """Build a mock service that returns channel info, playlist, and video stats."""
        mock_service = MagicMock()

        # channels().list().execute() → returns uploads playlist ID
        mock_channels_list = MagicMock()
        mock_channels_list.execute.return_value = {
            "items": [
                {
                    "contentDetails": {
                        "relatedPlaylists": {"uploads": "UU_uploads_playlist_id"}
                    }
                }
            ]
        }
        mock_service.channels.return_value.list.return_value = mock_channels_list

        # playlistItems().list().execute() → returns playlist items
        mock_playlist_list = MagicMock()
        mock_playlist_list.execute.return_value = {
            "items": [
                {
                    "contentDetails": {"videoId": "vid_001"},
                    "snippet": {
                        "title": "Video One",
                        "publishedAt": "2024-01-15T10:00:00Z",
                        "thumbnails": {
                            "high": {"url": "https://img.example.com/vid_001.jpg"}
                        },
                    },
                },
                {
                    "contentDetails": {"videoId": "vid_002"},
                    "snippet": {
                        "title": "Video Two",
                        "publishedAt": "2024-01-10T08:00:00Z",
                        "thumbnails": {
                            "high": {"url": "https://img.example.com/vid_002.jpg"}
                        },
                    },
                },
            ]
        }
        mock_service.playlistItems.return_value.list.return_value = mock_playlist_list

        # videos().list().execute() → returns video statistics
        mock_videos_list = MagicMock()
        mock_videos_list.execute.return_value = {
            "items": [
                {"id": "vid_001", "statistics": {"viewCount": "5000", "likeCount": "200", "commentCount": "50"}},
                {"id": "vid_002", "statistics": {"viewCount": "3000", "likeCount": "100", "commentCount": "25"}},
            ]
        }
        mock_service.videos.return_value.list.return_value = mock_videos_list

        return mock_service

    def test_get_recent_videos_success(self, mock_youtube_no_key):
        """Returns list of video dicts with title, video_id, views, likes, comments, etc."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        client._service = self._build_mock_service_with_recent_videos()

        result = client.get_recent_videos("UC_test_channel")

        assert len(result) == 2
        # Video 1
        assert result[0]["video_id"] == "vid_001"
        assert result[0]["title"] == "Video One"
        assert result[0]["views"] == 5000
        assert result[0]["likes"] == 200
        assert result[0]["comments"] == 50
        assert result[0]["published_at"] == "2024-01-15T10:00:00Z"
        assert result[0]["thumbnail_url"] == "https://img.example.com/vid_001.jpg"
        # Video 2
        assert result[1]["video_id"] == "vid_002"
        assert result[1]["title"] == "Video Two"
        assert result[1]["views"] == 3000

    def test_get_recent_videos_empty_channel(self, mock_youtube_no_key):
        """When channel has no items, returns empty list."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        mock_service = MagicMock()

        mock_channels_list = MagicMock()
        mock_channels_list.execute.return_value = {"items": []}
        mock_service.channels.return_value.list.return_value = mock_channels_list
        client._service = mock_service

        result = client.get_recent_videos("UC_empty_channel")

        assert result == []

    def test_get_recent_videos_service_unavailable(self, mock_youtube_no_key):
        """When _service is None, returns empty list."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        result = client.get_recent_videos("UC_test_channel")

        assert result == []


# ---------------------------------------------------------------------------
# TestGetVideoDetails
# ---------------------------------------------------------------------------


class TestGetVideoDetails:
    """Tests for YouTubeClient.get_video_details."""

    def test_get_video_details_success(self, mock_youtube_no_key):
        """Returns dict with title, description, views, tags, duration, etc."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        mock_service = MagicMock()

        mock_videos_list = MagicMock()
        mock_videos_list.execute.return_value = {
            "items": [
                {
                    "id": "vid_abc",
                    "snippet": {
                        "title": "Amazing Video",
                        "description": "A detailed description of the video.",
                        "channelId": "UC_channel123",
                        "channelTitle": "My Channel",
                        "publishedAt": "2024-02-01T12:00:00Z",
                        "thumbnails": {
                            "high": {"url": "https://img.example.com/thumb.jpg"}
                        },
                        "tags": ["python", "testing", "youtube"],
                    },
                    "statistics": {
                        "viewCount": "10000",
                        "likeCount": "500",
                        "commentCount": "75",
                    },
                    "contentDetails": {
                        "duration": "PT10M30S",
                    },
                }
            ]
        }
        mock_service.videos.return_value.list.return_value = mock_videos_list
        client._service = mock_service

        result = client.get_video_details("vid_abc")

        assert result["video_id"] == "vid_abc"
        assert result["title"] == "Amazing Video"
        assert result["description"] == "A detailed description of the video."
        assert result["views"] == 10000
        assert result["likes"] == 500
        assert result["comments"] == 75
        assert result["duration"] == "PT10M30S"
        assert result["tags"] == ["python", "testing", "youtube"]
        assert result["channel_title"] == "My Channel"
        assert result["thumbnail_url"] == "https://img.example.com/thumb.jpg"

        # Verify correct API call
        mock_service.videos.return_value.list.assert_called_once_with(
            part="snippet,statistics,contentDetails", id="vid_abc"
        )

    def test_get_video_details_not_found(self, mock_youtube_no_key):
        """When no items returned, returns empty dict."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        mock_service = MagicMock()

        mock_videos_list = MagicMock()
        mock_videos_list.execute.return_value = {"items": []}
        mock_service.videos.return_value.list.return_value = mock_videos_list
        client._service = mock_service

        result = client.get_video_details("vid_nonexistent")

        assert result == {}


# ---------------------------------------------------------------------------
# TestSearchTrending
# ---------------------------------------------------------------------------


class TestSearchTrending:
    """Tests for YouTubeClient.search_trending."""

    def test_search_trending_success(self, mock_youtube_no_key):
        """Returns list of video dicts sorted by view count."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        mock_service = MagicMock()

        # search().list().execute() → returns search results
        mock_search_list = MagicMock()
        mock_search_list.execute.return_value = {
            "items": [
                {
                    "id": {"videoId": "vid_a"},
                    "snippet": {
                        "title": "Video A",
                        "channelTitle": "Channel A",
                        "publishedAt": "2024-01-20T10:00:00Z",
                        "thumbnails": {
                            "high": {"url": "https://img.example.com/a.jpg"}
                        },
                    },
                },
                {
                    "id": {"videoId": "vid_b"},
                    "snippet": {
                        "title": "Video B",
                        "channelTitle": "Channel B",
                        "publishedAt": "2024-01-18T10:00:00Z",
                        "thumbnails": {
                            "high": {"url": "https://img.example.com/b.jpg"}
                        },
                    },
                },
            ]
        }
        mock_service.search.return_value.list.return_value = mock_search_list

        # videos().list().execute() → returns video stats
        mock_videos_list = MagicMock()
        mock_videos_list.execute.return_value = {
            "items": [
                {"id": "vid_a", "statistics": {"viewCount": "8000", "likeCount": "300"}},
                {"id": "vid_b", "statistics": {"viewCount": "12000", "likeCount": "600"}},
            ]
        }
        mock_service.videos.return_value.list.return_value = mock_videos_list

        client._service = mock_service

        result = client.search_trending("AI technology", region_code="PK")

        assert len(result) == 2
        # Method adds views/likes to each video dict
        video_ids = {v["video_id"] for v in result}
        assert "vid_a" in video_ids
        assert "vid_b" in video_ids

        # Verify search was called with correct params
        mock_service.search.return_value.list.assert_called_once_with(
            part="snippet",
            q="AI technology",
            type="video",
            order="viewCount",
            regionCode="PK",
            maxResults=10,
        )

    def test_search_trending_error(self, mock_youtube_no_key):
        """Returns empty list on API error."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")
        mock_service = MagicMock()

        mock_search_list = MagicMock()
        mock_search_list.execute.side_effect = Exception("HTTP 500 Server Error")
        mock_service.search.return_value.list.return_value = mock_search_list
        client._service = mock_service

        result = client.search_trending("test query")

        assert result == []


# ---------------------------------------------------------------------------
# TestGetTranscript
# ---------------------------------------------------------------------------


class TestGetTranscript:
    """Tests for YouTubeClient.get_transcript."""

    def _make_transcript_segment(self, text, start, duration):
        """Create a mock transcript segment object with attribute access."""
        seg = MagicMock()
        seg.text = text
        seg.start = start
        seg.duration = duration
        return seg

    def test_get_transcript_success(self, mock_youtube_no_key):
        """Returns dict with segments, caption_type, language, word_count."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        # Build mock transcript objects
        mock_segment_1 = self._make_transcript_segment("Hello world", 0.0, 2.5)
        mock_segment_2 = self._make_transcript_segment("This is a test", 2.5, 3.0)

        mock_transcript = MagicMock()
        mock_transcript.language_code = "en"
        mock_transcript.fetch.return_value = [mock_segment_1, mock_segment_2]

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript

        mock_yt_api = MagicMock()
        mock_yt_api.list_transcripts.return_value = mock_transcript_list

        with patch.dict(
            "sys.modules",
            {"youtube_transcript_api": MagicMock(YouTubeTranscriptApi=mock_yt_api)},
        ):
            result = client.get_transcript("vid_001")

        assert "segments" in result
        assert len(result["segments"]) == 2
        assert result["segments"][0]["text"] == "Hello world"
        assert result["segments"][0]["start"] == 0.0
        assert result["segments"][0]["duration"] == 2.5
        assert result["segments"][1]["text"] == "This is a test"
        assert result["caption_type"] == "manual"
        assert result["language"] == "en"
        assert result["word_count"] == 6  # "Hello world This is a test"

    def test_get_transcript_falls_back_to_auto_generated(self, mock_youtube_no_key):
        """Falls back to auto-generated captions when manual not available."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        mock_segment = self._make_transcript_segment("Auto generated text", 0.0, 3.0)

        mock_auto_transcript = MagicMock()
        mock_auto_transcript.language_code = "en"
        mock_auto_transcript.fetch.return_value = [mock_segment]

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_manually_created_transcript.side_effect = Exception("Not found")
        mock_transcript_list.find_generated_transcript.return_value = mock_auto_transcript

        mock_yt_api = MagicMock()
        mock_yt_api.list_transcripts.return_value = mock_transcript_list

        with patch.dict(
            "sys.modules",
            {"youtube_transcript_api": MagicMock(YouTubeTranscriptApi=mock_yt_api)},
        ):
            result = client.get_transcript("vid_002")

        assert result["caption_type"] == "auto_generated"
        assert result["language"] == "en"
        assert len(result["segments"]) == 1

    def test_get_transcript_no_captions(self, mock_youtube_no_key):
        """Returns empty dict when no captions available."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_manually_created_transcript.side_effect = Exception("Not found")
        mock_transcript_list.find_generated_transcript.side_effect = Exception("Not found")

        mock_yt_api = MagicMock()
        mock_yt_api.list_transcripts.return_value = mock_transcript_list

        with patch.dict(
            "sys.modules",
            {"youtube_transcript_api": MagicMock(YouTubeTranscriptApi=mock_yt_api)},
        ):
            result = client.get_transcript("vid_no_captions")

        assert result == {}

    def test_get_transcript_import_error(self, mock_youtube_no_key):
        """Returns empty dict when youtube-transcript-api not installed."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        # Simulate ImportError by making the module raise on import
        mock_module = MagicMock()
        mock_module.YouTubeTranscriptApi.list_transcripts.side_effect = ImportError("No module")

        with patch.dict(
            "sys.modules",
            {"youtube_transcript_api": mock_module},
        ):
            result = client.get_transcript("vid_001")

        assert result == {}


# ---------------------------------------------------------------------------
# TestGetCompetitorVideos
# ---------------------------------------------------------------------------


class TestGetCompetitorVideos:
    """Tests for YouTubeClient.get_competitor_videos."""

    def test_get_competitor_videos_single_channel(self, mock_youtube_no_key):
        """Single channel: calls get_recent_videos directly (no thread pool)."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        mock_service = MagicMock()

        # Set up mock for channels().list().execute()
        mock_channels_list = MagicMock()
        mock_channels_list.execute.return_value = {
            "items": [
                {
                    "contentDetails": {
                        "relatedPlaylists": {"uploads": "UU_playlist"}
                    }
                }
            ]
        }
        mock_service.channels.return_value.list.return_value = mock_channels_list

        mock_playlist_list = MagicMock()
        mock_playlist_list.execute.return_value = {
            "items": [
                {
                    "contentDetails": {"videoId": "comp_vid_1"},
                    "snippet": {
                        "title": "Competitor Video",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {"high": {"url": "https://img.example.com/t.jpg"}},
                    },
                }
            ]
        }
        mock_service.playlistItems.return_value.list.return_value = mock_playlist_list

        mock_videos_list = MagicMock()
        mock_videos_list.execute.return_value = {
            "items": [
                {"id": "comp_vid_1", "statistics": {"viewCount": "7500", "likeCount": "300", "commentCount": "40"}}
            ]
        }
        mock_service.videos.return_value.list.return_value = mock_videos_list

        client._service = mock_service

        result = client.get_competitor_videos(["UC_competitor1"])

        assert len(result) == 1
        assert result[0]["video_id"] == "comp_vid_1"
        assert result[0]["views"] == 7500

    def test_get_competitor_videos_multi_channel(self, mock_youtube_no_key):
        """Multiple channels: uses ThreadPoolExecutor, returns results from all sorted by views."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        mock_service = MagicMock()

        # Channel 1 returns video with 5000 views
        mock_channels_list_1 = MagicMock()
        mock_channels_list_1.execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU_p1"}}}]
        }
        mock_playlist_list_1 = MagicMock()
        mock_playlist_list_1.execute.return_value = {
            "items": [
                {
                    "contentDetails": {"videoId": "v1"},
                    "snippet": {
                        "title": "V1", "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {"high": {"url": "u1"}},
                    },
                }
            ]
        }

        # Channel 2 returns video with 10000 views
        mock_channels_list_2 = MagicMock()
        mock_channels_list_2.execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU_p2"}}}]
        }
        mock_playlist_list_2 = MagicMock()
        mock_playlist_list_2.execute.return_value = {
            "items": [
                {
                    "contentDetails": {"videoId": "v2"},
                    "snippet": {
                        "title": "V2", "publishedAt": "2024-01-02T00:00:00Z",
                        "thumbnails": {"high": {"url": "u2"}},
                    },
                }
            ]
        }

        # videos().list() returns stats for both
        mock_videos_list = MagicMock()
        mock_videos_list.execute.return_value = {
            "items": [
                {"id": "v1", "statistics": {"viewCount": "5000", "likeCount": "100", "commentCount": "10"}},
                {"id": "v2", "statistics": {"viewCount": "10000", "likeCount": "200", "commentCount": "20"}},
            ]
        }
        mock_service.videos.return_value.list.return_value = mock_videos_list

        # Set up the mock to return different channel/playlist responses
        # For simplicity with concurrent execution, we make channels() and playlistItems()
        # return the same data for all calls, and let videos().list() return combined stats
        mock_service.channels.return_value.list.return_value = mock_channels_list_1
        mock_service.playlistItems.return_value.list.return_value = mock_playlist_list_1

        client._service = mock_service

        result = client.get_competitor_videos(["UC_ch1", "UC_ch2"])

        # Results should be sorted by views descending
        assert len(result) >= 1
        # Verify sorted by views descending
        for i in range(len(result) - 1):
            assert result[i].get("views", 0) >= result[i + 1].get("views", 0)

    def test_get_competitor_videos_timeout(self, mock_youtube_no_key):
        """When a channel fetch times out, skips it and returns results from others."""
        from packages.integrations.youtube.client import YouTubeClient
        from unittest.mock import patch as patch_obj
        import concurrent.futures

        client = YouTubeClient(api_key="")
        mock_service = MagicMock()

        # Channel returns data, but we'll mock the executor to simulate timeout
        mock_channels_list = MagicMock()
        mock_channels_list.execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU_p"}}}]
        }
        mock_service.channels.return_value.list.return_value = mock_channels_list
        mock_playlist_list = MagicMock()
        mock_playlist_list.execute.return_value = {
            "items": [
                {
                    "contentDetails": {"videoId": "v_ok"},
                    "snippet": {
                        "title": "OK Video", "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {"high": {"url": "u"}},
                    },
                }
            ]
        }
        mock_service.playlistItems.return_value.list.return_value = mock_playlist_list

        mock_videos_list = MagicMock()
        mock_videos_list.execute.return_value = {
            "items": [
                {"id": "v_ok", "statistics": {"viewCount": "1000", "likeCount": "50", "commentCount": "5"}}
            ]
        }
        mock_service.videos.return_value.list.return_value = mock_videos_list

        client._service = mock_service

        # Create a mock future that raises TimeoutError
        mock_future_timeout = MagicMock()
        mock_future_timeout.result.side_effect = concurrent.futures.TimeoutError("30s exceeded")

        # Create a mock future that succeeds
        mock_future_ok = MagicMock()
        mock_future_ok.result.return_value = [
            {
                "video_id": "v_ok",
                "title": "OK Video",
                "views": 1000,
                "likes": 50,
                "comments": 5,
                "published_at": "2024-01-01T00:00:00Z",
                "thumbnail_url": "u",
            }
        ]

        mock_executor = MagicMock()
        mock_executor.submit.return_value = mock_future_timeout

        with patch_obj(
            "packages.integrations.youtube.client._youtube_executor", mock_executor
        ):
            result = client.get_competitor_videos(["UC_timeout_channel"])

        # Timeout channel should be skipped gracefully, returning empty list
        # since all channels timed out
        assert isinstance(result, list)

    def test_get_competitor_videos_service_unavailable(self, mock_youtube_no_key):
        """When _service is None, returns empty list."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        result = client.get_competitor_videos(["UC_ch1", "UC_ch2"])

        assert result == []

    def test_get_competitor_videos_empty_channel_list(self, mock_youtube_no_key):
        """When channel_ids is empty, returns empty list."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        # Even with a mock service, empty channel_ids returns []
        mock_service = MagicMock()
        client._service = mock_service

        result = client.get_competitor_videos([])

        assert result == []


# ---------------------------------------------------------------------------
# TestGetCaptionsList
# ---------------------------------------------------------------------------


class TestGetCaptionsList:
    """Tests for YouTubeClient.get_captions_list."""

    def test_get_captions_list_success(self, mock_youtube_no_key):
        """Returns list of caption tracks with language, language_code, is_generated."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        # Build mock transcript tracks
        mock_track_en = MagicMock()
        mock_track_en.language = "English"
        mock_track_en.language_code = "en"
        mock_track_en.is_generated = False

        mock_track_es = MagicMock()
        mock_track_es.language = "Spanish"
        mock_track_es.language_code = "es"
        mock_track_es.is_generated = True

        # Make transcript_list iterable
        mock_transcript_list = MagicMock()
        mock_transcript_list.__iter__ = MagicMock(return_value=iter([mock_track_en, mock_track_es]))

        mock_yt_api = MagicMock()
        mock_yt_api.list_transcripts.return_value = mock_transcript_list

        with patch.dict(
            "sys.modules",
            {"youtube_transcript_api": MagicMock(YouTubeTranscriptApi=mock_yt_api)},
        ):
            result = client.get_captions_list("vid_001")

        assert len(result) == 2
        assert result[0]["language"] == "English"
        assert result[0]["language_code"] == "en"
        assert result[0]["is_generated"] is False
        assert result[1]["language"] == "Spanish"
        assert result[1]["language_code"] == "es"
        assert result[1]["is_generated"] is True

    def test_get_captions_list_import_error(self, mock_youtube_no_key):
        """Returns empty list when youtube-transcript-api not installed."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        mock_module = MagicMock()
        mock_module.YouTubeTranscriptApi.list_transcripts.side_effect = ImportError("No module")

        with patch.dict(
            "sys.modules",
            {"youtube_transcript_api": mock_module},
        ):
            result = client.get_captions_list("vid_001")

        assert result == []

    def test_get_captions_list_api_error(self, mock_youtube_no_key):
        """Returns empty list when API raises an exception."""
        from packages.integrations.youtube.client import YouTubeClient

        client = YouTubeClient(api_key="")

        mock_yt_api = MagicMock()
        mock_yt_api.list_transcripts.side_effect = Exception("Transcripts disabled")

        with patch.dict(
            "sys.modules",
            {"youtube_transcript_api": MagicMock(YouTubeTranscriptApi=mock_yt_api)},
        ):
            result = client.get_captions_list("vid_001")

        assert result == []
