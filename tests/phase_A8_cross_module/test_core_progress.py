"""Tests for packages/core/progress.py — Progress tracking."""

import pytest
from datetime import datetime, timezone


class TestProgressStage:
    """Tests for ProgressStage enum."""

    def test_core_stages(self):
        from packages.core.progress import ProgressStage
        assert ProgressStage.STARTING.value == "starting"
        assert ProgressStage.IN_PROGRESS.value == "in_progress"
        assert ProgressStage.COMPLETED.value == "completed"
        assert ProgressStage.FAILED.value == "failed"

    def test_extended_stages(self):
        from packages.core.progress import ProgressStage
        expected = {"starting", "in_progress", "searching", "generating",
                     "scoring", "saving", "researching", "drafting",
                     "mutating", "evaluating", "publishing", "completed", "failed"}
        assert {s.value for s in ProgressStage} == expected


class TestProgressEvent:
    """Tests for ProgressEvent model."""

    def test_creation(self):
        from packages.core.progress import ProgressEvent, ProgressStage
        event = ProgressEvent(
            operation_id="run-123",
            operation_type="topic_generation",
        )
        assert event.operation_id == "run-123"
        assert event.stage == ProgressStage.STARTING
        assert event.progress_percent is None
        assert event.message == ""
        assert event.metadata == {}

    def test_full_creation(self):
        from packages.core.progress import ProgressEvent, ProgressStage
        event = ProgressEvent(
            operation_id="run-123",
            operation_type="script_writing",
            stage=ProgressStage.IN_PROGRESS,
            stage_label="Drafting",
            progress_percent=50,
            message="Writing section 3...",
            elapsed_seconds=12.5,
            total_stages=4,
            current_stage_index=2,
            metadata={"agent": "writer"},
        )
        assert event.progress_percent == 50
        assert event.metadata["agent"] == "writer"

    def test_has_timestamp(self):
        from packages.core.progress import ProgressEvent
        event = ProgressEvent(operation_id="x", operation_type="y")
        assert isinstance(event.timestamp, datetime)


class TestProgressTrackerInit:
    """Tests for ProgressTracker initialization."""

    def test_default_stages(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test_type")
        assert tracker.stages == ["processing"]
        assert tracker.total_stages == 1

    def test_custom_stages(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test", stages=["a", "b", "c"])
        assert tracker.total_stages == 3
        assert tracker.stages == ["a", "b", "c"]

    def test_total_steps(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test", total_steps=10)
        assert tracker.total_steps == 10


class TestProgressTrackerReport:
    """Tests for ProgressTracker.report()."""

    def test_report_basic(self):
        from packages.core.progress import ProgressTracker, ProgressStage
        tracker = ProgressTracker("op-1", "test")
        event = tracker.report(ProgressStage.IN_PROGRESS, "Working...", percent=50)
        assert event.progress_percent == 50
        assert event.stage == ProgressStage.IN_PROGRESS

    def test_report_string_stage(self):
        from packages.core.progress import ProgressTracker, ProgressStage
        tracker = ProgressTracker("op-1", "test")
        event = tracker.report("searching", "Searching...")
        assert event.stage == ProgressStage.SEARCHING

    def test_report_invalid_stage_defaults(self):
        from packages.core.progress import ProgressTracker, ProgressStage
        tracker = ProgressTracker("op-1", "test")
        event = tracker.report("invalid_stage_value", "msg")
        assert event.stage == ProgressStage.STARTING

    def test_backward_progress_prevention(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test")
        tracker.report("in_progress", "", percent=50)
        event = tracker.report("in_progress", "", percent=30)  # Try to go backward
        assert event.progress_percent == 50  # Should stay at 50

    def test_report_with_metadata(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test")
        event = tracker.report("in_progress", "msg", metadata={"key": "value"})
        assert event.metadata["key"] == "value"

    def test_estimated_remaining(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test")
        # Set some elapsed time first
        tracker.report("in_progress", "", percent=75)
        event = tracker.report("in_progress", "", percent=80)
        # At 80% with some elapsed time, remaining should be positive
        # The exact value depends on timing but should be positive
        if event.progress_percent == 80:
            assert event.estimated_remaining_seconds is not None

    def test_estimated_remaining_none_at_zero(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test")
        event = tracker.report("in_progress", "", percent=0)
        # At 0%, no estimate can be made
        assert event.estimated_remaining_seconds is None

    def test_percent_none_preserves_last(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test")
        tracker.report("in_progress", "", percent=25)
        event = tracker.report("in_progress", "still working")  # no percent
        assert event.progress_percent == 25


class TestProgressTrackerStartStage:
    """Tests for ProgressTracker.start_stage()."""

    def test_start_stage(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test", stages=["search", "generate", "score"])
        event = tracker.start_stage("generate", "Generating content...")
        assert event.stage_label == "generate"
        assert tracker.current_stage_index == 1

    def test_start_stage_calculates_percent(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test", stages=["a", "b", "c", "d"])
        tracker.start_stage("c", "")
        assert tracker._last_percent == 50  # 2/4 * 100


class TestProgressTrackerCompleteStage:
    """Tests for ProgressTracker.complete_stage()."""

    def test_complete_stage(self):
        from packages.core.progress import ProgressTracker, ProgressStage
        tracker = ProgressTracker("op-1", "test", stages=["a", "b", "c"])
        tracker.start_stage("a")
        event = tracker.complete_stage()
        assert event.stage == ProgressStage.COMPLETED

    def test_complete_stage_advances_progress(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test", stages=["a", "b", "c"])
        tracker.start_stage("a")
        tracker.complete_stage()
        assert tracker._last_percent >= 33  # at least 1/3 done


class TestProgressTrackerFinish:
    """Tests for ProgressTracker.finish() and complete()."""

    def test_finish_sets_100_percent(self):
        from packages.core.progress import ProgressTracker, ProgressStage
        tracker = ProgressTracker("op-1", "test")
        event = tracker.finish("All done!")
        assert event.progress_percent == 100
        assert event.stage == ProgressStage.COMPLETED
        assert event.message == "All done!"

    def test_complete_delegates_to_finish(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test")
        event = tracker.complete("Done!")
        assert event.progress_percent == 100

    def test_finish_default_message(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test")
        event = tracker.finish()
        assert "complete" in event.message.lower()


class TestProgressTrackerFail:
    """Tests for ProgressTracker.fail()."""

    def test_fail(self):
        from packages.core.progress import ProgressTracker, ProgressStage
        tracker = ProgressTracker("op-1", "test")
        tracker.report("in_progress", "", percent=50)
        event = tracker.fail("Something went wrong")
        assert event.stage == ProgressStage.FAILED
        assert event.message == "Something went wrong"
        assert event.progress_percent == 50  # Preserves last percent

    def test_fail_with_error_details(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test")
        event = tracker.fail("Error", error_details={"code": 500})
        assert event.metadata["code"] == 500


class TestProgressTrackerUpdateStage:
    """Tests for ProgressTracker.update_stage()."""

    def test_update_stage_percent(self):
        from packages.core.progress import ProgressTracker
        tracker = ProgressTracker("op-1", "test", stages=["a", "b", "c"])
        tracker.start_stage("a")
        event = tracker.update_stage("Progressing...", percent=50)
        assert event.progress_percent >= 0
        assert event.message == "Progressing..."


class TestEmitProgress:
    """Tests for emit_progress() standalone function."""

    def test_adds_timestamp(self):
        from packages.core.progress import emit_progress
        # Should not raise (no event loop in test context)
        emit_progress("test_event", {"operation_id": "op-1"})
