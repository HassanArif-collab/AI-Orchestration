"""Tests for packages.content_factory.music.transitions — TransitionArchitect."""

import pytest

from packages.content_factory.music.models import SectionMusicBrief, TransitionSpec
from packages.content_factory.music.transitions import TransitionArchitect


# ── Helpers ────────────────────────────────────────────────────────────────────

def _brief(
    section_index: int = 0,
    label: str = "BRIDGE",
    state_assignment: int = 2,
) -> SectionMusicBrief:
    return SectionMusicBrief(
        section_index=section_index,
        label=label,
        state_assignment=state_assignment,
        energy_level="Medium",
        volume_level="Background",
    )


# ── Silence Drop ──────────────────────────────────────────────────────────────

class TestSilenceDrop:
    """Transition into REVEAL should always be Silence Drop."""

    def test_anchor_to_reveal(self):
        briefs = [_brief(0, "ANCHOR", 3), _brief(1, "REVEAL", 3)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Silence Drop"

    def test_bridge_to_reveal(self):
        briefs = [_brief(0, "BRIDGE", 2), _brief(1, "REVEAL", 3)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Silence Drop"

    def test_hook_to_reveal(self):
        briefs = [_brief(0, "HOOK", 1), _brief(1, "REVEAL", 3)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Silence Drop"


# ── Resolution Settle ─────────────────────────────────────────────────────────

class TestResolutionSettle:
    """Transition into CONCLUSION should be Resolution Settle."""

    def test_reveal_to_conclusion(self):
        briefs = [_brief(0, "REVEAL", 3), _brief(1, "CONCLUSION", 4)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Resolution Settle"

    def test_anchor_to_conclusion(self):
        briefs = [_brief(0, "ANCHOR", 3), _brief(1, "CONCLUSION", 4)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Resolution Settle"

    def test_bridge_to_conclusion(self):
        briefs = [_brief(0, "BRIDGE", 2), _brief(1, "CONCLUSION", 4)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Resolution Settle"


# ── Gradual Thickening ────────────────────────────────────────────────────────

class TestGradualThickening:
    """State 2 → State 3 should be Gradual Thickening."""

    def test_thinking_to_feeling(self):
        briefs = [_brief(0, "BRIDGE", 2), _brief(1, "ANCHOR", 3)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Gradual Thickening"

    def test_thickening_duration_is_15(self):
        briefs = [_brief(0, "BRIDGE", 2), _brief(1, "ANCHOR", 3)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].duration_seconds == 15


# ── Gradual Thinning ──────────────────────────────────────────────────────────

class TestGradualThinning:
    """State 3 → State 2 should be Gradual Thinning."""

    def test_feeling_to_thinking(self):
        briefs = [_brief(0, "ANCHOR", 3), _brief(1, "BRIDGE", 2)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Gradual Thinning"


# ── Hard State Reset ──────────────────────────────────────────────────────────

class TestHardStateReset:
    """State 3 → State 3 should be Hard State Reset."""

    def test_feeling_to_feeling(self):
        briefs = [_brief(0, "ANCHOR", 3), _brief(1, "ANCHOR", 3)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Hard State Reset"


# ── Anticipatory Hold (default) ───────────────────────────────────────────────

class TestAnticipatoryHold:
    """Any unmatched pair gets Anticipatory Hold."""

    def test_state_1_to_state_1(self):
        briefs = [_brief(0, "HOOK", 1), _brief(1, "HOOK", 1)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Anticipatory Hold"

    def test_state_1_to_state_4(self):
        """State 1→4 doesn't match any state-based rule, and no label priority → Anticipatory Hold."""
        briefs = [_brief(0, "HOOK", 1), _brief(1, "CUSTOM", 4)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Anticipatory Hold"

    def test_state_1_to_state_2(self):
        briefs = [_brief(0, "HOOK", 1), _brief(1, "BRIDGE", 2)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Anticipatory Hold"


# ── TransitionSpec fields ─────────────────────────────────────────────────────

class TestTransitionSpecFields:
    def test_from_to_indices(self):
        briefs = [_brief(0, "HOOK", 1), _brief(1, "BRIDGE", 2), _brief(2, "ANCHOR", 3)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].from_section_index == 0
        assert transitions[0].to_section_index == 1
        assert transitions[1].from_section_index == 1
        assert transitions[1].to_section_index == 2

    def test_start_end_cues(self):
        briefs = [_brief(0, "HOOK", 1), _brief(1, "BRIDGE", 2)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert "HOOK" in transitions[0].start_cue
        assert "BRIDGE" in transitions[0].end_cue

    def test_default_duration_is_5(self):
        briefs = [_brief(0, "HOOK", 1), _brief(1, "BRIDGE", 2)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].duration_seconds == 5

    def test_editor_note(self):
        briefs = [_brief(0, "HOOK", 1), _brief(1, "REVEAL", 3)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert "Silence Drop" in transitions[0].editor_note
        assert "3" in transitions[0].editor_note

    def test_single_brief_no_transitions(self):
        briefs = [_brief(0, "HOOK", 1)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions == []

    def test_empty_briefs_no_transitions(self):
        transitions = TransitionArchitect().calculate_transitions([])
        assert transitions == []


# ── Priority rules ────────────────────────────────────────────────────────────

class TestRulePriority:
    """REVEAL and CONCLUSION should take priority over state-based rules."""

    def test_reveal_priority_over_thickening(self):
        """State 2→3 would be Thickening, but REVEAL label → Silence Drop."""
        briefs = [_brief(0, "BRIDGE", 2), _brief(1, "REVEAL", 3)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Silence Drop"

    def test_conclusion_priority_over_thinning(self):
        """State 3→2 would be Thinning, but CONCLUSION label → Resolution Settle."""
        briefs = [_brief(0, "REVEAL", 3), _brief(1, "CONCLUSION", 4)]
        transitions = TransitionArchitect().calculate_transitions(briefs)
        assert transitions[0].transition_type == "Resolution Settle"
