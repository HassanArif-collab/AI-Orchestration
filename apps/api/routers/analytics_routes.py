"""analytics_routes.py — YouTube channel analytics."""
from __future__ import annotations
import glob, os
from fastapi import APIRouter
from apps.api.dependencies import get_youtube_client

router = APIRouter()

@router.get("/channel")
async def get_channel_stats(channel_id: str = ""):
    client = get_youtube_client()
    if not client or not client.api_key:
        return {"subscriber_count": 0, "total_views": 0, "video_count": 0,
                "error": "YouTube API not configured. Set YOUTUBE_API_KEY in .env"}
    return client.get_channel_stats(channel_id) if channel_id else \
           {"subscriber_count": 0, "total_views": 0, "video_count": 0}

@router.get("/videos")
async def get_recent_videos(channel_id: str = "", limit: int = 20):
    client = get_youtube_client()
    if not client or not client.api_key:
        return []
    return client.get_recent_videos(channel_id, max_results=limit) if channel_id else []

@router.get("/competitors")
async def get_competitor_videos(limit: int = 10):
    client = get_youtube_client()
    if not client or not client.api_key:
        return []
    competitors = ["UCmGSJVG3mCRXVOP4yZrU1Dw",  # Johnny Harris
                   "UC3_hsOmAsodJwo5SIy6Jxng"]   # Cleo Abram
    return client.get_competitor_videos(competitors, max_results=limit)

@router.post("/snapshot")
async def save_snapshot(channel_id: str = ""):
    try:
        from packages.integrations.youtube.analytics import AnalyticsTracker
        tracker = AnalyticsTracker()
        data = tracker.pull_weekly_stats(channel_id) if channel_id else {}
        filepath = tracker.save_snapshot(data)
        return {"filepath": filepath, "status": "saved"}
    except Exception as e:
        return {"error": str(e)}

@router.get("/snapshots")
async def list_snapshots():
    snaps = []
    for f in sorted(glob.glob("packages/data/analytics/*.json"), reverse=True):
        snaps.append({"filepath": f, "date": os.path.basename(f).replace(".json", "")})
    return snaps
