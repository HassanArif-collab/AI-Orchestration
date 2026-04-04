"""Tests for orchestration/review.py — ReviewInterface.

Tests get_pending_escalations, resolve methods, and Supabase interactions.
"""

import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

for mod_name in [
    "langgraph", "langgraph.graph", "langgraph.types",
    "langgraph.prebuilt", "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

from packages.content_factory.orchestration.review import ReviewInterface, ReviewDecisions


def _make_review(master=None):
    """Create a test ReviewInterface."""
    if master is None:
        master = MagicMock()
        master.db = MagicMock()
        master.db.acquire_lock.return_value = True
        master.db._cycles.return_value = MagicMock()
        master.db._cycles.return_value.update.return_value = MagicMock()
        master.db._cycles.return_value.eq.return_value = MagicMock()
        master.db._cycles.return_value.execute.return_value = MagicMock()
        master.advance_phase = AsyncMock()
    return ReviewInterface(master)


class TestGetPendingEscalations:
    """Tests for get_pending_escalations — fetches from Supabase."""

    def test_returns_empty_on_error(self):
        """When Supabase fails, return empty list."""
        review = _make_review()

        with patch("packages.core.supabase_client.get_supabase", side_effect=Exception("db down")):
            result = review.get_pending_escalations()
            assert result == []

    def test_parses_pending_escalations(self):
        """Should parse escalation rows into EscalationItem objects."""
        review = _make_review()
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "escalation_id": "esc-1",
                "cycle_id": "cycle-1",
                "type": "instruction_update",
                "severity": "high",
                "context_payload": {"note": "test"},
                "status": "pending",
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            result = review.get_pending_escalations()
            assert len(result) == 1
            assert result[0].escalation_id == "esc-1"
            assert result[0].context_payload == {"note": "test"}

    def test_handles_string_context_payload(self):
        """Should parse string context_payload as JSON."""
        review = _make_review()
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "escalation_id": "esc-2",
                "cycle_id": "cycle-2",
                "type": "hard_failure",
                "severity": "critical",
                "context_payload": '{"key": "value"}',
                "status": "pending",
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            result = review.get_pending_escalations()
            assert len(result) == 1
            assert result[0].context_payload == {"key": "value"}

    def test_handles_invalid_json_context_payload(self):
        """Should handle invalid JSON gracefully."""
        review = _make_review()
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "escalation_id": "esc-3",
                "cycle_id": "cycle-3",
                "type": "hard_failure",
                "severity": "high",
                "context_payload": "not json at all",
                "status": "pending",
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            result = review.get_pending_escalations()
            assert len(result) == 1
            assert result[0].context_payload == {}


class TestResolveInstructionUpdate:
    """Tests for resolve_instruction_update."""

    def test_marks_resolved_on_approve(self):
        """Should call _mark_resolved with the decision."""
        review = _make_review()

        with patch.object(review, "_mark_resolved") as mock_mark:
            review.resolve_instruction_update("esc-1", ReviewDecisions.APPROVE)
            mock_mark.assert_called_once_with("esc-1", ReviewDecisions.APPROVE)

    def test_marks_resolved_on_modify(self):
        """Should call _mark_resolved on modify."""
        review = _make_review()

        with patch.object(review, "_mark_resolved") as mock_mark:
            review.resolve_instruction_update("esc-1", ReviewDecisions.MODIFY, modified_text="new text")
            mock_mark.assert_called_once_with("esc-1", ReviewDecisions.MODIFY)


class TestResolveHardFailure:
    """Tests for resolve_hard_failure."""

    def test_continue_baseline_fires_advance_phase(self):
        """CONTINUE_BASELINE should fire advance_phase."""
        review = _make_review()

        with patch.object(review, "_mark_resolved"), \
             patch.object(review, "_fire_advance_phase") as mock_fire:
            review.resolve_hard_failure("esc-1", "cycle-1", ReviewDecisions.CONTINUE_BASELINE)
            mock_fire.assert_called_once_with("cycle-1")

    def test_abandon_calls_abandon_cycle(self):
        """ABANDON should call _abandon_cycle."""
        review = _make_review()

        with patch.object(review, "_mark_resolved"), \
             patch.object(review, "_abandon_cycle") as mock_abandon:
            review.resolve_hard_failure("esc-1", "cycle-1", ReviewDecisions.ABANDON)
            mock_abandon.assert_called_once_with("cycle-1")


class TestResolveSensitiveContent:
    """Tests for resolve_sensitive_content."""

    def test_approve_and_revise_paths(self):
        """Both approve and revise should call _mark_resolved."""
        review = _make_review()

        with patch.object(review, "_mark_resolved") as mock_mark:
            review.resolve_sensitive_content("esc-1", "cycle-1", ReviewDecisions.APPROVE)
            review.resolve_sensitive_content("esc-2", "cycle-2", ReviewDecisions.REVISE_MANUALLY)
            assert mock_mark.call_count == 2


class TestMarkResolved:
    """Tests for _mark_resolved — updates Supabase."""

    def test_updates_supabase(self):
        """Should update status in Supabase escalations table."""
        review = _make_review()
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            review._mark_resolved("esc-1", "approved")

        mock_sb.table.assert_called_with("escalations")
        mock_sb.table.return_value.update.assert_called_once_with({"status": "approved"})

    def test_handles_supabase_error(self):
        """Should not crash on Supabase error."""
        review = _make_review()

        with patch("packages.core.supabase_client.get_supabase", side_effect=Exception("db down")):
            review._mark_resolved("esc-1", "approved")  # Should not raise


class TestAbandonCycle:
    """Tests for _abandon_cycle — releases lock and sets abandoned."""

    def test_abandons_when_lock_acquired(self):
        """Should set status to abandoned and release lock."""
        master = MagicMock()
        master.db.acquire_lock.return_value = True
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
        master.db._cycles.return_value = mock_table
        review = ReviewInterface(master)

        review._abandon_cycle("cycle-1")

        mock_table.update.assert_called_once()
        update_call = mock_table.update.call_args[0][0]
        assert update_call["status"] == "abandoned"
        master.db.release_lock.assert_called_once_with("cycle-1")

    def test_no_update_when_lock_not_acquired(self):
        """Should not attempt update when lock not acquired."""
        master = MagicMock()
        master.db.acquire_lock.return_value = False
        review = ReviewInterface(master)

        review._abandon_cycle("cycle-1")

        master.db._cycles.assert_not_called()


class TestReviewDecisions:
    """Tests for ReviewDecisions constants."""

    def test_constants(self):
        assert ReviewDecisions.APPROVE == "approve"
        assert ReviewDecisions.REJECT == "reject"
        assert ReviewDecisions.MODIFY == "modify"
        assert ReviewDecisions.CONTINUE_BASELINE == "continue"
        assert ReviewDecisions.REVISE_MANUALLY == "revise"
        assert ReviewDecisions.ABANDON == "abandon"


class TestFireAdvancePhase:
    """Tests for _fire_advance_phase — sync→async bridge."""

    def test_queues_when_no_loop(self):
        """When no running event loop, should queue the advance."""
        review = _make_review()

        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
            review._fire_advance_phase("cycle-1")
            assert len(review._pending_tasks) == 1
            assert review._pending_tasks[0][0] == "queued_advance"
