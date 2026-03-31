"""Pydantic models for Phase 2 — Adaptation Engine.

All structured document types for the 4-stage adaptation pipeline,
Source Video Library records, and error logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────


class SectionLabel(str, Enum):
    """Harris-style section labels from Phase 1 Style Reference."""
    HOOK = "HOOK"
    ANCHOR = "ANCHOR"
    BRIDGE = "BRIDGE"
    REVEAL = "REVEAL"
    CONCLUSION = "CONCLUSION"
    TRANSITION = "TRANSITION"


class ProcessingStatus(str, Enum):
    """Source Video Library processing states."""
    EXTRACTED_ONLY = "extracted_only"
    FULLY_ANALYZED = "fully_analyzed"
    ADAPTED = "adapted"
    ADAPTATION_REVIEWED = "adaptation_reviewed"


class ConfidenceLevel(str, Enum):
    """Localization substitution confidence."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VisualType(str, Enum):
    """Visual direction types — aligned with existing codebase VisualDecision."""
    TALKING_HEAD = "talking_head"
    BROLL = "broll"
    ANIMATION = "animation"
    ARCHIVE = "archive"
    DATA_VIZ = "data_viz"
    SOUL_MOMENT = "soul_moment"


# ─── Stage 1: Raw Extraction ─────────────────────────────────────────────────


class TranscriptSegment(BaseModel):
    """Single transcript entry with timestamp."""
    text: str
    start: float = Field(description="Start time in seconds")
    duration: float = Field(description="Duration in seconds")


class ChapterMarker(BaseModel):
    """YouTube chapter marker extracted from description."""
    title: str
    start_seconds: float


class RawExtraction(BaseModel):
    """Stage 1 output — everything extracted from a YouTube video."""
    video_id: str
    url: str
    title: str
    description: str = ""
    channel_id: str = ""
    channel_title: str = ""
    published_at: str = ""
    duration_iso: str = Field(default="", description="ISO 8601 duration from YouTube API")
    duration_seconds: float = 0.0
    views: int = 0
    likes: int = 0
    comments: int = 0
    tags: list[str] = []
    thumbnail_url: str = ""
    transcript_segments: list[TranscriptSegment] = []
    caption_type: Literal["manual", "auto_generated", "unknown"] = "unknown"
    transcript_language: str = "en"
    word_count: int = 0
    chapters: list[ChapterMarker] = []
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def full_transcript(self) -> str:
        """Join all segments into a single text."""
        return " ".join(seg.text for seg in self.transcript_segments)


# ─── Stage 2: Structural DNA ─────────────────────────────────────────────────


class StructuralSection(BaseModel):
    """A classified section of the video."""
    label: SectionLabel
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    first_sentence: str = ""
    content_summary: str = ""
    key_elements: list[str] = []


class VisualAnchorCandidate(BaseModel):
    """A visual anchor identified in an ANCHOR section."""
    description: str
    anchor_type: Literal["object", "location", "person", "document", "data_viz"] = "object"
    hierarchy_level: int = Field(ge=1, le=5, description="Anchor Substitution Hierarchy level")
    section_index: int = Field(description="Index of the ANCHOR section this belongs to")


class StructuralMetrics(BaseModel):
    """Document-level structural metrics."""
    anchor_to_bridge_ratio: float = 0.0
    hook_duration_seconds: float = 0.0
    first_anchor_position_seconds: float = 0.0
    reveal_position_percent: float = 0.0
    conclusion_duration_seconds: float = 0.0
    conclusion_duration_percent: float = 0.0
    total_anchor_duration: float = 0.0
    total_bridge_duration: float = 0.0


class StructuralMap(BaseModel):
    """Stage 2 output — the structural DNA of the video."""
    video_id: str
    sections: list[StructuralSection] = []
    section_sequence: list[str] = Field(
        default=[],
        description="Ordered list of section labels: ['HOOK', 'ANCHOR', 'BRIDGE', ...]"
    )
    metrics: StructuralMetrics = Field(default_factory=StructuralMetrics)
    big_question: str = ""
    visual_anchors: list[VisualAnchorCandidate] = []
    genre: str = Field(default="", description="Genre ID from Phase 1 Genre Schema")
    structural_integrity_score: int = Field(
        default=0, ge=0, le=7,
        description="Score out of 7 Research Quality questions"
    )
    analyzed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ─── Stage 3: Localization ───────────────────────────────────────────────────


class MonetarySubstitution(BaseModel):
    """Category 1: Monetary figure substitution."""
    original_figure: str
    original_context: str = Field(description="Class position / economic reality in source culture")
    pakistani_figure: str
    pakistani_context: str = Field(description="Class position / economic reality in Pakistan")
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    section_index: int = 0


