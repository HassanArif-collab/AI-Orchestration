"""YouTube Data API client for AI Orchestration system.

This client provides methods for interacting with the YouTube Data API v3
with graceful degradation - all methods return empty/default values when
the API is unavailable or not configured.

P2-08: Added concurrent fetching for competitor videos to avoid N+1 pattern.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from packages.core.config import get_settings
from packages.core.errors import IntegrationError
from packages.core.logger import get_logger

logger = get_logger(__name__)

# Thread pool for concurrent sync API calls
_youtube_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="youtube_")


class YouTubeClient:
    """Client for YouTube Data API v3 operations with graceful degradation.

    All methods return empty/default values when the YouTube API is unavailable
    or when the API key is not configured. This ensures the pipeline continues
    even if YouTube API is down or not configured.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the YouTube client.

        Args:
            api_key: Optional YouTube API key. If not provided, falls back to
                settings.YOUTUBE_API_KEY. If no key is available, the client
                will operate in degraded mode (all methods return defaults).
        """
        # Use api_key if explicitly provided (even empty string = degraded mode).
        # Fall back to settings only when no argument is passed (api_key is None).
        self.api_key = api_key if api_key is not None else get_settings().YOUTUBE_API_KEY
        self._service = None

        if self.api_key:
            try:
                from googleapiclient.discovery import build

                self._service = build("youtube", "v3", developerKey=self.api_key)
            except Exception as e:
                logger.warning(f"youtube_init_failed: {e}")
                self._service = None
        else:
            logger.debug("YouTube API key not configured, operating in degraded mode")

    def _check_service(self) -> bool:
        """Check if the YouTube service is available.

        Returns:
            True if service is available, False otherwise.
        """
        if not self._service:
            logger.warning("youtube_unavailable")
            return False
        return True

    def get_channel_stats(self, channel_id: str) -> dict:
        """Get statistics for a YouTube channel.

        Args:
            channel_id: The YouTube channel ID.

        Returns:
            Dictionary with subscriber_count, total_views, video_count.
            Returns default zeros on failure.
        """
        default_result = {
            "subscriber_count": 0,
            "total_views": 0,
            "video_count": 0,
            "channel_id": channel_id,
        }

        if not self._check_service():
            return default_result

        try:
            response = (
                self._service.channels()
                .list(part="statistics,snippet", id=channel_id)
                .execute()
            )

            if not response.get("items"):
                logger.warning(f"youtube_channel_not_found: {channel_id}")
                return default_result

            item = response["items"][0]
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})

            return {
                "channel_id": channel_id,
                "channel_title": snippet.get("title", ""),
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "total_views": int(stats.get("viewCount", 0)),
                "video_count": int(stats.get("videoCount", 0)),
            }
        except Exception as e:
            logger.warning(f"youtube_error in get_channel_stats: {e}")
            return default_result

    def get_recent_videos(
        self,
        channel_id: str,
        max_results: int = 20,
    ) -> list[dict]:
        """Get recent videos from a channel.

        Args:
            channel_id: The YouTube channel ID.
            max_results: Maximum number of videos to retrieve.

        Returns:
            List of video dictionaries, or empty list on failure.
            Each video contains: title, video_id, views, likes, comments,
            published_at, thumbnail_url.
        """
        if not self._check_service():
            return []

        try:
            # First get the uploads playlist ID
            channels_response = (
                self._service.channels()
                .list(part="contentDetails", id=channel_id)
                .execute()
            )

            if not channels_response.get("items"):
                logger.warning(f"youtube_channel_not_found: {channel_id}")
                return []

            uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

            # Get videos from uploads playlist
            playlist_response = (
                self._service.playlistItems()
                .list(
                    part="contentDetails,snippet",
                    playlistId=uploads_playlist_id,
                    maxResults=max_results,
                )
                .execute()
            )

            videos = []
            video_ids = []

            for item in playlist_response.get("items", []):
                video_id = item["contentDetails"]["videoId"]
                video_ids.append(video_id)
                videos.append({
                    "video_id": video_id,
                    "title": item["snippet"].get("title", ""),
                    "published_at": item["snippet"].get("publishedAt", ""),
                    "thumbnail_url": (
                        item["snippet"]
                        .get("thumbnails", {})
                        .get("high", {})
                        .get("url", "")
                    ),
                })

            # Get video statistics in batch
            if video_ids:
                videos_response = (
                    self._service.videos()
                    .list(part="statistics", id=",".join(video_ids))
                    .execute()
                )

                stats_by_id = {}
                for item in videos_response.get("items", []):
                    stats_by_id[item["id"]] = item.get("statistics", {})

                for video in videos:
                    stats = stats_by_id.get(video["video_id"], {})
                    video["views"] = int(stats.get("viewCount", 0))
                    video["likes"] = int(stats.get("likeCount", 0))
                    video["comments"] = int(stats.get("commentCount", 0))

            return videos
        except Exception as e:
            logger.warning(f"youtube_error in get_recent_videos: {e}")
            return []

    def get_video_details(self, video_id: str) -> dict:
        """Get detailed information about a specific video.

        Args:
            video_id: The YouTube video ID.

        Returns:
            Dictionary with video details, or empty dict on failure.
        """
        if not self._check_service():
            return {}

        try:
            response = (
                self._service.videos()
                .list(part="snippet,statistics,contentDetails", id=video_id)
                .execute()
            )

            if not response.get("items"):
                logger.warning(f"youtube_video_not_found: {video_id}")
                return {}

            item = response["items"][0]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content_details = item.get("contentDetails", {})

            return {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel_id": snippet.get("channelId", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "duration": content_details.get("duration", ""),
                "thumbnail_url": (
                    snippet.get("thumbnails", {})
                    .get("high", {})
                    .get("url", "")
                ),
                "tags": snippet.get("tags", []),
            }
        except Exception as e:
            logger.warning(f"youtube_error in get_video_details: {e}")
            return {}

    def search_trending(
        self,
        query: str,
        region_code: str = "PK",
        max_results: int = 10,
    ) -> list[dict]:
        """Search for trending videos matching a query.

        Args:
            query: Search query.
            region_code: Region code for trending videos (default: PK for Pakistan).
            max_results: Maximum number of results.

        Returns:
            List of video dictionaries, or empty list on failure.
        """
        if not self._check_service():
            return []

        try:
            response = (
                self._service.search()
                .list(
                    part="snippet",
                    q=query,
                    type="video",
                    order="viewCount",
                    regionCode=region_code,
                    maxResults=max_results,
                )
                .execute()
            )

            videos = []
            video_ids = []

            for item in response.get("items", []):
                video_id = item["id"]["videoId"]
                video_ids.append(video_id)
                snippet = item["snippet"]
                videos.append({
                    "video_id": video_id,
                    "title": snippet.get("title", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "thumbnail_url": (
                        snippet.get("thumbnails", {})
                        .get("high", {})
                        .get("url", "")
                    ),
                })

            # Get video statistics
            if video_ids:
                stats_response = (
                    self._service.videos()
                    .list(part="statistics", id=",".join(video_ids))
                    .execute()
                )

                stats_by_id = {}
                for item in stats_response.get("items", []):
                    stats_by_id[item["id"]] = item.get("statistics", {})

                for video in videos:
                    stats = stats_by_id.get(video["video_id"], {})
                    video["views"] = int(stats.get("viewCount", 0))
                    video["likes"] = int(stats.get("likeCount", 0))

            return videos
        except Exception as e:
            logger.warning(f"youtube_error in search_trending: {e}")
            return []

    def get_transcript(
        self,
        video_id: str,
        languages: list[str] | None = None,
    ) -> dict:
        """Extract timestamped transcript from a YouTube video.

        Uses youtube-transcript-api (does not require YouTube Data API key).
        Falls back to auto-generated captions if manual captions unavailable.
        Supports both v0.x (static methods) and v1.x (instance methods) of
        the library since v1.2.0 removed the old static API entirely.

        Args:
            video_id: The YouTube video ID.
            languages: Preferred languages in order (default: ['en']).

        Returns:
            Dictionary with:
                - segments: list of {text, start, duration} dicts
                - caption_type: 'manual' or 'auto_generated'
                - language: language code of the transcript used
                - word_count: total word count
            Returns empty dict on failure.
        """
        if languages is None:
            languages = ["en"]

        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            # v1.x uses instance methods (v1.2.0+ removed static methods entirely)
            # v0.x used static methods: YouTubeTranscriptApi.list_transcripts(video_id)
            _api = YouTubeTranscriptApi()
            use_v1_api = hasattr(_api, 'list') and not hasattr(YouTubeTranscriptApi, 'list_transcripts')

            if use_v1_api:
                # v1.x API: YouTubeTranscriptApi().list(video_id) → .find_*() → .fetch()
                transcript_list = _api.list(video_id)
            else:
                # v0.x API: YouTubeTranscriptApi.list_transcripts(video_id)
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try manual captions first, then auto-generated
            caption_type = "manual"
            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
            except Exception:
                try:
                    transcript = transcript_list.find_generated_transcript(languages)
                    caption_type = "auto_generated"
                except Exception:
                    logger.warning(f"youtube_no_transcript: {video_id} — no captions in {languages}")
                    return {}

            # Fetch the actual transcript data
            if use_v1_api:
                # v1.x: transcript.fetch() returns FetchedTranscript (iterable dataclass)
                fetched = transcript.fetch()
                segment_list = [
                    {
                        "text": seg.text if hasattr(seg, 'text') else seg.get("text", ""),
                        "start": seg.start if hasattr(seg, 'start') else seg.get("start", 0.0),
                        "duration": seg.duration if hasattr(seg, 'duration') else seg.get("duration", 0.0),
                    }
                    for seg in fetched
                ]
                lang_code = getattr(fetched, 'language_code', languages[0])
            else:
                # v0.x: transcript.fetch() returns a list of dicts
                segments = transcript.fetch()
                segment_list = [
                    {
                        "text": seg.text if hasattr(seg, 'text') else seg.get("text", ""),
                        "start": seg.start if hasattr(seg, 'start') else seg.get("start", 0.0),
                        "duration": seg.duration if hasattr(seg, 'duration') else seg.get("duration", 0.0),
                    }
                    for seg in segments
                ]
                lang_code = getattr(transcript, 'language_code', languages[0])

            full_text = " ".join(s["text"] for s in segment_list)
            word_count = len(full_text.split())

            return {
                "segments": segment_list,
                "caption_type": caption_type,
                "language": lang_code,
                "word_count": word_count,
            }
        except ImportError:
            logger.warning("youtube_transcript_api not installed — run: pip install youtube-transcript-api")
            return {}
        except Exception as e:
            logger.warning(f"youtube_error in get_transcript: {e}")
            return {}

    def get_captions_list(self, video_id: str) -> list[dict]:
        """Check available caption tracks for a video.

        Args:
            video_id: The YouTube video ID.

        Returns:
            List of caption track dicts with language, language_code,
            and is_generated fields. Returns empty list on failure.
        """
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            _api = YouTubeTranscriptApi()
            use_v1_api = hasattr(_api, 'list') and not hasattr(YouTubeTranscriptApi, 'list_transcripts')

            if use_v1_api:
                transcript_list = _api.list(video_id)
            else:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            captions = []

            for transcript in transcript_list:
                captions.append({
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                })

            return captions
        except ImportError:
            logger.warning("youtube_transcript_api not installed")
            return []
        except Exception as e:
            logger.warning(f"youtube_error in get_captions_list: {e}")
            return []

    def get_competitor_videos(
        self,
        channel_ids: list[str],
        max_results: int = 10,
    ) -> list[dict]:
        """Get recent videos from competitor channels with concurrent fetching.

        P2-08: Uses concurrent fetching with ThreadPoolExecutor to avoid
        N+1 pattern when fetching from multiple channels.

        Args:
            channel_ids: List of competitor channel IDs.
            max_results: Maximum results per channel.

        Returns:
            List of video dictionaries from all channels, or empty list on failure.
        """
        if not self._check_service():
            return []

        if not channel_ids:
            return []

        all_videos = []

        # P2-08: Use concurrent fetching for multiple channels
        if len(channel_ids) == 1:
            # Single channel - no need for concurrency
            all_videos = self.get_recent_videos(channel_ids[0], max_results=max_results)
        else:
            # Multiple channels - use concurrent fetching
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()

            # Run fetches in parallel using thread pool
            futures = [
                _youtube_executor.submit(self.get_recent_videos, channel_id, max_results)
                for channel_id in channel_ids
            ]

            # Collect results with timeout
            for future in futures:
                try:
                    videos = future.result(timeout=30.0)  # 30 second timeout per channel
                    if videos:
                        all_videos.extend(videos)
                except Exception as e:
                    logger.warning(f"youtube_competitor_fetch_error: {e}")
                    continue

        # Sort by views descending
        all_videos.sort(key=lambda v: v.get("views", 0), reverse=True)

        return all_videos

    async def get_competitor_videos_async(
        self,
        channel_ids: list[str],
        max_results: int = 10,
    ) -> list[dict]:
        """Async version of get_competitor_videos for use in async contexts.

        P2-08: Provides async interface for concurrent channel fetching.

        Args:
            channel_ids: List of competitor channel IDs.
            max_results: Maximum results per channel.

        Returns:
            List of video dictionaries from all channels, or empty list on failure.
        """
        if not self._check_service():
            return []

        if not channel_ids:
            return []

        all_videos = []

        # Run sync method in thread pool for async compatibility
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(
                _youtube_executor,
                self.get_recent_videos,
                channel_id,
                max_results
            )
            for channel_id in channel_ids
        ]

        # Wait for all futures concurrently
        results = await asyncio.gather(*futures, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"youtube_competitor_fetch_error: {result}")
                continue
            if result:
                all_videos.extend(result)

        # Sort by views descending
        all_videos.sort(key=lambda v: v.get("views", 0), reverse=True)

        return all_videos
