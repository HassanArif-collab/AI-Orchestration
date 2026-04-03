"""analytics_routes.py — YouTube channel analytics."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import glob
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.dependencies import get_youtube_client
from packages.core.supabase_client import get_supabase

router = APIRouter()


class RepurposeRequest(BaseModel):
    title: str
    video_id: str
    channel: str
    views: int


@router.get("/channel")
async def get_channel_stats(channel_id: str = ""):
    client = get_youtube_client()
    if not client or not client.api_key:
        raise HTTPException(status_code=503, detail="YouTube API not configured. Set YOUTUBE_API_KEY in .env")
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
    """Fetch latest videos from competitor channels."""
    client = get_youtube_client()
    if not client or not client.api_key:
        raise HTTPException(status_code=503, detail="YouTube API not configured")
    
    # Hardcoded competitor channels (Johnny Harris, Cleo Abram)
    competitors = ["UCmGSJVG3mCRXVOP4yZrU1Dw", "UC3_hsOmAsodJwo5SIy6Jxng"]
    videos = client.get_competitor_videos(competitors, max_results=limit)
    return {"videos": videos}


@router.post("/repurpose")
async def repurpose_competitor_video(body: RepurposeRequest):
    """
    Take a competitor video and create a new Kanban card for it.
    This triggers "Mode A" — adaptation of an existing topic.
    
    The card goes directly to Column 2 (Suggested Topics) with
    the competitor video info as the topic_brief.
    """
    try:
        sb = get_supabase()
    except Exception:
        raise HTTPException(500, "Supabase not configured")

    card_data = {
        "topic_brief": {
            "title": f"[Repurpose] {body.title}",
            "description": f"Adapted from competitor video: {body.channel}",
            "angle": "adaptation",
            "source_video_id": body.video_id,
            "source_url": f"https://youtube.com/watch?v={body.video_id}",
            "original_views": body.views,
        },
        "column_index": 2,
        "status": "suggested",
        "viability_score": None,
        "expires_at": None,  # Repurposed cards don't auto-expire
    }

    try:
        result = sb.table("kanban_cards").insert(card_data).execute()
        if result.data:
            return {"status": "created", "card_id": result.data[0]["id"]}
        return {"status": "error", "card_id": None}
    except Exception as e:
        raise HTTPException(500, f"Failed to create card: {str(e)}")


@router.post("/snapshot")
async def save_snapshot(channel_id: str = ""):
    try:
        from packages.integrations.youtube.analytics import AnalyticsTracker
        tracker = AnalyticsTracker()
        data = tracker.pull_weekly_stats(channel_id) if channel_id else {}
        filepath = tracker.save_snapshot(data)
        return {"filepath": filepath, "status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def list_snapshots():
    snaps = []
    for f in sorted(glob.glob("packages/data/analytics/*.json"), reverse=True):
        snaps.append({"filepath": f, "date": os.path.basename(f).replace(".json", "")})
    return snaps
