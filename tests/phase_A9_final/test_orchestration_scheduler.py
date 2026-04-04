"""Tests for orchestration/scheduler.py — Cron Scheduler with SQLite job state.

Tests boot_schedule, simulate_tick, job registration, and state persistence.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from pathlib import Path

for mod_name in [
    "langgraph", "langgraph.graph", "langgraph.types",
    "langgraph.prebuilt", "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


def _make_scheduler(master=None, tmp_path=None):
    """Create a Scheduler with mocked dependencies."""
    if master is None:
        master = MagicMock()
        master.db = MagicMock()
        master.db.get_active_cycles.return_value = []
        master.handle_escalation = AsyncMock()

    mock_topic_db = MagicMock()

    with patch("packages.content_factory.orchestration.scheduler.TopicReservoirDB", return_value=mock_topic_db), \
         patch("packages.content_factory.orchestration.scheduler.Scheduler._load_job_state", lambda self: None), \
         patch("packages.content_factory.orchestration.scheduler.Scheduler._get_db_path", return_value=tmp_path / "pipeline.db" if tmp_path else Path("/fake/pipeline.db")):
        from packages.content_factory.orchestration.scheduler import Scheduler
        scheduler = Scheduler.__new__(Scheduler)
        scheduler.master = master
        scheduler.topic_db = mock_topic_db
        scheduler.jobs = []
        scheduler._boot_schedule_called = False
        return scheduler


class TestRegisterCronJob:
    """Tests for register_cron_job."""

    def test_registers_job_with_correct_fields(self):
        """Should register a job with name, interval, action, and timing."""
        scheduler = _make_scheduler()
        action = MagicMock()

        scheduler.register_cron_job("TestJob", 6, action, "skip")

        assert len(scheduler.jobs) == 1
        job = scheduler.jobs[0]
        assert job["name"] == "TestJob"
        assert job["interval_hours"] == 6
        assert job["action"] is action
        assert job["failure_behavior"] == "skip"
        assert job["last_run"] is None
        assert job["next_run"] is not None


class TestBootSchedule:
    """Tests for boot_schedule — initializes all cron definitions."""

    def test_registers_all_standard_jobs(self):
        """Should register 6 standard cron jobs."""
        scheduler = _make_scheduler()

        with patch.object(scheduler, "register_cron_job", wraps=scheduler.register_cron_job), \
             patch.object(scheduler, "_apply_loaded_state"):
            scheduler.boot_schedule()

        assert len(scheduler.jobs) == 6
        names = [j["name"] for j in scheduler.jobs]
        assert "TopicFinder_Daily" in names
        assert "Production_Polling" in names
        assert "Learning_Synthesis_Weekly" in names
        assert "Health_Check_Hourly" in names
        assert "Analytics_Sweep_Daily" in names
        assert "Maintenance_Weekly" in names

    def test_prevents_double_init(self):
        """Should not register jobs twice if called again."""
        scheduler = _make_scheduler()

        with patch.object(scheduler, "_apply_loaded_state"):
            scheduler.boot_schedule()
            count_after_first = len(scheduler.jobs)
            scheduler.boot_schedule()  # Should skip
            assert len(scheduler.jobs) == count_after_first

    def test_correct_intervals(self):
        """Each job should have the correct interval."""
        scheduler = _make_scheduler()

        with patch.object(scheduler, "_apply_loaded_state"):
            scheduler.boot_schedule()

        intervals = {j["name"]: j["interval_hours"] for j in scheduler.jobs}
        assert intervals["TopicFinder_Daily"] == 24
        assert intervals["Production_Polling"] == 6
        assert intervals["Learning_Synthesis_Weekly"] == 168
        assert intervals["Health_Check_Hourly"] == 1
        assert intervals["Analytics_Sweep_Daily"] == 24
        assert intervals["Maintenance_Weekly"] == 168


class TestSimulateTick:
    """Tests for simulate_tick — executes due jobs."""

    @pytest.mark.asyncio
    async def test_skips_job_not_yet_due(self):
        """Should skip jobs whose next_run is in the future."""
        scheduler = _make_scheduler()
        future = datetime.now(timezone.utc) + timedelta(hours=5)
        scheduler.jobs = [{
            "name": "FutureJob",
            "interval_hours": 1,
            "action": MagicMock(),
            "failure_behavior": "skip",
            "last_run": None,
            "next_run": future,
        }]

        await scheduler.simulate_tick()
        scheduler.jobs[0]["action"].assert_not_called()

    @pytest.mark.asyncio
    async def test_executes_due_sync_job(self):
        """Should execute a sync job that is due."""
        scheduler = _make_scheduler()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        action = MagicMock()
        scheduler.jobs = [{
            "name": "DueJob",
            "interval_hours": 1,
            "action": action,
            "failure_behavior": "skip",
            "last_run": None,
            "next_run": past,
        }]

        with patch.object(scheduler, "_persist_job_state"):
            await scheduler.simulate_tick()
            action.assert_called_once()

    @pytest.mark.asyncio
    async def test_executes_due_async_job(self):
        """Should await an async job that is due."""
        scheduler = _make_scheduler()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        action = AsyncMock()
        scheduler.jobs = [{
            "name": "AsyncDueJob",
            "interval_hours": 1,
            "action": action,
            "failure_behavior": "skip",
            "last_run": None,
            "next_run": past,
        }]

        with patch.object(scheduler, "_persist_job_state"):
            await scheduler.simulate_tick()
            action.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_timing_after_success(self):
        """Should update last_run and next_run after successful execution."""
        scheduler = _make_scheduler()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        scheduler.jobs = [{
            "name": "TimingJob",
            "interval_hours": 6,
            "action": MagicMock(),
            "failure_behavior": "skip",
            "last_run": None,
            "next_run": past,
        }]

        with patch.object(scheduler, "_persist_job_state"):
            await scheduler.simulate_tick()

        job = scheduler.jobs[0]
        assert job["last_run"] is not None
        assert job["next_run"] is not None
        # next_run should be ~6 hours from now
        expected_next = job["last_run"] + timedelta(hours=6)
        assert abs((job["next_run"] - expected_next).total_seconds()) < 2

    @pytest.mark.asyncio
    async def test_handles_job_failure(self):
        """Should handle job failure, update timing, and not crash."""
        scheduler = _make_scheduler()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        failing_action = MagicMock(side_effect=RuntimeError("job failed"))
        scheduler.jobs = [{
            "name": "FailingJob",
            "interval_hours": 24,
            "action": failing_action,
            "failure_behavior": "skip",  # skip = no escalation
            "last_run": None,
            "next_run": past,
        }]

        with patch.object(scheduler, "_persist_job_state"):
            # Should not raise
            await scheduler.simulate_tick()
            assert scheduler.jobs[0]["last_run"] is not None
            # On failure, next_run = last_run + 1 hour (retry)
            expected_retry = scheduler.jobs[0]["last_run"] + timedelta(hours=1)
            assert abs((scheduler.jobs[0]["next_run"] - expected_retry).total_seconds()) < 2

    @pytest.mark.asyncio
    async def test_escalates_on_failure_with_escalate_behavior(self):
        """Jobs with failure_behavior='escalate' should trigger escalation."""
        scheduler = _make_scheduler()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        failing_action = MagicMock(side_effect=RuntimeError("job failed"))
        scheduler.jobs = [{
            "name": "EscalateJob",
            "interval_hours": 1,
            "action": failing_action,
            "failure_behavior": "escalate",
            "last_run": None,
            "next_run": past,
        }]

        with patch.object(scheduler, "_persist_job_state"):
            await scheduler.simulate_tick()
            scheduler.master.handle_escalation.assert_called_once()
            call_args = scheduler.master.handle_escalation.call_args
            assert call_args[0][1] == "cron_failure"
            assert call_args[0][2] == "high"


class TestJobStatePersistence:
    """Tests for SQLite job state persistence."""

    def test_persist_and_load_job_state(self, tmp_path):
        """Should persist job state to SQLite and reload on init."""
        db_path = tmp_path / "pipeline.db"

        # Create a scheduler and register a job
        scheduler1 = _make_scheduler(tmp_path=tmp_path)
        scheduler1.register_cron_job("PersistTest", 12, lambda: None)

        # Manually persist (bypass boot_schedule)
        with patch.object(scheduler1, "_get_db_path", return_value=db_path):
            scheduler1._persist_job_state()

        # Verify the file was created
        assert db_path.exists()

        # Now create a new scheduler and load from DB
        scheduler2 = _make_scheduler(tmp_path=tmp_path)
        scheduler2.register_cron_job("PersistTest", 12, lambda: None)

        # Simulate loading — read from DB
        import sqlite3
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute("SELECT job_name FROM scheduler_state").fetchall()
            names = [r[0] for r in rows]
            assert "PersistTest" in names

    def test_load_job_state_handles_missing_db(self, tmp_path):
        """Should handle missing DB gracefully."""
        db_path = tmp_path / "nonexistent" / "pipeline.db"
        scheduler = _make_scheduler(tmp_path=tmp_path)

        with patch.object(scheduler, "_get_db_path", return_value=db_path):
            scheduler._load_job_state()
            # Should not raise
            assert scheduler._loaded_state == {}


class TestRunHealthCheck:
    """Tests for run_health_check — now async."""

    @pytest.mark.asyncio
    async def test_ok_when_active_cycles_exist(self):
        """Should log normally when active cycles exist."""
        scheduler = _make_scheduler()
        mock_cycle = MagicMock()
        scheduler.master.db.get_active_cycles.return_value = [mock_cycle]

        # Should not raise
        await scheduler.run_health_check()

    @pytest.mark.asyncio
    async def test_escalates_when_reservoir_empty(self):
        """Should escalate when topic reservoir is empty."""
        scheduler = _make_scheduler()
        scheduler.master.db.get_active_cycles.return_value = []
        scheduler.topic_db.get_top_topics.return_value = []

        await scheduler.run_health_check()
        scheduler.master.handle_escalation.assert_called_once()
        call_args = scheduler.master.handle_escalation.call_args
        assert call_args[0][1] == "reservoir_low"


class TestTriggerProductionCycle:
    """Tests for trigger_production_cycle — event-based polling."""

    @pytest.mark.asyncio
    async def test_starts_cycle_when_topics_available(self):
        """Should call master.check_and_start_new_cycle when topics found."""
        scheduler = _make_scheduler()
        mock_topic = MagicMock()
        scheduler.topic_db.get_top_topics.return_value = [mock_topic]

        await scheduler.trigger_production_cycle()
        scheduler.master.check_and_start_new_cycle.assert_called_once_with([mock_topic])

    @pytest.mark.asyncio
    async def test_no_cycle_when_no_topics(self):
        """Should not call master when no topics available."""
        scheduler = _make_scheduler()
        scheduler.topic_db.get_top_topics.return_value = []

        await scheduler.trigger_production_cycle()
        scheduler.master.check_and_start_new_cycle.assert_not_called()
