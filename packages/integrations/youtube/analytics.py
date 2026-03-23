"""YouTube analytics tracking for AI Orchestration system.

Provides analytics tracking, comparison, and snapshot capabilities
for YouTube channel and video performance data.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.integrations.youtube.client import YouTubeClient
from packages.core.logger import get_logger

logger = get_logger(__name__)


class AnalyticsTracker:
    """Tracks and analyzes YouTube channel and video performance.

    Provides methods for pulling analytics, comparing videos,
    finding best performers, and saving snapshots.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the analytics tracker.

        Args:
            api_key: Optional YouTube API key. Falls back to settings.
        """
        self._client = YouTubeClient(api_key=api_key)

    def pull_weekly_stats(self, channel_id: str) -> dict:
        """Pull weekly statistics for a channel.

        Aggregates channel stats and recent video performance.

        Args:
            channel_id: The YouTube channel ID.

        Returns:
            Dictionary containing weekly stats summary.
        """
        result = {
            "channel_id": channel_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel_stats": {},
            "video_stats": {},
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "video_count": 0,
            "average_views": 0,
            "average_engagement": 0.0,
        }

        try:
            # Get channel stats
            channel_stats = self._client.get_channel_stats(channel_id)
            result["channel_stats"] = channel_stats

            # Get recent videos (typically last week's worth)
            videos = self._client.get_recent_videos(channel_id, max_results=20)

            if videos:
                total_views = sum(v.get("views", 0) for v in videos)
                total_likes = sum(v.get("likes", 0) for v in videos)
                total_comments = sum(v.get("comments", 0) for v in videos)

                result["video_stats"] = {
                    "videos": videos,
                    "count": len(videos),
                }
                result["total_views"] = total_views
                result["total_likes"] = total_likes
                result["total_comments"] = total_comments
                result["video_count"] = len(videos)

                if videos:
                    result["average_views"] = total_views // len(videos)
                    # Engagement rate: (likes + comments) / views * 100
                    if total_views > 0:
                        result["average_engagement"] = round(
                            ((total_likes + total_comments) / total_views) * 100, 2
                        )

            logger.debug(f"weekly_stats_pulled: channel={channel_id}, videos={result['video_count']}")

        except Exception as e:
            logger.warning(f"analytics_error in pull_weekly_stats: {e}")

        return result

    def compare_videos(self, video_ids: list[str]) -> list[dict]:
        """Compare multiple videos side by side.

        Args:
            video_ids: List of YouTube video IDs to compare.

        Returns:
            List of video comparison data, sorted by views descending.
        """
        comparisons = []

        for video_id in video_ids:
            details = self._client.get_video_details(video_id)
            if details:
                comparisons.append({
                    "video_id": video_id,
                    "title": details.get("title", ""),
                    "views": details.get("views", 0),
                    "likes": details.get("likes", 0),
                    "comments": details.get("comments", 0),
                    "engagement_rate": self._calculate_engagement(details),
                    "duration": details.get("duration", ""),
                    "published_at": details.get("published_at", ""),
                })

        # Sort by views descending
        comparisons.sort(key=lambda v: v.get("views", 0), reverse=True)

        return comparisons

    def find_best_performers(
        self,
        channel_id: str,
        metric: str = "views",
        top_n: int = 5,
    ) -> list[dict]:
        """Find the best performing videos on a channel.

        Args:
            channel_id: The YouTube channel ID.
            metric: Metric to rank by (views, likes, comments, engagement).
            top_n: Number of top performers to return.

        Returns:
            List of top performing videos with their metrics.
        """
        videos = self._client.get_recent_videos(channel_id, max_results=50)

        # Calculate engagement for each video
        for video in videos:
            video["engagement"] = self._calculate_engagement(video)

        # Sort by the requested metric
        valid_metrics = {"views", "likes", "comments", "engagement"}
        sort_key = metric if metric in valid_metrics else "views"

        videos.sort(key=lambda v: v.get(sort_key, 0), reverse=True)

        # Return top N
        top_performers = videos[:top_n]

        logger.debug(f"best_performers_found: channel={channel_id}, metric={metric}, count={len(top_performers)}")

        return top_performers

    def save_snapshot(self, data: dict, filepath: str | None = None) -> str:
        """Save analytics data to a JSON snapshot file.

        Creates the analytics directory if needed and saves data with
        a timestamp-based filename.

        Args:
            data: Analytics data to save.
            filepath: Optional custom filepath. If not provided, saves to
                packages/data/analytics/YYYY-MM-DD.json.

        Returns:
            The filepath where data was saved.
        """
        # Generate filename if not provided
        if filepath is None:
            # Ensure default directory exists
            analytics_dir = Path("packages/data/analytics")
            analytics_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            filepath = str(analytics_dir / f"{date_str}.json")
        else:
            # Ensure parent directory exists for custom filepath
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # Add metadata
        data["_snapshot_metadata"] = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "filepath": filepath,
        }

        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"analytics_snapshot_saved: {filepath}")

        return filepath

    def _calculate_engagement(self, video: dict) -> float:
        """Calculate engagement rate for a video.

        Args:
            video: Video dictionary with views, likes, comments.

        Returns:
            Engagement rate as a percentage.
        """
        views = video.get("views", 0)
        likes = video.get("likes", 0)
        comments = video.get("comments", 0)

        if views == 0:
            return 0.0

        return round(((likes + comments) / views) * 100, 2)


class YouTubeAnalyticsClient:
    """Client for YouTube Analytics API with graceful degradation."""

    def __init__(self, use_mock: bool = True) -> None:
        """Initialize Analytics API.
        
        Using use_mock by default in this orchestration system unless explicitly
        configured with OAuth 2.0 credentials for a specific channel.
        """
        self.use_mock = use_mock
        self._service = None
        
        # Real OAuth initialization would happen here in production.
        # Developer keys do not work for Analytics API (requires user token).
        logger.debug("YouTubeAnalyticsClient initialized in mock mode.")

    def get_video_performance(self, video_id: str, days_since_publish: int) -> dict[str, Any]:
        """Fetch post-publish metrics for a specific video.
        
        Returns:
            Dictionary containing retention metrics, CTR, Watch Time, Views, etc.
        """
        if self.use_mock:
            # Generate simulated Analytics data based on Harris patterns
            return self._mock_performance_data(video_id, days_since_publish)
            
        if not self._service:
            logger.warning("youtube_analytics_unavailable")
            return {}

        # Actual API call would go here
        # E.g. self._service.reports().query(ids=f"channel==mine", metrics="views,estimatedMinutesWatched,averageViewDuration", dimensions="video", filters=f"video=={video_id}").execute()
        return {}

    def _mock_performance_data(self, video_id: str, days: int) -> dict[str, Any]:
        """Mock realistic Pakistani audience retention data to feed the loop."""
        base_views = 50000 * days
        if days == 30:
            return {
                "views": base_views,
                "average_view_percentage": 58.5,
                "retention_curve_shape": "Harris-Pattern",
                "subscriber_conversion_rate": 0.05,
                "shares": base_views * 0.02,
                "return_viewer_percentage": 65.0,
                "anchor_avg_retention": 65.0,
                "bridge_avg_retention": 52.0
            }
        return {
            "views": base_views,
            "average_view_percentage": 50.0,
            "retention_curve_shape": "Continuous Decline",
            "subscriber_conversion_rate": 0.02,
            "shares": base_views * 0.01,
            "return_viewer_percentage": 40.0,
            "anchor_avg_retention": 55.0,
            "bridge_avg_retention": 45.0
        }

    def calculate_engagement_score(self, analytics_data: dict) -> float:
        """Calculate the composite Engagement Score.
        
        Weights:
        - View duration %: 40%
        - Curve shape: 25% (Harris-Pattern = 100, else = 50, early exit = 0)
        - Sub conversion: 20%
        - Share rate: 10%
        - Return viewer %: 5%
        """
        if not analytics_data:
            return 0.0
            
        avp_score = min(100.0, analytics_data.get("average_view_percentage", 0.0) * 1.5) * 0.40
        
        shape = analytics_data.get("retention_curve_shape")
        shape_score = 100.0 if shape == "Harris-Pattern" else 50.0 if shape == "Continuous Decline" else 0.0
        shape_score *= 0.25
        
        sub_conv = analytics_data.get("subscriber_conversion_rate", 0.0)
        sub_score = min(100.0, sub_conv * 1000) * 0.20 # 10% conversion = 100
        
        shares = analytics_data.get("shares", 0.0)
        views = analytics_data.get("views", 1.0)
        share_rate = shares / views
        share_score = min(100.0, share_rate * 2000) * 0.10 # 5% share rate = 100
        
        return_viewer = analytics_data.get("return_viewer_percentage", 0.0)
        return_score = return_viewer * 0.05
        
        return avp_score + shape_score + sub_score + share_score + return_score
