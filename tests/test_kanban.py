"""Tests for Kanban Dashboard functionality.

Tests cover:
- KanbanCallbackHandler agent integration (now Supabase-backed)
- TopicFinderAgent Kanban integration
- Stage mapping utilities
- Title extraction from pipeline runs
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_supabase():
    """Create a mock Supabase client with chainable table methods."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = []

    table_mock = MagicMock()
    for method in ['select', 'insert', 'update', 'upsert', 'delete',
                   'eq', 'neq', 'or_', 'order', 'limit', 'maybe_single',
                   'single']:
        getattr(table_mock, method).return_value = table_mock
    table_mock.execute.return_value = mock_response

    mock_client.table.return_value = table_mock
    return mock_client, table_mock, mock_response


# ─── KanbanCallbackHandler Tests ───────────────────────────────────────────────────

class TestKanbanCallbackHandler:
    """Tests for KanbanCallbackHandler (now Supabase-backed)."""

    @pytest.mark.asyncio
    async def test_on_thought(self):
        """Test reporting a thought writes to Supabase via report_thought."""
        mock_client, table_mock, mock_response = _mock_supabase()

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_client):
            from packages.agents.kanban_callback import KanbanCallbackHandler
            handler = KanbanCallbackHandler(task_id="test-task-id")

            with patch("packages.core.thoughts.report_thought") as mock_report:
                await handler.on_thought("Analyzing topic viability...", metadata={"agent_name": "researcher"})
                mock_report.assert_called_once_with(
                    card_id="test-task-id",
                    agent_name="researcher",
                    thought_type="thinking",
                    content="Analyzing topic viability...",
                )

    @pytest.mark.asyncio
    async def test_on_stage_change(self):
        """Test reporting a stage change updates kanban_cards in Supabase."""
        mock_client, table_mock, mock_response = _mock_supabase()
        mock_response.data = [{"id": "test-task-id"}]

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_client):
            from packages.agents.kanban_callback import KanbanCallbackHandler
            handler = KanbanCallbackHandler(task_id="test-task-id")

            result = await handler.on_stage_change(3)
            assert result is True
            table_mock.update.assert_called()
            table_mock.eq.assert_called()

    @pytest.mark.asyncio
    async def test_on_stage_change_invalid(self):
        """Test reporting invalid stage is rejected."""
        with patch("packages.core.supabase_client.get_supabase"):
            from packages.agents.kanban_callback import KanbanCallbackHandler
            handler = KanbanCallbackHandler(task_id="test-task-id")
            result = await handler.on_stage_change(7)  # Invalid stage
            assert result is False

    @pytest.mark.asyncio
    async def test_on_status_change(self):
        """Test reporting a status change updates kanban_cards in Supabase."""
        mock_client, table_mock, mock_response = _mock_supabase()
        mock_response.data = [{"id": "test-task-id"}]

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_client):
            from packages.agents.kanban_callback import KanbanCallbackHandler
            handler = KanbanCallbackHandler(task_id="test-task-id")

            result = await handler.on_status_change("thinking")
            assert result is True

    @pytest.mark.asyncio
    async def test_on_artifact(self):
        """Test reporting an artifact writes to thoughts as 'output' type."""
        with patch("packages.core.thoughts.report_thought") as mock_report:
            from packages.agents.kanban_callback import KanbanCallbackHandler
            handler = KanbanCallbackHandler(task_id="test-task-id")

            result = await handler.on_artifact("research", "Research content")
            assert result is True
            mock_report.assert_called_once()
            call_args = mock_report.call_args
            assert call_args.kwargs["thought_type"] == "output"


# ─── TopicFinderAgent Integration Tests ────────────────────────────────────────────

