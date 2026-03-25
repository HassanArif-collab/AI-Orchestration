"""
Agents package — base agent class and registry.

All agents inherit from BaseAgent and register via AgentRegistry.
Skill/prompt definitions for each agent live in data/skills/*.md
(filename matches agent name, e.g. researcher.md → researcher agent).

    from packages.agents import BaseAgent, AgentRegistry
"""

from packages.agents.base import BaseAgent
from packages.agents.registry import AgentRegistry
from packages.agents.crew_config import (
    create_research_crew,
    create_script_crew,
    create_visual_crew,
    CREWAI_AVAILABLE,
)

__all__ = [
    "BaseAgent",
    "AgentRegistry",
    "create_research_crew",
    "create_script_crew",
    "create_visual_crew",
    "CREWAI_AVAILABLE",
]
