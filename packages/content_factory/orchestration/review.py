"""Component 6: The Human Review Interface.

A structured mechanism for cases where the intelligence layer cannot resolve
something autonomously. Handles Instruction updates, Hard Failures, and
Sensitive Content Reviews.

C3 FIX: Migrated from SQLite to Supabase. Previously queried a separate
SQLite 'human_escalations' table while orchestrator wrote to Supabase
'escalations' table — making all escalations invisible to the review UI.
"""

from typing import Literal, Any
import json
import asyncio
from datetime import datetime, timezone
from packages.core.logger import get_logger
from packages.content_factory.orchestration.master import MasterOrchestrator
from packages.content_factory.orchestration.models import EscalationItem

logger = get_logger("HumanReviewInterface")

class ReviewDecisions:
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    CONTINUE_BASELINE = "continue"
    REVISE_MANUALLY = "revise"
    ABANDON = "abandon"

class ReviewInterface:
    def __init__(self, master: MasterOrchestrator):
        self.master = master
        self._pending_tasks: list = []
        # C3 FIX: Removed SQLite dependency (self.db_path)
        # All queries now go through Supabase (same DB as orchestrator)
        
    def get_pending_escalations(self) -> list[EscalationItem]:
        """Fetches unresolved escalations from Supabase 'escalations' table.
        
        C3 FIX: Previously queried SQLite 'human_escalations' table which
        was never written to by the orchestrator (which writes to Supabase).
        Now reads from the same Supabase table the orchestrator writes to.
        """
        from packages.core.supabase_client import get_supabase
        
        try:
            sb = get_supabase()
            result = (sb.table("escalations")
                .select("*")
                .eq("status", "pending")
                .order("created_at", desc=False)
                .execute())
            
            items = []
            for r in (result.data or []):
                context = r.get("context_payload", {})
                if isinstance(context, str):
                    try:
                        context = json.loads(context)
                    except json.JSONDecodeError:
                        context = {}
                items.append(EscalationItem(
                    escalation_id=r["escalation_id"],
                    cycle_id=r["cycle_id"],
                    type=r["type"],
                    severity=r["severity"],
                    context_payload=context,
                    status=r["status"],
                    created_at=datetime.fromisoformat(r["created_at"])
                ))
            return items
        except Exception as e:
            logger.error(f"get_pending_escalations_failed: {e}")
            return []

    def resolve_instruction_update(self, escalation_id: str, decision: str, modified_text: str = None):
        """Action handler for Instruction Update Approvals."""
        logger.info(f"resolving_instruction_escalation | esc_id={escalation_id} dec={decision}")
        if decision == ReviewDecisions.APPROVE:
            # Active version -> pass to Hermes memory skills
            pass
        elif decision == ReviewDecisions.MODIFY:
            # Save modified text to version history -> Active
            pass
            
        self._mark_resolved(escalation_id, decision)

    def _fire_advance_phase(self, cycle_id: str):
        """Bridge sync→async: queue advance_phase, log failures."""
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self.master.advance_phase(cycle_id, "completed"))
            task.add_done_callback(
                lambda t: logger.warning(f"advance_phase_task_failed: {t.exception()}")
                if t.exception() else None
            )
            self._pending_tasks.append(task)
            logger.info(f"advance_phase_fired: cycle={cycle_id}")
        except RuntimeError:
            logger.error(f"advance_phase_NO_LOOP: no running event loop, advance queued: cycle={cycle_id}")
            self._pending_tasks.append(("queued_advance", cycle_id))

    async def flush_pending_tasks(self):
        """Flush pending async tasks. Call from an async context to guarantee execution."""
        for item in self._pending_tasks:
            if isinstance(item, tuple) and item[0] == "queued_advance":
                try:
                    await self.master.advance_phase(item[1], "completed")
                    logger.info(f"flushed_queued_advance_phase: cycle={item[1]}")
                except Exception as e:
                    logger.error(f"flushed_advance_phase_failed: {e}")
            elif isinstance(item, asyncio.Task):
                try:
                    await item
                except Exception as e:
                    logger.error(f"flushed_task_failed: {e}")
        self._pending_tasks.clear()

    def resolve_hard_failure(self, escalation_id: str, cycle_id: str, decision: str):
        """Action handler for Hard Failure loops in Phase 4."""
        logger.info(f"resolving_hard_failure | cycle={cycle_id} dec={decision}")
        if decision == ReviewDecisions.CONTINUE_BASELINE:
            # Force advance phase
            self._fire_advance_phase(cycle_id)
        elif decision == ReviewDecisions.ABANDON:
            self._abandon_cycle(cycle_id)
        
        self._mark_resolved(escalation_id, decision)

    def resolve_sensitive_content(self, escalation_id: str, cycle_id: str, decision: str):
        """Partition/Religious claims mandatory human checkpoints."""
        logger.info(f"resolving_sensitive_content | cycle={cycle_id} dec={decision}")
        
        if decision == ReviewDecisions.APPROVE:
            # Allow cycle to continue to experiment loop
            pass
        elif decision == ReviewDecisions.REVISE_MANUALLY:
            # Flag cycle for revision
            pass
            
        self._mark_resolved(escalation_id, decision)

    def _mark_resolved(self, escalation_id: str, decision: str):
        """C3 FIX: Update status in Supabase 'escalations' table (was SQLite)."""
        from packages.core.supabase_client import get_supabase
        try:
            sb = get_supabase()
            sb.table("escalations").update({"status": decision}) \
                .eq("escalation_id", escalation_id).execute()
        except Exception as e:
            logger.error(f"mark_resolved_failed: {e}")

    def _abandon_cycle(self, cycle_id: str):
        """Releases lock, sets registry to ABANDONED via Supabase.
        
        C3 FIX: Uses OrchestrationDB instead of direct SQLite access.
        """
        if self.master.db.acquire_lock(cycle_id):
            try:
                self.master.db._cycles().update({
                    "status": "abandoned",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("cycle_id", cycle_id).execute()
            finally:
                self.master.db.release_lock(cycle_id)
