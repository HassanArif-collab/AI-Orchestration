"""Base agent class for all pipeline agents.

Provides common functionality for LLM calls and skill loading.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from packages.router.client import RouterClient
from packages.router.capabilities import get_model_for_capability
from packages.core.errors import LLMClientError


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Subclass to implement specific agent behaviors.
    """

    name: str
    role: str
    capability: str  # Maps to get_model_for_capability()
    skills_path: Optional[str] = None

    @abstractmethod
    async def execute(self, task: str, context: dict) -> str:
        """Execute the agent's task.

        Args:
            task: The task description
            context: Additional context for execution

        Returns:
            Execution result as string
        """
        ...

    def load_skills(self) -> str:
        """Load agent skills from markdown file.

        Returns:
            Skills content as string, or "" if file doesn't exist
        """
        if not self.skills_path:
            return ""

        skills_file = Path(self.skills_path)
        if not skills_file.exists():
            return ""

        return skills_file.read_text()

    async def call_llm(self, prompt: str, system: str = "") -> str:
        """Call the LLM with the agent's capability model.

        Args:
            prompt: User prompt
            system: System prompt

        Returns:
            LLM response text

        Raises:
            LLMClientError: On LLM errors
        """
        model = get_model_for_capability(self.capability)
        async with RouterClient() as client:
            return await client.complete_text(
                prompt,
                model=model,
                system=system,
            )
