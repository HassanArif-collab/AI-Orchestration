"""Phase 4 Auto-Research Loop: Baseline Manager.

Stores the highest-scoring scripts per genre to act as
evolutionary baselines for the mutation loop.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.core.logger import get_logger
from ..models import AdaptedScript

logger = get_logger(__name__)

DB_PATH = "packages/data/pipeline.db"


class BaselineManager:
    """SQLite persistence for top-scoring baseline scripts."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create baseline_scripts table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS baseline_scripts (
                    genre_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    score REAL NOT NULL,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_baseline(self, genre_id: str) -> AdaptedScript | None:
        """Get the highest scoring script for a specific genre."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT data_json FROM baseline_scripts WHERE genre_id = ?",
                (genre_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return AdaptedScript.model_validate_json(row["data_json"])

    def process_challenger(self, challenger: AdaptedScript) -> bool:
        """Compare challenger score to baseline. Save if higher (or if no baseline).
        
        Returns:
            True if challenger became the new baseline, False otherwise.
        """
        baseline = self.get_baseline(challenger.genre)
        
        is_new_baseline = False
        if baseline is None:
            is_new_baseline = True
        elif challenger.production_readiness_score > baseline.production_readiness_score:
            is_new_baseline = True
            
        if is_new_baseline:
            now = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO baseline_scripts
                    (genre_id, video_id, score, data_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        challenger.genre,
                        challenger.video_id,
                        challenger.production_readiness_score,
                        challenger.model_dump_json(),
                        now
                    )
                )
                conn.commit()
            logger.info(f"new_baseline_set: {challenger.genre} -> {challenger.production_readiness_score:.1f}% ({challenger.video_id})")
            return True
            
        logger.info(f"baseline_defended: {challenger.genre} remains at {baseline.production_readiness_score:.1f}%")
        return False
