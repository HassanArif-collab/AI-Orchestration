"""
Models for Script Generation

Defines data structures for scripts, entries, and evaluation results.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SectionLabel(str, Enum):
    """Section labels for dual-column script."""
    HOOK = "HOOK"
    ANCHOR = "ANCHOR"
    BRIDGE = "BRIDGE"
    REVEAL = "REVEAL"
    CONCLUSION = "CONCLUSION"
    TRANSITION = "TRANSITION"


class VisualType(str, Enum):
    """Types of visual elements."""
    TALKING_HEAD = "talking_head"
    BROLL = "broll"
    ANIMATION = "animation"
    ARCHIVE = "archive"
    DATA_VIZ = "data_viz"
    SOUL_MOMENT = "soul_moment"


@dataclass
class DualColumnEntry:
    """A single entry in the dual-column script."""
    section_label: SectionLabel
    prose: str  # Left column: narration
    visual_direction: str  # Right column: visual directions
    visual_type: VisualType = VisualType.BROLL
    duration_estimate_seconds: float = 0.0
    anchor_hierarchy_level: int = 1
    low_confidence_flag: bool = False
    notes: str = ""


@dataclass
class EvaluationResult:
    """Result of evaluating a single criterion."""
    criterion_id: str
    criterion_name: str
    score: float  # 0.0 to 1.0
    passed: bool
    feedback: str = ""
    details: str = ""


@dataclass
class SelfEvaluationReport:
    """Complete self-evaluation report."""
    overall_score: float
    passed_threshold: bool
    results: list[EvaluationResult] = field(default_factory=list)
    weak_areas: list[str] = field(default_factory=list)
    strong_areas: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)
    iteration: int = 0
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class IterationLog:
    """Log entry for a single iteration."""
    iteration: int
    score: float
    weak_areas: list[str]
    prompt_strategy: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DualColumnScript:
    """Complete dual-column script with metadata."""
    video_id: str
    adapted_title: str
    genre: str = ""
    entries: list[DualColumnEntry] = field(default_factory=list)
    section_sequence: list[str] = field(default_factory=list)
    self_check_results: list[dict] = field(default_factory=list)
    production_readiness_score: float = 0.0
    
    # Complexity metadata
    complexity_score: float = 0.0
    complexity_depth: str = "moderate"  # shallow, moderate, deep
    
    # Research metadata
    research_dossier_id: str = ""
    topic_statement: str = ""
    big_question: str = ""
    
    # Evolution metadata
    evolution_id: str = ""  # Links to evolution log for full history
    iteration_count: int = 0
    iteration_log: list[IterationLog] = field(default_factory=list)
    final_evaluation: Optional[SelfEvaluationReport] = None
    
    # Learning summary (populated after evolution completes)
    improvements_made: list[str] = field(default_factory=list)  # What improved
    approaches_failed: list[str] = field(default_factory=list)  # What didn't work
    strategies_used: list[str] = field(default_factory=list)    # All strategies tried
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [f"# {self.adapted_title}", ""]
        lines.append(f"**Genre:** {self.genre}")
        lines.append(f"**Complexity:** {self.complexity_depth} ({self.complexity_score:.1f}/3.0)")
        lines.append(f"**Production Readiness:** {self.production_readiness_score:.1f}%")
        lines.append(f"**Iterations:** {self.iteration_count}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        for entry in self.entries:
            lines.append(f"## {entry.section_label.value}")
            lines.append("")
            lines.append(f"**Duration:** ~{entry.duration_estimate_seconds:.0f}s")
            lines.append(f"**Visual Type:** {entry.visual_type.value}")
            lines.append("")
            lines.append("### Narration (Left Column)")
            lines.append(entry.prose)
            lines.append("")
            lines.append("### Visual Direction (Right Column)")
            lines.append(entry.visual_direction)
            lines.append("")
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def to_json(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "video_id": self.video_id,
            "adapted_title": self.adapted_title,
            "genre": self.genre,
            "complexity_score": self.complexity_score,
            "complexity_depth": self.complexity_depth,
            "production_readiness_score": self.production_readiness_score,
            "evolution_id": self.evolution_id,
            "iteration_count": self.iteration_count,
            "improvements_made": self.improvements_made,
            "approaches_failed": self.approaches_failed,
            "strategies_used": self.strategies_used,
            "entries": [
                {
                    "section_label": e.section_label.value,
                    "prose": e.prose,
                    "visual_direction": e.visual_direction,
                    "visual_type": e.visual_type.value,
                    "duration_estimate_seconds": e.duration_estimate_seconds,
                }
                for e in self.entries
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    def add_improvement(self, improvement: str) -> None:
        """Record an improvement made during evolution."""
        self.improvements_made.append(improvement)
    
    def add_failed_approach(self, approach: str) -> None:
        """Record a failed approach during evolution."""
        self.approaches_failed.append(approach)
    
    def add_strategy(self, strategy: str) -> None:
        """Record a strategy used during evolution."""
        if strategy not in self.strategies_used:
            self.strategies_used.append(strategy)
