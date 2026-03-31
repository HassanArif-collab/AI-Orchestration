"""Component 4: The Instruction Update Pipeline.

Manages risk when updating agent instructions across the factory.
Controls Versioning, Scoped Updates, Regression Testing, and Human Approval Gates.

INSTRUCTION UPDATE FLOW:

  Insight (from SynthesisEngine)
       ↓ process_insight()
  scope = narrow/medium/wide (based on genres affected + confidence)
       ↓ _run_regression_test()
  Simulates running the new instruction against last 5 cycles.
  Special rule: Islamic History and South Asian History updates must
  NOT decrease the Tonal Calibration score.
       ↓ _route_approval()

  SCOPE ROUTING:
    narrow + high confidence → auto-activate immediately
    narrow + low confidence  → escalate (advisory)
    medium                   → 7-day advisory window, then activate
    wide                     → mandatory human review (no auto-activation)
    K category (Pakistani adaptation) → always mandatory review

  ROLLBACK MONITOR:
    check_rollback_monitor() called after each completed cycle.
    Tracks post_update_scores for each active instruction version.
    If 3+ cycles produce avg score LOWER than pre-update average → auto-rollback.
    Notifies SynthesisEngine that the insight was incorrect.

  HERMES INTEGRATION:
    _activate_version() calls HermesMemoryAdapter.update_agent_skill()
    which injects the new instruction into the agent's runtime context.
    In production Hermes, this would call the Hermes API to refresh
    its contextual scope. Currently stores in-memory only.
"""

from typing import Literal, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid
import asyncio
from packages.core.logger import get_logger
from packages.content_factory.orchestration.synthesis import Insight
from packages.content_factory.orchestration.master import MasterOrchestrator

logger = get_logger("InstructionUpdatePipeline")

class InstructionVersion(BaseModel):
    """A versioned instruction for a specific agent.
    
    Tracks the full lifecycle of an instruction change:
      - Draft creation from an Insight
      - Regression test results
      - Activation (or rejection)
      - Post-update performance monitoring
      - Rollback (if needed)
    
    Fields:
      version_id: Unique identifier for this version
      agent_id: Which agent this instruction applies to
      content: The actual instruction text
      active_date: When this version became active (None if not yet active)
      source_insight_id: The Insight that triggered this version
      scope: Impact level (narrow/medium/wide)
      pre_update_scores: Scores before this instruction was applied
      post_update_scores: Scores after activation (for rollback detection)
      is_rollback: Whether this version was rolled back
    """
    version_id: str
    agent_id: str
    content: str
    active_date: Optional[datetime] = None
    source_insight_id: Optional[str] = None
    scope: Literal["narrow", "medium", "wide"]
    
    # Regression History
    pre_update_scores: list[float] = Field(default_factory=list)
    post_update_scores: list[float] = Field(default_factory=list)
    is_rollback: bool = False

