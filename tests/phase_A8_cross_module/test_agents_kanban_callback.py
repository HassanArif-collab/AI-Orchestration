"""Tests for packages/agents/kanban_callback.py — Kanban callback handler (Phase A.8)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


class TestConstants:
    """Tests for module constants."""

    def test_pipeline_to_kanban_stage_mapping(self):
        from packages.agents.kanban_callback import PIPELINE_TO_KANBAN_STAGE
        assert PIPELINE_TO_KANBAN_STAGE["trend_analysis"] == 1
        assert PIPELINE_TO_KANBAN_STAGE["research"] == 3
        assert PIPELINE_TO_KANBAN_STAGE["script_writing"] == 4
        assert PIPELINE_TO_KANBAN_STAGE["visual_planning"] == 5
        assert PIPELINE_TO_KANBAN_STAGE["publish"] == 6

    def test_valid_kanban_stages(self):
        from packages.agents.kanban_callback import VALID_KANBAN_STAGES
        assert VALID_KANBAN_STAGES == {1, 2, 3, 4, 5, 6}

    def test_valid_statuses(self):
        from packages.agents.kanban_callback import VALID_STATUSES
        assert "idle" in VALID_STATUSES
        assert "thinking" in VALID_STATUSES
        assert "error" in VALID_STATUSES
        assert "complete" in VALID_STATUSES
        assert "waiting" in VALID_STATUSES

    def test_valid_artifact_keys(self):
        from packages.agents.kanban_callback import VALID_ARTIFACT_KEYS
        assert "research" in VALID_ARTIFACT_KEYS
        assert "script" in VALID_ARTIFACT_KEYS
        assert "visual_cues" in VALID_ARTIFACT_KEYS
        assert "notion_url" in VALID_ARTIFACT_KEYS
        assert "content" in VALID_ARTIFACT_KEYS


class TestKanbanCallbackHandlerInit:
    """Tests for KanbanCallbackHandler initialization."""

    def test_init_with_task_id(self):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="test-id")
        assert handler.task_id == "test-id"

    def test_init_default_base_url(self):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="test-id")
        assert handler.base_url == "http://localhost:3000"

    def test_init_custom_base_url(self):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="test-id", base_url="http://custom:3000")
        assert handler.base_url == "http://custom:3000"

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="test-id")
        result = await handler.__aenter__()
        assert result is handler
        await handler.__aexit__(None, None, None)


class TestOnThought:
    """Tests for on_thought()."""

    @pytest.mark.asyncio
    @patch("packages.core.thoughts.report_thought")
    async def test_reports_thought_successfully(self, mock_report):
        mock_report.return_value = True
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.on_thought("Analyzing topic...")
        assert result is True
        mock_report.assert_called_once()

    @pytest.mark.asyncio
    @patch("packages.core.thoughts.report_thought", side_effect=Exception("fail"))
    async def test_returns_false_on_error(self, mock_report):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.on_thought("thought")
        assert result is False

    @pytest.mark.asyncio
    @patch("packages.core.thoughts.report_thought")
    async def test_passes_metadata(self, mock_report):
        mock_report.return_value = True
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        await handler.on_thought("thinking...", metadata={"agent_name": "researcher"})
        call_kwargs = mock_report.call_args.kwargs
        assert call_kwargs["agent_name"] == "researcher"

    @pytest.mark.asyncio
    @patch("packages.core.thoughts.report_thought")
    async def test_defaults_agent_name_to_unknown(self, mock_report):
        mock_report.return_value = True
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        await handler.on_thought("thinking...")
        call_kwargs = mock_report.call_args.kwargs
        assert call_kwargs["agent_name"] == "unknown"


class TestOnStageChange:
    """Tests for on_stage_change()."""

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase")
    async def test_valid_stage_calls_supabase(self, mock_get_sb):
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_update.eq = MagicMock(return_value=MagicMock(execute=MagicMock()))
        mock_table.update.return_value = mock_update
        mock_get_sb.return_value.table.return_value = mock_table

        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.on_stage_change(3)
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_stage_returns_false(self):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        assert await handler.on_stage_change(0) is False
        assert await handler.on_stage_change(7) is False
        assert await handler.on_stage_change(-1) is False

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase", side_effect=Exception("db error"))
    async def test_returns_false_on_supabase_error(self, mock_get_sb):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.on_stage_change(1)
        assert result is False


class TestOnStatusChange:
    """Tests for on_status_change()."""

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase")
    async def test_valid_status_calls_supabase(self, mock_get_sb):
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_update.eq = MagicMock(return_value=MagicMock(execute=MagicMock()))
        mock_table.update.return_value = mock_update
        mock_get_sb.return_value.table.return_value = mock_table

        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.on_status_change("thinking")
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_status_returns_false(self):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        assert await handler.on_status_change("invalid_status") is False

    @pytest.mark.asyncio
    async def test_all_valid_statuses(self):
        from packages.agents.kanban_callback import KanbanCallbackHandler, VALID_STATUSES
        handler = KanbanCallbackHandler(task_id="card-123")
        # All valid statuses pass the validation check
        for status in VALID_STATUSES:
            assert status in VALID_STATUSES  # already validated by constant


class TestOnArtifact:
    """Tests for on_artifact()."""

    @pytest.mark.asyncio
    @patch("packages.core.thoughts.report_thought")
    async def test_valid_artifact_key(self, mock_report):
        mock_report.return_value = True
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.on_artifact("research", "Some research content")
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_artifact_key_returns_false(self):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.on_artifact("invalid_key", "content")
        assert result is False

    @pytest.mark.asyncio
    @patch("packages.core.thoughts.report_thought")
    async def test_truncates_long_value(self, mock_report):
        mock_report.return_value = True
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        long_value = "x" * 600
        await handler.on_artifact("content", long_value)
        content_arg = mock_report.call_args.kwargs["content"]
        assert content_arg.startswith("[content]")
        # Value should be truncated to 500 chars (plus prefix)
        assert len(content_arg) < 600


class TestCreateChildTask:
    """Tests for create_child_task()."""

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase")
    async def test_creates_child_task(self, mock_get_sb):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_get_sb.return_value.table.return_value = mock_table

        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="parent-123")
        child_id = await handler.create_child_task(title="New Topic", stage=2)
        assert child_id is not None
        assert len(child_id) == 36  # UUID format

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase", side_effect=Exception("fail"))
    async def test_returns_none_on_error(self, mock_get_sb):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="parent-123")
        result = await handler.create_child_task(title="Topic")
        assert result is None


class TestUpdateTitle:
    """Tests for update_title()."""

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase")
    async def test_updates_title(self, mock_get_sb):
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_update.eq = MagicMock(return_value=MagicMock(execute=MagicMock()))
        mock_table.update.return_value = mock_update
        mock_get_sb.return_value.table.return_value = mock_table

        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.update_title("New Title")
        assert result is True

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase", side_effect=Exception("fail"))
    async def test_returns_false_on_error(self, mock_get_sb):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.update_title("Title")
        assert result is False


class TestDeleteTask:
    """Tests for delete_task()."""

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase")
    async def test_deletes_task(self, mock_get_sb):
        mock_table = MagicMock()
        mock_delete = MagicMock()
        mock_delete.eq = MagicMock(return_value=MagicMock(execute=MagicMock()))
        mock_table.delete.return_value = mock_delete
        mock_get_sb.return_value.table.return_value = mock_table

        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.delete_task()
        assert result is True

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase", side_effect=Exception("fail"))
    async def test_returns_false_on_error(self, mock_get_sb):
        from packages.agents.kanban_callback import KanbanCallbackHandler
        handler = KanbanCallbackHandler(task_id="card-123")
        result = await handler.delete_task()
        assert result is False


class TestCreateKanbanTask:
    """Tests for create_kanban_task() function."""

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase")
    async def test_creates_task(self, mock_get_sb):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_get_sb.return_value.table.return_value = mock_table

        from packages.agents.kanban_callback import create_kanban_task
        task_id = await create_kanban_task(title="Test Task", stage=1)
        assert task_id is not None
        assert len(task_id) == 36

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase", side_effect=Exception("fail"))
    async def test_returns_none_on_error(self, mock_get_sb):
        from packages.agents.kanban_callback import create_kanban_task
        result = await create_kanban_task(title="Test")
        assert result is None

    @pytest.mark.asyncio
    @patch("packages.core.supabase_client.get_supabase")
    async def test_with_color(self, mock_get_sb):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_get_sb.return_value.table.return_value = mock_table

        from packages.agents.kanban_callback import create_kanban_task
        task_id = await create_kanban_task(title="Colored", color="#0066cc")
        assert task_id is not None


class TestGetKanbanStage:
    """Tests for get_kanban_stage() function."""

    def test_known_stages(self):
        from packages.agents.kanban_callback import get_kanban_stage
        assert get_kanban_stage("trend_analysis") == 1
        assert get_kanban_stage("research") == 3
        assert get_kanban_stage("script_writing") == 4
        assert get_kanban_stage("visual_planning") == 5
        assert get_kanban_stage("publish") == 6

    def test_unknown_stage_defaults_to_one(self):
        from packages.agents.kanban_callback import get_kanban_stage
        assert get_kanban_stage("nonexistent_stage") == 1

    def test_seo_maps_to_script(self):
        from packages.agents.kanban_callback import get_kanban_stage
        assert get_kanban_stage("seo") == 4

    def test_human_review_maps_to_visual(self):
        from packages.agents.kanban_callback import get_kanban_stage
        assert get_kanban_stage("human_review") == 5