class TestTopicFinderIntegration:
    """Tests for TopicFinderAgent Kanban integration."""

    @pytest.mark.asyncio
    async def test_topic_finder_initializes_with_kanban_id(self):
        """Test TopicFinderAgent accepts kanban_task_id."""
        from packages.content_factory.topic_finder.finder import TopicFinderAgent

        agent = TopicFinderAgent(kanban_task_id="test-kanban-id")

        assert agent.kanban_task_id == "test-kanban-id"
        assert agent._kanban_callback is None  # Not initialized until needed

    @pytest.mark.asyncio
    async def test_topic_finder_without_kanban_id(self):
        """Test TopicFinderAgent works without kanban_task_id."""
        from packages.content_factory.topic_finder.finder import TopicFinderAgent

        agent = TopicFinderAgent()

        assert agent.kanban_task_id is None
        assert agent._kanban_callback is None

    @pytest.mark.asyncio
    async def test_report_thought_helper(self):
        """Test _report_thought helper method."""
        from packages.content_factory.topic_finder.finder import TopicFinderAgent

        agent = TopicFinderAgent(kanban_task_id="test-id")
        agent._kanban_callback = MagicMock()
        agent._kanban_callback.on_thought = AsyncMock(return_value=True)

        await agent._report_thought("Test thought")

        agent._kanban_callback.on_thought.assert_called_once_with("Test thought")

    @pytest.mark.asyncio
    async def test_report_thought_no_callback(self):
        """Test _report_thought does nothing without callback."""
        from packages.content_factory.topic_finder.finder import TopicFinderAgent

        agent = TopicFinderAgent()  # No kanban_task_id

        # Should not raise any error
        await agent._report_thought("Test thought")


# ─── Stage Mapping Tests ───────────────────────────────────────────────────────────

class TestStageMapping:
    """Tests for pipeline stage to Kanban stage mapping."""

    def test_stage_mapping_exists(self):
        """Test that stage mapping is defined."""
        from packages.agents.kanban_callback import PIPELINE_TO_KANBAN_STAGE

        assert len(PIPELINE_TO_KANBAN_STAGE) == 9

        # Verify all values are valid Kanban stages (1-6)
        for stage in PIPELINE_TO_KANBAN_STAGE.values():
            assert 1 <= stage <= 6

    def test_get_kanban_stage(self):
        """Test get_kanban_stage helper function."""
        from packages.agents.kanban_callback import get_kanban_stage

        assert get_kanban_stage("research") == 3
        assert get_kanban_stage("script_writing") == 4
        assert get_kanban_stage("unknown_stage") == 1  # Default


# ─── Title Extraction Tests (Task 7.1) ─────────────────────────────────────────────

class TestTitleExtraction:
    """Tests for title extraction from pipeline runs in Kanban view."""

    def test_extract_title_from_normalized_approval(self):
        """Test that _run_to_kanban_dict extracts title from normalized approval."""
        from apps.api.routers.kanban_routes import _run_to_kanban_dict

        mock_run = MagicMock()
        mock_run.to_dict.return_value = {
            "run_id": "test-run-123",
            "current_stage": "research",
            "status": "running",
            "stage_outputs": {
                "human_topic_approval": {
                    "title": "Why Pakistan's AI Policy Matters",
                    "subtitle": "What if the real bottleneck isn't technology?",
                    "gap_type": "Practical Gap",
                    "viability_total": 15,
                    "viability_max": 17,
                    "gap_pass": True,
                    "anchor_pass": 3,
                    "audience_pass": 3,
                }
            },
            "stage_status": {
                "trend_analysis": "complete",
                "human_topic_approval": "complete",
                "research": "running"
            },
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z"
        }

        # Mock thoughts to avoid real Supabase call
        with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]):
            result = _run_to_kanban_dict(mock_run)

        assert result["title"] == "Why Pakistan's AI Policy Matters"

    def test_extract_title_fallback_to_topic_statement(self):
        """Test that _run_to_kanban_dict falls back to topic_statement if title missing."""
        from apps.api.routers.kanban_routes import _run_to_kanban_dict

        mock_run = MagicMock()
        mock_run.to_dict.return_value = {
            "run_id": "test-run-456",
            "current_stage": "research",
            "status": "running",
            "stage_outputs": {
                "human_topic_approval": {
                    "topic_statement": "Raw Topic Statement",
                    "big_question": "What if...?",
                }
            },
            "stage_status": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z"
        }

        with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]):
            result = _run_to_kanban_dict(mock_run)

        assert result["title"] == "Raw Topic Statement"

    def test_extract_title_from_trend_analysis(self):
        """Test that _run_to_kanban_dict extracts title from trend_analysis if no approval."""
        from apps.api.routers.kanban_routes import _run_to_kanban_dict

        mock_run = MagicMock()
        mock_run.to_dict.return_value = {
            "run_id": "test-run-789",
            "current_stage": "human_topic_approval",
            "status": "waiting_human",
            "stage_outputs": {
                "trend_analysis": [
                    {
                        "title": "First Trend Topic",
                        "topic_statement": "First Trend Statement",
                        "viability_total": 10
                    }
                ]
            },
            "stage_status": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z"
        }

        with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]):
            result = _run_to_kanban_dict(mock_run)

        assert result["title"] == "First Trend Topic"


# ─── Run Tests ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
