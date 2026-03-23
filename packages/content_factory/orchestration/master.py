"""Component 1: The Hermes Master Orchestrator.

Routes documents between specialist agents, maintains the Production Cycle 
Registry, enforces conditional/sequential execution protocols, and handles
escalations.
"""

from packages.core.logger import get_logger
from packages.content_factory.orchestration.db import OrchestrationDB
from packages.content_factory.orchestration.models import ProductionCycleRecord, EscalationItem, CycleStatus, ProductionPhase
from packages.content_factory.topic_finder.models import TopicBrief
from datetime import datetime, timezone
import uuid
import time
from packages.memory.client import ZepMemoryClient

logger = get_logger("HermesMasterOrchestrator")

class MasterOrchestrator:
    def __init__(self):
        self.db = OrchestrationDB()
        self.max_concurrent_cycles = 2
        self.zep_client = ZepMemoryClient()
        
    def check_and_start_new_cycle(self, reservoir_topics: list[TopicBrief]):
        """Triggered by the Cron Scheduler or manual events. Scans for availability."""
        active = self.db.get_active_cycles()
        
        if len(active) >= self.max_concurrent_cycles:
            logger.info(f"orchestrator_full | active_cycles={len(active)}")
            return
            
        # Select best Tier 1 topic
        tier_1 = [t for t in reservoir_topics if t.viability_score_breakdown.get('total', 0) >= 12]
        if not tier_1:
            logger.info("orchestrator_idle_no_tier1_topics")
            return
            
        selected_topic = sorted(tier_1, key=lambda t: t.viability_score_breakdown.get('total', 0), reverse=True)[0]
        
        cycle = ProductionCycleRecord(
            cycle_id=str(uuid.uuid4()),
            topic_statement=selected_topic.topic_statement,
            genre=selected_topic.genre_id,
            source="topic_finder",
            current_phase=ProductionPhase.TOPIC_SELECTED.value,
            status=CycleStatus.ACTIVE.value
        )
        self.db.create_cycle(cycle)
        logger.info(f"started_new_cycle | cycle_id={cycle.cycle_id} topic={cycle.topic_statement[:40]}")
        
        # Initialize Zep Session for this Production Cycle
        self.zep_client.create_user(user_id=cycle.cycle_id, metadata={"topic": cycle.topic_statement})
        self.zep_client.create_session(session_id=cycle.cycle_id, user_id=cycle.cycle_id)
        self.zep_client.add_facts(session_id=cycle.cycle_id, facts=[{
            "fact": f"Started production cycle {cycle.cycle_id} for topic: {cycle.topic_statement} (Genre: {cycle.genre})",
            "source": "orchestrator",
            "phase": cycle.current_phase
        }])
        
        # Trigger the pipeline runner for this cycle (non-blocking)
        import asyncio
        asyncio.create_task(self._trigger_pipeline(cycle.cycle_id, selected_topic))

    async def _trigger_pipeline(self, cycle_id: str, topic: TopicBrief) -> None:
        """Start a PipelineRunner for this production cycle."""
        try:
            from packages.pipeline.runner import PipelineRunner
            runner = PipelineRunner()
            run = await runner.create_run()
            self.db.update_pipeline_run_id(cycle_id, run.run_id)
            logger.info(f"pipeline_triggered | cycle={cycle_id} run={run.run_id}")
        except Exception as e:
            logger.error(f"pipeline_trigger_failed: {e} cycle={cycle_id}")
        
    def advance_phase(self, cycle_id: str, new_phase: str):
        """Sequential Routing enforcement."""
        # 1. Acquire Lock
        if not self.db.acquire_lock(cycle_id):
            logger.warning(f"state_conflict_error | cycle_id={cycle_id}")
            return False
            
        try:
            # 2. Update DB (mocked as simple release for now)
            # Fetch, modify, save logic would go here.
            self.zep_client.add_facts(session_id=cycle_id, facts=[{
                "fact": f"Advanced to phase {new_phase}",
                "source": "orchestrator",
                "phase": new_phase
            }])
            logger.info(f"routing_advancement | cycle_id={cycle_id} new_phase={new_phase}")
        finally:
            self.db.release_lock(cycle_id)
            return True

    def handle_escalation(self, cycle_id: str, error_type: str, severity: str, context: dict):
        """Escalation Handler wrapping."""
        escalation = EscalationItem(
            escalation_id=str(uuid.uuid4()),
            cycle_id=cycle_id,
            type=error_type,
            severity=severity,
            context_payload=context
        )
        self.db.escalate(escalation)
        
        self.zep_client.add_facts(session_id=cycle_id, facts=[{
            "fact": f"Escalation triggered: {error_type} (Severity: {severity}). Context: {context}",
            "source": "orchestrator",
            "error_type": error_type,
            "severity": severity
        }])
        
        logger.warning(f"escalation_routed_to_human | cycle_id={cycle_id} type={error_type}")
        
        # Pause the cycle
        if not self.db.acquire_lock(cycle_id):
            return
        try:
            # Code to set status to 'paused' and phase to 'awaiting_review'
            pass
        finally:
            self.db.release_lock(cycle_id)

    def write_production_cycle_summary(
        self, 
        cycle_id: str, 
        topic_statement: str,
        genre: str,
        gap_type: str,
        source_type: str,
        final_score: float,
        iterations: int,
        engagement_score: float,
        view_duration_pct: float,
        subscriber_conversion: float,
        narrative_summary: str
    ):
        """Writes the end-of-cycle summary to the Zep Session combining production & analytics."""
        
        metadata = {
            "production_cycle_id": cycle_id,
            "topic_statement": topic_statement,
            "genre": genre,
            "gap_type": gap_type,
            "source_type": source_type,
            "final_binary_score": final_score,
            "experiment_iterations": iterations,
            "youtube_engagement_score": engagement_score,
            "view_duration_pct": view_duration_pct,
            "subscriber_conversion": subscriber_conversion,
            "production_date": datetime.now(timezone.utc).isoformat()
        }
        
        self.zep_client.add_facts(session_id=cycle_id, facts=[{
            "content": narrative_summary,
            "source": "production_cycle_summary",
            **metadata
        }])
        logger.info(f"wrote_production_cycle_summary_to_zep | cycle_id={cycle_id}")
