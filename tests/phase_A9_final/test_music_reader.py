"""Tests for packages.content_factory.music.reader — ShameDraftReader and ShameDraftData."""

import pytest
from unittest.mock import patch

from packages.content_factory.models import (
    AdaptedScript,
    DualColumnEntry,
    SectionLabel,
)
from packages.content_factory.music.reader import ShameDraftReader, ShameDraftData


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_entry(
    prose: str = "Some spoken text here.",
    visual_direction: str = "Show a chart on screen.",
    section_label: SectionLabel = SectionLabel.BRIDGE,
    type: str = "default",
) -> DualColumnEntry:
    """Create a DualColumnEntry with sensible defaults."""
    return DualColumnEntry(
        prose=prose,
        visual_direction=visual_direction,
        section_label=section_label,
    )


def _make_script(entries: list[DualColumnEntry], genre: str = "comparison_and_contrast") -> AdaptedScript:
    return AdaptedScript(video_id="test-vid", genre=genre, entries=entries)


# ── ShameDraftData: big_question_idx heuristics ───────────────────────────────

class TestBigQuestionIdx:
    """Heuristics for detecting the 'big question' section."""

    def test_detects_big_question_keyword(self):
        script = _make_script([
            _make_entry(prose="This is the hook section."),
            _make_entry(prose="Here is the big question we must address."),
            _make_entry(prose="And the answer is..."),
        ])
        data = ShameDraftData(script)
        assert data.big_question_idx == 1

    def test_detects_the_real_question_keyword(self):
        script = _make_script([
            _make_entry(prose="What is the real question here?"),
            _make_entry(prose="Let us explore further."),
        ])
        data = ShameDraftData(script)
        assert data.big_question_idx == 0

    def test_case_insensitive_big_question(self):
        script = _make_script([
            _make_entry(prose="Normal text."),
            _make_entry(prose="BIG QUESTION time."),
        ])
        data = ShameDraftData(script)
        assert data.big_question_idx == 1

    def test_fallback_to_zero_when_not_found(self):
        script = _make_script([
            _make_entry(prose="Just some text."),
            _make_entry(prose="More text here."),
        ])
        data = ShameDraftData(script)
        assert data.big_question_idx == 0

    def test_empty_script_fallback_to_zero(self):
        script = _make_script([])
        data = ShameDraftData(script)
        assert data.big_question_idx == 0


# ── ShameDraftData: reveal_idx heuristics ─────────────────────────────────────

class TestRevealIdx:
    """Heuristics for detecting the REVEAL section index."""

    def test_detects_reveal_section_label(self):
        script = _make_script([
            _make_entry(section_label=SectionLabel.HOOK),
            _make_entry(section_label=SectionLabel.ANCHOR),
            _make_entry(section_label=SectionLabel.REVEAL),
        ])
        data = ShameDraftData(script)
        assert data.reveal_idx == 2

    def test_fallback_to_last_anchor(self):
        script = _make_script([
            _make_entry(section_label=SectionLabel.HOOK),
            _make_entry(section_label=SectionLabel.ANCHOR),
            _make_entry(section_label=SectionLabel.BRIDGE),
            _make_entry(section_label=SectionLabel.ANCHOR),
            _make_entry(section_label=SectionLabel.CONCLUSION),
        ])
        data = ShameDraftData(script)
        # Last ANCHOR is at index 3
        assert data.reveal_idx == 3

    def test_fallback_no_anchor_gives_negative_one(self):
        script = _make_script([
            _make_entry(section_label=SectionLabel.HOOK),
            _make_entry(section_label=SectionLabel.BRIDGE),
        ])
        data = ShameDraftData(script)
        assert data.reveal_idx == -1

    def test_empty_script_fallback(self):
        script = _make_script([])
        data = ShameDraftData(script)
        assert data.reveal_idx == -1


# ── ShameDraftData: human_character_moments ──────────────────────────────────

class TestHumanCharacterMoments:
    """Detects sections whose visual_direction mentions 'human' or 'person'."""

    def test_detects_human_keyword(self):
        script = _make_script([
            _make_entry(visual_direction="Show a human walking."),
            _make_entry(visual_direction="Data overlay."),
        ])
        data = ShameDraftData(script)
        assert 0 in data.human_character_moments

    def test_detects_person_keyword(self):
        script = _make_script([
            _make_entry(visual_direction="Zoom into a person's hands."),
        ])
        data = ShameDraftData(script)
        assert 0 in data.human_character_moments

    def test_case_insensitive(self):
        script = _make_script([
            _make_entry(visual_direction="PERSON standing alone."),
        ])
        data = ShameDraftData(script)
        assert 0 in data.human_character_moments

    def test_no_match(self):
        script = _make_script([
            _make_entry(visual_direction="Show a chart on screen."),
            _make_entry(visual_direction="Animated transition."),
        ])
        data = ShameDraftData(script)
        assert data.human_character_moments == []


# ── ShameDraftData: duration estimates ────────────────────────────────────────

class TestDurationEstimates:
    """Duration estimate: word_count / 2.5 per section."""

    def test_single_section_duration(self):
        # "one two three four five six seven eight nine ten" = 10 words
        prose = "one two three four five six seven eight nine ten"
        script = _make_script([_make_entry(prose=prose)])
        data = ShameDraftData(script)
        assert data.total_duration_estimate == int(10 / 2.5)

    def test_multi_section_cumulative(self):
        # 10 words → 4s each, 2 sections → 8s
        prose = "one two three four five six seven eight nine ten"
        script = _make_script([_make_entry(prose=prose), _make_entry(prose=prose)])
        data = ShameDraftData(script)
        expected = int(10 / 2.5) * 2
        assert data.total_duration_estimate == expected

    def test_empty_prose_zero_duration(self):
        script = _make_script([_make_entry(prose="")])
        data = ShameDraftData(script)
        assert data.total_duration_estimate == 0


# ── ShameDraftData: genre_id ─────────────────────────────────────────────────

class TestGenreId:
    def test_genre_id_passed_through(self):
        script = _make_script([], genre="islamic_history")
        data = ShameDraftData(script)
        assert data.genre_id == "islamic_history"

    def test_sections_stored(self):
        e1 = _make_entry()
        e2 = _make_entry()
        script = _make_script([e1, e2])
        data = ShameDraftData(script)
        assert len(data.sections) == 2


# ── ShameDraftReader integration ──────────────────────────────────────────────

class TestShameDraftReader:
    """ShameDraftReader.read() is a thin wrapper around ShameDraftData."""

    def test_read_returns_shame_draft_data(self):
        script = _make_script([
            _make_entry(prose="Here is the big question.", section_label=SectionLabel.HOOK),
            _make_entry(section_label=SectionLabel.ANCHOR),
            _make_entry(section_label=SectionLabel.REVEAL),
        ])
        reader = ShameDraftReader()
        result = reader.read(script)
        assert isinstance(result, ShameDraftData)
        assert result.big_question_idx == 0
        assert result.reveal_idx == 2

    @patch("packages.content_factory.music.reader.logger")
    def test_read_logs_sector_count(self, mock_logger):
        script = _make_script([_make_entry(), _make_entry(), _make_entry()])
        reader = ShameDraftReader()
        reader.read(script)
        mock_logger.info.assert_called_once_with("reading_shame_draft: sectors=3")
