"""
YouTube Integration Package

Provides clients for:
- YouTube Data API v3 (trending videos, search)
- YouTube Analytics API (channel performance)

Requirements:
- YOUTUBE_API_KEY for Data API (public data)
- YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN for Analytics (own channel)
"""

from .youtube_data import (
    YouTubeDataClient,
    YouTubeVideo,
    TrendingVideo,
    fetch_trending_for_region,
    search_youtube,
    YouTubeAPIError,
    QuotaExceededError,
)

from .youtube_analytics import (
    YouTubeAnalyticsClient,
    ChannelAnalytics,
    VideoPerformance,
    ContentGapAnalysis,
    get_my_channel_analytics,
    analyze_my_content_gaps,
    YouTubeAnalyticsError,
)

__all__ = [
    # Data API
    "YouTubeDataClient",
    "YouTubeVideo",
    "TrendingVideo",
    "fetch_trending_for_region",
    "search_youtube",
    "YouTubeAPIError",
    "QuotaExceededError",
    
    # Analytics API
    "YouTubeAnalyticsClient",
    "ChannelAnalytics",
    "VideoPerformance",
    "ContentGapAnalysis",
    "get_my_channel_analytics",
    "analyze_my_content_gaps",
    "YouTubeAnalyticsError",
]
