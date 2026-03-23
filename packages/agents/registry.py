"""Agent registry for managing available agents.

Simple singleton registry for agent instances.
"""

from typing import Optional

from packages.agents.base import BaseAgent


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
