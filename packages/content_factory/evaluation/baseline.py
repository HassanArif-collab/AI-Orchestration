"""Phase 4 Auto-Research Loop: Baseline Manager.

Stores the highest-scoring script for each genre as the current "champion."
New scripts produced by the pipeline must BEAT the champion to replace it.
This ensures the system only ever moves forward — never produces worse output.

HOW IT WORKS:
  process_challenger(script) compares the challenger's score to the current
  baseline for that genre. If the challenger scores higher, it becomes the
  new baseline and returns True. Otherwise returns False.

  The baseline is the MINIMUM acceptable standard for a genre. A script
  that scores below baseline should trigger another ExperimentLoop iteration.

STORAGE:
  SQLite table "baseline_scripts" in packages/data/pipeline.db
  One row per genre_id — always the highest-scoring script ever produced
  for that genre.

GENRES TRACKED (from genre_schema.json):
  history, current_situation, tech_systems, comparison,
  islamic_history, south_asian_history

RELATIONSHIP TO EXPERIMENTLOOP:
  ExperimentLoop.run_iterations() calls process_challenger() after each
  mutation iteration. If the challenger beats baseline, it becomes the
  new starting point for subsequent mutations.
  baseline.py is DUMB — it just compares scores. ExperimentLoop is the
  intelligent loop that decides what to mutate next.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.core.logger import get_logger
from ..models import AdaptedScript

logger = get_logger(__name__)

DB_PATH = "packages/data/pipeline.db"


class BaselineManager:
    """SQLite persistence for top-scoring baseline scripts.
    
    The baseline manager implements the EVOLUTIONARY DEFENSE LINE.
    It stores one champion script per genre and defends it against
    challengers that don't score higher.
    
    This is the GUARDIAN of quality improvement. Without this, the
    system could produce worse scripts and not notice.
    
    TABLE SCHEMA:
      genre_id (PK)    — The genre this baseline is for
      video_id         — ID of the champion script
      score            — Production readiness score (0-100)
      data_json        — Full AdaptedScript JSON
      updated_at       — When this baseline was established
    
    USAGE:
      bm = BaselineManager()
      
      # Get current champion for a genre
      champion = bm.get_baseline("islamic_history")
      
      # After experiment loop, see if challenger wins
      is_new_champion = bm.process_challenger(mutated_script)
      if is_new_champion:
          print("New baseline established!")
    """

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create baseline_scripts table if it doesn't exist.
        
        One row per genre. PRIMARY KEY on genre_id ensures
        only one baseline per genre.
        """
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
        """Get the highest scoring script for a specific genre.
        
        This is the CHAMPION that new scripts must beat.
        Returns None if no baseline exists yet (first run for this genre).
        
        Args:
            genre_id: The genre to get baseline for
        
        Returns:
            AdaptedScript of the champion, or None
        """
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
        
        This is the EVOLUTIONARY COMPARISON. The challenger must score
        STRICTLY HIGHER than the baseline to become the new champion.
        
        TIE-BREAKING: Equal scores do NOT replace the baseline.
        This prevents churn on identical-quality scripts.
        
        Args:
            challenger: The new script to compare
        
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
