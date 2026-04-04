"""Tests for packages.content_factory.music.arc_designer — EmotionalArcDesigner."""

import pytest

from packages.content_factory.models import (
    AdaptedScript,
    DualColumnEntry,
    SectionLabel,
)
from packages.content_factory.music.reader import ShameDraftData
from packages.content_factory.music.arc_designer import EmotionalArcDesigner
from packages.content_factory.music.models import EmotionalArcMap, RankedPeak, SilenceMoment, SonicPaletteFlag


# ── Helpers ────────────────────────────────────────────────────────────────────

def _entry(
    prose: str = "Some text here for the section.",
    visual_direction: str = "Show chart.",
    section_label: SectionLabel = SectionLabel.BRIDGE,
) -> DualColumnEntry:
    return DualColumnEntry(
        prose=prose,
        visual_direction=visual_direction,
        section_label=section_label,
    )


def _script(entries, genre="comparison_and_contrast") -> AdaptedScript:
    return AdaptedScript(video_id="vid", genre=genre, entries=entries)


def _draft(entries, genre="comparison_and_contrast") -> ShameDraftData:
    return ShameDraftData(_script(entries, genre=genre))


# ── Basic structure ────────────────────────────────────────────────────────────

class TestDesignArcReturns:
    def test_returns_emotional_arc_map(self):
        draft = _draft([_entry(section_label=SectionLabel.HOOK)])
        result = EmotionalArcDesigner().design_arc(draft)
        assert isinstance(result, EmotionalArcMap)

    def test_arc_summary_contains_section_count(self):
        draft = _draft([_entry(), _entry(), _entry()])
        result = EmotionalArcDesigner().design_arc(draft)
        assert "3 sections" in result.arc_summary


# ── Energy trajectory ──────────────────────────────────────────────────────────

class TestEnergyTrajectory:
    def test_pre_big_question_sections_energy_one(self):
        """Sections up to and including big_question_idx get energy=1."""
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question about life"),
            _entry(section_label=SectionLabel.ANCHOR),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        # big_question_idx=0, so section 0 gets energy=1 (and continue skips)
        # section 1 is ANCHOR, energy = min(1+1,4) = 2
        assert result.energy_trajectory[0] == 1

    def test_anchor_increases_energy(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question here"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.ANCHOR),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        assert result.energy_trajectory[1] == 2
        assert result.energy_trajectory[2] == 3
        assert result.energy_trajectory[3] == 4

    def test_anchor_energy_capped_at_4(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.ANCHOR),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        # After 4 increments, stays at 4
        assert result.energy_trajectory[5] == 4

    def test_bridge_decreases_energy(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.BRIDGE),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        # energy before bridge: 3 (section 2), bridge drops by 1, min 2 → 2
        assert result.energy_trajectory[3] == 2

    def test_bridge_energy_floor_at_2(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.BRIDGE),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        # energy before bridge: 2, max(2-1, 2) = 2
        assert result.energy_trajectory[2] == 2

    def test_reveal_energy_is_5(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.REVEAL),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        assert result.energy_trajectory[1] == 5

    def test_conclusion_energy_is_2(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.CONCLUSION),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        assert result.energy_trajectory[1] == 2


# ── Peaks ─────────────────────────────────────────────────────────────────────

class TestPeaks:
    def test_anchor_with_human_moment_creates_peak(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR, visual_direction="a human walking"),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        assert len(result.peak_inventory) == 1
        assert result.peak_inventory[0].section_index == 1
        assert result.peak_inventory[0].intensity == 2

    def test_anchor_without_human_moment_no_peak(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR, visual_direction="chart overlay"),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        anchor_peaks = [p for p in result.peak_inventory if p.label != "REVEAL" and p.label != "CONCLUSION"]
        assert len(anchor_peaks) == 0

    def test_reveal_creates_peak(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.REVEAL),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        reveal_peaks = [p for p in result.peak_inventory if p.label == "REVEAL"]
        assert len(reveal_peaks) == 1
        assert reveal_peaks[0].intensity == 5

    def test_conclusion_creates_peak(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.CONCLUSION),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        conclusion_peaks = [p for p in result.peak_inventory if p.label == "CONCLUSION"]
        assert len(conclusion_peaks) == 1
        assert conclusion_peaks[0].intensity == 2


# ── Silences ──────────────────────────────────────────────────────────────────

class TestSilences:
    def test_silence_inserted_before_reveal(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.REVEAL),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        assert len(result.silence_locations) == 1
        silence = result.silence_locations[0]
        assert silence.section_index == 2
        assert silence.duration_seconds == 5
        assert "silence" in silence.reason.lower()

    def test_no_silence_without_reveal(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.CONCLUSION),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        assert len(result.silence_locations) == 0

    def test_silence_timestamp_estimate(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.REVEAL),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        silence = result.silence_locations[0]
        # reveal at index 1 → timestamp_estimate = 1*60 - 5 = 55
        assert silence.timestamp_estimate == 55


# ── Sonic Palette Flags ───────────────────────────────────────────────────────

class TestSonicPaletteFlags:
    def test_islamic_history_full_video_flag(self):
        draft = _draft(
            [_entry(section_label=SectionLabel.HOOK, prose="big question")],
            genre="islamic_history",
        )
        result = EmotionalArcDesigner().design_arc(draft)
        assert len(result.pakistani_sonic_palette_flags) == 1
        flag = result.pakistani_sonic_palette_flags[0]
        assert flag.section_index == -1  # Full video
        assert "Oud" in flag.instrumentation_direction

    def test_south_asian_history_full_video_flag(self):
        draft = _draft(
            [_entry(section_label=SectionLabel.HOOK, prose="big question")],
            genre="south_asian_history",
        )
        result = EmotionalArcDesigner().design_arc(draft)
        flag = result.pakistani_sonic_palette_flags[0]
        assert flag.section_index == -1

    def test_non_special_genre_flags_last_section(self):
        entries = [
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.CONCLUSION),
        ]
        draft = _draft(entries, genre="comparison_and_contrast")
        result = EmotionalArcDesigner().design_arc(draft)
        flag = result.pakistani_sonic_palette_flags[0]
        assert flag.section_index == 2  # Last section
        assert "sitar" in flag.instrumentation_direction.lower()

    def test_special_genre_avoid_list(self):
        draft = _draft(
            [_entry(section_label=SectionLabel.HOOK, prose="big question")],
            genre="islamic_history",
        )
        result = EmotionalArcDesigner().design_arc(draft)
        flag = result.pakistani_sonic_palette_flags[0]
        assert "Western Orchestral Swells" in flag.avoid_list


# ── Recovery Moments ─────────────────────────────────────────────────────────

class TestRecoveryMoments:
    def test_long_bridge_adds_recovery_moment(self):
        # 200 words / 2.5 = 80 seconds > 60 threshold
        long_prose = " ".join(["word"] * 200) + "."
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.BRIDGE, prose=long_prose),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        assert 1 in result.recovery_moments

    def test_short_bridge_no_recovery_moment(self):
        draft = _draft([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.BRIDGE, prose="Short text."),
        ])
        result = EmotionalArcDesigner().design_arc(draft)
        assert 1 not in result.recovery_moments
