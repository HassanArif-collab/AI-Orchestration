"""Tests for packages/core — types, config, errors, logger."""

import pytest
from datetime import datetime
from packages.core.types import (
    VideoIdea, ResearchOutput, Script, ScriptSection,
    VisualDecision, VisualPlan, SEOPackage, PipelineState,
)
from packages.core.errors import (
    LLMClientError, RateLimitError, ZepMemoryError,
    PipelineError, IntegrationError,
)
from packages.core.config import get_settings


def test_video_idea_valid():
    idea = VideoIdea(
        title="Why GPT-4 is slower than GPT-3",
        angle="counterintuitive",
        curiosity_gap="Everyone assumes newer = faster",
        timeliness="trending this week",
        viral_score=8,
    )
    assert idea.viral_score == 8
    assert idea.competition_notes == ""


def test_video_idea_viral_score_bounds():
    with pytest.raises(Exception):
        VideoIdea(title="t", angle="a", curiosity_gap="c",
                  timeliness="t", viral_score=11)
    with pytest.raises(Exception):
        VideoIdea(title="t", angle="a", curiosity_gap="c",
                  timeliness="t", viral_score=0)


def test_pipeline_state_defaults():
    state = PipelineState(run_id="abc-123", stage="idea")
    assert state.status == "running"
    assert state.video_idea is None
    assert state.research is None
    assert isinstance(state.created_at, datetime)


def test_pipeline_state_with_idea():
    idea = VideoIdea(title="t", angle="a", curiosity_gap="c",
                     timeliness="t", viral_score=5)
    state = PipelineState(run_id="abc-123", stage="research", video_idea=idea)
    assert state.video_idea.title == "t"


def test_script_sections():
    section = ScriptSection(
        section_type="hook",
        text="Did you know...",
        duration_seconds=15,
    )
    script = Script(
        title="Test Video",
        sections=[section],
        total_duration=15,
    )
    assert script.sections[0].section_type == "hook"


def test_errors_are_not_builtins():
    """Verify none of our custom exceptions shadow Python builtins."""
    import builtins
    assert not hasattr(builtins, "LLMClientError")
    assert not hasattr(builtins, "ZepMemoryError")
    assert not hasattr(builtins, "RateLimitError")


def test_rate_limit_is_subclass():
    assert issubclass(RateLimitError, LLMClientError)


def test_settings_freerouter_url():
    settings = get_settings()
    assert settings.FREEROUTER_URL.startswith("http")
    assert "4000" in settings.FREEROUTER_URL or "localhost" in settings.FREEROUTER_URL
