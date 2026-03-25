"""
YouTube Data API v3 Integration

Fetches trending videos and search results from YouTube.

API Documentation: https://developers.google.com/youtube/v3

Required scopes:
- None for public data (only API key needed)

Rate limits:
- 10,000 units/day (free tier)
- Each search costs 100 units
- Each videos.list costs 1 unit
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from packages.core.logger import get_logger

log = get_logger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class YouTubeVideo:
    """Represents a YouTube video."""
    video_id: str
    title: str
    description: str
    channel_title: str
    channel_id: str
    published_at: str
    view_count: int
    like_count: int
    comment_count: int
    thumbnail_url: str
    category_id: str
    tags: list[str]
    duration: str
    
    @property
    def url(self) -> str:
        return f"https://youtube.com/watch?v={self.video_id}"


@dataclass
class TrendingVideo(YouTubeVideo):
    """A trending video with additional metadata."""
    trending_rank: int = 0
    trending_region: str = ""
    fetched_at: str = ""


# ─── YouTube Data API Client ─────────────────────────────────────────────────────

class YouTubeDataClient:
    """
    Client for YouTube Data API v3.
    
    Usage:
        async with YouTubeDataClient(api_key) as client:
            trending = await client.get_trending_videos("PK")
            search_results = await client.search("Pakistan news")
    """
    
    BASE_URL = "https://www.googleapis.com/youtube/v3"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "")
        
        if not self.api_key:
            log.warning("youtube_api_key_not_set: API calls will fail")
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()
    
    async def _request(self, endpoint: str, params: dict) -> dict:
        """Make an API request."""
        params["key"] = self.api_key
        
        response = await self._client.get(
            f"{self.BASE_URL}/{endpoint}",
            params=params
        )
        
        if response.status_code == 403:
            # Check if quota exceeded
            error = response.json().get("error", {})
            if error.get("errors", [{}])[0].get("reason") == "quotaExceeded":
                raise QuotaExceededError("YouTube API quota exceeded")
            raise YouTubeAPIError(f"Forbidden: {error}")
        
        if response.status_code == 400:
            error = response.json().get("error", {})
            raise YouTubeAPIError(f"Bad request: {error}")
        
        response.raise_for_status()
        return response.json()
    
    # ─── Trending Videos ────────────────────────────────────────────────────────
    
    async def get_trending_videos(
        self,
        region_code: str = "PK",
        category_id: str = None,
        max_results: int = 50
    ) -> list[TrendingVideo]:
        """
        Get most popular (trending) videos for a region.
        
        Args:
            region_code: ISO 3166-1 alpha-2 country code (PK = Pakistan)
            category_id: Video category ID (0 = all categories)
            max_results: Maximum videos to return (1-50)
        
        Returns:
            List of TrendingVideo objects, ranked by popularity
        """
        params = {
            "part": "snippet,statistics,contentDetails",
            "chart": "mostPopular",
            "regionCode": region_code,
            "maxResults": max_results,
        }
        
        if category_id:
            params["videoCategoryId"] = category_id
        
        try:
            data = await self._request("videos", params)
            
            videos = []
            for i, item in enumerate(data.get("items", [])):
                video = self._parse_video(item)
                trending = TrendingVideo(
                    **video.__dict__,
                    trending_rank=i + 1,
                    trending_region=region_code,
                    fetched_at=datetime.now(timezone.utc).isoformat()
                )
                videos.append(trending)
            
            log.info(f"youtube_trending_fetched: {len(videos)} videos for {region_code}")
            return videos
            
        except Exception as e:
            log.error(f"youtube_trending_failed: {e}")
            return []
    
    # ─── Search ──────────────────────────────────────────────────────────────────
    
    async def search(
        self,
        query: str,
        max_results: int = 25,
        order: str = "relevance",
        video_duration: str = None,
        published_after: str = None,
        region_code: str = "PK"
    ) -> list[YouTubeVideo]:
        """
        Search for videos.
        
        Args:
            query: Search query
            max_results: Maximum results (1-50)
            order: Order by (relevance, date, viewCount, rating)
            video_duration: Filter by duration (short, medium, long)
            published_after: RFC 3339 datetime string
            region_code: Region for results
        
        Note:
            Search costs 100 quota units per call.
        """
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "order": order,
            "regionCode": region_code,
        }
        
        if video_duration:
            params["videoDuration"] = video_duration
        if published_after:
            params["publishedAfter"] = published_after
        
        try:
            data = await self._request("search", params)
            
            # Get video IDs
            video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
            
            if not video_ids:
                return []
            
            # Fetch full video details (to get statistics)
            videos = await self.get_videos_by_ids(video_ids)
            
            log.info(f"youtube_search_fetched: {len(videos)} videos for '{query[:30]}'")
            return videos
            
        except Exception as e:
            log.error(f"youtube_search_failed: {e}")
            return []
    
    async def get_videos_by_ids(self, video_ids: list[str]) -> list[YouTubeVideo]:
        """Get video details by IDs."""
        if not video_ids:
            return []
        
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids[:50]),  # Max 50 IDs
        }
        
        try:
            data = await self._request("videos", params)
            return [self._parse_video(item) for item in data.get("items", [])]
        except Exception as e:
            log.error(f"youtube_get_videos_failed: {e}")
            return []
    
    # ─── Categories ──────────────────────────────────────────────────────────────
    
    async def get_categories(self, region_code: str = "PK") -> dict[str, str]:
        """Get video categories for a region."""
        params = {
            "part": "snippet",
            "regionCode": region_code,
        }
        
        try:
            data = await self._request("videoCategories", params)
            return {
                item["id"]: item["snippet"]["title"]
                for item in data.get("items", [])
            }
        except Exception as e:
            log.error(f"youtube_categories_failed: {e}")
            return {}
    
    # ─── Channel Info ────────────────────────────────────────────────────────────
    
    async def get_channel_info(self, channel_id: str) -> Optional[dict]:
        """Get channel information."""
        params = {
            "part": "snippet,statistics",
            "id": channel_id,
        }
        
        try:
            data = await self._request("channels", params)
            items = data.get("items", [])
            if items:
                item = items[0]
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                return {
                    "channel_id": channel_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "subscriber_count": int(stats.get("subscriberCount", 0)),
                    "view_count": int(stats.get("viewCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                    "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                }
        except Exception as e:
            log.error(f"youtube_channel_info_failed: {e}")
        
        return None
    
    # ─── Helper Methods ──────────────────────────────────────────────────────────
    
    def _parse_video(self, item: dict) -> YouTubeVideo:
        """Parse a video item from API response."""
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        thumbnails = snippet.get("thumbnails", {})
        
        # Get best thumbnail
        thumbnail_url = (
            thumbnails.get("maxres", {}).get("url") or
            thumbnails.get("high", {}).get("url") or
            thumbnails.get("default", {}).get("url") or
            ""
        )
        
        return YouTubeVideo(
            video_id=item.get("id", ""),
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            channel_title=snippet.get("channelTitle", ""),
            channel_id=snippet.get("channelId", ""),
            published_at=snippet.get("publishedAt", ""),
            view_count=int(stats.get("viewCount", 0)),
            like_count=int(stats.get("likeCount", 0)),
            comment_count=int(stats.get("commentCount", 0)),
            thumbnail_url=thumbnail_url,
            category_id=snippet.get("categoryId", ""),
            tags=snippet.get("tags", []),
            duration=content.get("duration", ""),
        )


# ─── Exceptions ────────────────────────────────────────────────────────────────

class YouTubeAPIError(Exception):
    """YouTube API error."""
    pass


class QuotaExceededError(YouTubeAPIError):
    """YouTube API quota exceeded."""
    pass


# ─── Convenience Functions ──────────────────────────────────────────────────────

async def fetch_trending_for_region(region: str = "PK", max_results: int = 50) -> list[TrendingVideo]:
    """Convenience function to fetch trending videos."""
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        log.warning("youtube_api_key_not_configured")
        return []
    
    async with YouTubeDataClient(api_key) as client:
        return await client.get_trending_videos(region, max_results=max_results)


async def search_youtube(query: str, max_results: int = 25) -> list[YouTubeVideo]:
    """Convenience function to search YouTube."""
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        log.warning("youtube_api_key_not_configured")
        return []
    
    async with YouTubeDataClient(api_key) as client:
        return await client.search(query, max_results=max_results)
