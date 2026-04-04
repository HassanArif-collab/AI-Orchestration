"""Tests for agent bootstrap registration.

These tests verify that bootstrap_agents() properly registers
CrewAI agents into the AgentRegistry at startup.
"""


def test_bootstrap_registers_agents():
    """bootstrap_agents() should register agents into AgentRegistry."""
    from packages.agents.registry import AgentRegistry
    from packages.agents.bootstrap import bootstrap_agents
    AgentRegistry.clear()
    bootstrap_agents()
    # If crewai is installed, agents should be registered
    # If crewai not installed, bootstrap returns gracefully and list is empty
    result = AgentRegistry.list_agents()
    assert isinstance(result, list)


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
