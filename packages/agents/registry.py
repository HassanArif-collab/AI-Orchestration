"""Agent registry for managing available agents.

Simple singleton registry for agent instances.
"""

from pathlib import Path
from typing import Optional

from packages.agents.base import BaseAgent

# Agent skill/prompt definition files live in data/skills/*.md
# Each filename matches the agent's role name:
#   data/skills/researcher.md      → researcher agent
#   data/skills/script_writer.md   → script writer agent
#   data/skills/seo_specialist.md  → SEO specialist agent
#   data/skills/trend_looker.md    → trend looker agent
#   data/skills/visual_planner.md  → visual planner agent
SKILLS_DIR = Path(__file__).parent.parent.parent / "data" / "skills"


def load_skill(agent_name: str) -> str:
    """Load the skill definition markdown for a named agent.

    Args:
        agent_name: Agent name matching a file in data/skills/ (e.g. 'researcher')

    Returns:
        Skill markdown content, or empty string if file not found.
    """
    skill_file = SKILLS_DIR / f"{agent_name}.md"
    if skill_file.exists():
        return skill_file.read_text(encoding="utf-8")
    return ""


class AgentRegistry:
    """Singleton registry for agents.

    Allows agents to be registered and retrieved by name.
    """

    _agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        """Register an agent.

        Args:
            agent: Agent instance to register
        """
        cls._agents[agent.name] = agent

    @classmethod
    def get(cls, name: str) -> Optional[BaseAgent]:
        """Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None if not found
        """
        return cls._agents.get(name)

    @classmethod
    def list_agents(cls) -> list[str]:
        """List all registered agent names.

        Returns:
            List of agent names
        """
        return list(cls._agents.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered agents (useful for testing)."""
        cls._agents.clear()
