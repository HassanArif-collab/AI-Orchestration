"""Agent registry for managing available agents.

Simple singleton registry for agent instances.

AGENT REGISTRY vs CREWAI AGENTS:
  This registry is for BaseAgent subclasses (Type 1 agents).
  CrewAI agents from production/agents.py are NOT registered here —
  they are instantiated directly by RoundBasedProductionWorkflow.

HOW SKILLS CONNECT TO AGENTS:
  SKILLS_DIR points to data/skills/
  load_skill("researcher") reads data/skills/researcher.md
  The skill file name MUST match the agent's functional name.
  Currently all skill files contain "TODO: Extract from NotebookLM" —
  these need to be filled with actual system prompts.

CURRENT STATE:
  No agents are registered in the registry yet. The registry pattern
  is ready for use when pipeline infrastructure agents are built.
  To register an agent:
    from packages.agents.registry import AgentRegistry
    from packages.agents.base import BaseAgent

    class TrendAgent(BaseAgent):
        name = "trend_looker"
        capability = "trend_analysis"
        skills_path = str(SKILLS_DIR / "trend_looker.md")
        ...

    AgentRegistry.register(TrendAgent())

USAGE:
  # Register an agent
  AgentRegistry.register(my_agent)
  
  # Retrieve an agent
  agent = AgentRegistry.get("trend_looker")
  
  # List all agents
  names = AgentRegistry.list_agents()
  
  # Load skill prompt for an agent
  skill_prompt = load_skill("researcher")
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

    Skills are stored in data/skills/{agent_name}.md. They contain
    the system prompt, rules, and examples for the agent.

    Args:
        agent_name: Agent name matching a file in data/skills/ (e.g. 'researcher')

    Returns:
        Skill markdown content, or empty string if file not found.
    
    EXAMPLE:
        skill = load_skill("researcher")
        # skill contains the full markdown prompt for the researcher agent
        prompt = f"{skill}\n\nTopic: {topic}"
        result = await agent.call_llm(prompt)
    """
    skill_file = SKILLS_DIR / f"{agent_name}.md"
    if skill_file.exists():
        return skill_file.read_text(encoding="utf-8")
    return ""


class AgentRegistry:
    """Singleton registry for agents.

    Allows agents to be registered and retrieved by name.
    
    This is a CLASS-LEVEL registry (singleton pattern). All agents
    share the same _agents dict.
    
    THREAD SAFETY:
      Not thread-safe. In a multi-threaded environment, use external
      locking when registering agents.
    
    EXAMPLE:
        # Register an agent at startup
        AgentRegistry.register(my_researcher)
        
        # Retrieve later in the pipeline
        agent = AgentRegistry.get("researcher")
        if agent:
            result = await agent.execute(task, context)
    """

    _agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        """Register an agent.

        Args:
            agent: Agent instance to register
        
        NOTE:
            If an agent with the same name already exists, it will be
            replaced. This allows for agent updates during development.
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
        """Clear all registered agents (useful for testing).
        
        In production, this should rarely be called. It exists primarily
        for test isolation.
        """
        cls._agents.clear()
