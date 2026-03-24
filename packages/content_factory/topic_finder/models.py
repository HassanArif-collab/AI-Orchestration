"""Phase 5: Topic Finder and Analytics Pydantic Models."""

import uuid
from typing import Literal, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from packages.content_factory.models import SourceVideoRecord

class TopicBrief(BaseModel):
    """The document that triggers Phase 3 production."""
    brief_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this topic brief"
    )
    topic_statement: str
    big_question: str
    genre_id: str
    gap_type: Literal["Hidden Mechanism", "Oversimplified Narrative", "Hidden Connection", "Universal in Local"]
    viability_score_breakdown: dict[str, Any] # The mapping of 17 rules -> Pass/Fail + total
    anchor_candidates: list[str]
    mainstream_assumption: str
    structural_reference: SourceVideoRecord | None = None
    urgency_flag: bool = False
    timing_rationale: str
    created_at: datetime
    status: Literal["reservoir", "in_production", "complete"] = "reservoir"
    
    # NEW: Content routing fields
    content_type: Literal["original", "adaptation"] = "original"
    # If content_type == "adaptation", this is the JH YouTube video ID to adapt
    adaptation_source_video_id: Optional[str] = None
    # The most structurally similar JH video for reference (both modes)
    structural_reference_video_id: Optional[str] = None


class VideoPerformanceProfile(BaseModel):
    """The structured analytics profile for a published video."""
    video_id: str
    publication_date: datetime
    genre_id: str
    topic_statement: str
    viability_score_at_selection: float
    
    # Engagement stats
    engagement_24h: float | None = None
    engagement_7d: float | None = None
    engagement_30d: float | None = None
    engagement_90d: float | None = None
    
    retention_curve_shape: Literal["Harris-Pattern", "Continuous Decline", "Early Exit", "Late Drop"] | None = None
    anchor_bridge_correlation: dict[str, float] | None = None  # e.g. {"anchor": 85.0, "bridge": 70.0}
    topic_resonance_score: float | None = None


class AudienceModel(BaseModel):
    """The accumulated intelligence about the Pakistani audience."""
    knowledge_baseline: dict[str, str] = Field(default_factory=dict)
    attention_patterns: dict[str, str] = Field(default_factory=dict)
    topic_resonance_map: dict[str, float] = Field(default_factory=dict)
    genre_engagement_rankings: dict[str, float] = Field(default_factory=dict)
    last_updated: datetime
