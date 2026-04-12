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


# ─── Run Tests ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
