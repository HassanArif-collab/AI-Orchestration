"""Tests for topic_finder/db.py -- verify Supabase-backed TopicReservoirDB and PerformanceDB."""

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
def test_row_to_brief_handles_optional_columns(mock_get_sb):
    """Verify _row_to_brief works when optional columns are None/missing."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_get_sb.return_value = mock_client

    from packages.content_factory.topic_finder.db import TopicReservoirDB
    from packages.content_factory.topic_finder.models import TopicBrief

    db = TopicReservoirDB()
    row = {
        "brief_id": "test-1",
        "topic_statement": "Test Topic",
        "big_question": "Test Question?",
        "genre_id": "current_situation",
        "gap_type": "Hidden Mechanism",
        "viability_score_breakdown": {},
        "anchor_candidates": [],
        "mainstream_assumption": "Test assumption",
        "urgency_flag": False,
        "timing_rationale": "Test rationale",
        "created_at": "2024-01-01T00:00:00",
        "status": "reservoir",
        "content_type": None,
        "adaptation_source_video_id": None,
        "structural_reference_video_id": None,
    }

    result = db._row_to_brief(row)

    assert result.brief_id == "test-1"
    assert result.topic_statement == "Test Topic"
    # Optional columns should have defaults
    assert result.content_type == "original"
    assert result.adaptation_source_video_id is None


@patch("packages.core.supabase_client.get_supabase")
def test_row_to_brief_handles_all_columns(mock_get_sb):
    """Verify _row_to_brief works when all columns are present."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_get_sb.return_value = mock_client

    from packages.content_factory.topic_finder.db import TopicReservoirDB

    db = TopicReservoirDB()
    row = {
        "brief_id": "test-2",
        "topic_statement": "Test Topic 2",
        "big_question": "Test Question?",
        "genre_id": "explainer",
        "gap_type": "Hidden Connection",
        "viability_score_breakdown": {"total": 15},
        "anchor_candidates": [],
        "mainstream_assumption": "Test assumption",
        "urgency_flag": True,
        "timing_rationale": "Test rationale",
        "created_at": "2024-01-01T00:00:00",
        "status": "reservoir",
        "content_type": "adaptation",
        "adaptation_source_video_id": "vid-123",
        "structural_reference_video_id": "vid-456",
    }

    result = db._row_to_brief(row)

    assert result.content_type == "adaptation"
    assert result.adaptation_source_video_id == "vid-123"
    assert result.structural_reference_video_id == "vid-456"


@patch("packages.core.supabase_client.get_supabase")
def test_save_topic_calls_upsert(mock_get_sb):
    """Verify save_topic calls upsert on topic_briefs table."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_get_sb.return_value = mock_client

    from packages.content_factory.topic_finder.db import TopicReservoirDB
    from packages.content_factory.topic_finder.models import TopicBrief

    db = TopicReservoirDB()
    topic = TopicBrief(
        brief_id="test-3",
        topic_statement="Test Save",
        big_question="Why?",
        genre_id="explainer",
        gap_type="Hidden Mechanism",
        viability_score_breakdown={"total": 15},
        anchor_candidates=["anchor1"],
        mainstream_assumption="Everyone thinks X",
        urgency_flag=True,
        timing_rationale="Now is the time",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    db.save_topic(topic)

    mock_client.table.assert_called_with("topic_briefs")
    table_mock.upsert.assert_called_once()


@patch("packages.core.supabase_client.get_supabase")
def test_save_performance_calls_upsert(mock_get_sb):
    """Verify save_performance calls upsert on video_performance table."""
    mock_client, table_mock, mock_response = _mock_supabase()
    mock_get_sb.return_value = mock_client

    from packages.content_factory.topic_finder.db import PerformanceDB
    from packages.content_factory.topic_finder.models import VideoPerformanceProfile

    db = PerformanceDB()
    profile = VideoPerformanceProfile(
        video_id="vid-test",
        publication_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        genre_id="explainer",
        topic_statement="Test topic",
        viability_score_at_selection=75.0,
    )

    db.save_performance(profile)

    mock_client.table.assert_called_with("video_performance")
    table_mock.upsert.assert_called_once()
