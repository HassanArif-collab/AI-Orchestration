"""Tests for packages/content_factory/models.py — Content factory Pydantic models."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError


class TestEnums:
    """Tests for model enums."""

    def test_section_label_values(self):
        from packages.content_factory.models import SectionLabel
        assert SectionLabel.HOOK.value == "HOOK"
        assert SectionLabel.ANCHOR.value == "ANCHOR"
        assert SectionLabel.BRIDGE.value == "BRIDGE"
        assert SectionLabel.REVEAL.value == "REVEAL"
        assert SectionLabel.CONCLUSION.value == "CONCLUSION"
        assert SectionLabel.TRANSITION.value == "TRANSITION"

    def test_processing_status_values(self):
        from packages.content_factory.models import ProcessingStatus
        assert ProcessingStatus.EXTRACTED_ONLY.value == "extracted_only"
        assert ProcessingStatus.FULLY_ANALYZED.value == "fully_analyzed"
        assert ProcessingStatus.ADAPTED.value == "adapted"
        assert ProcessingStatus.ADAPTATION_REVIEWED.value == "adaptation_reviewed"

    def test_confidence_level_values(self):
        from packages.content_factory.models import ConfidenceLevel
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"

    def test_visual_type_values(self):
        from packages.content_factory.models import VisualType
        expected = {"talking_head", "broll", "animation", "archive", "data_viz", "soul_moment"}
        assert {v.value for v in VisualType} == expected


class TestTranscriptSegment:
    """Tests for TranscriptSegment."""

    def test_creation(self):
        from packages.content_factory.models import TranscriptSegment
        seg = TranscriptSegment(text="Hello world", start=0.0, duration=2.5)
        assert seg.text == "Hello world"
        assert seg.start == 0.0
        assert seg.duration == 2.5


class TestChapterMarker:
    """Tests for ChapterMarker."""

    def test_creation(self):
        from packages.content_factory.models import ChapterMarker
        marker = ChapterMarker(title="Introduction", start_seconds=0.0)
        assert marker.title == "Introduction"


class TestRawExtraction:
    """Tests for RawExtraction model."""

    def test_minimal_creation(self):
        from packages.content_factory.models import RawExtraction
        ext = RawExtraction(video_id="abc123", url="https://youtube.com/watch?v=abc123", title="Test Video")
        assert ext.video_id == "abc123"
        assert ext.views == 0
        assert ext.transcript_segments == []
        assert ext.caption_type == "unknown"

    def test_full_creation(self):
        from packages.content_factory.models import RawExtraction, TranscriptSegment
        ext = RawExtraction(
            video_id="abc123",
            url="https://youtube.com/watch?v=abc123",
            title="Test Video",
            views=10000,
            tags=["tag1", "tag2"],
            transcript_segments=[TranscriptSegment(text="Hi", start=0.0, duration=1.0)],
            caption_type="manual",
        )
        assert ext.views == 10000
        assert len(ext.tags) == 2
        assert len(ext.transcript_segments) == 1

    def test_full_transcript_property(self):
        from packages.content_factory.models import RawExtraction, TranscriptSegment
        ext = RawExtraction(
            video_id="abc",
            url="https://youtube.com",
            title="Test",
            transcript_segments=[
                TranscriptSegment(text="Hello", start=0, duration=1),
                TranscriptSegment(text="World", start=1, duration=1),
            ],
        )
        assert ext.full_transcript == "Hello World"

    def test_full_transcript_empty(self):
        from packages.content_factory.models import RawExtraction
        ext = RawExtraction(video_id="abc", url="https://youtube.com", title="Test")
        assert ext.full_transcript == ""


class TestStructuralSection:
    """Tests for StructuralSection."""

    def test_creation(self):
        from packages.content_factory.models import StructuralSection, SectionLabel
        section = StructuralSection(
            label=SectionLabel.HOOK,
            start_seconds=0.0,
            end_seconds=10.0,
            duration_seconds=10.0,
        )
        assert section.label == SectionLabel.HOOK


class TestStructuralMap:
    """Tests for StructuralMap model."""

    def test_defaults(self):
        from packages.content_factory.models import StructuralMap, StructuralMetrics
        smap = StructuralMap(video_id="abc")
        assert smap.sections == []
        assert smap.big_question == ""
        assert isinstance(smap.metrics, StructuralMetrics)
        assert smap.structural_integrity_score == 0

    def test_integrity_score_bounds(self):
        from packages.content_factory.models import StructuralMap
        smap = StructuralMap(video_id="abc", structural_integrity_score=7)
        assert smap.structural_integrity_score == 7
        with pytest.raises(ValidationError):
            StructuralMap(video_id="abc", structural_integrity_score=8)


class TestMonetarySubstitution:
    """Tests for MonetarySubstitution."""

    def test_creation(self):
        from packages.content_factory.models import MonetarySubstitution, ConfidenceLevel
        sub = MonetarySubstitution(
            original_figure="$100,000",
            original_context="US middle class",
            pakistani_figure="PKR 15,000,000",
            pakistani_context="Pakistani middle class",
            confidence=ConfidenceLevel.HIGH,
        )
        assert sub.original_figure == "$100,000"
        assert sub.confidence == ConfidenceLevel.HIGH


class TestLocalizationMap:
    """Tests for LocalizationMap model."""

    def test_creation(self):
        from packages.content_factory.models import LocalizationMap, MonetarySubstitution
        lmap = LocalizationMap(
            video_id="abc",
            monetary=[MonetarySubstitution(
                original_figure="$50k",
                original_context="US",
                pakistani_figure="PKR 7.5M",
                pakistani_context="PK",
            )],
        )
        assert len(lmap.monetary) == 1
        assert lmap.video_id == "abc"


class TestDualColumnEntry:
    """Tests for DualColumnEntry model."""

    def test_creation(self):
        from packages.content_factory.models import DualColumnEntry, VisualType, SectionLabel
        entry = DualColumnEntry(
            prose="The real question is...",
            visual_direction="Talking head close-up",
            visual_type=VisualType.TALKING_HEAD,
            section_label=SectionLabel.HOOK,
        )
        assert entry.prose == "The real question is..."
        assert entry.low_confidence_flag is False

    def test_anchor_hierarchy_validation(self):
        from packages.content_factory.models import DualColumnEntry
        # Valid hierarchy levels: ge=1, le=5
        for level in [1, 2, 3, 4, 5]:
            entry = DualColumnEntry(prose="test", visual_direction="test", anchor_hierarchy_level=level)
            assert entry.anchor_hierarchy_level == level

        # Invalid (0) — outside ge=1
        with pytest.raises(ValidationError):
            DualColumnEntry(prose="test", visual_direction="test", anchor_hierarchy_level=0)

        # Invalid (6) — outside le=5
        with pytest.raises(ValidationError):
            DualColumnEntry(prose="test", visual_direction="test", anchor_hierarchy_level=6)

    def test_none_hierarchy_is_valid(self):
        from packages.content_factory.models import DualColumnEntry
        entry = DualColumnEntry(prose="test", visual_direction="test", anchor_hierarchy_level=None)
        assert entry.anchor_hierarchy_level is None


class TestAdaptedScript:
    """Tests for AdaptedScript model."""

    def test_defaults(self):
        from packages.content_factory.models import AdaptedScript
        script = AdaptedScript(video_id="abc")
        assert script.entries == []
        assert script.production_readiness_score == 0.0
        assert script.persistent_failures == []

    def test_score_bounds(self):
        from packages.content_factory.models import AdaptedScript
        script = AdaptedScript(video_id="abc", production_readiness_score=100.0)
        assert script.production_readiness_score == 100.0
        with pytest.raises(ValidationError):
            AdaptedScript(video_id="abc", production_readiness_score=101.0)


class TestSourceVideoRecord:
    """Tests for SourceVideoRecord model."""

    def test_creation(self):
        from packages.content_factory.models import SourceVideoRecord, ProcessingStatus
        record = SourceVideoRecord(
            video_id="abc123",
            url="https://youtube.com/watch?v=abc123",
            title="Test Video",
            processing_status=ProcessingStatus.FULLY_ANALYZED,
        )
        assert record.video_id == "abc123"
        assert record.processing_status == ProcessingStatus.FULLY_ANALYZED


class TestAdaptationStage:
    """Tests for AdaptationStage IntEnum."""

    def test_values(self):
        from packages.content_factory.models import AdaptationStage
        assert AdaptationStage.STRUCTURAL_ANALYSIS == 1
        assert AdaptationStage.SCRIPT_GENERATION == 3
        assert AdaptationStage.PRODUCTION == 5
        assert AdaptationStage.FINAL_REVIEW == 6

    def test_from_int_valid(self):
        from packages.content_factory.models import AdaptationStage
        assert AdaptationStage.from_int(1) == AdaptationStage.STRUCTURAL_ANALYSIS
        assert AdaptationStage.from_int(6) == AdaptationStage.FINAL_REVIEW

    def test_from_int_invalid(self):
        from packages.content_factory.models import AdaptationStage
        with pytest.raises(ValueError, match="Invalid adaptation stage"):
            AdaptationStage.from_int(99)
        with pytest.raises(ValueError, match="Invalid adaptation stage"):
            AdaptationStage.from_int(0)


class TestAdaptationError:
    """Tests for AdaptationError model."""

    def test_creation(self):
        from packages.content_factory.models import AdaptationError, AdaptationStage
        err = AdaptationError(
            production_cycle_id="cycle-1",
            stage_number=AdaptationStage.LOCALIZATION,
            error_type="missing_anchor",
            description="No anchor substitution found",
        )
        assert err.error_type == "missing_anchor"
        assert err.pipeline_stopped is False
        assert err.severity == "error"

    def test_stage_number_accepts_int(self):
        from packages.content_factory.models import AdaptationError, AdaptationStage
        # IntEnum should accept both the enum and int
        err = AdaptationError(production_cycle_id="x", error_type="test", description="desc", stage_number=1)
        assert err.stage_number == 1
