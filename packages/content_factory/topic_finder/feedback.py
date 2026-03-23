"""Phase 5: Feedback Integration and Audience Model.

Closes the loop between post-publish analytics and generation. Uses YouTube Analytics
data to update the Audience Model and recalibrate Topic Finder weights over time.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from packages.core.logger import get_logger
from packages.content_factory.topic_finder.models import AudienceModel
from packages.memory.client import ZepMemoryClient
from packages.core.config import get_settings

logger = get_logger(__name__)

AUDIENCE_MODEL_PATH = Path("packages/data/audience_model.json")

class FeedbackLoop:
    def __init__(self) -> None:
        self.model = self._load_audience_model()
        self.zep_client = ZepMemoryClient()
        self.audience_user_id = get_settings().ZEP_AUDIENCE_USER_ID
        self.zep_session_id = f"{self.audience_user_id}_session"

    def _load_audience_model(self) -> AudienceModel:
        """Load the evolving behavioral model for Pakistani Audience."""
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
        """Persist to disk."""
        try:
            with open(AUDIENCE_MODEL_PATH, "w", encoding="utf-8") as f:
                # Use model_dump for pydantic v2
                dump = self.model.model_dump(mode="json")
                json.dump(dump, f, indent=2)
            logger.info("audience_model_saved")
        except Exception as e:
            logger.error(f"failed_to_save_audience_model: {e}")

    def recalibrate_from_performance(self, profile: dict) -> None:
        """Update the audience model using a VideoPerformanceProfile dict representation."""
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
        
        # Write facts to Zep
        if facts:
            self.zep_client.add_facts(session_id=self.zep_session_id, facts=facts)
            logger.info(f"wrote_{len(facts)}_facts_to_zep_for_genre: {genre}")
            
        logger.info(f"recalibrated_feedback_loop_for_genre: {genre}")
