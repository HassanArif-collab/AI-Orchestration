"""
test_types.py — Phase A.0: Tests for packages/core/types.py

Covers:
  - PipelineState model creation and defaults
  - SessionType, AgentRole, MessageRole enums
  - Integration metadata types (VideoMetadata, ChannelMetadata, etc.)
  - MemoryFact model
"""

import pytest
from datetime import datetime, timezone


class TestPipelineState:
    """Tests for the PipelineState model — central state object."""

    def test_creation_with_required_fields(self):
        from packages.core.types import PipelineState
        state = PipelineState(run_id="run-001", stage="research")
        assert state.run_id == "run-001"
        assert state.stage == "research"

    def test_default_status_is_running(self):
        from packages.core.types import PipelineState
        state = PipelineState(run_id="r1", stage="s1")
        assert state.status == "running"

    def test_default_error_message_empty(self):
        from packages.core.types import PipelineState
        state = PipelineState(run_id="r1", stage="s1")
        assert state.error_message == ""

    def test_default_timestamps_are_datetime(self):
        from packages.core.types import PipelineState
        state = PipelineState(run_id="r1", stage="s1")
        assert isinstance(state.created_at, datetime)
        assert isinstance(state.updated_at, datetime)
        # Should be timezone-aware (UTC)
        assert state.created_at.tzinfo is not None

    def test_all_valid_statuses(self):
        from packages.core.types import PipelineState
        for status in ["running", "waiting_human", "complete", "error"]:
            state = PipelineState(run_id="r1", stage="s1", status=status)
            assert state.status == status

    def test_invalid_status_raises(self):
        from packages.core.types import PipelineState
        with pytest.raises(Exception):
            PipelineState(run_id="r1", stage="s1", status="bogus")

    def test_error_message_updatable(self):
        from packages.core.types import PipelineState
        state = PipelineState(run_id="r1", stage="research")
        state.error_message = "LLM call failed"
        assert state.error_message == "LLM call failed"

    def test_serialization_round_trip(self):
        from packages.core.types import PipelineState
        state = PipelineState(run_id="r1", stage="research", status="running")
        data = state.model_dump()
        state2 = PipelineState.model_validate(data)
        assert state.run_id == state2.run_id
        assert state.stage == state2.stage

    def test_json_serialization(self):
        from packages.core.types import PipelineState
        state = PipelineState(run_id="r1", stage="research")
        json_str = state.model_dump_json()
        assert "r1" in json_str
        assert "research" in json_str


class TestEnums:
    """Tests for SessionType, AgentRole, MessageRole enums."""

    def test_session_type_values(self):
        from packages.core.types import SessionType
        assert SessionType.AGENT.value == "agent"
        assert SessionType.AUDIENCE.value == "audience"
        assert SessionType.LEARNING.value == "learning"

    def test_session_type_from_string(self):
        from packages.core.types import SessionType
        assert SessionType("agent") == SessionType.AGENT

    def test_agent_role_values(self):
        from packages.core.types import AgentRole
        expected = {"researcher", "script_writer", "visual_planner", "seo_specialist"}
        actual = {role.value for role in AgentRole}
        assert actual == expected

    def test_message_role_values(self):
        from packages.core.types import MessageRole
        expected = {"user", "assistant", "system"}
        actual = {role.value for role in MessageRole}
        assert actual == expected


class TestVideoMetadata:
    """Tests for YouTube video metadata model."""

    def test_creation_with_required_fields(self):
        from packages.core.types import VideoMetadata
        vm = VideoMetadata(video_id="abc123", title="Test Video")
        assert vm.video_id == "abc123"
        assert vm.title == "Test Video"

    def test_default_values(self):
        from packages.core.types import VideoMetadata
        vm = VideoMetadata(video_id="abc", title="T")
        assert vm.description == ""
        assert vm.channel_id == ""
        assert vm.duration_seconds == 0
        assert vm.view_count == 0
        assert vm.like_count == 0
        assert vm.tags == []

    def test_full_population(self):
        from packages.core.types import VideoMetadata
        vm = VideoMetadata(
            video_id="abc", title="T",
            channel_id="ch1", channel_title="My Channel",
            published_at="2025-01-01", duration_seconds=600,
            view_count=1000, like_count=100, comment_count=50,
            tags=["python", "ai"]
        )
        assert vm.duration_seconds == 600
        assert len(vm.tags) == 2


class TestChannelMetadata:
    """Tests for YouTube channel metadata model."""

    def test_creation_with_required_fields(self):
        from packages.core.types import ChannelMetadata
        cm = ChannelMetadata(channel_id="ch1", title="My Channel")
        assert cm.channel_id == "ch1"
        assert cm.subscriber_count == 0

    def test_full_population(self):
        from packages.core.types import ChannelMetadata
        cm = ChannelMetadata(
            channel_id="ch1", title="My Channel",
            description="A channel", subscriber_count=5000,
            video_count=100, view_count=50000
        )
        assert cm.subscriber_count == 5000
        assert cm.view_count == 50000


class TestAnalyticsMetadata:
    """Tests for YouTube analytics metadata model."""

    def test_creation_with_required(self):
        from packages.core.types import AnalyticsMetadata
        am = AnalyticsMetadata(video_id="abc", date="2025-01-01")
        assert am.views == 0
        assert am.watch_time_minutes == 0.0

    def test_float_fields(self):
        from packages.core.types import AnalyticsMetadata
        am = AnalyticsMetadata(
            video_id="abc", date="2025-01-01",
            watch_time_minutes=123.5,
            average_view_duration=45.2,
            click_through_rate=5.5
        )
        assert am.click_through_rate == 5.5


class TestChannelStats:
    """Tests for channel statistics model."""

    def test_defaults(self):
        from packages.core.types import ChannelStats
        cs = ChannelStats(channel_id="ch1")
        assert cs.total_views == 0
        assert cs.engagement_rate == 0.0


class TestMemoryFact:
    """Tests for the Zep memory fact model."""

    def test_creation_with_required(self):
        from packages.core.types import MemoryFact
        mf = MemoryFact(fact_id="f1", content="AI is great")
        assert mf.fact_id == "f1"
        assert mf.content == "AI is great"
        assert mf.source == ""
        assert mf.metadata == {}

    def test_full_population(self):
        from packages.core.types import MemoryFact
        mf = MemoryFact(
            fact_id="f1", content="Test",
            source="research", metadata={"confidence": 0.9}
        )
        assert mf.source == "research"
        assert mf.metadata["confidence"] == 0.9
        assert isinstance(mf.created_at, datetime)
