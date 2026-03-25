"""Component 6: The Human Review Interface.

A structured mechanism for cases where the intelligence layer cannot resolve
something autonomously. Handles Instruction updates, Hard Failures, and
Sensitive Content Reviews.
"""

from typing import Literal, Any
import sqlite3
from pathlib import Path
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
        self.db_path = Path("packages/data/pipeline.db")
        
    def get_pending_escalations(self) -> list[EscalationItem]:
        """Fetches unresolved escalations ordered by severity and age."""
        if not self.db_path.exists():
            return []
            
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM human_escalations 
                WHERE status = 'pending'
                ORDER BY 
                    CASE severity 
                        WHEN 'critical' THEN 1 
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    created_at ASC
            ''')
            rows = cursor.fetchall()
            
            import json
            results = []
            for r in rows:
                from datetime import datetime
                results.append(EscalationItem(
                    escalation_id=r['escalation_id'],
                    cycle_id=r['cycle_id'],
                    type=r['type'],
                    severity=r['severity'],
                    context_payload=json.loads(r['context_payload']),
                    status=r['status'],
                    created_at=datetime.fromisoformat(r['created_at'])
                ))
            return results

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

    def resolve_hard_failure(self, escalation_id: str, cycle_id: str, decision: str):
        """Action handler for Hard Failure loops in Phase 4."""
        logger.info(f"resolving_hard_failure | cycle={cycle_id} dec={decision}")
        if decision == ReviewDecisions.CONTINUE_BASELINE:
            # Force advance phase
            self.master.advance_phase(cycle_id, "completed") # skips experiment
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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE human_escalations 
                SET status = ? 
                WHERE escalation_id = ?
            ''', (decision, escalation_id))
            conn.commit()

    def _abandon_cycle(self, cycle_id: str):
        """Releases lock, sets registry to ABANDONED."""
        if self.master.db.acquire_lock(cycle_id):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE production_registry SET status = 'abandoned' WHERE cycle_id = ?",
                        (cycle_id,)
                    )
                    conn.commit()
            finally:
                self.master.db.release_lock(cycle_id)
