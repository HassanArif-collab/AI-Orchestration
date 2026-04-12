"""Tests for packages/content_factory/music/section_brief.py — Section brief generator."""

import pytest
from unittest.mock import MagicMock

from packages.content_factory.models import SectionLabel, VisualType
from packages.content_factory.music.models import (
    SectionMusicBrief, EmotionalArcMap, SonicPaletteFlag
)


def _make_entry(section_label, prose="Test prose content. More text here. Third sentence here.", visual_direction="Talking head"):
    """Create a mock DualColumnEntry."""
    entry = MagicMock()
    entry.section_label = section_label
    entry.prose = prose
    entry.visual_direction = visual_direction
    return entry


def _make_script(entries):
    """Create a mock AdaptedScript."""
    script = MagicMock()
    script.entries = entries
    script.genre = "tech"
    return script


def _make_draft_data(script):
    """Create ShameDraftData from script entries."""
    from packages.content_factory.music.reader import ShameDraftData
    return ShameDraftData(script)


def _make_arc_map(energy_trajectory=None, palette_flags=None):
    """Create a test EmotionalArcMap."""
    return EmotionalArcMap(
        arc_summary="Test",
        peak_inventory=[],
        energy_trajectory=energy_trajectory or {0: 3, 1: 2, 2: 4, 3: 5, 4: 2},
        silence_locations=[],
        pakistani_sonic_palette_flags=palette_flags or [],
        recovery_moments=[],
    )


class TestSectionMusicBriefGenerator:
    """Tests for SectionMusicBriefGenerator.generate_briefs()."""

    def test_hook_state_assignment(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([
            _make_entry("HOOK"),
            _make_entry("BRIDGE"),
        ])
        draft = _make_draft_data(script)
        arc = _make_arc_map()
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[0].state_assignment == 1  # Confusion Open
        assert briefs[0].volume_level == "Present"

    def test_bridge_state_assignment(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([
            _make_entry("HOOK"),
            _make_entry("BRIDGE"),
        ])
        draft = _make_draft_data(script)
        arc = _make_arc_map()
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[1].state_assignment == 2  # Thinking Track
        assert briefs[1].volume_level == "Background"

    def test_reveal_state_assignment(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([
            _make_entry("HOOK"),
            _make_entry("BRIDGE"),
            _make_entry("ANCHOR"),
            _make_entry("REVEAL"),
        ])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 2, 1: 2, 2: 3, 3: 5})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[3].state_assignment == 3
        assert briefs[3].volume_level == "Dominant"

    def test_conclusion_state_assignment(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([
            _make_entry("HOOK"),
            _make_entry("CONCLUSION"),
        ])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 3, 1: 1})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[1].state_assignment == 4  # Contemplative Close
        assert briefs[1].volume_level == "Present"

    def test_anchor_chart_visual(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([
            _make_entry("ANCHOR", visual_direction="Show chart with data"),
        ])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 2})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[0].state_assignment == 2  # chart/data → Thinking Track
        assert briefs[0].volume_level == "Present"

    def test_anchor_normal_visual(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([
            _make_entry("ANCHOR", visual_direction="Person talking to camera"),
        ])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 3})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[0].state_assignment == 3  # Feeling Track

    def test_energy_mapping_low(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([_make_entry("HOOK")])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 1})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[0].energy_level == "Low"

    def test_energy_mapping_high(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([_make_entry("HOOK")])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 4})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[0].energy_level == "High"

    def test_energy_mapping_medium(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([_make_entry("HOOK")])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 3})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[0].energy_level == "Medium"

    def test_sonic_palette_match(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([_make_entry("HOOK"), _make_entry("BRIDGE")])
        draft = _make_draft_data(script)
        palette = SonicPaletteFlag(
            section_index=1,
            reason="Cultural resonance",
            instrumentation_direction="Sitar",
            avoid_list=["electric guitar"],
        )
        arc = _make_arc_map(palette_flags=[palette])
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert briefs[1].sonic_palette is not None
        assert briefs[1].sonic_palette.instrumentation_direction == "Sitar"

    def test_sonic_palette_global_flag(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([_make_entry("HOOK"), _make_entry("BRIDGE")])
        draft = _make_draft_data(script)
        palette = SonicPaletteFlag(
            section_index=-1,  # Global flag
            reason="Throughout",
            instrumentation_direction="Tabla",
        )
        arc = _make_arc_map(palette_flags=[palette])
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        # Global flag (-1) should apply to all sections
        assert briefs[0].sonic_palette is not None
        assert briefs[1].sonic_palette is not None

    def test_surface_moment_cue_generation(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        long_prose = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        script = _make_script([_make_entry("BRIDGE", prose=long_prose)])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 2})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        # Should have a surface moment after 3rd sentence
        assert len(briefs[0].surface_moment_cues) == 1

    def test_no_surface_moment_for_reveal(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        long_prose = "First sentence. Second sentence. Third sentence. Fourth sentence."
        script = _make_script([_make_entry("REVEAL", prose=long_prose)])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 5})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert len(briefs[0].surface_moment_cues) == 0

    def test_returns_correct_count(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([
            _make_entry("HOOK"),
            _make_entry("ANCHOR"),
            _make_entry("BRIDGE"),
            _make_entry("REVEAL"),
            _make_entry("CONCLUSION"),
        ])
        draft = _make_draft_data(script)
        arc = _make_arc_map(energy_trajectory={0: 2, 1: 3, 2: 2, 3: 5, 4: 1})
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        assert len(briefs) == 5

    def test_all_briefs_are_section_music_brief(self):
        from packages.content_factory.music.section_brief import SectionMusicBriefGenerator
        script = _make_script([_make_entry("HOOK"), _make_entry("BRIDGE")])
        draft = _make_draft_data(script)
        arc = _make_arc_map()
        gen = SectionMusicBriefGenerator()
        briefs = gen.generate_briefs(draft, arc)
        for brief in briefs:
            assert isinstance(brief, SectionMusicBrief)
