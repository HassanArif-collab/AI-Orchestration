"""Tests for agent bootstrap registration.

These tests verified that bootstrap_agents() properly registered
CrewAI agents into the AgentRegistry at startup.

SKIPPED: packages.agents.bootstrap was deleted in Phase 3 (CrewAI dead code removal).
LangGraph nodes now handle content creation directly without CrewAI agents.
"""

import pytest


@pytest.mark.skip(reason="packages.agents.bootstrap deleted in Phase 3 — CrewAI agents replaced by LangGraph nodes")
def test_bootstrap_registers_agents():
    """bootstrap_agents() should register agents into AgentRegistry."""
    from packages.agents.registry import AgentRegistry
    from packages.agents.bootstrap import bootstrap_agents
    AgentRegistry.clear()
    bootstrap_agents()
    result = AgentRegistry.list_agents()
    assert isinstance(result, list)


@pytest.mark.skip(reason="packages.agents.bootstrap deleted in Phase 3 — CrewAI agents replaced by LangGraph nodes")
def test_bootstrapped_agents_have_required_attrs():
    """Registered agents must have name and capability attributes."""
    from packages.agents.registry import AgentRegistry
    from packages.agents.bootstrap import bootstrap_agents
    AgentRegistry.clear()
    bootstrap_agents()
    for name in AgentRegistry.list_agents():
        agent = AgentRegistry.get(name)
        assert agent is not None
        assert hasattr(agent, "name")
        assert hasattr(agent, "capability")
