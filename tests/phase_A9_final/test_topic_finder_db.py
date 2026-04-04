"""Tests for packages.content_factory.topic_finder.db — TopicReservoirDB and PerformanceDB."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from packages.content_factory.topic_finder.models import TopicBrief, VideoPerformanceProfile


# ── Helpers ──

def _make_brief(**overrides):
    """Create a TopicBrief with sensible defaults."""
    defaults = {
        "topic_statement": "Why Pakistan's water crisis is hidden",
        "big_question": "What is the real cause?",
        "genre_id": "tech",
        "gap_type": "Hidden Mechanism",
        "viability_score_breakdown": {"gap_1": True, "gap_2": True, "gap_3": True},
        "anchor_candidates": ["Karachi"],
        "mainstream_assumption": "Climate change only",
        "urgency_flag": True,
        "timing_rationale": "Monsoon season",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "status": "reservoir",
    }
    defaults.update(overrides)
    return TopicBrief(**defaults)


def _make_mock_table():
    """Create a mock supabase table with chainable API."""
    table = MagicMock()
    table.upsert.return_value = table
    table.insert.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(data=[])
    return table


# ══════════════════════════════════════════════════════════════
# TopicReservoirDB
# ══════════════════════════════════════════════════════════════

class TestTopicReservoirDBSave:

    @patch("packages.content_factory.topic_finder.db.TopicReservoirDB._db")
    def test_save_topic_upserts_with_all_fields(self, mock_db):
        brief = _make_brief()
        table = _make_mock_table()
        mock_db.return_value = table

        from packages.content_factory.topic_finder.db import TopicReservoirDB
        db = TopicReservoirDB()
        db.save_topic(brief)

        table.upsert.assert_called_once()
        call_args = table.upsert.call_args
        data = call_args[0][0]
        assert data["brief_id"] == brief.brief_id
        assert data["topic_statement"] == brief.topic_statement
        assert data["status"] == "reservoir"
        assert data["urgency_flag"] is True
        assert call_args[1]["on_conflict"] == "brief_id"

    @patch("packages.content_factory.topic_finder.db.TopicReservoirDB._db")
    def test_save_topic_with_structural_reference(self, mock_db):
        from packages.content_factory.models import SourceVideoRecord

        ref = SourceVideoRecord(
            video_id="sv_001",
            url="https://youtube.com/watch?v=sv_001",
            title="Original video",
            published_at="2024-01-01T00:00:00Z",
        )
        brief = _make_brief(structural_reference=ref, structural_reference_video_id="sv_001")
        table = _make_mock_table()
        mock_db.return_value = table

        from packages.content_factory.topic_finder.db import TopicReservoirDB
        db = TopicReservoirDB()
        db.save_topic(brief)

        call_args = table.upsert.call_args
        data = call_args[0][0]
        assert data["structural_reference_id"] == "sv_001"
        assert data["structural_reference_video_id"] == "sv_001"

    @patch("packages.content_factory.topic_finder.db.TopicReservoirDB._db")
    def test_save_topic_handles_duplicate_key_gracefully(self, mock_db):
        brief = _make_brief()
        table = _make_mock_table()
        table.execute.side_effect = Exception("duplicate key violation")
        mock_db.return_value = table

        from packages.content_factory.topic_finder.db import TopicReservoirDB
        db = TopicReservoirDB()
        # Should not raise
        db.save_topic(brief)

    @patch("packages.content_factory.topic_finder.db.TopicReservoirDB._db")
    def test_save_topic_reraises_non_duplicate_error(self, mock_db):
        brief = _make_brief()
        table = _make_mock_table()
        table.execute.side_effect = Exception("connection timeout")
        mock_db.return_value = table

        from packages.content_factory.topic_finder.db import TopicReservoirDB
        db = TopicReservoirDB()
        with pytest.raises(Exception, match="connection timeout"):
            db.save_topic(brief)


class TestTopicReservoirDBGetTop:

    @patch("packages.content_factory.topic_finder.db.TopicReservoirDB._db")
    def test_get_top_topics_returns_briefs(self, mock_db):
        table = _make_mock_table()
        row = {
            "brief_id": "brief_001",
            "topic_statement": "Test topic",
            "big_question": "Why?",
            "genre_id": "tech",
            "gap_type": "Hidden Mechanism",
            "viability_score_breakdown": {"gap_1": True},
            "anchor_candidates": ["anchor1"],
            "mainstream_assumption": "assumption",
            "urgency_flag": True,
            "timing_rationale": "now",
            "created_at": "2025-01-01T00:00:00+00:00",
            "status": "reservoir",
            "content_type": "original",
            "adaptation_source_video_id": None,
            "structural_reference_video_id": None,
        }
        table.execute.return_value = MagicMock(data=[row])
        mock_db.return_value = table

        from packages.content_factory.topic_finder.db import TopicReservoirDB
        db = TopicReservoirDB()
        results = db.get_top_topics(limit=5)

        assert len(results) == 1
        assert results[0].topic_statement == "Test topic"
        assert results[0].urgency_flag is True

    @patch("packages.content_factory.topic_finder.db.TopicReservoirDB._db")
    def test_get_top_topics_empty_result(self, mock_db):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=[])
        mock_db.return_value = table

        from packages.content_factory.topic_finder.db import TopicReservoirDB
        db = TopicReservoirDB()
        results = db.get_top_topics()

        assert results == []

    @patch("packages.content_factory.topic_finder.db.TopicReservoirDB._db")
    def test_get_top_topics_uses_correct_query(self, mock_db):
        table = _make_mock_table()
        table.execute.return_value = MagicMock(data=None)
        mock_db.return_value = table

        from packages.content_factory.topic_finder.db import TopicReservoirDB
        db = TopicReservoirDB()
        db.get_top_topics(limit=3)

        table.select.assert_called_once_with("*")
        table.eq.assert_called_once_with("status", "reservoir")
        table.order.assert_any_call("urgency_flag", desc=True)
        table.order.assert_any_call("created_at", desc=True)
        table.limit.assert_called_once_with(3)


class TestTopicReservoirDBRowToBrief:

    def test_row_to_brief_full(self):
        row = {
            "brief_id": "b1",
            "topic_statement": "Topic",
            "big_question": "Q?",
            "genre_id": "tech",
            "gap_type": "Hidden Mechanism",
            "viability_score_breakdown": {"gap_1": True, "gap_2": False},
            "anchor_candidates": ["a1", "a2"],
            "mainstream_assumption": "assumption",
            "urgency_flag": False,
            "timing_rationale": "rationale",
            "created_at": "2025-06-15T12:00:00+00:00",
            "status": "reservoir",
            "content_type": "adaptation",
            "adaptation_source_video_id": "sv_001",
            "structural_reference_video_id": "sv_002",
        }

        from packages.content_factory.topic_finder.db import TopicReservoirDB
        db = TopicReservoirDB()
        brief = db._row_to_brief(row)

        assert brief.brief_id == "b1"
        assert brief.topic_statement == "Topic"
        assert brief.viability_score_breakdown == {"gap_1": True, "gap_2": False}
        assert brief.anchor_candidates == ["a1", "a2"]
        assert brief.urgency_flag is False
        assert brief.content_type == "adaptation"
        assert brief.adaptation_source_video_id == "sv_001"

    def test_row_to_brief_none_fields_default(self):
        row = {
            "brief_id": "b2",
            "topic_statement": "Topic2",
            "big_question": "Q2",
            "genre_id": "food",
            "gap_type": "Hidden Connection",
            "viability_score_breakdown": None,
            "anchor_candidates": None,
            "mainstream_assumption": "assumption",
            "urgency_flag": None,
            "timing_rationale": "rationale",
            "created_at": "2025-06-15T12:00:00+00:00",
            "status": "reservoir",  # DB default, always a valid literal
            "content_type": None,
            "adaptation_source_video_id": None,
            "structural_reference_video_id": None,
        }

        from packages.content_factory.topic_finder.db import TopicReservoirDB
        db = TopicReservoirDB()
        brief = db._row_to_brief(row)

        assert brief.viability_score_breakdown == {}
        assert brief.anchor_candidates == []
        assert brief.urgency_flag is False
        assert brief.status == "reservoir"
        assert brief.content_type == "original"


# ══════════════════════════════════════════════════════════════
# PerformanceDB
# ══════════════════════════════════════════════════════════════

class TestPerformanceDB:

    @patch("packages.content_factory.topic_finder.db.PerformanceDB._db")
    def test_save_performance_upserts(self, mock_db):
        table = _make_mock_table()
        mock_db.return_value = table

        profile = VideoPerformanceProfile(
            video_id="vid_001",
            publication_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            genre_id="tech",
            topic_statement="Water crisis",
            viability_score_at_selection=78.5,
            engagement_24h=1000.0,
            engagement_7d=5000.0,
        )

        from packages.content_factory.topic_finder.db import PerformanceDB
        db = PerformanceDB()
        db.save_performance(profile)

        table.upsert.assert_called_once()
        call_args = table.upsert.call_args
        data = call_args[0][0]
        assert data["video_id"] == "vid_001"
        assert data["engagement_24h"] == 1000.0
        assert data["viability_score_at_selection"] == 78.5
        assert call_args[1]["on_conflict"] == "video_id"

    @patch("packages.content_factory.topic_finder.db.PerformanceDB._db")
    def test_save_performance_with_optional_fields(self, mock_db):
        table = _make_mock_table()
        mock_db.return_value = table

        profile = VideoPerformanceProfile(
            video_id="vid_002",
            publication_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            genre_id="food",
            topic_statement="Cuisine history",
            viability_score_at_selection=82.0,
            retention_curve_shape="Harris-Pattern",
            anchor_bridge_correlation={"anchor": 85.0, "bridge": 70.0},
            topic_resonance_score=91.2,
        )

        from packages.content_factory.topic_finder.db import PerformanceDB
        db = PerformanceDB()
        db.save_performance(profile)

        call_args = table.upsert.call_args
        data = call_args[0][0]
        assert data["retention_curve_shape"] == "Harris-Pattern"
        assert data["anchor_bridge_correlation"] == {"anchor": 85.0, "bridge": 70.0}
        assert data["topic_resonance_score"] == 91.2
