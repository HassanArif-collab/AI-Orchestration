"""Source Video Library — SQLite persistence for processed Harris videos.

Follows the same RunStore pattern from packages/pipeline/state.py.
Uses the same database file (packages/data/pipeline.db) with a new table.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.core.logger import get_logger

from .models import ProcessingStatus, SourceVideoRecord

logger = get_logger(__name__)


class SourceVideoLibrary:
    """SQLite persistence for Source Video Library records.

    Stores processed Harris videos with their extraction data,
    structural analysis, and processing status. Prevents redundant
    API calls and provides a growing archive for Phase 5's Topic Finder.
    """

    def __init__(self, db_path: str = "packages/data/pipeline.db") -> None:
        """Initialize the source video library.

        Args:
            db_path: Path to SQLite database file (shared with pipeline).
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create source_videos table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_videos (
                    video_id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    processing_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            )
            conn.commit()

    def exists(self, video_id: str) -> bool:
        """Check if a video is already in the library.

        Args:
            video_id: YouTube video ID.

        Returns:
            True if the video exists in the library.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM source_videos WHERE video_id = ?",
                (video_id,),
            )
            return cursor.fetchone() is not None

    def save(self, record: SourceVideoRecord) -> None:
        """Save or update a source video record.

        Args:
            record: The source video record to save.
        """
        now = datetime.now(timezone.utc).isoformat()
        record.updated_at = datetime.now(timezone.utc)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_videos
                (video_id, data_json, processing_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.video_id,
                    record.model_dump_json(),
                    record.processing_status.value,
                    record.created_at.isoformat(),
                    now,
                ),
            )
            conn.commit()
        logger.info(f"source_video_saved: {record.video_id} ({record.processing_status.value})")

    def load(self, video_id: str) -> SourceVideoRecord | None:
        """Load a source video record.

        Args:
            video_id: YouTube video ID.

        Returns:
            SourceVideoRecord or None if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT data_json FROM source_videos WHERE video_id = ?",
                (video_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return SourceVideoRecord.model_validate_json(row["data_json"])

    def update_status(self, video_id: str, status: ProcessingStatus) -> None:
        """Update the processing status of a video.

        Args:
            video_id: YouTube video ID.
            status: New processing status.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Also update the status in the JSON data
        record = self.load(video_id)
        if record:
            record.processing_status = status
            record.updated_at = datetime.now(timezone.utc)
            self.save(record)
        else:
            logger.warning(f"source_video_not_found for status update: {video_id}")

    def list_videos(
        self,
        limit: int = 50,
        status: ProcessingStatus | None = None,
    ) -> list[dict]:
        """List source videos with optional status filter.

        Args:
            limit: Maximum number of records to return.
            status: Optional filter by processing status.

        Returns:
            List of summary dicts with video_id, processing_status, updated_at.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if status:
                cursor = conn.execute(
                    """
                    SELECT video_id, processing_status, updated_at
                    FROM source_videos
                    WHERE processing_status = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (status.value, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT video_id, processing_status, updated_at
                    FROM source_videos
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def find_by_genre(self, genre: str, limit: int = 10) -> list[SourceVideoRecord]:
        """Find source videos by genre classification.

        Used by the Researcher in Phase 3 to find structurally similar
        Harris videos as architectural references.

        Args:
            genre: Genre ID from Phase 1 Genre Schema.
            limit: Maximum results.

        Returns:
            List of matching SourceVideoRecords.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT data_json FROM source_videos
                WHERE processing_status IN ('fully_analyzed', 'adapted', 'adaptation_reviewed')
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            records = []
            for row in cursor.fetchall():
                record = SourceVideoRecord.model_validate_json(row["data_json"])
                if record.genre == genre:
                    records.append(record)
            return records
