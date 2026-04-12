"""Tests for packages.content_factory.music.agent — MusicAgent.

These are end-to-end tests using the real sub-components
(reader, arc_designer, section_brief, transitions) which have no
external dependencies (no Zep, no LLM calls).
"""

import pytest

from packages.content_factory.models import (
    AdaptedScript,
    DualColumnEntry,
    SectionLabel,
)
from packages.content_factory.music.agent import MusicAgent
from packages.content_factory.music.models import MusicArchitectureDocument


# ── Helpers ────────────────────────────────────────────────────────────────────

def _entry(
    prose: str = "Some spoken text here for the section.",
    visual_direction: str = "Show a chart on screen.",
    section_label: SectionLabel = SectionLabel.BRIDGE,
) -> DualColumnEntry:
    return DualColumnEntry(
        prose=prose,
        visual_direction=visual_direction,
        section_label=section_label,
    )


def _script(entries, genre="comparison_and_contrast", video_id="vid-001") -> AdaptedScript:
    return AdaptedScript(video_id=video_id, genre=genre, entries=entries)


# ── End-to-end pipeline ──────────────────────────────────────────────────────

class TestMusicAgentE2E:
    """Test the full pipeline: reader → arc → briefs → transitions."""

    def test_returns_music_architecture_document(self):
        script = _script([
            _entry(prose="What is the big question about life?", section_label=SectionLabel.HOOK),
            _entry(section_label=SectionLabel.ANCHOR, visual_direction="a human walking"),
            _entry(section_label=SectionLabel.BRIDGE),
            _entry(section_label=SectionLabel.REVEAL),
            _entry(section_label=SectionLabel.CONCLUSION),
        ])
        agent = MusicAgent()
        result = agent.generate_music_architecture("test-vid", script)
        assert isinstance(result, MusicArchitectureDocument)

    def test_video_id_propagated(self):
        script = _script([_entry(section_label=SectionLabel.HOOK, prose="big question")])
        agent = MusicAgent()
        result = agent.generate_music_architecture("my-custom-vid", script)
        assert result.video_id == "my-custom-vid"

    def test_genre_id_propagated(self):
        script = _script([_entry(section_label=SectionLabel.HOOK, prose="big question")], genre="islamic_history")
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        assert result.genre_id == "islamic_history"

    def test_arc_summary_not_empty(self):
        script = _script([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
        ])
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        assert len(result.arc_summary) > 0

    def test_section_briefs_match_entries(self):
        entries = [
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.BRIDGE),
        ]
        script = _script(entries)
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        assert len(result.section_briefs) == 3

    def test_transitions_count(self):
        entries = [
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.BRIDGE),
            _entry(section_label=SectionLabel.REVEAL),
        ]
        script = _script(entries)
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        # 4 sections → 3 transitions
        assert len(result.transitions) == 3

    def test_silence_before_reveal(self):
        script = _script([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.REVEAL),
        ])
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        assert len(result.silence_map) == 1
        assert result.silence_map[0].section_index == 1

    def test_integrity_score_is_100(self):
        script = _script([_entry(section_label=SectionLabel.HOOK, prose="big question")])
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        assert result.music_architecture_integrity_score == 100.0

    def test_failed_questions_empty(self):
        script = _script([_entry(section_label=SectionLabel.HOOK, prose="big question")])
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        assert result.failed_questions == []

    def test_empty_script(self):
        script = _script([])
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        assert isinstance(result, MusicArchitectureDocument)
        assert len(result.section_briefs) == 0
        assert len(result.transitions) == 0


# ── Transition type propagation ──────────────────────────────────────────────

class TestMusicAgentTransitions:
    def test_reveal_transition_is_silence_drop(self):
        script = _script([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.REVEAL),
        ])
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        # Find transition going into REVEAL (index 2)
        reveal_transitions = [t for t in result.transitions if t.to_section_index == 2]
        assert len(reveal_transitions) == 1
        assert reveal_transitions[0].transition_type == "Silence Drop"

    def test_conclusion_transition_is_resolution_settle(self):
        script = _script([
            _entry(section_label=SectionLabel.HOOK, prose="big question"),
            _entry(section_label=SectionLabel.ANCHOR),
            _entry(section_label=SectionLabel.CONCLUSION),
        ])
        agent = MusicAgent()
        result = agent.generate_music_architecture("vid", script)
        conclusion_transitions = [t for t in result.transitions if t.to_section_index == 2]
        assert len(conclusion_transitions) == 1
        assert conclusion_transitions[0].transition_type == "Resolution Settle"
