"""Tests for packages/core — types, config, errors, logger."""

import pytest
from datetime import datetime
from packages.core.types import PipelineState
from packages.core.errors import (
    LLMClientError, RateLimitError, ZepMemoryError,
    PipelineError, IntegrationError,
)
from packages.core.config import get_settings


def test_pipeline_state_defaults():
    state = PipelineState(run_id="abc-123", stage="idea")
    assert state.status == "running"
    assert state.error_message == ""
    assert isinstance(state.created_at, datetime)


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


def test_core_types_does_not_export_pipeline_content_types():
    import packages.core.types as t
    for name in ["VideoIdea", "ResearchOutput", "Script", "ScriptSection",
                 "VisualDecision", "VisualPlan", "SEOPackage"]:
        assert not hasattr(t, name), f"core.types still exports '{name}' — should be removed"


def test_core_types_still_exports_integration_types():
    from packages.core.types import (PipelineState, SessionType, AgentRole,
        MessageRole, VideoMetadata, ChannelMetadata, AnalyticsMetadata, ChannelStats, MemoryFact)
    assert PipelineState is not None
