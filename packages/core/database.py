"""Database Router — Enforces one table, one owner.

Prevents dual-write bugs by routing each table to its canonical backend.
Moving a table from SQLite to Supabase (or vice versa) requires changing
only the SQLITE_TABLES set.

Current ownership:
  SUPABASE (8 tables): pipeline_runs, kanban_cards, agent_thoughts,
    research_cache, production_cycles, escalations, topic_briefs,
    video_performance, iteration_logs
  SQLITE (4 tables): usage_log, baseline_scripts, source_videos,
    binary_evaluations
"""

from packages.core.logger import get_logger

logger = get_logger(__name__)

# Tables owned by SQLite. Everything else goes to Supabase.
SQLITE_TABLES = frozenset({
    "usage_log",
    "baseline_scripts",
    "source_videos",
    "binary_evaluations",
})


def get_backend_for_table(table_name: str) -> str:
    """Return 'sqlite' or 'supabase' for the given table.

    Use this when adding new database operations to ensure you're
    writing to the correct backend.

    Args:
        table_name: The table being accessed

    Returns:
        'sqlite' or 'supabase'
    """
    backend = "sqlite" if table_name in SQLITE_TABLES else "supabase"
    return backend


def assert_single_owner(table_name: str, actual_backend: str) -> None:
    """Assert that the actual backend matches the canonical owner.

    Call this in critical paths to catch dual-write bugs at runtime.

    Args:
        table_name: The table being accessed
        actual_backend: 'sqlite' or 'supabase' — the backend being used

    Raises:
        AssertionError: If the backend doesn't match the canonical owner
    """
    expected = get_backend_for_table(table_name)
    if expected != actual_backend:
        raise AssertionError(
            f"Table '{table_name}' belongs to {expected}, "
            f"but code is using {actual_backend}. "
            f"This is a dual-write bug!"
        )
