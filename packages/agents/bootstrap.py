"""Agent Bootstrap — Register CrewAI Agents into AgentRegistry at Startup.

This module provides bootstrap_agents() which instantiates the CrewAI agents
from packages/content_factory/production/agents.py and registers them into
the AgentRegistry so they can be retrieved by name throughout the system.

The agents are wrapped in _CrewAIAgentWrapper which adapts them to the
BaseAgent interface.

USAGE:
    from packages.agents.bootstrap import bootstrap_agents
    bootstrap_agents()  # Call once at application startup

SAFETY:
    bootstrap_agents() is safe to call even if CrewAI is not installed.
    It will log a warning and return without error.
"""

from packages.agents.registry import AgentRegistry
from packages.agents.base import BaseAgent
from packages.core.logger import get_logger

log = get_logger(__name__)


class _CrewAIAgentWrapper(BaseAgent):
    """Wrapper to adapt CrewAI Agent to BaseAgent interface.
    
    CrewAI agents don't inherit from BaseAgent, so this wrapper
    provides the required interface for the AgentRegistry.
    
    Attributes:
        name: Agent identifier for registry lookup
        role: Human-readable role description (from CrewAI agent)
        capability: Functional capability for model selection
        _crewai_agent: The underlying CrewAI Agent instance
    """
    
    def __init__(self, name: str, capability: str, crewai_agent):
        """Initialize the wrapper.
        
        Args:
            name: Agent identifier
            capability: Functional capability for model selection
            crewai_agent: The CrewAI Agent instance to wrap
        """
        self.name = name
        self.role = getattr(crewai_agent, "role", name)
        self.capability = capability
        self._crewai_agent = crewai_agent
    
    async def execute(self, task: str, context: dict) -> str:
        """Execute a task using the LLM.
        
        This implementation uses call_llm() from BaseAgent which
        routes through RouterClient.
        
        Args:
            task: The task description
            context: Additional context (unused in this wrapper)
            
        Returns:
            LLM response as string
        """
        return await self.call_llm(task, system=self.role)


def bootstrap_agents() -> None:
    """Register CrewAI agents into the AgentRegistry.
    
    This function instantiates the production agents from
    packages/content_factory/production/agents.py and registers
    them into the AgentRegistry.
    
    Safety:
        - If CrewAI is not installed, logs a warning and returns gracefully.
        - If agent creation fails, logs a warning and returns gracefully.
        - Safe to call multiple times (will re-register agents).
    
    Registered Agents:
        - researcher: Investigative research agent
        - script_agent: Lead writer agent
        - visual_agent: Visual director agent
    """
    try:
        from packages.content_factory.production.agents import (
            create_researcher,
            create_script_agent,
            create_visual_agent,
        )
    except ImportError as e:
        log.warning(f"crewai_not_installed: agent bootstrap skipped ({e})")
        return
    
    try:
        agents = [
            _CrewAIAgentWrapper("researcher", "research", create_researcher(architectural_references=[])),
            _CrewAIAgentWrapper("script_agent", "scripting", create_script_agent()),
            _CrewAIAgentWrapper("visual_agent", "visual_planning", create_visual_agent()),
        ]
        
        for agent in agents:
            AgentRegistry.register(agent)
            log.info(f"agent_registered: name={agent.name}")
            
    except Exception as e:
        log.warning(f"agent_bootstrap_failed: {e}")
