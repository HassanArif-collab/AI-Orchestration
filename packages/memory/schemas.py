"""
Zep Session and User Metadata Schemas.

These dictionaries define the base metadata structures used when creating
Zep users and sessions. Always extend these base dicts — never replace them.

THREE SESSION TYPES IN THIS SYSTEM:

1. VIDEO_SESSION_METADATA — per video production run
   session_id: pipeline run_id (UUID from PipelineRun)
   user_id: channel owner user ID
   Add: video_topic, pipeline_run_id, stage, agent_name

2. CHANNEL_USER_METADATA — per channel owner (created once)
   user_id: stable channel identifier
   Add: channel_name, audience_primary, content_style, competitors

3. ANALYTICS_SESSION_METADATA — per published video's feedback loop
   session_id: f"{video_id}_analytics"
   user_id: channel owner user ID
   Add: video_id, published_date, views, ctr, retention

HOW THESE RELATE TO THE TWO ZEP USERS:
  The two system Zep users (AUDIENCE and LEARNING) use a different
  naming convention — see ZepMemoryClient docstring for those conventions.
  These metadata schemas are for per-video and per-channel sessions.

USAGE PATTERN:
  When creating a new video production session:
    metadata = {**VIDEO_SESSION_METADATA, "video_topic": "AI in Pakistan", ...}
    client.create_session(session_id=run_id, user_id=owner, metadata=metadata)
"""

# Base metadata for video production sessions
VIDEO_SESSION_METADATA: dict = {
    "session_type": "video_production",
    # Additional per-session fields:
    # - video_topic: str - The topic/title of the video
    # - pipeline_run_id: str - Unique ID for this pipeline execution
    # - stage: str - Current pipeline stage (research, script, production)
    # - agent_name: str - Name of the agent working on this session
    #
    # Example extended metadata:
    # {
    #     **VIDEO_SESSION_METADATA,
    #     "video_topic": "Pakistan's Digital Payment Revolution",
    #     "pipeline_run_id": "run_abc123",
    #     "stage": "script_writing",
    #     "agent_name": "writer"
    # }
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
    #
    # Example extended metadata:
    # {
    #     **CHANNEL_USER_METADATA,
    #     "channel_name": "Pakistani Explainer",
    #     "audience_primary": "Pakistani youth aged 18-35",
    #     "content_style": "investigative documentary"
    # }
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
    #
    # Example extended metadata:
    # {
    #     **ANALYTICS_SESSION_METADATA,
    #     "video_id": "abc123xyz",
    #     "published_date": "2024-03-15",
    #     "views": 50000,
    #     "ctr": 4.5,
    #     "retention": 65.2
    # }
}