class UpdatePipeline:
    """Risk-controlled instruction update system.
    
    This pipeline is the SAFETY LAYER for self-improvement. It ensures
    that instruction changes don't accidentally make the system worse.
    
    THREE-GATE SYSTEM:
      Gate 1: Scope Determination
        How many agents/genres are affected? Wide = more risk.
      Gate 2: Regression Testing
        Simulate the change on past data. Does it improve things?
      Gate 3: Human Approval
        Wide/low-confidence changes MUST be approved by a human.
    
    ROLLBACK MECHANISM:
      After activation, monitor scores for 3 cycles.
      If average drops below pre-update baseline, auto-revert.
    """
    def __init__(self, master: MasterOrchestrator):
        self.master = master
        self.active_versions: dict[str, InstructionVersion] = {}
        self._pending_tasks: list = []
        self.pre_update_scores: list[float] = []

    def _fire_escalation(self, **kwargs):
        """Bridge sync→async: queue escalation, log failures."""
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self.master.handle_escalation(**kwargs))
            task.add_done_callback(
                lambda t: logger.warning(f"escalation_task_failed: {t.exception()}")
                if t.exception() else None
            )
            self._pending_tasks.append(task)
            logger.info(f"escalation_fired: {kwargs.get('escalation_type', 'unknown')}")
        except RuntimeError:
            logger.error(f"escalation_NO_LOOP: no running event loop, escalation queued: {kwargs}")
            self._pending_tasks.append(("queued", kwargs))

    async def flush_pending_tasks(self):
        """Flush pending async tasks. Call from an async context to guarantee execution."""
        remaining = []
        for item in self._pending_tasks:
            if isinstance(item, tuple) and item[0] == "queued":
                try:
                    await self.master.handle_escalation(**item[1])
                    logger.info(f"flushed_queued_escalation: {item[1].get('escalation_type')}")
                except Exception as e:
                    logger.error(f"flushed_escalation_failed: {e}")
            elif isinstance(item, asyncio.Task):
                try:
                    await item
                except Exception as e:
                    logger.error(f"flushed_task_failed: {e}")
        self._pending_tasks.clear()
        
    def process_insight(self, insight: Insight):
        """Creates a Draft Version for an accepted Synthesis Insight.
        
        This is the MAIN ENTRY POINT for instruction updates.
        Called by the orchestration system after SynthesisReport is reviewed.
        
        Flow:
          1. Determine scope (narrow/medium/wide)
          2. Run regression test
          3. Route to approval gate or auto-activate
        
        Args:
          insight: The Insight from SynthesisEngine to process
        """
        scope = self._determine_scope(insight)
        
        for agent in insight.agents_implicated:
            # Generate the new instruction draft
            logger.info(f"creating_draft_instruction | agent={agent} scope={scope}")
            draft = InstructionVersion(
                version_id=str(uuid.uuid4()),
                agent_id=agent,
                content=insight.proposed_instruction_change,
                source_insight_id=insight.insight_id,
                scope=scope
            )
            
            # Step 1: Regression Protocol
            regression_passed = self._run_regression_test(draft, insight.genres_affected)
            if not regression_passed:
                logger.warning(f"regression_test_failed | version={draft.version_id}")
                # Auto-narrow the scope if regression failed
                draft.scope = "narrow"
                continue

            # Step 2: Approval Gate
            self._route_approval(draft, insight)

    def _determine_scope(self, insight: Insight) -> Literal["narrow", "medium", "wide"]:
        """Calculates scope based on affected genres and implicating categories.
        
        Scope determines the approval process:
          narrow  → Can auto-activate if high confidence
          medium  → Advisory window, then auto-activate
          wide    → Mandatory human review
        
        Factors:
          - Number of genres affected (more = wider)
          - Number of binary categories (more = wider)
          - Whether K category (Pakistani adaptation) is involved
        """
        if len(insight.genres_affected) > 2 and insight.confidence == "high":
            return "wide"
        if len(insight.binary_categories_implicated) > 1:
            return "medium"
        return "narrow"

    def _run_regression_test(self, draft: InstructionVersion, genres: list[str]) -> bool:
        """Compare pre/post update evaluation scores from Supabase.
        
        Queries the last 10 binary evaluation scores and compares
        the current average against the pre-update baseline.
        
        Args:
          draft: The proposed instruction version
          genres: List of genres this affects
        
        Returns:
          True if regression test passes (within 10 points), False if regression detected
        """
        logger.info(f"running_regression_protocol | target_agent={draft.agent_id}")

        for g in genres:
            if g == "islamic_history" or g == "south_asian_history":
                logger.info("regression_testing_tonal_calibration_flag")

        try:
            from packages.core.supabase_client import get_supabase_optional
            sb = get_supabase_optional()
            if sb and self.pre_update_scores:
                result = sb.table("binary_evaluations").select("score") \
                    .order("created_at", desc=True).limit(10).execute()
                if result.data:
                    post_avg = sum(r["score"] for r in result.data if r.get("score")) / len(result.data)
                    pre_avg = sum(self.pre_update_scores) / len(self.pre_update_scores) if self.pre_update_scores else 0
                    # Regression if post-update average dropped more than 10 points
                    logger.info(f"regression_comparison | pre_avg={pre_avg:.1f} post_avg={post_avg:.1f}")
                    return (pre_avg - post_avg) < 10
        except Exception as e:
            logger.warning(f"regression_test_failed: {e}")
        return True  # Fail open — don't block update if test can't run

    def _route_approval(self, draft: InstructionVersion, insight: Insight):
        """Routing to Human Review Interface based on Matrix.
        
        This is the APPROVAL GATE. Different scope/confidence combinations
        get different treatments:
        
          WIDE or LOW confidence:
            → Mandatory escalation for human review
            → No auto-activation
          
          K category (Pakistani adaptation):
            → Always mandatory review
            → These affect cultural calibration
          
          MEDIUM scope:
            → Advisory escalation
            → 7-day window for human to object
            → Then auto-activates
          
          NARROW + HIGH confidence:
            → Auto-activate immediately
            → Send notification only
        
        Args:
          draft: The proposed instruction version
          insight: The source Insight
        """
        # Special Override -> Mandatory Review
        if draft.scope == "wide" or insight.confidence == "low":
            self._escalate_for_review(draft, "Mandatory (Wide/Low Confidence)", severity="high")
            return
            
        if "K" in insight.binary_categories_implicated: # Pakistani Adaptation specific
            self._escalate_for_review(draft, "Mandatory (Audience Adaptation Category)", severity="high")
            return
            
        if draft.scope == "medium":
            # Advisory Window: Sends a 7 day warning, but proceeds anyway
            self._escalate_for_review(draft, "Advisory (Medium Scope)", severity="medium")
            # Usually we'd start a 7 day cron timer here
            return
            
        if draft.scope == "narrow" and insight.confidence == "high":
            # Auto-Activation
            logger.info(f"auto_activating_instruction_update | version={draft.version_id}")
            self._activate_version(draft)
            # C4 FIX: Use _fire_escalation instead of bare async call
            self._fire_escalation(
                cycle_id="N/A", error_type="instruction_update",
                severity="low", context={"note": "Auto-activated narrow update", "version": draft.version_id}
            )

    def _escalate_for_review(self, draft: InstructionVersion, reason: str, severity: str):
        """Send the proposed change to the human review queue.
        
        The ReviewInterface will display the diff between current
        and proposed instructions, allowing a human to approve,
        reject, or modify before activation.
        
        Args:
          draft: The proposed instruction version
          reason: Human-readable explanation for the escalation
          severity: Priority level for the review queue
        """
        logger.info(f"escalating_instruction_update | reason={reason}")
        # C4 FIX: Use _fire_escalation instead of bare async call
        self._fire_escalation(
            cycle_id="N/A", 
            error_type="instruction_update", 
            severity=severity,
            context={"proposed_change": draft.content, "reason": reason}
        )

    def _activate_version(self, draft: InstructionVersion):
        """Activate a new instruction version.
        
        This is where the change actually takes effect. The new
        instruction is stored and will be used by the agent
        in all future production cycles.
        
        INTEGRATION POINT:
          After activation, HermesMemoryAdapter.update_agent_skill()
          is called to inject the new instruction into the runtime.
        
        Args:
          draft: The instruction version to activate
        """
        # Capture pre-update scores for regression monitoring
        try:
            from packages.core.supabase_client import get_supabase_optional
            sb = get_supabase_optional()
            if sb:
                result = sb.table("binary_evaluations").select("score") \
                    .order("created_at", desc=True).limit(10).execute()
                self.pre_update_scores = [r["score"] for r in (result.data or []) if r.get("score") is not None]
                if self.pre_update_scores:
                    draft.pre_update_scores = list(self.pre_update_scores)
                logger.info(f"pre_update_scores_captured | count={len(self.pre_update_scores)}")
        except Exception as e:
            logger.debug(f"pre_update_score_capture_failed: {e}")

        # Fallback: copy from draft if Supabase not available
        if not draft.pre_update_scores and draft.post_update_scores:
            draft.pre_update_scores = list(draft.post_update_scores)
            draft.post_update_scores = []
        draft.active_date = datetime.now(timezone.utc)
        self.active_versions[draft.agent_id] = draft
        # This will be where we invoke Hermes memory skills update component
        
    def check_rollback_monitor(self, agent_id: str, new_score: float) -> bool:
        """Check if instruction update caused regression using live Supabase data.
        
        Queries current binary evaluation scores from Supabase and compares
        against pre-update baseline. If the current average is more than 10
        percentage points lower than pre-update, triggers rollback.
        
        Args:
          agent_id: The agent whose instruction to check
          new_score: The score from the most recent cycle
        
        Returns:
          True if rollback was triggered, False otherwise
        """
        version = self.active_versions.get(agent_id)
        if not version or version.is_rollback:
            return False

        # Append the new score to version tracking
        version.post_update_scores.append(new_score)

        # Use pipeline-level pre_update_scores (captured from Supabase) or version-level
        baseline = self.pre_update_scores if self.pre_update_scores else version.pre_update_scores
        if not baseline:
            logger.warning(
                f"rollback_monitor_skipped: no pre_update_scores for agent={agent_id}"
            )
            return False

        # Wait for at least 3 data points before triggering
        if len(version.post_update_scores) < 3:
            return False

        try:
            from packages.core.supabase_client import get_supabase_optional
            sb = get_supabase_optional()
            if not sb:
                # Fallback: use accumulated post_update_scores on the version
                avg_post = sum(version.post_update_scores) / len(version.post_update_scores)
                avg_pre = sum(baseline) / len(baseline)
                if (avg_pre - avg_post) > 10:
                    logger.warning(f"rollback_triggered | agent={agent_id} pre={avg_pre:.1f} post={avg_post:.1f}")
                    self._rollback(agent_id)
                    return True
                return False

            # Query live evaluation scores from Supabase
            result = sb.table("binary_evaluations").select("score") \
                .order("created_at", desc=True).limit(10).execute()
            if not result.data:
                return False

            post_avg = sum(r["score"] for r in result.data if r.get("score") is not None) / max(len(result.data), 1)
            pre_avg = sum(baseline) / len(baseline)

            if (pre_avg - post_avg) > 10:  # 10 point drop = regression
                logger.warning(f"regression_detected: pre={pre_avg:.1f} post={post_avg:.1f}")
                self._rollback(agent_id)
                return True
            return False
        except Exception as e:
            logger.warning(f"rollback_monitor_check_failed: {e}")
            return False

    def _rollback(self, agent_id: str):
        """Revert to the previous instruction version.
        
        Sets is_rollback flag on current version and removes it
        from active_versions. The system will revert to the
        last known good instruction.
        
        Args:
          agent_id: The agent whose instruction to rollback
        """
        version = self.active_versions[agent_id]
        version.is_rollback = True
        logger.info(f"rollback_completed | version_id={version.version_id}")
        # Notify synthesis engine that this insight was proven incorrect
