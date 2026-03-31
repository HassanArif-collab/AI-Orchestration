"""Base Agent — Abstract Foundation for All Pipeline Agents.

This module defines the abstract BaseAgent class that ALL agents in this
system must inherit from. It ensures every agent:
  1. Uses RouterClient for LLM calls (never direct API calls)
  2. Has a named capability that maps to a preferred model
  3. Can optionally load skill prompts from data/skills/*.md

TWO TYPES OF AGENTS IN THIS SYSTEM:

  Type 1: BaseAgent subclasses (packages/agents/)
    Custom Python classes. Used for pipeline infrastructure agents
    (trend analysis, SEO, etc.) that need direct code control.
    Inherit from BaseAgent, implement execute().
    Example: Create packages/agents/trend_agent.py

  Type 2: CrewAI agents (packages/content_factory/production/agents.py)
    CrewAI Agent objects. Used for the content creation agents
    (Researcher, Visual Director, Writer) where multi-agent collaboration
    and task handoff is needed.
    These do NOT inherit from BaseAgent — they are CrewAI native objects.
    But they MUST still use RouterClient for LLM calls via FreeRouter.

SKILL LOADING:
  Each agent can have a skill definition file at data/skills/{name}.md
  Load it with: self.load_skills()
  The skill file contains the agent's system prompt, examples, and rules.
  Current skill files: researcher.md, script_writer.md, seo_specialist.md,
                       trend_looker.md, visual_planner.md

CAPABILITY → MODEL MAPPING:
  The capability string maps to a preferred model via capabilities.py.
  Example: capability="research" → "groq/llama-3.3-70b-versatile"
  FreeRouter auto-falls back if the preferred model is unavailable.
  Override models without code changes: create packages/capabilities.yaml
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from packages.router.client import RouterClient
from packages.router.capabilities import get_model_for_capability
from packages.core.errors import LLMClientError


class BaseAgent(ABC):
    """Abstract base class for all agents.
    
    Subclass to implement specific agent behaviors. Every agent must:
      1. Define name, role, and capability attributes
      2. Implement the execute() method
      3. Optionally set skills_path to load skill prompts
    
    AGENT LIFECYCLE:
      1. Agent is instantiated with specific configuration
      2. execute() is called with a task and context
      3. Agent uses call_llm() to interact with LLM
      4. Result is returned to the pipeline
    
    EXAMPLE IMPLEMENTATION:
      class TrendAgent(BaseAgent):
          name = "trend_looker"
          role = "Finds trending topics for video production"
          capability = "trend_analysis"
          skills_path = str(SKILLS_DIR / "trend_looker.md")
          
          async def execute(self, task: str, context: dict) -> str:
              skills = self.load_skills()
              prompt = f"{skills}\n\nTask: {task}"
              return await self.call_llm(prompt, system="You are a trend analyst.")
    
    IMPORTANT:
      - NEVER make direct API calls to LLM providers
      - ALWAYS use call_llm() which goes through RouterClient
      - The capability determines which model is used
    """

    name: str
    role: str
    capability: str  # Maps to get_model_for_capability()
    skills_path: Optional[str] = None

    @abstractmethod
    async def execute(self, task: str, context: dict) -> str:
        """Execute the agent's task.

        This is the MAIN ENTRY POINT for any agent. Override this method
        to implement agent-specific behavior.

        Args:
            task: The task description (what the agent should do)
            context: Additional context (previous outputs, config, etc.)

        Returns:
            Execution result as string (usually JSON or markdown)
        """
        ...

    def load_skills(self) -> str:
        """Load agent skills from markdown file.
        
        Skills are stored in data/skills/{agent_name}.md and contain
        the system prompt, rules, and examples for the agent.
        
        Returns:
            Skills content as string, or "" if file doesn't exist
        
        USAGE:
            skills = self.load_skills()
            if skills:
                prompt = f"{skills}\n\n{user_task}"
            else:
                prompt = user_task  # Fall back to bare task
        """
        if not self.skills_path:
            return ""

        skills_file = Path(self.skills_path)
        if not skills_file.exists():
            return ""

        return skills_file.read_text()

    async def call_llm(self, prompt: str, system: str = "") -> str:
        """Call the LLM with the agent's capability model.

        This is the ONLY way an agent should interact with LLMs.
        It routes through RouterClient → FreeRouter → actual provider.

        Args:
            prompt: User prompt (the main task/question)
            system: System prompt (agent personality, rules)

        Returns:
            LLM response text

        Raises:
            LLMClientError: On LLM errors (network, rate limit, etc.)
        
        MODEL SELECTION:
            The model is determined by the agent's capability attribute.
            See packages/router/capabilities.py for the mapping.
        """
        model = get_model_for_capability(self.capability)
        client = RouterClient()
        try:
            return await client.complete_text(
                prompt,
                model=model,
                system=system,
            )
        finally:
            await client.close()