class NameSubstitution(BaseModel):
    """Category 2: Named individual substitution."""
    original_name: str
    name_type: Literal["global_public_figure", "western_reference", "generic_illustrative"]
    narrative_function: str
    pakistani_replacement: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    retained: bool = Field(default=False, description="True if global figure was retained")
    section_index: int = 0


class GeographicSubstitution(BaseModel):
    """Category 3: Geographic reference substitution."""
    original_location: str
    symbolic_function: str
    location_type: Literal["functionally_replaceable", "essential"] = "functionally_replaceable"
    pakistani_replacement: str
    equivalence_basis: str = ""
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    section_index: int = 0


class CulturalSubstitution(BaseModel):
    """Category 4: Cultural reference substitution."""
    original_reference: str
    cultural_work: str = Field(description="What cultural work the reference performs")
    pakistani_replacement: str
    replacement_cultural_work: str = ""
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    section_index: int = 0


class StructuralArgumentLocalization(BaseModel):
    """Category 5: Document-level structural argument."""
    original_argument: str
    translates_directly: bool = True
    pakistani_argument: str = ""
    sections_requiring_major_changes: list[int] = []
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class LocalizationSummary(BaseModel):
    """Summary statistics for the localization."""
    total_substitutions: int = 0
    by_category: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    localization_integrity_warning: bool = False
    low_confidence_percent: float = 0.0


class LocalizationMap(BaseModel):
    """Stage 3 output — all substitutions for Pakistani adaptation."""
    video_id: str
    monetary: list[MonetarySubstitution] = []
    names: list[NameSubstitution] = []
    geographic: list[GeographicSubstitution] = []
    cultural: list[CulturalSubstitution] = []
    structural_argument: Optional[StructuralArgumentLocalization] = None
    summary: LocalizationSummary = Field(default_factory=LocalizationSummary)
    localized_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ─── Stage 4: Dual-Column Script ─────────────────────────────────────────────


class DualColumnEntry(BaseModel):
    """Single row of the dual-column script."""
    prose: str = Field(description="Left column — spoken narration")
    visual_direction: str = Field(description="Right column — production direction")
    visual_type: VisualType = VisualType.TALKING_HEAD
    section_label: SectionLabel = SectionLabel.BRIDGE
    duration_estimate_seconds: float = 0.0
    anchor_hierarchy_level: Optional[int] = Field(
        default=None, ge=1, le=5,
        description="For ANCHOR sections — which hierarchy level"
    )
    low_confidence_flag: bool = Field(
        default=False,
        description="True if this entry contains a Low-confidence substitution"
    )


class SelfCheckResult(BaseModel):
    """Result of a single binary evaluation question check."""
    question_id: str
    question_text: str
    passed: bool
    failure_section: Optional[str] = None
    failure_reason: Optional[str] = None
    fix_attempts: int = 0


class AdaptedScript(BaseModel):
    """Stage 4 output — production-ready dual-column script."""
    video_id: str
    source_video_id: str = Field(
        default="",
        description="Source YouTube video ID that was adapted"
    )
    source_title: str = ""
    adapted_title: str = ""
    genre: str = ""
    entries: list[DualColumnEntry] = []
    section_sequence: list[str] = []
    self_check_results: list[SelfCheckResult] = []
    production_readiness_score: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="Percentage of self-check questions that passed"
    )
    persistent_failures: list[str] = Field(
        default=[],
        description="Question IDs that failed 3+ times despite retries"
    )
    adapted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ─── Source Video Library Record ──────────────────────────────────────────────


class SourceVideoRecord(BaseModel):
    """Complete record in the Source Video Library."""
    video_id: str
    url: str
    title: str
    published_at: str = ""
    views: int = 0
    likes: int = 0
    extraction: Optional[RawExtraction] = None
    structural_map: Optional[StructuralMap] = None
    genre: str = ""
    structural_integrity_score: int = 0
    anchor_to_bridge_ratio: float = 0.0
    section_sequence: list[str] = []
    big_question: str = ""
    processing_status: ProcessingStatus = ProcessingStatus.EXTRACTED_ONLY
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ─── Error Logging ───────────────────────────────────────────────────────────


class AdaptationError(BaseModel):
    """Standard error/warning log entry for the adaptation pipeline."""
    production_cycle_id: str
    stage_number: int = Field(ge=1, le=6)
    error_type: str
    content_element: str = ""
    description: str
    pipeline_stopped: bool = False
    severity: Literal["error", "warning"] = "error"
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
