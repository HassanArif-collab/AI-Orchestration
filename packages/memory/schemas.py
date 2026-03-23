"""Metadata schemas for Zep memory operations.

These dictionaries define the base metadata structures for different
session and user types in the YouTube automation system.
"""

# Base metadata for video production sessions
VIDEO_SESSION_METADATA: dict = {
    "session_type": "video_production",
    # Additional per-session fields:
    # - video_topic: str - The topic/title of the video
    # - pipeline_run_id: str - Unique ID for this pipeline execution
    # - stage: str - Current pipeline stage (research, script, production)
    # - agent_name: str - Name of the agent working on this session
}

# Base metadata for channel owners/users
CHANNEL_USER_METADATA: dict = {
    "user_type": "channel_owner",
    # Additional per-user fields:
    # - channel_name: str - YouTube channel name
    # - audience_primary: str - Primary target audience
    # - audience_secondary: str - Secondary target audience
    # - content_style: str - Content style preferences
    # - competitors: list[str] - List of competitor channel IDs
}

# Base metadata for analytics feedback sessions
ANALYTICS_SESSION_METADATA: dict = {
    "session_type": "analytics_feedback",
    # Additional per-session fields:
    # - video_id: str - YouTube video ID
    # - published_date: str - Publication date of the video
    # - views: int - View count
    # - ctr: float - Click-through rate
    # - retention: float - Average retention percentage
}
