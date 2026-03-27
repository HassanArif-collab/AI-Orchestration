"""
types.py — Shared Pydantic models used across ALL pipeline packages.

Context: Every stage of the YouTube pipeline passes data using these models.
They define the data contract between agents. If a model changes here,
all agents are affected — change carefully.

Imports: pydantic, datetime
Imported by: packages/pipeline/, packages/agents/, packages/router/
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class PipelineState(BaseModel):
    """
    Full state of one pipeline run. Passed between all stages.
    Stored in packages/data/pipeline.db by the pipeline package.
    """
    run_id: str
    stage: str
    status: Literal["running", "waiting_human", "complete", "error"] = "running"
    error_message: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Memory & Session Types ───────────────────────────────────────────────────


class SessionType(str, Enum):
    """Zep session types for memory management."""
    AGENT = "agent"
    AUDIENCE = "audience"
    LEARNING = "learning"


class AgentRole(str, Enum):
    """Agent role identifiers for memory context."""
    RESEARCHER = "researcher"
    SCRIPT_WRITER = "script_writer"
    VISUAL_PLANNER = "visual_planner"
    SEO_SPECIALIST = "seo_specialist"


class MessageRole(str, Enum):
    """Message role in conversation history."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ─── Integration Metadata Types ───────────────────────────────────────────────


class VideoMetadata(BaseModel):
    """YouTube video metadata from API."""
    video_id: str
    title: str
    description: str = ""
    channel_id: str = ""
    channel_title: str = ""
    published_at: str = ""
    duration_seconds: int = 0
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    tags: list[str] = []


class ChannelMetadata(BaseModel):
    """YouTube channel metadata from API."""
    channel_id: str
    title: str
    description: str = ""
    subscriber_count: int = 0
    video_count: int = 0
    view_count: int = 0


class AnalyticsMetadata(BaseModel):
    """YouTube analytics data for a video."""
    video_id: str
    date: str
    views: int = 0
    watch_time_minutes: float = 0.0
    average_view_duration: float = 0.0
    click_through_rate: float = 0.0
    impressions: int = 0


class ChannelStats(BaseModel):
    """Channel statistics summary."""
    channel_id: str
    total_views: int = 0
    total_subscribers: int = 0
    total_videos: int = 0
    engagement_rate: float = 0.0


class MemoryFact(BaseModel):
    """A fact stored in Zep memory."""
    fact_id: str
    content: str
    source: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = {}
