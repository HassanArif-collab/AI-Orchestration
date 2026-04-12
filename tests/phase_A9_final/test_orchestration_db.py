"""Tests for packages.content_factory.orchestration.db — OrchestrationDB."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from packages.content_factory.orchestration.models import (
    ProductionCycleRecord,
    EscalationItem,
)


# ── Helpers ──

def _make_mock_table():
    """Create a mock supabase table with chainable API."""
    table = MagicMock()
    table.insert.return_value = table
    table.update.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.or_.return_value = table
    table.execute.return_value = MagicMock(data=[])
    return table


def _make_cycle_record(**overrides):
    defaults = {
        "cycle_id": "cycle_001",
        "topic_statement": "Why Pakistan's water crisis is hidden",
        "genre": "investigative",
        "current_phase": "topic_selected",
        "status": "active",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return ProductionCycleRecord(**defaults)


def _make_escalation_item(**overrides):
    defaults = {
        "escalation_id": "esc_001",
        "cycle_id": "cycle_001",
        "type": "hard_failure",
        "severity": "high",
        "context_payload": {"error": "Script generation failed 3 times"},
        "status": "pending",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return EscalationItem(**defaults)


# ══════════════════════════════════════════════════════════════
# create_cycle
# ══════════════════════════════════════════════════════════════

class TestCreateCycle:

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_inserts_cycle_with_all_fields(self, mock_cycles):
        table = _make_mock_table()
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        record = _make_cycle_record(
            source="adaptation",
            current_baseline_score=72.5,
            experiment_iterations=3,
        )
        db.create_cycle(record)

        table.insert.assert_called_once()
        data = table.insert.call_args[0][0]
        assert data["cycle_id"] == "cycle_001"
        assert data["topic_statement"] == "Why Pakistan's water crisis is hidden"
        assert data["genre"] == "investigative"
        assert data["source"] == "adaptation"
        assert data["current_baseline_score"] == 72.5
        assert data["experiment_iterations"] == 3
        assert data["status"] == "active"
        assert "created_at" in data
        assert "updated_at" in data

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_inserts_with_optional_fields_none(self, mock_cycles):
        table = _make_mock_table()
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        record = _make_cycle_record()
        db.create_cycle(record)

        data = table.insert.call_args[0][0]
        assert data["music_architecture_id"] is None
        assert data["published_video_id"] is None


# ══════════════════════════════════════════════════════════════
# acquire_lock
# ══════════════════════════════════════════════════════════════

class TestAcquireLock:

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_returns_true_when_row_updated(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[{"cycle_id": "cycle_001"}])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        result = db.acquire_lock("cycle_001", owner_id="worker_1")
        assert result is True

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_returns_false_when_no_row_updated(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        result = db.acquire_lock("cycle_001", owner_id="worker_1")
        assert result is False

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_uses_correct_filter(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[{"cycle_id": "c1"}])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        db.acquire_lock("c1", owner_id="w1", ttl_seconds=60)

        table.update.assert_called_once()
        update_data = table.update.call_args[0][0]
        assert "lock_expires_at" in update_data
        assert update_data["lock_owner"] == "w1"
        assert "updated_at" in update_data
        table.eq.assert_called_with("cycle_id", "c1")

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_default_owner_is_default(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[{}])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        db.acquire_lock("c1")

        update_data = table.update.call_args[0][0]
        assert update_data["lock_owner"] == "default"


# ══════════════════════════════════════════════════════════════
# release_lock
# ══════════════════════════════════════════════════════════════

class TestReleaseLock:

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_release_clears_lock(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[{"cycle_id": "c1"}])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        db.release_lock("c1")

        table.update.assert_called_once_with({"lock_expires_at": None})
        table.eq.assert_any_call("cycle_id", "c1")

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_release_with_owner_filters_by_owner(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[{"cycle_id": "c1"}])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        db.release_lock("c1", owner_id="worker_1")

        eq_calls = table.eq.call_args_list
        assert any(call[0] == ("cycle_id", "c1") for call in eq_calls)
        assert any(call[0] == ("lock_owner", "worker_1") for call in eq_calls)

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_release_no_match_logs_warning(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        # Should log warning but not raise
        db.release_lock("c1", owner_id="wrong_owner")

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_release_without_owner(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[{}])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        db.release_lock("c1", owner_id=None)

        # Should only filter by cycle_id, not by lock_owner
        eq_calls = table.eq.call_args_list
        assert len(eq_calls) == 1
        assert eq_calls[0][0] == ("cycle_id", "c1")


# ══════════════════════════════════════════════════════════════
# get_active_cycles
# ══════════════════════════════════════════════════════════════

class TestGetActiveCycles:

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_returns_records(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[
            {
                "cycle_id": "c1",
                "topic_statement": "Topic 1",
                "genre": "tech",
                "source": "topic_finder",
                "current_phase": "phase_3_round_1a",
                "status": "active",
                "current_baseline_score": 72.5,
                "experiment_iterations": 3,
                "music_architecture_id": None,
                "published_video_id": None,
                "created_at": "2025-01-01T00:00:00+00:00",
                "updated_at": "2025-01-02T00:00:00+00:00",
            }
        ])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        results = db.get_active_cycles()

        assert len(results) == 1
        assert results[0].cycle_id == "c1"
        assert results[0].status == "active"
        assert results[0].current_baseline_score == 72.5
        assert results[0].experiment_iterations == 3

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_empty_result(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        results = db.get_active_cycles()

        assert results == []

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_filters_by_status_active(self, mock_cycles):
        table = _make_mock_table()
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        db.get_active_cycles()

        table.select.assert_called_once_with("*")
        table.eq.assert_called_once_with("status", "active")

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_handles_missing_optional_fields(self, mock_cycles):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[
            {
                "cycle_id": "c1",
                "topic_statement": "T",
                "genre": "g",
                "current_phase": "p",
                "status": "active",
                "created_at": "2025-01-01T00:00:00+00:00",
                "updated_at": "2025-01-01T00:00:00+00:00",
            }
        ])
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        results = db.get_active_cycles()

        assert len(results) == 1
        assert results[0].source == "topic_finder"
        assert results[0].current_baseline_score == 0.0
        assert results[0].experiment_iterations == 0


# ══════════════════════════════════════════════════════════════
# escalate
# ══════════════════════════════════════════════════════════════

class TestEscalate:

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._escalations")
    def test_inserts_escalation(self, mock_esc):
        table = _make_mock_table()
        mock_esc.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        item = _make_escalation_item()
        db.escalate(item)

        table.insert.assert_called_once()
        data = table.insert.call_args[0][0]
        assert data["escalation_id"] == "esc_001"
        assert data["cycle_id"] == "cycle_001"
        assert data["type"] == "hard_failure"
        assert data["severity"] == "high"
        assert data["status"] == "pending"
        assert "created_at" in data

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._escalations")
    def test_escalation_without_cycle_id(self, mock_esc):
        table = _make_mock_table()
        mock_esc.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        item = _make_escalation_item(cycle_id=None, type="reservoir_low", severity="medium")
        db.escalate(item)

        data = table.insert.call_args[0][0]
        assert data["cycle_id"] is None
        assert data["type"] == "reservoir_low"


# ══════════════════════════════════════════════════════════════
# update_pipeline_run_id
# ══════════════════════════════════════════════════════════════

class TestUpdatePipelineRunId:

    @patch("packages.content_factory.orchestration.db.OrchestrationDB._cycles")
    def test_updates_pipeline_run_id(self, mock_cycles):
        table = _make_mock_table()
        mock_cycles.return_value = table

        from packages.content_factory.orchestration.db import OrchestrationDB
        db = OrchestrationDB()
        db.update_pipeline_run_id("cycle_001", "run_abc123")

        table.update.assert_called_once_with({"pipeline_run_id": "run_abc123"})
        table.eq.assert_called_once_with("cycle_id", "cycle_001")
