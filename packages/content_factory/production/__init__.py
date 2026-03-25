"""
Mode B Pipeline — Original Pakistani Investigative Content.

Takes a TopicBrief and produces an original DualColumnScript using three
CrewAI agents working in sequence with iterative self-correction rounds.

Agents: Researcher → Visual Director → Writer (defined in agents.py)
Workflow: RoundBasedProductionWorkflow in workflow.py
Entry point: workflow.py → run_production_workflow(idea, ...)

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
