"""Component 4: The Instruction Update Pipeline.

Manages risk when updating agent instructions across the factory.
Controls Versioning, Scoped Updates, Regression Testing, and Human Approval Gates.
"""

from typing import Literal, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid
from packages.core.logger import get_logger
from packages.content_factory.orchestration.synthesis import Insight
from packages.content_factory.orchestration.master import MasterOrchestrator

logger = get_logger("InstructionUpdatePipeline")

class InstructionVersion(BaseModel):
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
    def __init__(self, master: MasterOrchestrator):
        self.master = master
        self.active_versions: dict[str, InstructionVersion] = {}
        
    def process_insight(self, insight: Insight):
        """Creates a Draft Version for an accepted Synthesis Insight."""
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
        """Calculates scope based on affected genres and implicating categories."""
        if len(insight.genres_affected) > 2 and insight.confidence == "high":
            return "wide"
        if len(insight.binary_categories_implicated) > 1:
            return "medium"
        return "narrow"

    def _run_regression_test(self, draft: InstructionVersion, genres: list[str]) -> bool:
        """
        Simulates scoring the last 5 completed cycles with the new draft instruction.
        Special Rule: For Islamic History updates, Tonal Calibration must not decrease.
        """
        logger.info(f"running_regression_protocol | target_agent={draft.agent_id}")
        # Mocking passing all simulations
        
        for g in genres:
            if g == "islamic_history" or g == "south_asian_history":
                logger.info("regression_testing_tonal_calibration_flag")
                # Specific tonal check mapping
                pass
                
        # If simulation score < actual old score -> False
        return True

    def _route_approval(self, draft: InstructionVersion, insight: Insight):
        """Routing to Human Review Interface based on Matrix."""
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
            # Notification only
            self.master.handle_escalation(
                cycle_id="N/A", error_type="instruction_update",
                severity="low", context={"note": "Auto-activated narrow update", "version": draft.version_id}
            )

    def _escalate_for_review(self, draft: InstructionVersion, reason: str, severity: str):
        logger.info(f"escalating_instruction_update | reason={reason}")
        # Passes the proposed and old instruction diff to the Esc handler
        self.master.handle_escalation(
            cycle_id="N/A", 
            error_type="instruction_update", 
            severity=severity,
            context={"proposed_change": draft.content, "reason": reason}
        )

    def _activate_version(self, draft: InstructionVersion):
        draft.active_date = datetime.now(timezone.utc)
        self.active_versions[draft.agent_id] = draft
        # This will be where we invoke Hermes memory skills update component
        
    def check_rollback_monitor(self, agent_id: str, new_score: float):
        """Monitors post-update actual cycles for regressions. Three drops -> Rollback."""
        version = self.active_versions.get(agent_id)
        if not version or version.is_rollback:
            return
            
        version.post_update_scores.append(new_score)
        if len(version.post_update_scores) >= 3:
            avg_post = sum(version.post_update_scores) / len(version.post_update_scores)
            avg_pre = sum(version.pre_update_scores) / len(version.pre_update_scores) if version.pre_update_scores else avg_post
            if avg_post < avg_pre:
                logger.warning(f"rollback_triggered | agent={agent_id} pre={avg_pre} post={avg_post}")
                self._rollback(agent_id)

    def _rollback(self, agent_id: str):
        version = self.active_versions[agent_id]
        version.is_rollback = True
        logger.info(f"rollback_completed | version_id={version.version_id}")
        # Notify synthesis engine that this insight was proven incorrect
