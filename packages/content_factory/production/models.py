"""
production/models.py — Pydantic models for Deep Research Engine.

Context: These models structure the output of the systematic research
methodology adopted from deer-flow's deep-research skill.

The ResearchDossier is the primary output, containing:
  - Multi-dimensional research findings
  - Physical anchors and human characters for documentary production
  - Completeness scoring for quality validation

FIXES APPLIED:
1. Added fact validation fields (corroboration_count, validation_status)
2. Added fact deduplication support in ResearchDossier
3. Added _seen_statements for tracking duplicates

Usage:
    from packages.content_factory.production.models import ResearchDossier

    dossier = ResearchDossier(topic="Pakistan Economy")
    dossier.add_fact_if_unique({"statement": "...", "source": "..."})

Imports: pydantic, datetime
Imported by: packages/content_factory/production/deep_research.py
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, PrivateAttr, field_validator


class InformationType(str, Enum):
    """Types of information to gather during research (from deer-flow methodology)."""
    FACTS_DATA = "facts_data"           # Statistics, numbers, concrete evidence
    EXAMPLES_CASES = "examples_cases"   # Real-world applications, case studies
    EXPERT_OPINIONS = "expert_opinions" # Authority perspectives, interviews
    TRENDS = "trends"                   # Future direction, forecasts
    COMPARISONS = "comparisons"         # Context and alternatives
    CHALLENGES = "challenges"           # Counterarguments, limitations


class AnchorType(str, Enum):
    """Types of physical anchors for documentary production."""
    DOCUMENT = "document"       # Primary source documents
    LOCATION = "location"       # Geographic locations
    OBJECT = "object"           # Physical objects
    DATA_VIZ = "data_viz"       # Data visualizations
    ARCHIVE = "archive"         # Archive footage/material


class ValidationStatus(str, Enum):
    """Validation status for research facts."""
    UNVERIFIED = "unverified"           # Not yet validated
    PARTIALLY_VERIFIED = "partially_verified"  # One source confirms
    VERIFIED = "verified"               # Multiple sources confirm
    DISPUTED = "disputed"               # Sources contradict


class ResearchFact(BaseModel):
    """A single research fact with source attribution and validation."""
    statement: str = Field(description="The factual statement")
    source_url: str = Field(default="", description="URL where fact was found")
    source_name: str = Field(default="", description="Name of the source (e.g., 'Dawn News')")
    information_type: InformationType = Field(
        default=InformationType.FACTS_DATA,
        description="Category of this information"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the fact's accuracy"
    )
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Fact validation fields (new)
    corroboration_count: int = Field(
        default=1,
        ge=1,
        description="Number of independent sources confirming this fact"
    )
    corroboration_sources: list[str] = Field(
        default_factory=list,
        description="URLs of sources that confirm this fact"
    )
    validation_status: ValidationStatus = Field(
        default=ValidationStatus.UNVERIFIED,
        description="Verification status of this fact"
    )


class PhysicalAnchor(BaseModel):
    """A tangible physical anchor for documentary production."""
    description: str = Field(description="What the anchor is")
    anchor_type: AnchorType = Field(
        default=AnchorType.OBJECT,
        description="Type of physical anchor"
    )
    hierarchy_level: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Anchor Substitution Hierarchy level (1=best, 5=worst)"
    )
    source_url: str = Field(default="", description="Where this anchor was discovered")
    availability: str = Field(
        default="unknown",
        description="How to obtain/visualize: 'public', 'request_required', 'paid', 'unknown'"
    )
    visual_direction: str = Field(
        default="",
        description="Suggested visual approach for this anchor"
    )


class HumanCharacter(BaseModel):
    """A human character whose story illustrates the macro problem."""
    name: str = Field(default="", description="Character name or identifier")
    role: str = Field(description="Their role or position")
    story_summary: str = Field(description="Brief summary of their story")
    relevance: str = Field(description="How their story connects to the topic")
    source_url: str = Field(default="", description="Where this story was found")
    contact_available: bool = Field(
        default=False,
        description="Whether contact/interview might be possible"
    )


class DimensionFindings(BaseModel):
    """Research findings for a single dimension/subtopic."""
    dimension_name: str = Field(description="Name of this research dimension")
    summary: str = Field(default="", description="Brief summary of findings")
    facts: list[ResearchFact] = Field(default_factory=list)
    sources_consulted: list[str] = Field(default_factory=list)
    search_queries_used: list[str] = Field(default_factory=list)


class ResearchDossier(BaseModel):
    """
    Complete research output from the Deep Research Engine.

    This is the primary artifact passed to the script writing agents.
    It contains all gathered information structured for documentary production.

    Features:
        - Fact deduplication based on statement similarity
        - Cross-source fact validation tracking
        - Completeness scoring for quality validation
    """

    topic: str = Field(description="Main research topic")
    genre_id: str = Field(default="", description="Genre ID for structural reference")

    # Multi-dimensional research findings
    dimensions_explored: list[str] = Field(
        default_factory=list,
        description="List of dimensions/subtopics researched"
    )
    dimension_findings: dict[str, DimensionFindings] = Field(
        default_factory=dict,
        description="Detailed findings per dimension"
    )

    # Information organized by type (deer-flow methodology)
    facts_and_data: list[ResearchFact] = Field(
        default_factory=list,
        description="Statistics, numbers, concrete evidence"
    )
    examples_cases: list[ResearchFact] = Field(
        default_factory=list,
        description="Real-world applications, case studies"
    )
    expert_opinions: list[ResearchFact] = Field(
        default_factory=list,
        description="Authority perspectives, interviews"
    )
    trends: list[ResearchFact] = Field(
        default_factory=list,
        description="Future direction, forecasts"
    )
    comparisons: list[ResearchFact] = Field(
        default_factory=list,
        description="Context and alternatives"
    )
    challenges: list[ResearchFact] = Field(
        default_factory=list,
        description="Counterarguments, limitations"
    )

    # Documentary-specific elements
    physical_anchors: list[PhysicalAnchor] = Field(
        default_factory=list,
        description="Tangible objects/locations for camera work"
    )
    human_characters: list[HumanCharacter] = Field(
        default_factory=list,
        description="People whose stories illustrate the problem"
    )

    # Mainstream narrative contradiction
    mainstream_assumption: str = Field(
        default="",
        description="What the mainstream narrative assumes"
    )
    contradicting_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence that challenges mainstream assumptions"
    )

    # Big Question framing
    big_question: str = Field(
        default="",
        description="Central question the documentary explores"
    )
    chronological_sequence: list[str] = Field(
        default_factory=list,
        description="Timeline of key events if applicable"
    )

    # Quality metrics
    completeness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall research completeness (0.0-1.0)"
    )
    information_type_coverage: dict[str, bool] = Field(
        default_factory=lambda: {t.value: False for t in InformationType},
        description="Which information types have been gathered"
    )

    # Source tracking
    all_sources: list[str] = Field(
        default_factory=list,
        description="All unique source URLs consulted"
    )
    search_queries_total: int = Field(
        default=0,
        description="Total number of search queries executed"
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    research_duration_seconds: float = Field(
        default=0.0,
        description="Time spent on research"
    )

    # Private attributes for deduplication (not serialized)
    _seen_statements: set[str] = PrivateAttr(default_factory=set)

    def model_post_init(self, __context: Any) -> None:
        """Initialize private attributes after model creation."""
        self._seen_statements = set()

        # Rebuild seen_statements from existing facts (for deserialized dossiers)
        for fact in (
            self.facts_and_data +
            self.examples_cases +
            self.expert_opinions +
            self.trends +
            self.comparisons +
            self.challenges
        ):
            self._seen_statements.add(self._normalize_statement(fact.statement))

    def _normalize_statement(self, statement: str) -> str:
        """Normalize statement for comparison."""
        # Remove extra whitespace, lowercase, strip punctuation
        normalized = re.sub(r'\s+', ' ', statement.lower().strip())
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return normalized[:100]  # Compare first 100 chars

    def _is_duplicate_fact(self, fact: ResearchFact) -> bool:
        """Check if fact is duplicate of existing one."""
        normalized = self._normalize_statement(fact.statement)

        # Exact match check
        if normalized in self._seen_statements:
            return True

        # Similarity check (overlap ratio)
        for seen in self._seen_statements:
            words_seen = set(seen.split())
            words_new = set(normalized.split())

            if not words_seen or not words_new:
                continue

            # Calculate Jaccard similarity
            intersection = len(words_seen & words_new)
            union = len(words_seen | words_new)

            if union > 0 and (intersection / union) > 0.8:  # 80% similarity threshold
                return True

        return False

    def add_fact_if_unique(self, fact: ResearchFact) -> bool:
        """
        Add fact only if not duplicate. Returns True if added.

        This method performs similarity-based deduplication to prevent
        the same fact from being added multiple times from different sources.

        Args:
            fact: The ResearchFact to potentially add

        Returns:
            True if fact was added, False if it was a duplicate
        """
        if self._is_duplicate_fact(fact):
            return False

        self._seen_statements.add(self._normalize_statement(fact.statement))
        self._add_fact_to_dossier(fact)
        return True

    def add_fact(self, fact: ResearchFact) -> None:
        """Add a fact to the appropriate information type list."""
        self._seen_statements.add(self._normalize_statement(fact.statement))
        self._add_fact_to_dossier(fact)

    def _add_fact_to_dossier(self, fact: ResearchFact) -> None:
        """Internal method to add fact to the correct list."""
        if fact.information_type == InformationType.FACTS_DATA:
            self.facts_and_data.append(fact)
        elif fact.information_type == InformationType.EXAMPLES_CASES:
            self.examples_cases.append(fact)
        elif fact.information_type == InformationType.EXPERT_OPINIONS:
            self.expert_opinions.append(fact)
        elif fact.information_type == InformationType.TRENDS:
            self.trends.append(fact)
        elif fact.information_type == InformationType.COMPARISONS:
            self.comparisons.append(fact)
        elif fact.information_type == InformationType.CHALLENGES:
            self.challenges.append(fact)

    def add_anchor(self, anchor: PhysicalAnchor) -> None:
        """Add a physical anchor."""
        self.physical_anchors.append(anchor)

    def add_character(self, character: HumanCharacter) -> None:
        """Add a human character."""
        self.human_characters.append(character)

    def add_source(self, url: str) -> None:
        """Add a source URL if not already present."""
        if url and url not in self.all_sources:
            self.all_sources.append(url)

    def get_anchors_by_level(self, min_level: int = 1, max_level: int = 3) -> list[PhysicalAnchor]:
        """Get anchors within a hierarchy level range (default: Level 1-3)."""
        return [
            a for a in self.physical_anchors
            if min_level <= a.hierarchy_level <= max_level
        ]

    def calculate_completeness(self) -> float:
        """
        Calculate completeness score based on deer-flow quality bar.

        Checks:
        - 3+ facts and data points
        - 2+ examples/cases
        - 1+ expert opinions
        - 3+ physical anchors (Level 1-3 preferred)
        - 1+ human characters
        - All 6 information types covered
        """
        checks = [
            len(self.facts_and_data) >= 3,
            len(self.examples_cases) >= 2,
            len(self.expert_opinions) >= 1,
            len(self.get_anchors_by_level(1, 3)) >= 2,  # At least 2 Level 1-3 anchors
            len(self.human_characters) >= 1,
            len(self.challenges) >= 1,  # Has counterarguments
        ]

        self.completeness_score = sum(checks) / len(checks)
        return self.completeness_score

    def is_complete(self, threshold: float = 0.8) -> bool:
        """Check if research meets completeness threshold."""
        return self.calculate_completeness() >= threshold

    def get_missing_elements(self) -> list[str]:
        """Get list of missing research elements."""
        missing = []

        if len(self.facts_and_data) < 3:
            missing.append("facts_and_data: need 3+ facts")
        if len(self.examples_cases) < 2:
            missing.append("examples_cases: need 2+ examples")
        if len(self.expert_opinions) < 1:
            missing.append("expert_opinions: need 1+ opinions")
        if len(self.get_anchors_by_level(1, 3)) < 2:
            missing.append("physical_anchors: need 2+ Level 1-3 anchors")
        if len(self.human_characters) < 1:
            missing.append("human_characters: need 1+ character")
        if len(self.challenges) < 1:
            missing.append("challenges: need counterarguments")

        return missing

    def get_validation_stats(self) -> dict:
        """Get statistics about fact validation status."""
        all_facts = (
            self.facts_and_data +
            self.examples_cases +
            self.expert_opinions +
            self.trends +
            self.comparisons +
            self.challenges
        )

        stats = {
            "total_facts": len(all_facts),
            "verified": 0,
            "partially_verified": 0,
            "unverified": 0,
            "disputed": 0,
            "avg_corroboration": 0.0,
        }

        if not all_facts:
            return stats

        total_corroboration = 0
        for fact in all_facts:
            total_corroboration += fact.corroboration_count
            if fact.validation_status == ValidationStatus.VERIFIED:
                stats["verified"] += 1
            elif fact.validation_status == ValidationStatus.PARTIALLY_VERIFIED:
                stats["partially_verified"] += 1
            elif fact.validation_status == ValidationStatus.DISPUTED:
                stats["disputed"] += 1
            else:
                stats["unverified"] += 1

        stats["avg_corroboration"] = total_corroboration / len(all_facts)
        return stats

    def to_markdown(self) -> str:
        """
        Convert dossier to markdown format for downstream agents.

        This is the format expected by the Script Writer agent.
        """
        sections = []

        # Header
        sections.append(f"# Research Dossier: {self.topic}")
        sections.append(f"\n**Genre:** {self.genre_id or 'Not specified'}")
        sections.append(f"**Completeness:** {self.completeness_score:.0%}")
        sections.append(f"**Sources:** {len(self.all_sources)}")

        # Validation stats
        validation = self.get_validation_stats()
        if validation["total_facts"] > 0:
            sections.append(f"**Fact Verification:** {validation['verified']}/{validation['total_facts']} verified")

        # Big Question
        if self.big_question:
            sections.append(f"\n## Big Question\n{self.big_question}")

        # Mainstream Assumption & Contradiction
        if self.mainstream_assumption:
            sections.append(f"\n## Mainstream Narrative\n**Assumption:** {self.mainstream_assumption}")
            if self.contradicting_evidence:
                sections.append("\n**Contradicting Evidence:**")
                for evidence in self.contradicting_evidence:
                    sections.append(f"- {evidence}")

        # Physical Anchors (most important for documentary)
        if self.physical_anchors:
            sections.append("\n## Physical Anchors")
            for anchor in self.physical_anchors:
                level_str = f"Level {anchor.hierarchy_level}"
                verified_marker = "✓" if anchor.availability == "public" else "?"
                sections.append(f"- **[{level_str}]** {verified_marker} {anchor.description} ({anchor.anchor_type.value})")

        # Human Characters
        if self.human_characters:
            sections.append("\n## Human Characters")
            for char in self.human_characters:
                sections.append(f"- **{char.role}**: {char.story_summary}")

        # Key Facts
        if self.facts_and_data:
            sections.append("\n## Key Facts & Data")
            for fact in self.facts_and_data[:10]:  # Limit to top 10
                verified_marker = "✓" if fact.validation_status == ValidationStatus.VERIFIED else ""
                sections.append(f"- {verified_marker} {fact.statement}")

        # Examples & Cases
        if self.examples_cases:
            sections.append("\n## Examples & Cases")
            for ex in self.examples_cases[:5]:
                sections.append(f"- {ex.statement}")

        # Expert Opinions
        if self.expert_opinions:
            sections.append("\n## Expert Opinions")
            for op in self.expert_opinions[:5]:
                sections.append(f"- {op.statement}")

        # Challenges
        if self.challenges:
            sections.append("\n## Challenges & Counterarguments")
            for ch in self.challenges[:5]:
                sections.append(f"- {ch.statement}")

        # Chronological Sequence
        if self.chronological_sequence:
            sections.append("\n## Timeline")
            for i, event in enumerate(self.chronological_sequence, 1):
                sections.append(f"{i}. {event}")

        # Sources
        if self.all_sources:
            sections.append("\n## Sources")
            for url in self.all_sources[:20]:
                sections.append(f"- {url}")

        return "\n".join(sections)

    def to_research_summary(self) -> str:
        """Brief summary for logging and debugging."""
        validation = self.get_validation_stats()
        return (
            f"ResearchDossier(topic='{self.topic[:50]}...', "
            f"anchors={len(self.physical_anchors)}, "
            f"characters={len(self.human_characters)}, "
            f"facts={validation['total_facts']}, "
            f"verified={validation['verified']}, "
            f"completeness={self.completeness_score:.0%})"
        )
