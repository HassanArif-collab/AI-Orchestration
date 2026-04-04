"""Tests for packages/content_factory/topic_finder/models.py — Topic finder models."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError


class TestTopicBrief:
    """Tests for TopicBrief model."""

    def test_minimal_creation(self):
        from packages.content_factory.topic_finder.models import TopicBrief
        brief = TopicBrief(
            topic_statement="AI in Pakistan",
            big_question="How is AI transforming Pakistan's economy?",
            genre_id="tech",
            gap_type="Hidden Mechanism",
            viability_score_breakdown={"total": 85},
            anchor_candidates=["Digital Pakistan"],
            mainstream_assumption="Pakistan is not investing in AI",
            timing_rationale="Current government push",
            created_at=datetime.now(timezone.utc),
        )
        assert brief.topic_statement == "AI in Pakistan"
        assert brief.status == "reservoir"
        assert brief.content_type == "original"
        assert brief.urgency_flag is False

    def test_adaptation_fields(self):
        from packages.content_factory.topic_finder.models import TopicBrief
        brief = TopicBrief(
            topic_statement="Test",
            big_question="Q?",
            genre_id="tech",
            gap_type="Hidden Mechanism",
            viability_score_breakdown={"total": 90},
            anchor_candidates=["A"],
            mainstream_assumption="Assumption",
            timing_rationale="Now",
            created_at=datetime.now(timezone.utc),
            content_type="adaptation",
            adaptation_source_video_id="sourceVid123",
            structural_reference_video_id="refVid456",
        )
        assert brief.content_type == "adaptation"
        assert brief.adaptation_source_video_id == "sourceVid123"
        assert brief.structural_reference_video_id == "refVid456"

    def test_gap_type_literal(self):
        from packages.content_factory.topic_finder.models import TopicBrief
        for gap in ["Hidden Mechanism", "Oversimplified Narrative", "Hidden Connection", "Universal in Local"]:
            brief = TopicBrief(
                topic_statement="Test", big_question="Q?", genre_id="tech",
                gap_type=gap, viability_score_breakdown={"total": 80},
                anchor_candidates=["A"], mainstream_assumption="X",
                timing_rationale="Y", created_at=datetime.now(timezone.utc),
            )
            assert brief.gap_type == gap

    def test_invalid_gap_type_raises(self):
        from packages.content_factory.topic_finder.models import TopicBrief
        with pytest.raises(ValidationError):
            TopicBrief(
                topic_statement="Test", big_question="Q?", genre_id="tech",
                gap_type="Invalid Gap", viability_score_breakdown={"total": 80},
                anchor_candidates=["A"], mainstream_assumption="X",
                timing_rationale="Y", created_at=datetime.now(timezone.utc),
            )

    def test_status_literal(self):
        from packages.content_factory.topic_finder.models import TopicBrief
        for status in ["reservoir", "in_production", "complete"]:
            brief = TopicBrief(
                topic_statement="T", big_question="Q?", genre_id="g",
                gap_type="Hidden Mechanism", viability_score_breakdown={},
                anchor_candidates=[], mainstream_assumption="X",
                timing_rationale="Y", created_at=datetime.now(timezone.utc),
                status=status,
            )
            assert brief.status == status

    def test_auto_generated_brief_id(self):
        from packages.content_factory.topic_finder.models import TopicBrief
        brief = TopicBrief(
            topic_statement="Test", big_question="Q?", genre_id="tech",
            gap_type="Hidden Mechanism", viability_score_breakdown={},
            anchor_candidates=[], mainstream_assumption="X",
            timing_rationale="Y", created_at=datetime.now(timezone.utc),
        )
        assert brief.brief_id is not None
        assert isinstance(brief.brief_id, str)


class TestVideoPerformanceProfile:
    """Tests for VideoPerformanceProfile model."""

    def test_minimal_creation(self):
        from packages.content_factory.topic_finder.models import VideoPerformanceProfile
        profile = VideoPerformanceProfile(
            video_id="vid123",
            publication_date=datetime.now(timezone.utc),
            genre_id="tech",
            topic_statement="AI in Pakistan",
            viability_score_at_selection=85.0,
        )
        assert profile.engagement_24h is None
        assert profile.topic_resonance_score is None

    def test_with_engagement_data(self):
        from packages.content_factory.topic_finder.models import VideoPerformanceProfile
        profile = VideoPerformanceProfile(
            video_id="vid123",
            publication_date=datetime.now(timezone.utc),
            genre_id="tech",
            topic_statement="AI in Pakistan",
            viability_score_at_selection=85.0,
            engagement_7d=72.5,
            engagement_30d=65.0,
            retention_curve_shape="Harris-Pattern",
            topic_resonance_score=0.85,
        )
        assert profile.retention_curve_shape == "Harris-Pattern"
        assert profile.topic_resonance_score == 0.85

    def test_retention_curve_shapes(self):
        from packages.content_factory.topic_finder.models import VideoPerformanceProfile
        shapes = ["Harris-Pattern", "Continuous Decline", "Early Exit", "Late Drop"]
        for shape in shapes:
            profile = VideoPerformanceProfile(
                video_id="v", publication_date=datetime.now(timezone.utc),
                genre_id="g", topic_statement="T", viability_score_at_selection=80.0,
                retention_curve_shape=shape,
            )
            assert profile.retention_curve_shape == shape


class TestAudienceModel:
    """Tests for AudienceModel model."""

    def test_creation(self):
        from packages.content_factory.topic_finder.models import AudienceModel
        model = AudienceModel(
            last_updated=datetime.now(timezone.utc),
        )
        assert model.knowledge_baseline == {}
        assert model.attention_patterns == {}
        assert model.topic_resonance_map == {}
        assert model.genre_engagement_rankings == {}

    def test_with_data(self):
        from packages.content_factory.topic_finder.models import AudienceModel
        model = AudienceModel(
            knowledge_baseline={"economy": "Growing IT sector"},
            attention_patterns={"hooks": "Short attention span"},
            topic_resonance_map={"tech": 0.85},
            genre_engagement_rankings={"tech": 0.9},
            last_updated=datetime.now(timezone.utc),
        )
        assert len(model.knowledge_baseline) == 1
        assert model.topic_resonance_map["tech"] == 0.85
