"""Phase 7: Orchestration Models.

Defines the core state tracking structures for the Production Cycle Registry,
Hermes memory injection payloads, and Human Review Escalations.
"""

from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Literal, Optional, Any
from enum import Enum

class ProductionPhase(str, Enum):
    """The sequence of phases a production cycle moves through."""
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
    """The high-level status of the cycle."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class ProductionCycleRecord(BaseModel):
    """The authoritative record of a single production cycle."""
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
    """An item requiring human review."""
    escalation_id: str
    cycle_id: Optional[str] = None
    type: Literal["instruction_update", "hard_failure", "reservoir_low", "weekly_summary", "sensitive_content"]
    severity: Literal["low", "medium", "high", "critical"]
    context_payload: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "approved", "rejected", "modified"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
