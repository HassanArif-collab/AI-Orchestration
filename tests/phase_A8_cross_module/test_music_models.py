"""Tests for packages/content_factory/music/models.py — Music agent models."""

import pytest
from pydantic import ValidationError


class TestRankedPeak:
    """Tests for RankedPeak model."""

    def test_creation(self):
        from packages.content_factory.music.models import RankedPeak
        peak = RankedPeak(section_index=0, label="HOOK", intensity=5, timestamp_estimate=0)
        assert peak.intensity == 5
        assert peak.label == "HOOK"

    def test_intensity_bounds(self):
        from packages.content_factory.music.models import RankedPeak
        peak = RankedPeak(section_index=0, label="X", intensity=1, timestamp_estimate=0)
        assert peak.intensity == 1
        peak2 = RankedPeak(section_index=0, label="X", intensity=5, timestamp_estimate=0)
        assert peak2.intensity == 5


class TestSilenceMoment:
    """Tests for SilenceMoment model."""

    def test_creation(self):
        from packages.content_factory.music.models import SilenceMoment
        moment = SilenceMoment(section_index=3, timestamp_estimate=120, reason="Emotional pause")
        assert moment.duration_seconds == 4  # default
        assert moment.reason == "Emotional pause"

    def test_custom_duration(self):
        from packages.content_factory.music.models import SilenceMoment
        moment = SilenceMoment(section_index=1, timestamp_estimate=30, duration_seconds=8, reason="Big reveal")
        assert moment.duration_seconds == 8


class TestSonicPaletteFlag:
    """Tests for SonicPaletteFlag model."""

    def test_creation(self):
        from packages.content_factory.music.models import SonicPaletteFlag
        flag = SonicPaletteFlag(
            section_index=0,
            reason="Cultural resonance needed",
            instrumentation_direction="Use sitar",
            avoid_list=["electric guitar", "drum machine"],
        )
        assert flag.section_index == 0
        assert len(flag.avoid_list) == 2

    def test_default_avoid_list(self):
        from packages.content_factory.music.models import SonicPaletteFlag
        flag = SonicPaletteFlag(section_index=0, reason="test", instrumentation_direction="piano")
        assert flag.avoid_list == []


class TestEmotionalArcMap:
    """Tests for EmotionalArcMap model."""

    def test_creation(self):
        from packages.content_factory.music.models import (
            EmotionalArcMap, RankedPeak, SilenceMoment, SonicPaletteFlag,
        )
        arc = EmotionalArcMap(
            arc_summary="Building tension",
            peak_inventory=[RankedPeak(section_index=2, label="REVEAL", intensity=5, timestamp_estimate=60)],
            energy_trajectory={0: 2, 1: 3, 2: 5, 3: 4, 4: 1},
            silence_locations=[SilenceMoment(section_index=3, timestamp_estimate=90, reason="Reflection")],
            pakistani_sonic_palette_flags=[],
            recovery_moments=[4],
        )
        assert arc.arc_summary == "Building tension"
        assert len(arc.peak_inventory) == 1
        assert arc.energy_trajectory[2] == 5
        assert arc.recovery_moments == [4]


class TestSectionMusicBrief:
    """Tests for SectionMusicBrief model."""

    def test_creation(self):
        from packages.content_factory.music.models import SectionMusicBrief
        brief = SectionMusicBrief(
            section_index=0,
            label="HOOK",
            state_assignment=1,
            energy_level="Medium",
            volume_level="Present",
        )
        assert brief.state_assignment == 1
        assert brief.sonic_palette is None

    def test_literal_constraints(self):
        from packages.content_factory.music.models import SectionMusicBrief
        # Valid state assignments
        for state in [1, 2, 3, 4]:
            brief = SectionMusicBrief(
                section_index=0, label="X", state_assignment=state,
                energy_level="Low", volume_level="Background",
            )
            assert brief.state_assignment == state

    def test_valid_energy_levels(self):
        from packages.content_factory.music.models import SectionMusicBrief
        for energy in ["Low", "Medium", "High"]:
            brief = SectionMusicBrief(
                section_index=0, label="X", state_assignment=2,
                energy_level=energy, volume_level="Background",
            )
            assert brief.energy_level == energy

    def test_valid_volume_levels(self):
        from packages.content_factory.music.models import SectionMusicBrief
        for vol in ["Background", "Present", "Surface", "Dominant"]:
            brief = SectionMusicBrief(
                section_index=0, label="X", state_assignment=2,
                energy_level="Medium", volume_level=vol,
            )
            assert brief.volume_level == vol


class TestTransitionSpec:
    """Tests for TransitionSpec model."""

    def test_creation(self):
        from packages.content_factory.music.models import TransitionSpec
        spec = TransitionSpec(
            from_section_index=0,
            to_section_index=1,
            transition_type="Gradual Thickening",
            start_cue="Anchor ends",
            end_cue="Bridge begins",
            duration_seconds=5,
            editor_note="Smooth transition",
        )
        assert spec.transition_type == "Gradual Thickening"
        assert spec.duration_seconds == 5
        assert spec.sonic_palette_overlap_notes is None

    def test_all_transition_types(self):
        from packages.content_factory.music.models import TransitionSpec
        types = [
            "Gradual Thickening", "Gradual Thinning", "Silence Drop",
            "Resolution Settle", "Anticipatory Hold", "Hard State Reset",
        ]
        for t in types:
            spec = TransitionSpec(
                from_section_index=0, to_section_index=1, transition_type=t,
                start_cue="x", end_cue="y", duration_seconds=3, editor_note="n",
            )
            assert spec.transition_type == t


class TestMusicArchitectureDocument:
    """Tests for MusicArchitectureDocument model."""

    def test_creation(self):
        from packages.content_factory.music.models import (
            MusicArchitectureDocument, SectionMusicBrief, TransitionSpec,
        )
        doc = MusicArchitectureDocument(
            video_id="abc",
            genre_id="tech",
            arc_summary="Test arc",
            silence_map=[],
            section_briefs=[],
            transitions=[],
        )
        assert doc.video_id == "abc"
        assert doc.music_architecture_integrity_score is None
        assert doc.failed_questions == []

    def test_with_score(self):
        from packages.content_factory.music.models import MusicArchitectureDocument
        doc = MusicArchitectureDocument(
            video_id="abc", genre_id="tech", arc_summary="arc",
            silence_map=[], section_briefs=[], transitions=[],
            music_architecture_integrity_score=85.5,
            failed_questions=["q1", "q2"],
        )
        assert doc.music_architecture_integrity_score == 85.5
        assert len(doc.failed_questions) == 2
