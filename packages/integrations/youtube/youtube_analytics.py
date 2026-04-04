"""
YouTube Analytics API Integration

Fetches analytics data for the user's own channel.

API Documentation: https://developers.google.com/youtube/analytics

Required OAuth2 scopes:
- https://www.googleapis.com/auth/yt-analytics.readonly
- https://www.googleapis.com/auth/yt-analytics-monetary.readonly (for revenue)

Authentication:
- Requires OAuth2 credentials (Client ID, Client Secret, Refresh Token)
- Not available with simple API key
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from packages.core.config import get_settings
from packages.core.logger import get_logger

log = get_logger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class VideoPerformance:
    """Performance metrics for a video."""
    video_id: str
    title: str = ""
    views: int = 0
    estimated_minutes_watched: int = 0
    average_view_duration: float = 0.0
    average_view_percentage: float = 0.0
    likes: int = 0
    dislikes: int = 0
    comments: int = 0
    shares: int = 0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    estimated_revenue: float = 0.0
    impression_count: int = 0
    impression_click_through_rate: float = 0.0
    thumbnail_url: str = ""
    published_at: str = ""


@dataclass
class ChannelAnalytics:
    """Overall channel analytics."""
    channel_id: str
    channel_name: str = ""
    
    # Time period
    start_date: str = ""
    end_date: str = ""
    
    # Aggregate metrics
    views: int = 0
    estimated_minutes_watched: int = 0
    average_view_duration: float = 0.0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    estimated_revenue: float = 0.0
    
    # Top videos
    top_videos: list[VideoPerformance] = field(default_factory=list)
    
    # Traffic sources
    traffic_sources: dict[str, int] = field(default_factory=dict)
    
    # Demographics
    age_distribution: dict[str, float] = field(default_factory=dict)
    gender_distribution: dict[str, float] = field(default_factory=dict)
    
    # Geography
    top_countries: dict[str, int] = field(default_factory=dict)


@dataclass
class ContentGapAnalysis:
    """Analysis of content gaps from channel performance."""
    underperforming_topics: list[str] = field(default_factory=list)
    overperforming_topics: list[str] = field(default_factory=list)
    suggested_topics: list[str] = field(default_factory=list)
    retention_drop_points: list[dict] = field(default_factory=list)


# ─── YouTube Analytics Client ────────────────────────────────────────────────────

class YouTubeAnalyticsClient:
    """
    Client for YouTube Analytics API.
    
    Requires OAuth2 authentication with refresh token.
    
    Usage:
        async with YouTubeAnalyticsClient(
            client_id="...",
            client_secret="...",
            refresh_token="..."
        ) as client:
            analytics = await client.get_channel_analytics(days=30)
            top_videos = await client.get_top_videos(days=30)
    """
    
    AUTH_URL = "https://oauth2.googleapis.com/token"
    BASE_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
    
    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        refresh_token: str = None
    ):
        self.client_id = client_id or get_settings().YOUTUBE_CLIENT_ID
        self.client_secret = client_secret or get_settings().YOUTUBE_CLIENT_SECRET
        self.refresh_token = refresh_token or get_settings().YOUTUBE_REFRESH_TOKEN
        
        self._access_token: str = ""
        self._token_expires: datetime = datetime.min.replace(tzinfo=timezone.utc)
        
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            log.warning("youtube_oauth_not_configured: analytics unavailable")
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()
    
    async def _ensure_access_token(self):
        """Get or refresh access token."""
        if self._access_token and datetime.now(timezone.utc) < self._token_expires:
            return
        
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise YouTubeAnalyticsError("OAuth credentials not configured")
        
        response = await self._client.post(
            self.AUTH_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
        )
        
        if response.status_code != 200:
            raise YouTubeAnalyticsError(f"Token refresh failed: {response.text}")
        
        data = response.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
        
        log.debug("youtube_access_token_refreshed")
    
    async def _request(self, params: dict) -> dict:
        """Make an API request."""
        await self._ensure_access_token()
        
        headers = {"Authorization": f"Bearer {self._access_token}"}
        
        response = await self._client.get(
            self.BASE_URL,
            params=params,
            headers=headers
        )
        
        if response.status_code == 401:
            # Token expired, refresh and retry
            self._access_token = ""
            await self._ensure_access_token()
            headers = {"Authorization": f"Bearer {self._access_token}"}
            response = await self._client.get(self.BASE_URL, params=params, headers=headers)
        
        if response.status_code == 403:
            error = response.json().get("error", {})
            raise YouTubeAnalyticsError(f"Forbidden: {error}")
        
        response.raise_for_status()
        return response.json()
    
    # ─── Main Analytics Methods ──────────────────────────────────────────────────
    
    async def get_channel_analytics(
        self,
        channel_id: str = None,
        days: int = 30
    ) -> ChannelAnalytics:
        """
        Get comprehensive channel analytics.
        
        Args:
            channel_id: Channel ID (uses 'mine' if not specified)
            days: Number of days to analyze
        """
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Basic metrics
        params = {
            "ids": channel_id if channel_id else "channel==MINE",
            "startDate": start_date,
            "endDate": end_date,
            "metrics": ",".join([
                "views",
                "estimatedMinutesWatched",
                "averageViewDuration",
                "subscribersGained",
                "subscribersLost",
                "estimatedRevenue"
            ]),
            "dimensions": "day",
            "sort": "day"
        }
        
        try:
            data = await self._request(params)
            column_headers = [h["name"] for h in data.get("columnHeaders", [])]
            rows = data.get("rows", [])
            
            # Aggregate metrics
            total_views = sum(row[0] for row in rows) if rows else 0
            total_minutes = sum(row[1] for row in rows) if rows else 0
            total_sub_gained = sum(row[3] for row in rows) if rows else 0
            total_sub_lost = sum(row[4] for row in rows) if rows else 0
            total_revenue = sum(row[5] for row in rows if len(row) > 5) if rows else 0
            
            avg_duration = total_minutes * 60 / total_views if total_views > 0 else 0
            
            analytics = ChannelAnalytics(
                channel_id=channel_id or "MINE",
                start_date=start_date,
                end_date=end_date,
                views=total_views,
                estimated_minutes_watched=total_minutes,
                average_view_duration=avg_duration,
                subscribers_gained=total_sub_gained,
                subscribers_lost=total_sub_lost,
                estimated_revenue=total_revenue
            )
            
            # Get top videos
            analytics.top_videos = await self.get_top_videos(days=days, max_results=10)
            
            # Get traffic sources
            analytics.traffic_sources = await self.get_traffic_sources(days=days)
            
            log.info(f"youtube_analytics_fetched: {total_views} views, {days} days")
            return analytics
            
        except Exception as e:
            log.error(f"youtube_analytics_failed: {e}")
            return ChannelAnalytics(channel_id=channel_id or "MINE")
    
    async def get_top_videos(
        self,
        days: int = 30,
        max_results: int = 10
    ) -> list[VideoPerformance]:
        """Get top performing videos."""
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        
        params = {
            "ids": "channel==MINE",
            "startDate": start_date,
            "endDate": end_date,
            "metrics": ",".join([
                "views",
                "estimatedMinutesWatched",
                "averageViewDuration",
                "averageViewPercentage",
                "likes",
                "comments",
                "subscribersGained",
                "subscribersLost"
            ]),
            "dimensions": "video",
            "sort": "-views",
            "maxResults": max_results
        }
        
        try:
            data = await self._request(params)
            rows = data.get("rows", [])
            
            videos = []
            for row in rows:
                videos.append(VideoPerformance(
                    video_id=row[0],
                    views=row[1],
                    estimated_minutes_watched=row[2],
                    average_view_duration=row[3],
                    average_view_percentage=row[4],
                    likes=row[5],
                    comments=row[6],
                    subscribers_gained=row[7],
                    subscribers_lost=row[8]
                ))
            
            return videos
            
        except Exception as e:
            log.error(f"youtube_top_videos_failed: {e}")
            return []
    
    async def get_traffic_sources(self, days: int = 30) -> dict[str, int]:
        """Get traffic source breakdown."""
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        
        params = {
            "ids": "channel==MINE",
            "startDate": start_date,
            "endDate": end_date,
            "metrics": "views",
            "dimensions": "insightTrafficSourceType",
            "sort": "-views"
        }
        
        try:
            data = await self._request(params)
            rows = data.get("rows", [])
            return {row[0]: row[1] for row in rows}
        except Exception as e:
            log.error(f"youtube_traffic_sources_failed: {e}")
            return {}
    
    async def get_video_retention(
        self,
        video_id: str
    ) -> list[dict]:
        """Get audience retention data for a video."""
        params = {
            "ids": "channel==MINE",
            "startDate": "2000-01-01",  # All time
            "endDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "metrics": "audienceWatchRatio",
            "dimensions": "elapsedVideoTimeRatio",
            "filters": f"video=={video_id}"
        }
        
        try:
            data = await self._request(params)
            rows = data.get("rows", [])
            
            retention = []
            for row in rows:
                retention.append({
                    "time_ratio": row[0],  # 0.0 to 1.0
                    "watch_ratio": row[1]  # Percentage still watching
                })
            
            return retention
            
        except Exception as e:
            log.error(f"youtube_retention_failed: {e}")
            return []
    
    async def analyze_content_gaps(
        self,
        days: int = 90
    ) -> ContentGapAnalysis:
        """
        Analyze channel performance to identify content gaps.
        
        Returns insights about:
        - Topics that underperformed
        - Topics that overperformed
        - Suggested new topics
        """
        top_videos = await self.get_top_videos(days=days, max_results=20)
        
        if not top_videos:
            return ContentGapAnalysis()
        
        # Calculate average performance
        avg_views = sum(v.views for v in top_videos) / len(top_videos)
        
        underperforming = []
        overperforming = []
        
        for video in top_videos:
            # Get video titles from YouTube Data API for topic extraction
            # For now, use video_id as placeholder
            if video.views < avg_views * 0.5:
                underperforming.append(video.video_id)
            elif video.views > avg_views * 1.5:
                overperforming.append(video.video_id)
        
        # Analyze retention patterns
        retention_drop_points = []
        for video in top_videos[:5]:  # Top 5 videos
            retention = await self.get_video_retention(video.video_id)
            
            # Find significant drops
            for i, point in enumerate(retention[1:], 1):
                prev = retention[i-1]
                drop = prev["watch_ratio"] - point["watch_ratio"]
                if drop > 0.1:  # 10% drop
                    retention_drop_points.append({
                        "video_id": video.video_id,
                        "time_ratio": point["time_ratio"],
                        "drop_percentage": drop * 100
                    })
        
        return ContentGapAnalysis(
            underperforming_topics=underperforming,
            overperforming_topics=overperforming,
            retention_drop_points=retention_drop_points
        )


# ─── Exceptions ────────────────────────────────────────────────────────────────

class YouTubeAnalyticsError(Exception):
    """YouTube Analytics API error."""
    pass


# ─── Convenience Functions ──────────────────────────────────────────────────────

async def get_my_channel_analytics(days: int = 30) -> ChannelAnalytics:
    """Convenience function to get channel analytics."""
    async with YouTubeAnalyticsClient() as client:
        return await client.get_channel_analytics(days=days)


async def analyze_my_content_gaps(days: int = 90) -> ContentGapAnalysis:
    """Convenience function to analyze content gaps."""
    async with YouTubeAnalyticsClient() as client:
        return await client.analyze_content_gaps(days=days)
