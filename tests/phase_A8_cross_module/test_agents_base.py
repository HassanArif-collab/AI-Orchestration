"""Tests for packages/agents/base.py — Base agent class."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


class TestBaseAgentAbstract:
    """Tests for BaseAgent as an abstract class."""

    def test_cannot_instantiate_directly(self):
        from packages.agents.base import BaseAgent
        with pytest.raises(TypeError):
            BaseAgent()

    def test_subclass_must_implement_execute(self):
        from packages.agents.base import BaseAgent

        class IncompleteAgent(BaseAgent):
            name = "incomplete"
            role = "incomplete role"
            capability = "research"

        with pytest.raises(TypeError):
            IncompleteAgent()

    def test_valid_subclass_can_be_instantiated(self):
        from packages.agents.base import BaseAgent

        class GoodAgent(BaseAgent):
            name = "good"
            role = "Good agent"
            capability = "research"

            async def execute(self, task: str, context: dict) -> str:
                return "done"

        agent = GoodAgent()
        assert agent.name == "good"
        assert agent.capability == "research"


class TestBaseAgentLoadSkills:
    """Tests for BaseAgent.load_skills()."""

    def _make_agent_cls(self, skills_path=None):
        from packages.agents.base import BaseAgent
        _sp = skills_path

        class TestAgent(BaseAgent):
            name = "test"
            role = "test"
            capability = "research"
            skills_path = _sp

            async def execute(self, task: str, context: dict) -> str:
                return ""

        return TestAgent

    def test_returns_empty_when_no_skills_path(self):
        agent = self._make_agent_cls(skills_path=None)()
        assert agent.load_skills() == ""

    def test_returns_empty_when_file_not_exists(self):
        agent = self._make_agent_cls(skills_path="/nonexistent/path.md")()
        assert agent.load_skills() == ""

    def test_reads_file_when_exists(self, tmp_path):
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("# Test Skill\n\nBe creative.", encoding="utf-8")
        agent = self._make_agent_cls(skills_path=str(skill_file))()
        content = agent.load_skills()
        assert "# Test Skill" in content
        assert "Be creative." in content


class TestBaseAgentCallLlm:
    """Tests for BaseAgent.call_llm()."""

    @pytest.mark.asyncio
    async def test_calls_router_with_capability_model(self):
        from packages.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "test"
            capability = "research"

            async def execute(self, task: str, context: dict) -> str:
                return ""

        agent = TestAgent()
        mock_router = MagicMock()
        mock_router.complete_text = AsyncMock(return_value="LLM says hello")
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_router)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("packages.agents.base.RouterClient", return_value=mock_ctx):
            with patch("packages.agents.base.get_model_for_capability", return_value="groq/test-model"):
                result = await agent.call_llm("Tell me about AI", system="Be concise")

        mock_router.complete_text.assert_called_once()
        # complete_text is called with positional args: (prompt, system=..., model=...)
        call_args = mock_router.complete_text.call_args
        assert call_args[0][0] == "Tell me about AI"  # first positional arg (prompt)
        assert call_args.kwargs["system"] == "Be concise"
        assert call_args.kwargs["model"] == "groq/test-model"
        assert result == "LLM says hello"

    @pytest.mark.asyncio
    async def test_call_llm_default_system(self):
        from packages.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "test"
            capability = "scripting"

            async def execute(self, task: str, context: dict) -> str:
                return ""

        agent = TestAgent()
        mock_router = MagicMock()
        mock_router.complete_text = AsyncMock(return_value="response")
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_router)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("packages.agents.base.RouterClient", return_value=mock_ctx):
            with patch("packages.agents.base.get_model_for_capability", return_value="auto"):
                result = await agent.call_llm("prompt")

        assert result == "response"
        assert mock_router.complete_text.call_args.kwargs["system"] == ""
