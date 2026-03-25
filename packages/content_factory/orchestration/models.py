"""Phase 7: Orchestration Models.

Defines the core state tracking structures for the Production Cycle Registry,
Hermes memory injection payloads, and Human Review Escalations.

KEY MODEL RELATIONSHIPS:

  ProductionPhase (enum)
    The fine-grained phase tracker inside a cycle. Maps to the
    RoundBasedProductionWorkflow rounds:
      TOPIC_SELECTED → PHASE_3_ROUND_1A → 1B → 2 → 3 → 4
      → PHASE_4_EXPERIMENT → PHASE_6_MUSIC → AWAITING_REVIEW → COMPLETED

  ProductionCycleRecord
    The master record. One per video being produced.
    current_baseline_score: updated after each ExperimentLoop iteration
    experiment_iterations: how many mutation cycles have run
    pipeline_run_id: links to packages/pipeline's PipelineRun.run_id
    lock_expires_at: set by advance_phase() to prevent concurrent writes

  EscalationItem
    Created whenever the system cannot proceed without human input.
    Five types and what triggers them:
      instruction_update → UpdatePipeline found a wide/low-confidence change
      hard_failure       → Stage failed 3+ times in a row
      reservoir_low      → TopicReservoir has < 3 Tier 1 topics
      weekly_summary     → Normal weekly SynthesisReport for human review
      sensitive_content  → Script flagged for cultural sensitivity review
"""

from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Literal, Optional, Any
from enum import Enum

class ProductionPhase(str, Enum):
    """The sequence of phases a production cycle moves through.
    
    A production cycle progresses through these phases in order:
      1. TOPIC_SELECTED — Tier 1 topic picked from reservoir
      2. PHASE_3_ROUND_1A — Initial research gathering
      3. PHASE_3_ROUND_1B — Anchor availability check
      4. PHASE_3_ROUND_2 — Script opening generation
      5. PHASE_3_ROUND_3 — Full script with score threshold
      6. PHASE_3_ROUND_4 — Final assembly
      7. PHASE_4_EXPERIMENT — Self-correction loop (baseline vs challenger)
      8. PHASE_6_MUSIC — Music architecture generation
      9. AWAITING_REVIEW — Human review gate
      10. COMPLETED — Published successfully
      (or FAILED/ABANDONED if something went wrong)
    
    Each phase corresponds to a specific stage in the pipeline.
    """
    TOPIC_SELECTED = "topic_selected"
    PHASE_3_ROUND_1A = "phase_3_round_1a"
    PHASE_3_ROUND_1B = "phase_3_round_1b"
    PHASE_3_ROUND_2 = "phase_3_round_2"
    PHASE_3_ROUND_3 = "phase_3_round_3"
    PHASE_3_ROUND_4 = "phase_3_round_4"
    PHASE_4_EXPERIMENT = "phase_4_experiment"
    PHASE_6_MUSIC = "phase_6_music"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"

class CycleStatus(str, Enum):
    """The high-level status of the cycle.
    
    ACTIVE — Currently in progress
    PAUSED — Waiting for external input (escalation, review)
    COMPLETED — Successfully finished and published
    FAILED — Unrecoverable error
    """
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class ProductionCycleRecord(BaseModel):
    """The authoritative record of a single production cycle.
    
    This is the MASTER RECORD that tracks a video from topic selection
    through publication. One row per video in production_registry table.
    
    LIFECYCLE:
      1. Created when MasterOrchestrator picks a Tier 1 topic
      2. Updated as each phase completes
      3. Marked COMPLETED/FAILED when done
    
    LOCKING:
      lock_expires_at prevents concurrent modifications.
      Always acquire lock before modifying, release after.
    
    KEY FIELDS:
      cycle_id: UUID identifying this cycle
      topic_statement: The video topic being produced
      genre: Video genre (affects evaluation questions)
      current_baseline_score: Latest ExperimentLoop score
      experiment_iterations: Count of mutation cycles run
      music_architecture_id: Reference to music plan
      published_video_id: YouTube video ID after publish
    """
    cycle_id: str
    topic_statement: str
    genre: str
    source: Literal["topic_finder", "adaptation", "manual"] = "topic_finder"
    current_phase: str = ProductionPhase.TOPIC_SELECTED.value
    status: str = CycleStatus.ACTIVE.value
    
    # State tracking
    current_baseline_score: float = 0.0
    experiment_iterations: int = 0
    music_architecture_id: Optional[str] = None
    published_video_id: Optional[str] = None
    
    # Time tracking
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Locking
    lock_expires_at: Optional[datetime] = None

class EscalationItem(BaseModel):
    """An item requiring human review.
    
    Escalations are created when the system encounters a situation
    it cannot resolve automatically. They appear in the ReviewInterface
    for human judgment.
    
    TYPES AND THEIR CAUSES:
      instruction_update — UpdatePipeline found a change needing approval
      hard_failure — A stage failed 3+ times consecutively
      reservoir_low — TopicReservoir has insufficient Tier 1 topics
      weekly_summary — Normal weekly SynthesisReport review
      sensitive_content — Content flagged for cultural sensitivity
    
    STATUS FLOW:
      pending → approved/rejected/modified
    
    FIELDS:
      escalation_id: Unique identifier
      cycle_id: Associated production cycle (if any)
      type: Category of escalation
      severity: Priority level (critical > high > medium > low)
      context_payload: Arbitrary context data for the reviewer
      status: Current resolution state
    """
    escalation_id: str
    cycle_id: Optional[str] = None
    type: Literal["instruction_update", "hard_failure", "reservoir_low", "weekly_summary", "sensitive_content"]
    severity: Literal["low", "medium", "high", "critical"]
    context_payload: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "approved", "rejected", "modified"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
