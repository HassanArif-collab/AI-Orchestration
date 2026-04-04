"""
test_database_router.py — Phase A.0: Tests for packages/core/database.py

Covers:
  - SQLITE_TABLES constant contains expected tables
  - get_backend_for_table() returns correct backend
  - assert_single_owner() passes for correct backend
  - assert_single_owner() raises for wrong backend
"""

import pytest


class TestSqliteTables:
    """Verify the SQLITE_TABLES set is correct."""

    def test_is_frozenset(self):
        from packages.core.database import SQLITE_TABLES
        assert isinstance(SQLITE_TABLES, frozenset)

    def test_expected_sqlite_tables(self):
        from packages.core.database import SQLITE_TABLES
        expected = {"usage_log", "baseline_scripts", "source_videos", "binary_evaluations"}
        assert expected.issubset(SQLITE_TABLES), f"Missing: {expected - SQLITE_TABLES}"


class TestGetBackendForTable:
    """Tests for get_backend_for_table()."""

    def test_sqlite_table_returns_sqlite(self):
        from packages.core.database import get_backend_for_table
        assert get_backend_for_table("usage_log") == "sqlite"
        assert get_backend_for_table("baseline_scripts") == "sqlite"
        assert get_backend_for_table("source_videos") == "sqlite"
        assert get_backend_for_table("binary_evaluations") == "sqlite"

    def test_supabase_table_returns_supabase(self):
        from packages.core.database import get_backend_for_table
        supabase_tables = [
            "pipeline_runs", "kanban_cards", "agent_thoughts",
            "research_cache", "production_cycles", "escalations",
            "topic_briefs", "video_performance", "iteration_logs",
        ]
        for table in supabase_tables:
            assert get_backend_for_table(table) == "supabase", f"Failed for {table}"

    def test_unknown_table_defaults_to_supabase(self):
        from packages.core.database import get_backend_for_table
        assert get_backend_for_table("totally_new_table") == "supabase"


class TestAssertSingleOwner:
    """Tests for assert_single_owner()."""

    def test_passes_for_correct_backend(self):
        from packages.core.database import assert_single_owner
        # Should not raise
        assert_single_owner("usage_log", "sqlite")
        assert_single_owner("pipeline_runs", "supabase")

    def test_raises_for_wrong_backend(self):
        from packages.core.database import assert_single_owner
        with pytest.raises(AssertionError, match="dual-write bug"):
            assert_single_owner("usage_log", "supabase")

        with pytest.raises(AssertionError, match="dual-write bug"):
            assert_single_owner("pipeline_runs", "sqlite")

    def test_error_message_contains_table_name(self):
        from packages.core.database import assert_single_owner
        with pytest.raises(AssertionError, match="usage_log"):
            assert_single_owner("usage_log", "supabase")
