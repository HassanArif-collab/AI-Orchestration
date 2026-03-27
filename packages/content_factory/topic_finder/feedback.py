"""Feedback Loop — Closes the Circle from Analytics to Topic Discovery.

This module is the FEEDBACK LAYER of the self-improving system. After a video
is published and collects YouTube analytics, FeedbackLoop ingests those results
and updates the audience intelligence model so future topics are better calibrated.

HOW IT FITS IN THE OVERALL LOOP:
  Published video
       ↓ (YouTube Analytics, collected after 30 days)
  FeedbackLoop.ingest_analytics(analytics_data)
       ↓
  audience_model.json updated (local fallback)
       ↓ (if ZEP_ENABLED=true)
  Zep Audience Session updated with new facts
       ↓
  TopicFinderAgent reads audience context → better topic suggestions

THE AUDIENCE MODEL (AudienceModel Pydantic model in models.py):
  knowledge_baseline: dict — what the audience already knows per topic
  attention_patterns: dict — when viewers drop off (e.g. "flat drop at bridge")
  topic_resonance_map: dict — float scores per topic (which topics resonate)
  genre_engagement_rankings: dict — which genres get best engagement

ANALYTICS INGESTION TRIGGERS (from Scheduler):
  run_analytics_sweep() — daily (every 24h)
  But only ingests videos that are 30+ days old (let data stabilize)

ZEP INTEGRATION:
  When ZEP_ENABLED=true, ingest_analytics() also calls:
  ZepAudienceModelStore.write_video_performance() to store facts like:
  "Video about Pakistan's digital payments (current_situation) achieved
   72% 7-day engagement. Retention: Harris-Pattern."

  These facts power the SynthesisEngine's audience_response_patterns
  analysis and TopicFinderAgent's context string.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone

from packages.core.logger import get_logger
from packages.content_factory.topic_finder.models import AudienceModel
from packages.memory.client import AsyncZepMemoryClient
from packages.core.config import get_settings

logger = get_logger(__name__)

AUDIENCE_MODEL_PATH = Path("packages/data/audience_model.json")


class FeedbackLoop:
    """Closes the loop between published analytics and future topic discovery.
    
    This is the LEARNING INPUT layer. It takes real-world performance data
    and converts it into actionable intelligence for the topic finder.
    
    WHAT IT LEARNS:
      - Which genres get the best engagement (genre_engagement_rankings)
      - Which specific topics resonate (topic_resonance_map)
      - Where viewers drop off (attention_patterns)
      - What the audience already knows (knowledge_baseline)
    
    HOW IT UPDATES:
      Uses a simple moving average for genre rankings to smooth out
      individual video variance. Individual topic scores are stored
      directly.
    
    ZEP DUAL-WRITE:
      All learned facts are written to both:
        1. Local audience_model.json
        2. Zep audience session (for semantic retrieval)
    """
    def __init__(self) -> None:
        self.model = self._load_audience_model()
        self.zep_client = AsyncZepMemoryClient()
        self.audience_user_id = get_settings().ZEP_AUDIENCE_USER_ID
        self.zep_session_id = f"{self.audience_user_id}_session"

    def _load_audience_model(self) -> AudienceModel:
        """Load the evolving behavioral model for Pakistani Audience.
        
        Returns:
            Existing AudienceModel from disk, or default model if none exists.
        
        DEFAULT MODEL:
            If no file exists, creates a baseline model with:
            - Placeholder knowledge_baseline
            - Default attention pattern for bridge sections
            - Equal weight for all genres
        """
        if not AUDIENCE_MODEL_PATH.parent.exists():
            AUDIENCE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            
        if AUDIENCE_MODEL_PATH.exists():
            try:
                with open(AUDIENCE_MODEL_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return AudienceModel(**data)
            except Exception as e:
                logger.error(f"failed_to_load_audience_model: {e}")
                
        # Return default if not exists
        return AudienceModel(
            knowledge_baseline={"General": "Pre-established assumptions"},
            attention_patterns={"Bridge Sections": "Need high cadence"},
            topic_resonance_map={"Economy": 1.0, "Islamic History": 1.0},
            genre_engagement_rankings={"islamic_history": 1.0, "south_asian_history": 1.0},
            last_updated=datetime.now(timezone.utc)
        )

    def save_audience_model(self) -> None:
        """Persist to disk.
        
        Saves the current model state to packages/data/audience_model.json.
        This file is the LOCAL FALLBACK when Zep is unavailable.
        """
        try:
            with open(AUDIENCE_MODEL_PATH, "w", encoding="utf-8") as f:
                # Use model_dump for pydantic v2
                dump = self.model.model_dump(mode="json")
                json.dump(dump, f, indent=2)
            logger.info("audience_model_saved")
        except Exception as e:
            logger.error(f"failed_to_save_audience_model: {e}")

    def recalibrate_from_performance(self, profile: dict) -> None:
        """Update the audience model using a VideoPerformanceProfile dict representation.
        
        This is the MAIN ENTRY POINT for analytics ingestion. Called by
        Scheduler.run_analytics_sweep() for each video with 30+ days of data.
        
        WHAT IT UPDATES:
          1. genre_engagement_rankings — moving average of all videos in genre
          2. topic_resonance_map — direct mapping of topic → score
          3. attention_patterns — bridge section drop-off detection
        
        ZEP WRITE:
          Each learned fact is written to the Zep audience session with
          structured metadata (genre, topic_type, metric, date).
        
        Args:
            profile: VideoPerformanceProfile as dict, containing:
              - genre_id
              - topic_statement
              - topic_resonance_score
              - anchor_bridge_correlation
              - video_id
              - publication_date
        """
        # 1. Update Genre Engagement Rankings
        genre = profile.get("genre_id")
        topic = profile.get("topic_statement", "Unknown")
        score = profile.get("topic_resonance_score", 0.0)
        
        facts = []
        # Support either string or datetime object for publication_date
        pub_date_raw = profile.get("publication_date")
        if isinstance(pub_date_raw, datetime):
            date_str = pub_date_raw.isoformat()
        elif isinstance(pub_date_raw, str):
            date_str = pub_date_raw
        else:
            date_str = datetime.now(timezone.utc).isoformat()
        
        if genre and score:
            current = self.model.genre_engagement_rankings.get(genre, 1.0)
            # Moving average
            self.model.genre_engagement_rankings[genre] = (current + score) / 2.0
            
            # Map topic resonance directly
            self.model.topic_resonance_map[topic] = score
            
            facts.append({
                "fact": f"Videos in {genre} regarding '{topic}' achieved a topic resonance score of {score}.",
                "source": profile.get("video_id", "unknown"),
                "genre": genre,
                "topic_type": profile.get("gap_type", "unknown"),
                "metric": "topic_resonance_score",
                "date": date_str
            })
            
        # 2. Extract Anchor-Bridge Calibration if available
        ab_corr = profile.get("anchor_bridge_correlation")
        if ab_corr and isinstance(ab_corr, dict):
            bridge_val = ab_corr.get("bridge", 0)
            if bridge_val < 50.0:
                self.model.attention_patterns["Bridge Sections"] = "High drop-off detected. Needs more surface moments."
                facts.append({
                    "fact": f"Bridge sections in {genre} videos showed high drop-off. Needs more surface moments.",
                    "source": profile.get("video_id", "unknown"),
                    "genre": genre,
                    "topic_type": profile.get("gap_type", "unknown"),
                    "metric": "anchor_bridge_correlation",
                    "date": date_str
                })
            else:
                self.model.attention_patterns["Bridge Sections"] = "Stable retention."
                facts.append({
                    "fact": f"Bridge sections in {genre} videos showed stable retention (>{bridge_val}%).",
                    "source": profile.get("video_id", "unknown"),
                    "genre": genre,
                    "topic_type": profile.get("gap_type", "unknown"),
                    "metric": "anchor_bridge_correlation",
                    "date": date_str
                })
                
        self.model.last_updated = datetime.now(timezone.utc)
        self.save_audience_model()
        
        # Write facts to Zep (async, non-blocking)
        if facts:
            asyncio.create_task(self._write_facts_to_zep(facts))
            logger.info(f"wrote_{len(facts)}_facts_to_zep_for_genre: {genre}")
            
        logger.info(f"recalibrated_feedback_loop_for_genre: {genre}")

    async def _write_facts_to_zep(self, facts: list[dict]) -> None:
        """Write facts to Zep (async helper for background execution)."""
        try:
            await self.zep_client.add_facts(session_id=self.zep_session_id, facts=facts)
        except Exception as e:
            logger.debug(f"zep_write_failed: {e}")
