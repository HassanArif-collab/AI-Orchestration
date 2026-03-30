"""Iteration Log Store - Persists ExperimentLoop iteration data to Supabase.

Each iteration of the script evolution loop is saved with:
- Score and previous score
- Mutation zone
- Whether it beat the baseline
- Full script JSON
- Failed/fixed question IDs

This feeds the frontend score graph and enables analysis of evolution patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


class IterationLogStore:
    """Supabase-backed store for iteration logs.

    Usage:
        store = IterationLogStore()
        store.save(run_id="r1", iteration=1, score=74.2, ...)
        rows = store.get_all("r1")
    """

    def __init__(self) -> None:
        """Initialize the store. Tables are pre-created via Supabase migration."""
        pass

    def _db(self):
        from packages.core.supabase_client import get_supabase
        return get_supabase().table("iteration_logs")

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
        self._db().insert({
            "run_id": run_id,
            "iteration": iteration,
            "score": score,
            "previous_score": previous_score,
            "beat_baseline": beat_baseline,
            "mutation_zone": mutation_zone,
            "script_json": script_json,
            "failed_questions": failed_questions or [],
            "fixed_questions": fixed_questions or [],
        }).execute()

    def get_all(self, run_id: str) -> list[dict]:
        """Get all iteration logs for a run.

        Args:
            run_id: Pipeline run ID

        Returns:
            List of iteration log dicts, ordered by iteration number
        """
        result = (
            self._db()
            .select("*")
            .eq("run_id", run_id)
            .order("iteration")
            .execute()
        )
        return [
            {
                "id": str(row["id"]),
                "run_id": row["run_id"],
                "iteration": row["iteration"],
                "score": row["score"],
                "previous_score": row["previous_score"],
                "beat_baseline": row["beat_baseline"],
                "mutation_zone": row["mutation_zone"],
                "script_json": row.get("script_json"),
                "failed_questions": row.get("failed_questions", []),
                "fixed_questions": row.get("fixed_questions", []),
                "created_at": row["created_at"],
            }
            for row in (result.data or [])
        ]

    def delete_for_run(self, run_id: str) -> int:
        """Delete all iteration logs for a run.

        Args:
            run_id: Pipeline run ID

        Returns:
            Number of rows deleted
        """
        result = self._db().delete().eq("run_id", run_id).execute()
        return len(result.data) if result.data else 0
