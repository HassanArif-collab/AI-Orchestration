import sqlite3
import json
from pathlib import Path
from typing import Any
from datetime import datetime

from packages.core.logger import get_logger
from packages.content_factory.topic_finder.models import TopicBrief, VideoPerformanceProfile

logger = get_logger(__name__)

DB_PATH = Path("packages/data/pipeline.db")

def init_db() -> None:
    """Initialize the Topic Reservoir and Video Performance tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Topic Reservoir Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_reservoir (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brief_id TEXT UNIQUE,
                topic_statement TEXT UNIQUE,
                big_question TEXT,
                genre_id TEXT,
                gap_type TEXT,
                score_breakdown TEXT,
                anchor_candidates TEXT,
                mainstream_assumption TEXT,
                structural_reference_id TEXT,
                urgency_flag BOOLEAN,
                timing_rationale TEXT,
                created_at TIMESTAMP,
                status TEXT,
                content_type TEXT DEFAULT 'original',
                adaptation_source_video_id TEXT DEFAULT NULL,
                structural_reference_video_id TEXT DEFAULT NULL
            )
        """)
        
        # Video Performance Pipeline Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_performance (
                video_id TEXT PRIMARY KEY,
                publication_date TIMESTAMP,
                genre_id TEXT,
                topic_statement TEXT,
                viability_score_at_selection REAL,
                engagement_24h REAL,
                engagement_7d REAL,
                engagement_30d REAL,
                engagement_90d REAL,
                retention_curve_shape TEXT,
                anchor_bridge_correlation TEXT,
                topic_resonance_score REAL
            )
        """)
        conn.commit()
    
    # Safe migration — add new columns if they don't exist
    with sqlite3.connect(DB_PATH) as conn:
        migration_columns = [
            ("content_type", "TEXT DEFAULT 'original'"),
            ("adaptation_source_video_id", "TEXT DEFAULT NULL"),
            ("structural_reference_video_id", "TEXT DEFAULT NULL"),
        ]
        for col_name, col_def in migration_columns:
            try:
                conn.execute(f"ALTER TABLE topic_reservoir ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass  # Column already exists
        conn.commit()


class TopicReservoirDB:
    def __init__(self) -> None:
        init_db()
        
    def save_topic(self, topic: TopicBrief) -> None:
        """Save a new topic brief to the reservoir."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Serialize breakdown & candidates
            score_json = json.dumps(topic.viability_score_breakdown)
            anchors_json = json.dumps(topic.anchor_candidates)
            ref_id = topic.structural_reference.video_id if topic.structural_reference else None
            
            try:
                cursor.execute("""
                    INSERT INTO topic_reservoir (
                        brief_id, topic_statement, big_question, genre_id, gap_type,
                        score_breakdown, anchor_candidates, mainstream_assumption,
                        structural_reference_id, urgency_flag, timing_rationale,
                        created_at, status, content_type, adaptation_source_video_id,
                        structural_reference_video_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    topic.brief_id, topic.topic_statement, topic.big_question, topic.genre_id, topic.gap_type,
                    score_json, anchors_json, topic.mainstream_assumption,
                    ref_id, topic.urgency_flag, topic.timing_rationale,
                    topic.created_at.isoformat(), topic.status,
                    topic.content_type, topic.adaptation_source_video_id,
                    topic.structural_reference_video_id
                ))
                conn.commit()
                logger.info(f"saved_topic_to_reservoir: {topic.topic_statement[:50]}...")
            except sqlite3.IntegrityError:
                logger.warning(f"topic_already_exists_in_reservoir: {topic.topic_statement[:50]}...")

    def get_top_topics(self, limit: int = 5) -> list[TopicBrief]:
        """Fetch the top reservoir topics. In MVP just gets recent available."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM topic_reservoir 
                WHERE status = 'reservoir'
                ORDER BY urgency_flag DESC, created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            
        topics = []
        for row in rows:
            topics.append(self._row_to_brief(row))
        return topics

    def _row_to_brief(self, row: sqlite3.Row) -> TopicBrief:
        """Convert a database row to a TopicBrief object."""
        # Helper to safely get optional columns from sqlite3.Row
        def get_col(row: sqlite3.Row, name: str, default=None):
            if name in row.keys():
                val = row[name]
                return val if val is not None else default
            return default

        return TopicBrief(
            brief_id=row["brief_id"],
            topic_statement=row["topic_statement"],
            big_question=row["big_question"],
            genre_id=row["genre_id"],
            gap_type=row["gap_type"],
            viability_score_breakdown=json.loads(row["score_breakdown"]),
            anchor_candidates=json.loads(row["anchor_candidates"]),
            mainstream_assumption=row["mainstream_assumption"],
            urgency_flag=bool(row["urgency_flag"]),
            timing_rationale=row["timing_rationale"],
            created_at=datetime.fromisoformat(row["created_at"]),
            status=row["status"],
            content_type=get_col(row, "content_type", "original"),
            adaptation_source_video_id=get_col(row, "adaptation_source_video_id"),
            structural_reference_video_id=get_col(row, "structural_reference_video_id"),
        )


class PerformanceDB:
    def __init__(self) -> None:
        init_db()

    def save_performance(self, profile: VideoPerformanceProfile) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            ab_corr = json.dumps(profile.anchor_bridge_correlation) if profile.anchor_bridge_correlation else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO video_performance (
                    video_id, publication_date, genre_id, topic_statement,
                    viability_score_at_selection, engagement_24h, engagement_7d,
                    engagement_30d, engagement_90d, retention_curve_shape,
                    anchor_bridge_correlation, topic_resonance_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.video_id, profile.publication_date.isoformat(),
                profile.genre_id, profile.topic_statement, profile.viability_score_at_selection,
                profile.engagement_24h, profile.engagement_7d, profile.engagement_30d, profile.engagement_90d,
                profile.retention_curve_shape, ab_corr, profile.topic_resonance_score
            ))
            conn.commit()
            logger.info(f"saved_performance_profile: video_id={profile.video_id}")
