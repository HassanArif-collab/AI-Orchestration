"""Phase 7: Orchestration Database Strategy.

Maintains the persistent Production Cycle Registry using Supabase.
Includes Optimistic Locking mechanism for State Synchronization.

DATABASE TABLES:

  production_cycles
    One row per production cycle. Tracks lifecycle from topic_selected
    through all production rounds to completed/failed.
    Key fields: cycle_id, topic_statement, genre, current_phase,
                current_baseline_score, experiment_iterations,
                pipeline_run_id (links to PipelineRunner run_id)
    Locking: lock_expires_at prevents concurrent phase advances.
             Locks expire after 30 seconds to prevent deadlocks.

  escalations
    Items requiring human decision before the system can proceed.
    Created by: MasterOrchestrator.handle_escalation()
    Read by: ReviewInterface.get_pending_escalations()
    Status flow: pending -> approved/rejected/modified

ALL DATA IN SUPABASE -- replacing packages/data/pipeline.db
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from packages.content_factory.orchestration.models import ProductionCycleRecord, EscalationItem


class OrchestrationDB:
    """Supabase persistence layer for the orchestration system.

    Handles all database operations for production cycle state,
    human escalations, and instruction version tracking.

    USAGE:
      db = OrchestrationDB()
      db.create_cycle(record)
      db.acquire_lock(cycle_id)  # before modifying
      # ... make changes ...
      db.release_lock(cycle_id)
    """

    def __init__(self):
        pass  # Tables pre-created via Supabase migration

    def _cycles(self):
        from packages.core.supabase_client import get_supabase
        return get_supabase().table("production_cycles")

    def _escalations(self):
        from packages.core.supabase_client import get_supabase
        return get_supabase().table("escalations")

    def create_cycle(self, record: ProductionCycleRecord):
        """Insert a new production cycle record.

        Called by MasterOrchestrator.check_and_start_new_cycle()
        when a Tier 1 topic is selected for production.

        Args:
          record: ProductionCycleRecord with all required fields
        """
        self._cycles().insert({
            "cycle_id": record.cycle_id,
            "topic_statement": record.topic_statement,
            "genre": record.genre,
            "source": record.source,
            "current_phase": record.current_phase,
            "status": record.status,
            "current_baseline_score": record.current_baseline_score,
            "experiment_iterations": record.experiment_iterations,
            "music_architecture_id": record.music_architecture_id,
            "published_video_id": record.published_video_id,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }).execute()

    def acquire_lock(self, cycle_id: str, owner_id: str = "default", ttl_seconds: int = 3600) -> bool:
        """Optimistic locking for safe concurrent access.

        Attempts to acquire an exclusive lock on a cycle record.
        Returns True if the lock was acquired, False if already locked.

        Locks automatically expire after ttl_seconds to prevent
        deadlocks if a process crashes while holding a lock.

        Args:
          cycle_id: The cycle to lock
          owner_id: Identifier of the lock owner (default "default")
          ttl_seconds: Lock expiration time (default 3600s)

        Returns:
          True if lock acquired, False if already locked by another process
        """
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(seconds=ttl_seconds)).isoformat()
        # Try to update only if lock is expired or null
        result = (
            self._cycles()
            .update({"lock_expires_at": expires, "lock_owner": owner_id, "updated_at": now.isoformat()})
            .eq("cycle_id", cycle_id)
            .or_(f"lock_expires_at.is.null,lock_expires_at.lt.{now.isoformat()}")
            .execute()
        )
        return bool(result.data)  # True if a row was updated

    def release_lock(self, cycle_id: str, owner_id: str = None):
        """Release a previously acquired lock.

        Only the owner who acquired the lock can release it.
        Always call this after completing a modification, even if
        the operation failed -- prevents lock buildup.

        Args:
          cycle_id: The cycle to unlock
          owner_id: Identifier of the lock owner (required if lock has owner)
        """
        query = self._cycles().update(
            {"lock_expires_at": None}
        ).eq("cycle_id", cycle_id)

        # If owner_id provided, only release if we own the lock
        if owner_id is not None:
            query = query.eq("lock_owner", owner_id)

        result = query.execute()
        if not result.data:
            import logging
            logging.getLogger(__name__).warning(
                f"release_lock_no_match: cycle_id={cycle_id} owner_id={owner_id}"
            )

    def get_active_cycles(self) -> list[ProductionCycleRecord]:
        """Fetch all cycles currently in active production.

        Used by MasterOrchestrator to enforce the max 2 concurrent
        cycles limit.

        Returns:
          List of ProductionCycleRecord objects with status='active'
        """
        result = self._cycles().select("*").eq("status", "active").execute()
        return [
            ProductionCycleRecord(
                cycle_id=r["cycle_id"],
                topic_statement=r["topic_statement"],
                genre=r["genre"],
                source=r.get("source", "topic_finder"),
                current_phase=r["current_phase"],
                status=r["status"],
                current_baseline_score=r.get("current_baseline_score", 0.0),
                experiment_iterations=r.get("experiment_iterations", 0),
                music_architecture_id=r.get("music_architecture_id"),
                published_video_id=r.get("published_video_id"),
                created_at=datetime.fromisoformat(r["created_at"]),
                updated_at=datetime.fromisoformat(r["updated_at"]),
            )
            for r in (result.data or [])
        ]

    def escalate(self, item: EscalationItem):
        """Create a human escalation record.

        Called by MasterOrchestrator.handle_escalation() when the system
        encounters a situation requiring human judgment.

        Args:
          item: EscalationItem with all required fields
        """
        self._escalations().insert({
            "escalation_id": item.escalation_id,
            "cycle_id": item.cycle_id,
            "type": item.type,
            "severity": item.severity,
            "context_payload": item.context_payload,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
        }).execute()

    def update_pipeline_run_id(self, cycle_id: str, pipeline_run_id: str) -> None:
        """Link a pipeline run to a production cycle."""
        self._cycles().update(
            {"pipeline_run_id": pipeline_run_id}
        ).eq("cycle_id", cycle_id).execute()
