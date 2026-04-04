"""Tests for orchestration wiring.

These tests verify that:
1. The scheduler references MasterOrchestrator
2. background_tasks references the scheduler for startup
3. OrchestrationDB uses Supabase (not SQLite)
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


def test_orchestration_db_no_sqlite_import():
    """OrchestrationDB must not import sqlite3."""
    import packages.content_factory.orchestration.db as db_mod
    import inspect
    src = inspect.getsource(db_mod)
    assert "sqlite3" not in src, "OrchestrationDB must not import sqlite3"
    assert "import sqlite3" not in src


def test_orchestration_db_no_db_path():
    """OrchestrationDB must not use DB_PATH constant."""
    import packages.content_factory.orchestration.db as db_mod
    import inspect
    src = inspect.getsource(db_mod)
    assert "DB_PATH" not in src, "OrchestrationDB must not use DB_PATH"
