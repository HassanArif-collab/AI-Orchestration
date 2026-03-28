"""Iteration Log Store - Persists ExperimentLoop iteration data to SQLite.

Each iteration of the script evolution loop is saved with:
- Score and previous score
- Mutation zone
- Whether it beat the baseline
- Full script JSON
- Failed/fixed question IDs

This feeds the frontend score graph and enables analysis of evolution patterns.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from packages.core.config import get_settings


class IterationLogStore:
    """SQLite-backed store for iteration logs.
    
    Usage:
        store = IterationLogStore()
        store.save(run_id="r1", iteration=1, score=74.2, ...)
        rows = store.get_all("r1")
    """
    
    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the store.
        
        Args:
            db_path: Path to SQLite database. Defaults to DATA_DIR/iteration_logs.db
        """
        settings = get_settings()
        self.db_path = db_path or str(Path(settings.DATA_DIR) / "iteration_logs.db")
        self._ensure_table()
    
    def _ensure_table(self) -> None:
        """Create the iteration_log table if it doesn't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS iteration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                score REAL NOT NULL,
                previous_score REAL NOT NULL,
                beat_baseline INTEGER NOT NULL,
                mutation_zone TEXT NOT NULL,
                script_json TEXT,
                failed_questions TEXT,
                fixed_questions TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_iteration_log_run_id 
            ON iteration_log(run_id)
        """)
        conn.commit()
        conn.close()
    
    def save(
        self,
        run_id: str,
        iteration: int,
        score: float,
        previous_score: float,
        beat_baseline: bool,
        mutation_zone: str,
        script_json: Optional[dict] = None,
        failed_questions: Optional[list] = None,
        fixed_questions: Optional[list] = None,
    ) -> None:
        """Save an iteration log entry.
        
        Args:
            run_id: Pipeline run ID
            iteration: Iteration number (0-indexed)
            score: Current iteration score
            previous_score: Score before this iteration
            beat_baseline: Whether this iteration beat the baseline
            mutation_zone: Which mutation zone was applied
            script_json: Full script as dict (optional)
            failed_questions: List of failed question IDs (optional)
            fixed_questions: List of fixed question IDs (optional)
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO iteration_log (
                run_id, iteration, score, previous_score, beat_baseline,
                mutation_zone, script_json, failed_questions, fixed_questions, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                iteration,
                score,
                previous_score,
                1 if beat_baseline else 0,
                mutation_zone,
                json.dumps(script_json, default=str) if script_json else None,
                json.dumps(failed_questions, default=str) if failed_questions else None,
                json.dumps(fixed_questions, default=str) if fixed_questions else None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()
    
    def get_all(self, run_id: str) -> list[dict]:
        """Get all iteration logs for a run.
        
        Args:
            run_id: Pipeline run ID
            
        Returns:
            List of iteration log dicts, ordered by iteration number
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT * FROM iteration_log 
            WHERE run_id = ? 
            ORDER BY iteration ASC
            """,
            (run_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "run_id": row["run_id"],
                "iteration": row["iteration"],
                "score": row["score"],
                "previous_score": row["previous_score"],
                "beat_baseline": bool(row["beat_baseline"]),
                "mutation_zone": row["mutation_zone"],
                "script_json": json.loads(row["script_json"]) if row["script_json"] else None,
                "failed_questions": json.loads(row["failed_questions"]) if row["failed_questions"] else [],
                "fixed_questions": json.loads(row["fixed_questions"]) if row["fixed_questions"] else [],
                "created_at": row["created_at"],
            })
        
        return result
    
    def delete_for_run(self, run_id: str) -> int:
        """Delete all iteration logs for a run.
        
        Args:
            run_id: Pipeline run ID
            
        Returns:
            Number of rows deleted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "DELETE FROM iteration_log WHERE run_id = ?",
            (run_id,),
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted
