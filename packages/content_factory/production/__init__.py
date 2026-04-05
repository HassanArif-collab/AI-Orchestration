"""
Mode B Pipeline — Original Pakistani Investigative Content.

Takes a TopicBrief and produces an original DualColumnScript using
LangGraph pipeline nodes with iterative self-correction rounds.

Pipeline: Research → Draft → Score → Mutate Loop → Visuals → Review → Publish
Entry point: orchestration/graphs.py → LangGraph production graph

Genres supported: history, current_situation, tech_systems, comparison,
                  islamic_history, south_asian_history

DEEP RESEARCH ENGINE:
  The DeepResearchEngine provides systematic multi-angle research methodology
  from deer-flow. It replaces simple single-prompt research with a 4-phase
  process: Broad Exploration → Deep Dive → Diversity & Validation → Synthesis.

  Usage:
    from packages.content_factory.production import DeepResearchEngine
    engine = DeepResearchEngine()
    dossier = await engine.research(topic="Pakistan Economy")
    markdown = dossier.to_markdown()  # For script writer

NOTE: workflow.py and agents.py (CrewAI round-based workflow) were removed
in Phase 2 dead code cleanup. Production now runs exclusively via LangGraph.
"""

from packages.content_factory.production.models import (
    AnchorType,
    DimensionFindings,
    HumanCharacter,
    InformationType,
    PhysicalAnchor,
    ResearchDossier,
    ResearchFact,
    ValidationStatus,
)
from packages.content_factory.production.deep_research import DeepResearchEngine

__all__ = [
    # Deep Research Engine
    "DeepResearchEngine",
    # Research Models
    "ResearchDossier",
    "ResearchFact",
    "PhysicalAnchor",
    "HumanCharacter",
    "InformationType",
    "AnchorType",
    "DimensionFindings",
    "ValidationStatus",
]
