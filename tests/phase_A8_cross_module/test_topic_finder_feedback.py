"""Tests for packages/content_factory/topic_finder/feedback.py — Feedback loop."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from pathlib import Path


def _make_settings():
    """Create mock settings for FeedbackLoop."""
    s = MagicMock()
    s.ZEP_AUDIENCE_USER_ID = "audience_user"
    return s


class TestFeedbackLoopInit:
    """Tests for FeedbackLoop initialization."""

    def test_creates_default_model_when_no_file(self):
        from packages.content_factory.topic_finder.feedback import FeedbackLoop
        with patch("packages.content_factory.topic_finder.feedback.get_settings", return_value=_make_settings()):
            with patch("packages.content_factory.topic_finder.feedback.AUDIENCE_MODEL_PATH") as mock_path:
                mock_path.parent.exists.return_value = True
                mock_path.exists.return_value = False
                loop = FeedbackLoop()
                assert loop.model.topic_resonance_map is not None
                assert loop.model.topic_resonance_map["Economy"] == 1.0


class TestRecalibrateFromPerformance:
    """Tests for recalibrate_from_performance()."""

    @pytest.fixture()
    def feedback_loop(self):
        with patch("packages.content_factory.topic_finder.feedback.get_settings", return_value=_make_settings()):
            with patch("packages.content_factory.topic_finder.feedback.AsyncZepMemoryClient"):
                with patch("packages.content_factory.topic_finder.feedback.AUDIENCE_MODEL_PATH") as mock_path:
                    mock_path.parent.exists.return_value = True
                    mock_path.exists.return_value = False
                    from packages.content_factory.topic_finder.feedback import FeedbackLoop
                    loop = FeedbackLoop()
                    loop._pending_facts = []
                    return loop

    def test_updates_genre_rankings(self, feedback_loop):
        feedback_loop.recalibrate_from_performance({
            "genre_id": "tech",
            "topic_statement": "AI in Pakistan",
            "topic_resonance_score": 0.85,
            "video_id": "vid123",
            "publication_date": datetime.now(timezone.utc),
        })
        assert "tech" in feedback_loop.model.genre_engagement_rankings
        expected = (1.0 + 0.85) / 2.0
        assert abs(feedback_loop.model.genre_engagement_rankings["tech"] - expected) < 0.001

    def test_updates_topic_resonance(self, feedback_loop):
        feedback_loop.recalibrate_from_performance({
            "genre_id": "tech",
            "topic_statement": "AI in Pakistan",
            "topic_resonance_score": 0.85,
            "video_id": "vid123",
            "publication_date": datetime.now(timezone.utc),
        })
        assert feedback_loop.model.topic_resonance_map["AI in Pakistan"] == 0.85

    def test_bridge_drop_off_detection(self, feedback_loop):
        feedback_loop.recalibrate_from_performance({
            "genre_id": "tech",
            "topic_statement": "Test",
            "topic_resonance_score": 0.8,
            "anchor_bridge_correlation": {"anchor": 85.0, "bridge": 40.0},
            "video_id": "vid123",
            "publication_date": datetime.now(timezone.utc),
        })
        assert "High drop-off" in feedback_loop.model.attention_patterns["Bridge Sections"]

    def test_bridge_stable_retention(self, feedback_loop):
        feedback_loop.recalibrate_from_performance({
            "genre_id": "tech",
            "topic_statement": "Test",
            "topic_resonance_score": 0.8,
            "anchor_bridge_correlation": {"anchor": 85.0, "bridge": 70.0},
            "video_id": "vid123",
            "publication_date": datetime.now(timezone.utc),
        })
        assert "Stable retention" in feedback_loop.model.attention_patterns["Bridge Sections"]

    def test_handles_string_publication_date(self, feedback_loop):
        feedback_loop.recalibrate_from_performance({
            "genre_id": "tech",
            "topic_statement": "Test",
            "topic_resonance_score": 0.8,
            "video_id": "vid123",
            "publication_date": "2024-06-15T00:00:00Z",
        })
        assert "tech" in feedback_loop.model.genre_engagement_rankings

    def test_no_genre_no_update(self, feedback_loop):
        initial_rankings = dict(feedback_loop.model.genre_engagement_rankings)
        feedback_loop.recalibrate_from_performance({
            "genre_id": None,
            "topic_statement": "Test",
            "topic_resonance_score": 0.8,
            "video_id": "vid123",
        })
        assert feedback_loop.model.genre_engagement_rankings == initial_rankings


class TestFlushPendingFacts:
    """Tests for flush_pending_facts()."""

    @pytest.mark.asyncio
    async def test_flush_empty(self):
        with patch("packages.content_factory.topic_finder.feedback.get_settings", return_value=_make_settings()):
            with patch("packages.content_factory.topic_finder.feedback.AsyncZepMemoryClient"):
                with patch("packages.content_factory.topic_finder.feedback.AUDIENCE_MODEL_PATH") as mp:
                    mp.parent.exists.return_value = True
                    mp.exists.return_value = False
                    from packages.content_factory.topic_finder.feedback import FeedbackLoop
                    loop = FeedbackLoop()
                    await loop.flush_pending_facts()  # Should be no-op

    @pytest.mark.asyncio
    async def test_flush_with_pending(self):
        with patch("packages.content_factory.topic_finder.feedback.get_settings", return_value=_make_settings()):
            mock_client = MagicMock()
            mock_client.add_facts = AsyncMock()
            with patch("packages.content_factory.topic_finder.feedback.AsyncZepMemoryClient", return_value=mock_client):
                with patch("packages.content_factory.topic_finder.feedback.AUDIENCE_MODEL_PATH") as mp:
                    mp.parent.exists.return_value = True
                    mp.exists.return_value = False
                    from packages.content_factory.topic_finder.feedback import FeedbackLoop
                    loop = FeedbackLoop()
                    loop._pending_facts = [{"fact": "test fact"}]
                    await loop.flush_pending_facts()
                    mock_client.add_facts.assert_called_once()
                    assert loop._pending_facts == []
