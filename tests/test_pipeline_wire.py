"""Tests for pipeline_wire -- verify RunStore uses Supabase."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


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
def test_runstore_save_calls_upsert(mock_get_sb):
    """Verify RunStore.save calls upsert on pipeline_runs."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_get_sb.return_value = mock_client

    from packages.pipeline.state import RunStore, PipelineRun

    store = RunStore()
    run = PipelineRun.new()
    store.save(run)

    mock_client.table.assert_called_with("pipeline_runs")
    table_mock.upsert.assert_called_once()
    call_kwargs = table_mock.upsert.call_args
    data = call_kwargs[0][0]
    assert data["run_id"] == run.run_id


@patch("packages.core.supabase_client.get_supabase")
def test_runstore_load_returns_none(mock_get_sb):
    """Verify RunStore.load returns None when not found."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_response.data = None
    mock_get_sb.return_value = mock_client

    from packages.pipeline.state import RunStore

    store = RunStore()
    result = store.load("nonexistent")

    assert result is None


@patch("packages.core.supabase_client.get_supabase")
def test_runstore_list_runs(mock_get_sb):
    """Verify RunStore.list_runs returns Supabase data."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_response.data = [
        {"run_id": "r1", "current_stage": "research", "status": "running", "updated_at": "2024-01-01"},
        {"run_id": "r2", "current_stage": "script_writing", "status": "idle", "updated_at": "2024-01-02"},
    ]
    mock_get_sb.return_value = mock_client

    from packages.pipeline.state import RunStore

    store = RunStore()
    runs = store.list_runs(limit=10)

    assert len(runs) == 2
    assert runs[0]["run_id"] == "r1"


@patch("packages.core.supabase_client.get_supabase")
def test_runstore_delete(mock_get_sb):
    """Verify RunStore.delete calls delete on pipeline_runs."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_get_sb.return_value = mock_client

    from packages.pipeline.state import RunStore

    store = RunStore()
    store.delete("r1")

    mock_client.table.assert_called_with("pipeline_runs")
    table_mock.delete.assert_called_once()
