"""Tests for topic_finder/db.py — verify sqlite3.Row handling."""

import sqlite3
import pytest


def test_row_to_brief_handles_optional_columns():
    """Verify _row_to_brief works with sqlite3.Row objects that lack .get()."""
    from packages.content_factory.topic_finder.db import TopicReservoirDB

    # Create an in-memory database with the reservoir schema
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create minimal schema for testing (without optional columns)
    cursor.execute("""
        CREATE TABLE topic_reservoir (
            brief_id TEXT PRIMARY KEY,
            topic_statement TEXT,
            big_question TEXT,
            genre_id TEXT,
            gap_type TEXT,
            score_breakdown TEXT,
            anchor_candidates TEXT,
            mainstream_assumption TEXT,
            urgency_flag INTEGER,
            timing_rationale TEXT,
            created_at TEXT,
            status TEXT
        )
    """)

    # Insert a row WITHOUT the optional columns
    cursor.execute("""
        INSERT INTO topic_reservoir VALUES (
            'test-1', 'Test Topic', 'Test Question?', 'current_situation',
            'Hidden Mechanism', '{}', '[]', 'Test assumption', 0,
            'Test rationale', '2024-01-01T00:00:00', 'reservoir'
        )
    """)
    conn.commit()

    cursor.execute("SELECT * FROM topic_reservoir WHERE brief_id = 'test-1'")
    row = cursor.fetchone()

    # This should NOT raise AttributeError
    db = TopicReservoirDB.__new__(TopicReservoirDB)
    result = db._row_to_brief(row)

    assert result.brief_id == "test-1"
    assert result.topic_statement == "Test Topic"
    # Optional columns should have defaults
    assert result.content_type == "original"
    assert result.adaptation_source_video_id is None

    conn.close()


def test_row_to_brief_handles_all_columns():
    """Verify _row_to_brief works when all columns are present."""
    from packages.content_factory.topic_finder.db import TopicReservoirDB

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE topic_reservoir (
            brief_id TEXT PRIMARY KEY,
            topic_statement TEXT,
            big_question TEXT,
            genre_id TEXT,
            gap_type TEXT,
            score_breakdown TEXT,
            anchor_candidates TEXT,
            mainstream_assumption TEXT,
            urgency_flag INTEGER,
            timing_rationale TEXT,
            created_at TEXT,
            status TEXT,
            content_type TEXT,
            adaptation_source_video_id TEXT,
            structural_reference_video_id TEXT
        )
    """)

    cursor.execute("""
        INSERT INTO topic_reservoir VALUES (
            'test-2', 'Test Topic 2', 'Test Question?', 'explainer',
            'Hidden Connection', '{"total": 15}', '[]', 'Test assumption', 1,
            'Test rationale', '2024-01-01T00:00:00', 'reservoir',
            'adaptation', 'vid-123', 'vid-456'
        )
    """)
    conn.commit()

    cursor.execute("SELECT * FROM topic_reservoir WHERE brief_id = 'test-2'")
    row = cursor.fetchone()

    db = TopicReservoirDB.__new__(TopicReservoirDB)
    result = db._row_to_brief(row)

    assert result.content_type == "adaptation"
    assert result.adaptation_source_video_id == "vid-123"
    assert result.structural_reference_video_id == "vid-456"

    conn.close()
