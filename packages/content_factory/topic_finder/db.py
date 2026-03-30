from typing import Any
from datetime import datetime

from packages.core.logger import get_logger
from packages.content_factory.topic_finder.models import TopicBrief, VideoPerformanceProfile

logger = get_logger(__name__)


class TopicReservoirDB:
    """Supabase-backed store for topic briefs (reservoir).

    Replaces SQLite-backed version that used packages/data/pipeline.db.
    Tables are pre-created via Supabase migration SQL.
    """

    def __init__(self) -> None:
        pass  # Tables pre-created via Supabase migration

    def _db(self):
        from packages.core.supabase_client import get_supabase
        return get_supabase().table("topic_briefs")

    def save_topic(self, topic: TopicBrief) -> None:
        """Save a topic brief to the reservoir (upsert on brief_id)."""
        ref_id = topic.structural_reference.video_id if topic.structural_reference else None
        data = {
            "brief_id": topic.brief_id,
            "topic_statement": topic.topic_statement,
            "big_question": topic.big_question,
            "genre_id": topic.genre_id,
            "gap_type": topic.gap_type,
            "viability_score_breakdown": topic.viability_score_breakdown,
            "anchor_candidates": topic.anchor_candidates,
            "mainstream_assumption": topic.mainstream_assumption,
            "urgency_flag": topic.urgency_flag,
            "timing_rationale": topic.timing_rationale,
            "created_at": topic.created_at.isoformat(),
            "status": topic.status,
            "content_type": topic.content_type,
            "adaptation_source_video_id": topic.adaptation_source_video_id,
            "structural_reference_video_id": topic.structural_reference_video_id,
            "structural_reference_id": ref_id,
        }
        try:
            self._db().upsert(data, on_conflict="brief_id").execute()
            logger.info(f"saved_topic_to_reservoir: {topic.topic_statement[:50]}...")
        except Exception as e:
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                logger.warning(f"topic_already_exists: {topic.topic_statement[:50]}...")
            else:
                raise

    def get_top_topics(self, limit: int = 5) -> list[TopicBrief]:
        """Fetch the top reservoir topics (status='reservoir')."""
        result = (
            self._db()
            .select("*")
            .eq("status", "reservoir")
            .order("urgency_flag", desc=True)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_brief(row) for row in (result.data or [])]

    def _row_to_brief(self, row: dict) -> TopicBrief:
        """Convert a Supabase row dict to a TopicBrief object."""
        return TopicBrief(
            brief_id=row["brief_id"],
            topic_statement=row["topic_statement"],
            big_question=row["big_question"],
            genre_id=row["genre_id"],
            gap_type=row["gap_type"],
            viability_score_breakdown=row["viability_score_breakdown"] or {},
            anchor_candidates=row["anchor_candidates"] or [],
            mainstream_assumption=row["mainstream_assumption"],
            urgency_flag=bool(row.get("urgency_flag", False)),
            timing_rationale=row["timing_rationale"],
            created_at=datetime.fromisoformat(row["created_at"]),
            status=row.get("status", "reservoir"),
            content_type=row.get("content_type") or "original",
            adaptation_source_video_id=row.get("adaptation_source_video_id"),
            structural_reference_video_id=row.get("structural_reference_video_id"),
        )


class PerformanceDB:
    """Supabase-backed store for video performance profiles.

    Replaces SQLite-backed version that used packages/data/pipeline.db.
    Tables are pre-created via Supabase migration SQL.
    """

    def __init__(self) -> None:
        pass  # Tables pre-created via Supabase migration

    def _db(self):
        from packages.core.supabase_client import get_supabase
        return get_supabase().table("video_performance")

    def save_performance(self, profile: VideoPerformanceProfile) -> None:
        """Save a video performance profile (upsert on video_id)."""
        data = {
            "video_id": profile.video_id,
            "publication_date": profile.publication_date.isoformat(),
            "genre_id": profile.genre_id,
            "topic_statement": profile.topic_statement,
            "viability_score_at_selection": profile.viability_score_at_selection,
            "engagement_24h": profile.engagement_24h,
            "engagement_7d": profile.engagement_7d,
            "engagement_30d": profile.engagement_30d,
            "engagement_90d": profile.engagement_90d,
            "retention_curve_shape": profile.retention_curve_shape,
            "anchor_bridge_correlation": profile.anchor_bridge_correlation,
            "topic_resonance_score": profile.topic_resonance_score,
        }
        self._db().upsert(data, on_conflict="video_id").execute()
        logger.info(f"saved_performance_profile: video_id={profile.video_id}")
