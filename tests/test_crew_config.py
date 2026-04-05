"""Tests for crew_config.py - verify real CrewAI delegation.

These tests verified that the create_*_crew() functions return real CrewAI
Crew objects when crewai is available, and None when it is not.

SKIPPED: packages.agents.crew_config was deleted in Phase 3 (CrewAI dead code removal).
LangGraph pipeline handles research, scripting, and visuals without CrewAI crews.
"""

import pytest


@pytest.mark.skip(reason="packages.agents.crew_config deleted in Phase 3 — CrewAI replaced by LangGraph pipeline")
def test_create_research_crew_no_skeleton():
    """Verify create_research_crew returns a real Crew, not a skeleton dict."""
    from packages.agents.crew_config import create_research_crew, CREWAI_AVAILABLE

    result = create_research_crew("Pakistan AI policy")

    if CREWAI_AVAILABLE:
        assert not (
            isinstance(result, dict) and result.get("status") == "skeleton"
        ), "Must return a real Crew, not a skeleton dict"
    else:
        assert result is None


@pytest.mark.skip(reason="packages.agents.crew_config deleted in Phase 3 — CrewAI replaced by LangGraph pipeline")
def test_create_script_crew_no_skeleton():
    """Verify create_script_crew returns a real Crew, not a skeleton dict."""
    from packages.agents.crew_config import create_script_crew, CREWAI_AVAILABLE

    result = create_script_crew({"topic": "test"})

    if CREWAI_AVAILABLE:
        assert not (
            isinstance(result, dict) and result.get("status") == "skeleton"
        ), "Must return a real Crew, not a skeleton dict"
    else:
        assert result is None


@pytest.mark.skip(reason="packages.agents.crew_config deleted in Phase 3 — CrewAI replaced by LangGraph pipeline")
def test_create_visual_crew_no_skeleton():
    """Verify create_visual_crew returns a real Crew, not a skeleton dict."""
    from packages.agents.crew_config import create_visual_crew, CREWAI_AVAILABLE

    result = create_visual_crew({"adapted_title": "test"})

    if CREWAI_AVAILABLE:
        assert not (
            isinstance(result, dict) and result.get("status") == "skeleton"
        ), "Must return a real Crew, not a skeleton dict"
    else:
        assert result is None
