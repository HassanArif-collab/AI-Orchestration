"""Tests for packages/content_factory/orchestration/models.py

Covers:
  - ProductionPhase enum values and count
  - CycleStatus enum values and count
  - ProductionCycleRecord: creation, defaults, validation, Literal constraints
  - EscalationItem: creation, defaults, Literal constraints
"""

from datetime import datetime, timezone

import pytest


class TestProductionPhase:
    def test_all_members(self, orch_models):
        members = list(orch_models.ProductionPhase)
        assert len(members) == 12

    def test_expected_values(self, orch_models):
        expected_values = {
            "topic_selected", "phase_3_round_1a", "phase_3_round_1b",
            "phase_3_round_2", "phase_3_round_3", "phase_3_round_4",
            "phase_4_experiment", "phase_6_music", "awaiting_review",
            "completed", "failed", "abandoned",
        }
        actual = {m.value for m in orch_models.ProductionPhase}
        assert actual == expected_values

    def test_is_string_enum(self, orch_models):
        assert isinstance(orch_models.ProductionPhase.TOPIC_SELECTED.value, str)

    def test_str_comparison(self, orch_models):
        assert orch_models.ProductionPhase.COMPLETED == "completed"
        assert orch_models.ProductionPhase.FAILED == "failed"


class TestCycleStatus:
    def test_all_members(self, orch_models):
        members = list(orch_models.CycleStatus)
        assert len(members) == 4

    def test_expected_values(self, orch_models):
        expected = {"active", "paused", "completed", "failed"}
        actual = {m.value for m in orch_models.CycleStatus}
        assert actual == expected

    def test_str_comparison(self, orch_models):
        assert orch_models.CycleStatus.ACTIVE == "active"
        assert orch_models.CycleStatus.PAUSED == "paused"


class TestProductionCycleRecord:
    def test_minimal_creation(self, orch_models):
        record = orch_models.ProductionCycleRecord(
            cycle_id="c-1",
            topic_statement="Test Topic",
            genre="documentary",
        )
        assert record.cycle_id == "c-1"
        assert record.source == "topic_finder"
        assert record.current_phase == "topic_selected"
        assert record.status == "active"
        assert record.current_baseline_score == 0.0
        assert record.experiment_iterations == 0
        assert record.music_architecture_id is None
        assert record.published_video_id is None
        assert record.lock_expires_at is None
        assert isinstance(record.created_at, datetime)
        assert isinstance(record.updated_at, datetime)

    def test_full_creation(self, orch_models):
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)
        record = orch_models.ProductionCycleRecord(
            cycle_id="c-2",
            topic_statement="Deep Topic",
            genre="explainer",
            source="manual",
            current_phase="phase_4_experiment",
            status="active",
            current_baseline_score=82.5,
            experiment_iterations=5,
            music_architecture_id="ma-1",
            published_video_id="vid-123",
            created_at=now,
            updated_at=now,
            lock_expires_at=now,
        )
        assert record.source == "manual"
        assert record.current_phase == "phase_4_experiment"
        assert record.current_baseline_score == 82.5
        assert record.experiment_iterations == 5
        assert record.published_video_id == "vid-123"

    def test_source_literal_validation(self, orch_models):
        """source must be one of: topic_finder, adaptation, manual"""
        orch_models.ProductionCycleRecord(
            cycle_id="c", topic_statement="T", genre="g", source="topic_finder"
        )
        orch_models.ProductionCycleRecord(
            cycle_id="c", topic_statement="T", genre="g", source="adaptation"
        )
        orch_models.ProductionCycleRecord(
            cycle_id="c", topic_statement="T", genre="g", source="manual"
        )
        with pytest.raises(Exception):
            orch_models.ProductionCycleRecord(
                cycle_id="c", topic_statement="T", genre="g", source="invalid"
            )

    def test_defaults_match_enums(self, orch_models):
        record = orch_models.ProductionCycleRecord(
            cycle_id="c", topic_statement="T", genre="g"
        )
        assert record.current_phase == orch_models.ProductionPhase.TOPIC_SELECTED.value
        assert record.status == orch_models.CycleStatus.ACTIVE.value


class TestEscalationItem:
    def test_minimal_creation(self, orch_models):
        item = orch_models.EscalationItem(
            escalation_id="e-1",
            type="hard_failure",
            severity="high",
        )
        assert item.escalation_id == "e-1"
        assert item.cycle_id is None
        assert item.context_payload == {}
        assert item.status == "pending"
        assert isinstance(item.created_at, datetime)

    def test_full_creation(self, orch_models):
        item = orch_models.EscalationItem(
            escalation_id="e-2",
            cycle_id="c-1",
            type="sensitive_content",
            severity="critical",
            context_payload={"script_excerpt": "..."},
            status="pending",
        )
        assert item.cycle_id == "c-1"
        assert item.context_payload == {"script_excerpt": "..."}

    def test_type_literal_validation(self, orch_models):
        valid_types = ["instruction_update", "hard_failure", "reservoir_low", "weekly_summary", "sensitive_content"]
        for t in valid_types:
            orch_models.EscalationItem(escalation_id="e", type=t, severity="low")
        with pytest.raises(Exception):
            orch_models.EscalationItem(escalation_id="e", type="invalid", severity="low")

    def test_severity_literal_validation(self, orch_models):
        valid_severities = ["low", "medium", "high", "critical"]
        for s in valid_severities:
            orch_models.EscalationItem(escalation_id="e", type="hard_failure", severity=s)
        with pytest.raises(Exception):
            orch_models.EscalationItem(escalation_id="e", type="hard_failure", severity="urgent")

    def test_status_literal_validation(self, orch_models):
        valid_statuses = ["pending", "approved", "rejected", "modified"]
        for s in valid_statuses:
            orch_models.EscalationItem(escalation_id="e", type="hard_failure", severity="low", status=s)
        with pytest.raises(Exception):
            orch_models.EscalationItem(escalation_id="e", type="hard_failure", severity="low", status="in_progress")
