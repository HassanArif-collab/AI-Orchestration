"""Tests for packages/agents/registry.py — Agent registry."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestLoadSkill:
    """Tests for load_skill() function."""

    def test_returns_content_when_file_exists(self, tmp_path):
        from packages.agents.registry import SKILLS_DIR

        # Patch SKILLS_DIR
        skill_file = tmp_path / "researcher.md"
        skill_file.write_text("# Researcher Skill\n\nBe thorough.", encoding="utf-8")

        with patch("packages.agents.registry.SKILLS_DIR", tmp_path):
            from packages.agents.registry import load_skill
            result = load_skill("researcher")
        assert "# Researcher Skill" in result
        assert "Be thorough." in result

    def test_returns_empty_when_file_not_exists(self, tmp_path):
        with patch("packages.agents.registry.SKILLS_DIR", tmp_path):
            from packages.agents.registry import load_skill
            result = load_skill("nonexistent_agent")
        assert result == ""

    def test_returns_empty_for_nonexistent_dir(self):
        with patch("packages.agents.registry.SKILLS_DIR", Path("/nonexistent/path")):
            from packages.agents.registry import load_skill
            result = load_skill("any")
        assert result == ""


def _make_agent(name="test_agent"):
    """Create a valid BaseAgent subclass instance for testing."""
    from packages.agents.base import BaseAgent

    class TestAgent(BaseAgent):
        def __init__(self, agent_name):
            self.name = agent_name
            self.role = "Test"
            self.capability = "research"

        async def execute(self, task: str, context: dict) -> str:
            return "done"

    return TestAgent(name)


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    @pytest.fixture(autouse=True)
    def _clear_registry(self):
        """Clear registry before and after each test."""
        from packages.agents.registry import AgentRegistry
        AgentRegistry.clear()
        yield
        AgentRegistry.clear()

    def test_register_and_get(self):
        from packages.agents.registry import AgentRegistry
        agent = _make_agent("my_agent")
        AgentRegistry.register(agent)
        retrieved = AgentRegistry.get("my_agent")
        assert retrieved is agent

    def test_get_nonexistent_returns_none(self):
        from packages.agents.registry import AgentRegistry
        assert AgentRegistry.get("nonexistent") is None

    def test_register_replaces_existing(self):
        from packages.agents.registry import AgentRegistry
        agent1 = _make_agent("agent")
        agent2 = _make_agent("agent")
        AgentRegistry.register(agent1)
        AgentRegistry.register(agent2)
        assert AgentRegistry.get("agent") is agent2

    def test_list_agents(self):
        from packages.agents.registry import AgentRegistry
        AgentRegistry.register(_make_agent("a"))
        AgentRegistry.register(_make_agent("b"))
        AgentRegistry.register(_make_agent("c"))
        names = AgentRegistry.list_agents()
        assert set(names) == {"a", "b", "c"}

    def test_list_agents_empty(self):
        from packages.agents.registry import AgentRegistry
        assert AgentRegistry.list_agents() == []

    def test_clear(self):
        from packages.agents.registry import AgentRegistry
        AgentRegistry.register(_make_agent("x"))
        AgentRegistry.clear()
        assert AgentRegistry.list_agents() == []
        assert AgentRegistry.get("x") is None

    def test_list_returns_strings(self):
        from packages.agents.registry import AgentRegistry
        AgentRegistry.register(_make_agent("agent1"))
        names = AgentRegistry.list_agents()
        assert all(isinstance(n, str) for n in names)


class TestSkillsDir:
    """Tests for SKILLS_DIR constant."""

    def test_skills_dir_points_to_data_skills(self):
        from packages.agents.registry import SKILLS_DIR
        assert SKILLS_DIR.name == "skills"
        assert SKILLS_DIR.parent.name == "data"
