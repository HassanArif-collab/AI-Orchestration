"""Tests for orchestration wiring.

These tests verify that:
1. The scheduler references MasterOrchestrator
2. background_tasks references the scheduler for startup
"""


def test_scheduler_references_master_orchestrator():
    """Scheduler must reference MasterOrchestrator."""
    import packages.content_factory.orchestration.scheduler as sched
    import inspect
    src = inspect.getsource(sched)
    assert "MasterOrchestrator" in src, "scheduler must reference MasterOrchestrator"


def test_background_tasks_references_scheduler():
    """background_tasks must reference the scheduler."""
    import apps.api.background_tasks as bt
    import inspect
    src = inspect.getsource(bt)
    assert "scheduler" in src.lower() or "orchestrat" in src.lower(), \
        "background_tasks must reference the scheduler"
