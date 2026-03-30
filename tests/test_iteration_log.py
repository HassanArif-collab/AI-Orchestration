"""Tests for IterationLogStore (now Supabase-backed)."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


def _mock_supabase():
    """Create a mock Supabase client with chainable table methods."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = []

    table_mock = MagicMock()
    for method in ['select', 'insert', 'update', 'upsert', 'delete',
                   'eq', 'neq', 'or_', 'order', 'limit', 'maybe_single',
                   'single']:
        getattr(table_mock, method).return_value = table_mock
    table_mock.execute.return_value = mock_response

    mock_client.table.return_value = table_mock
    return mock_client, table_mock, mock_response


@patch("packages.core.supabase_client.get_supabase")
def test_save_and_retrieve(mock_get_sb):
    """Test basic save and retrieve operations."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_get_sb.return_value = mock_client

    from packages.pipeline.iteration_store import IterationLogStore

    store = IterationLogStore()
    store.save(
        run_id="r1",
        iteration=1,
        score=74.2,
        previous_score=61.0,
        beat_baseline=True,
        mutation_zone="script_prose",
        script_json={"adapted_title": "T", "entries": []},
        failed_questions=["B3"],
        fixed_questions=["A1"],
    )

    table_mock.insert.assert_called_once()
    call_kwargs = table_mock.insert.call_args
    data = call_kwargs[0][0]
    assert data["run_id"] == "r1"
    assert data["score"] == 74.2
    assert data["beat_baseline"] is True


@patch("packages.core.supabase_client.get_supabase")
def test_multiple_runs(mock_get_sb):
    """Test that multiple runs are isolated correctly."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_get_sb.return_value = mock_client

    from packages.pipeline.iteration_store import IterationLogStore

    store = IterationLogStore()

    # Add 3 iterations for run-1
    for i in range(3):
        store.save(
            run_id="run-1",
            iteration=i,
            score=60.0 + i * 5,
            previous_score=60.0,
            beat_baseline=i > 0,
            mutation_zone="script_prose",
            script_json={},
            failed_questions=[],
            fixed_questions=[],
        )

    # Add 1 iteration for run-2
    store.save(
        run_id="run-2",
        iteration=0,
        score=55.0,
        previous_score=0,
        beat_baseline=False,
        mutation_zone="visual_direction",
        script_json={},
        failed_questions=[],
        fixed_questions=[],
    )

    assert table_mock.insert.call_count == 4


@patch("packages.core.supabase_client.get_supabase")
def test_get_all_returns_data(mock_get_sb):
    """Test that get_all returns data from Supabase."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_response.data = [
        {
            "id": "iter-1",
            "run_id": "r1",
            "iteration": 1,
            "score": 74.2,
            "previous_score": 61.0,
            "beat_baseline": True,
            "mutation_zone": "script_prose",
            "script_json": {"adapted_title": "T"},
            "failed_questions": [],
            "fixed_questions": [],
            "created_at": "2024-01-01T00:00:00Z",
        }
    ]
    mock_get_sb.return_value = mock_client

    from packages.pipeline.iteration_store import IterationLogStore

    store = IterationLogStore()
    rows = store.get_all("r1")

    assert len(rows) == 1
    assert rows[0]["score"] == 74.2
    assert rows[0]["beat_baseline"] is True


@patch("packages.core.supabase_client.get_supabase")
def test_empty_run(mock_get_sb):
    """Test that non-existent run returns empty list."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_response.data = []
    mock_get_sb.return_value = mock_client

    from packages.pipeline.iteration_store import IterationLogStore

    store = IterationLogStore()
    assert store.get_all("nobody") == []


@patch("packages.core.supabase_client.get_supabase")
def test_delete_for_run(mock_get_sb):
    """Test delete_for_run returns count."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_response.data = [{"id": "a"}, {"id": "b"}]
    mock_get_sb.return_value = mock_client

    from packages.pipeline.iteration_store import IterationLogStore

    store = IterationLogStore()
    deleted = store.delete_for_run("r1")

    assert deleted == 2
    table_mock.delete.assert_called_once()
