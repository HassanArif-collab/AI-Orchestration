"""Tests for packages.content_factory.orchestration.thoughts.

This is the orchestration thoughts module (pipeline thought streaming),
NOT packages.core.thoughts (which is tested in Phase A.8).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.content_factory.orchestration.thoughts import (
    STAGE_TO_COLUMN,
    AGENT_COLORS,
    report_thought,
    update_card_stage,
    pipeline_node,
    report_milestone,
    report_error,
)


# ══════════════════════════════════════════════════════════════
# STAGE_TO_COLUMN mapping
# ══════════════════════════════════════════════════════════════

class TestStageToColumn:
    def test_discovering_maps_to_1(self):
        assert STAGE_TO_COLUMN["discovering"] == 1

    def test_grading_maps_to_1(self):
        assert STAGE_TO_COLUMN["grading"] == 1

    def test_suggested_maps_to_2(self):
        assert STAGE_TO_COLUMN["suggested"] == 2

    def test_researching_maps_to_3(self):
        assert STAGE_TO_COLUMN["researching"] == 3

    def test_drafting_maps_to_4(self):
        assert STAGE_TO_COLUMN["drafting"] == 4

    def test_scoring_maps_to_4(self):
        assert STAGE_TO_COLUMN["scoring"] == 4

    def test_mutating_maps_to_4(self):
        assert STAGE_TO_COLUMN["mutating"] == 4

    def test_visuals_maps_to_5(self):
        assert STAGE_TO_COLUMN["visuals"] == 5

    def test_review_maps_to_5(self):
        assert STAGE_TO_COLUMN["review"] == 5

    def test_publishing_maps_to_6(self):
        assert STAGE_TO_COLUMN["publishing"] == 6

    def test_complete_maps_to_6(self):
        assert STAGE_TO_COLUMN["complete"] == 6

    def test_completed_maps_to_6(self):
        assert STAGE_TO_COLUMN["completed"] == 6

    def test_error_maps_to_none(self):
        assert STAGE_TO_COLUMN["error"] is None

    def test_unknown_stage_missing(self):
        assert "unknown_stage" not in STAGE_TO_COLUMN


# ══════════════════════════════════════════════════════════════
# AGENT_COLORS
# ══════════════════════════════════════════════════════════════

class TestAgentColors:
    def test_has_expected_agents(self):
        expected = ["topic_finder", "researcher", "script_writer", "scorer",
                    "challenger", "visual_annotator", "system", "notion_publisher"]
        for agent in expected:
            assert agent in AGENT_COLORS

    def test_colors_are_strings(self):
        for name, color in AGENT_COLORS.items():
            assert isinstance(color, str)


# ══════════════════════════════════════════════════════════════
# report_thought
# ══════════════════════════════════════════════════════════════

class TestReportThought:

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            result = await report_thought("card_1", "researcher", "Starting research", "info")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        with patch("packages.core.supabase_client.get_supabase", side_effect=Exception("DB down")):
            result = await report_thought("card_1", "researcher", "Thought", "info")
        assert result is False

    @pytest.mark.asyncio
    async def test_inserts_correct_data(self):
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            await report_thought("card_42", "scorer", "Score: 85", "success", {"score": 85})

        mock_sb.table.assert_called_once_with("agent_thoughts")
        mock_table.insert.assert_called_once()
        insert_data = mock_table.insert.call_args[0][0]
        assert insert_data["card_id"] == "card_42"
        assert insert_data["agent_name"] == "scorer"
        # "success" maps to "output" via _THOUGHT_TYPE_MAP
        assert insert_data["thought_type"] == "output"
        assert insert_data["content"] == "Score: 85"

    @pytest.mark.asyncio
    async def test_default_metadata_not_inserted(self):
        mock_sb = MagicMock()
        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            await report_thought("c1", "a1", "thought", "info")
        insert_data = mock_sb.table.return_value.insert.call_args[0][0]
        # report_thought only inserts: card_id, agent_name, thought_type, content
        assert set(insert_data.keys()) == {"card_id", "agent_name", "thought_type", "content"}
        # "info" maps to "thinking" via _THOUGHT_TYPE_MAP
        assert insert_data["thought_type"] == "thinking"

    @pytest.mark.asyncio
    async def test_never_raises(self):
        """Even severe exceptions should be caught and return False."""
        with patch("packages.core.supabase_client.get_supabase", side_effect=RuntimeError("fatal")):
            result = await report_thought("c1", "a1", "t", "info")
        assert result is False


# ══════════════════════════════════════════════════════════════
# update_card_stage
# ══════════════════════════════════════════════════════════════

class TestUpdateCardStage:

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            result = await update_card_stage("card_1", "researching")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_stage(self):
        result = await update_card_stage("card_1", "unknown_stage_xyz")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_error_stage(self):
        result = await update_card_stage("card_1", "error")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        with patch("packages.core.supabase_client.get_supabase", side_effect=Exception("DB down")):
            result = await update_card_stage("card_1", "drafting")
        assert result is False

    @pytest.mark.asyncio
    async def test_updates_correct_column_and_status(self):
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            await update_card_stage("card_99", "visuals")

        mock_sb.table.assert_called_once_with("kanban_cards")
        mock_table.update.assert_called_once()
        update_data = mock_table.update.call_args[0][0]
        assert update_data["column_index"] == 5
        assert update_data["status"] == "visuals"
        assert "updated_at" in update_data


# ══════════════════════════════════════════════════════════════
# @pipeline_node decorator
# ══════════════════════════════════════════════════════════════

class TestPipelineNodeDecorator:

    @pytest.mark.asyncio
    async def test_wraps_function(self):
        @pipeline_node("test_agent")
        async def my_node(state):
            return {"result": "done"}

        assert asyncio.iscoroutinefunction(my_node)
        result = await my_node({"card_id": "c1"})
        assert result == {"result": "done"}

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        @pipeline_node("agent")
        async def special_node(state):
            pass
        assert special_node.__name__ == "special_node"

    @pytest.mark.asyncio
    async def test_error_returns_error_state(self):
        @pipeline_node("failing_agent")
        async def bad_node(state):
            raise ValueError("something broke")

        result = await bad_node({"card_id": "c1"})
        assert result["error"] is not None
        assert "failing_agent" in result["error"]
        assert "ValueError" in result["error"]
        assert result["pipeline_status"] == "error"

    @pytest.mark.asyncio
    async def test_none_result_converted_to_empty_dict(self):
        @pipeline_node("agent")
        async def empty_node(state):
            return None

        result = await empty_node({"card_id": "c1"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_reports_start_and_completion(self):
        with patch("packages.content_factory.orchestration.thoughts.report_thought", new_callable=AsyncMock) as mock_rt:
            with patch("packages.content_factory.orchestration.thoughts.update_card_stage", new_callable=AsyncMock) as mock_uc:
                @pipeline_node("researcher")
                async def research_node(state):
                    return {"research_dossier": "data"}

                await research_node({"card_id": "c1", "pipeline_status": "researching"})

                # Should have called report_thought for start and success
                assert mock_rt.call_count == 2
                # First call: starting
                assert "Starting researcher" in mock_rt.call_args_list[0][0][2]
                assert mock_rt.call_args_list[0][0][3] == "thinking"
                # Second call: completed
                assert "researcher complete" in mock_rt.call_args_list[1][0][2]
                assert mock_rt.call_args_list[1][0][3] == "success"
                # Should have called update_card_stage once
                mock_uc.assert_called_once_with("c1", "researching")

    @pytest.mark.asyncio
    async def test_reports_error_on_exception(self):
        with patch("packages.content_factory.orchestration.thoughts.report_thought", new_callable=AsyncMock) as mock_rt:
            with patch("packages.content_factory.orchestration.thoughts.update_card_stage", new_callable=AsyncMock):
                @pipeline_node("scorer")
                async def failing_node(state):
                    raise RuntimeError("LLM timeout")

                result = await failing_node({"card_id": "c1"})

                # Should have 3 calls: start, error, completion NOT called
                assert mock_rt.call_count == 2
                # Error call should have type "error"
                assert mock_rt.call_args_list[1][0][3] == "error"
                assert "RuntimeError" in mock_rt.call_args_list[1][0][2]

    @pytest.mark.asyncio
    async def test_uses_pipeline_status_from_state(self):
        with patch("packages.content_factory.orchestration.thoughts.update_card_stage", new_callable=AsyncMock) as mock_uc:
            @pipeline_node("agent")
            async def node(state):
                return {}

            await node({"card_id": "c1", "pipeline_status": "mutating"})
            mock_uc.assert_called_once_with("c1", "mutating")

    @pytest.mark.asyncio
    async def test_uses_agent_name_as_default_stage(self):
        with patch("packages.content_factory.orchestration.thoughts.update_card_stage", new_callable=AsyncMock) as mock_uc:
            @pipeline_node("my_agent")
            async def node(state):
                return {}

            await node({"card_id": "c1"})
            mock_uc.assert_called_once_with("c1", "my_agent")


# ══════════════════════════════════════════════════════════════
# report_milestone
# ══════════════════════════════════════════════════════════════

class TestReportMilestone:

    @pytest.mark.asyncio
    async def test_delegates_to_report_thought_with_milestone_type(self):
        with patch("packages.content_factory.orchestration.thoughts.report_thought", new_callable=AsyncMock, return_value=True) as mock_rt:
            result = await report_milestone("c1", "scorer", "Score reached 90!", {"score": 90})
        assert result is True
        mock_rt.assert_called_once_with("c1", "scorer", "Score reached 90!", "milestone", {"score": 90})

    @pytest.mark.asyncio
    async def test_default_metadata_is_none(self):
        with patch("packages.content_factory.orchestration.thoughts.report_thought", new_callable=AsyncMock, return_value=True) as mock_rt:
            await report_milestone("c1", "agent", "Milestone!")
        mock_rt.assert_called_once_with("c1", "agent", "Milestone!", "milestone", None)


# ══════════════════════════════════════════════════════════════
# report_error
# ══════════════════════════════════════════════════════════════

class TestReportError:

    @pytest.mark.asyncio
    async def test_delegates_to_report_thought_with_error_type(self):
        with patch("packages.content_factory.orchestration.thoughts.report_thought", new_callable=AsyncMock, return_value=True) as mock_rt:
            result = await report_error("c1", "researcher", "API rate limited")
        assert result is True
        mock_rt.assert_called_once()
        args = mock_rt.call_args[0]
        assert args[0] == "c1"
        assert args[1] == "researcher"
        assert args[2].startswith("\u274c")  # ❌ prefix
        assert "API rate limited" in args[2]
        assert args[3] == "error"

    @pytest.mark.asyncio
    async def test_includes_metadata(self):
        with patch("packages.content_factory.orchestration.thoughts.report_thought", new_callable=AsyncMock, return_value=True) as mock_rt:
            await report_error("c1", "a", "err", {"code": 429})
        mock_rt.assert_called_once_with("c1", "a", "\u274c err", "error", {"code": 429})

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self):
        with patch("packages.content_factory.orchestration.thoughts.report_thought", new_callable=AsyncMock, return_value=False):
            result = await report_error("c1", "a", "err")
        assert result is False
