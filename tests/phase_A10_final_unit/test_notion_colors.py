"""
test_notion_colors.py — Tests for packages/integrations/notion/colors.py.

Covers the color/emoji lookup functions and the VISUAL_TYPE_COLORS /
EMOJI_MAP constant dictionaries.
"""

from __future__ import annotations

import pytest

from packages.integrations.notion.colors import (
    VISUAL_TYPE_COLORS,
    EMOJI_MAP,
    get_color,
    get_emoji,
)


class TestGetColor:
    """Tests for the get_color() lookup function."""

    def test_talking_head_returns_red(self):
        """talking_head maps to 'red'."""
        assert get_color("talking_head") == "red"

    def test_animation_returns_blue(self):
        """animation maps to 'blue'."""
        assert get_color("animation") == "blue"

    def test_broll_returns_green(self):
        """broll maps to 'green'."""
        assert get_color("broll") == "green"

    def test_screen_recording_returns_yellow(self):
        """screen_recording maps to 'yellow'."""
        assert get_color("screen_recording") == "yellow"

    def test_data_viz_returns_purple(self):
        """data_viz maps to 'purple'."""
        assert get_color("data_viz") == "purple"

    def test_shader_bg_returns_gray(self):
        """shader_bg maps to 'gray'."""
        assert get_color("shader_bg") == "gray"

    def test_unknown_type_returns_default(self):
        """An unrecognised visual type returns 'default'."""
        assert get_color("nonexistent") == "default"

    def test_empty_string_returns_default(self):
        """Empty string is not a known type, returns 'default'."""
        assert get_color("") == "default"

    def test_none_returns_default(self):
        """None is not a valid key for the dict, returns 'default'."""
        # get() on dict with None key — VISUAL_TYPE_COLORS has no None key
        assert get_color(None) == "default"  # type: ignore[arg-type]

    def test_case_sensitivity(self):
        """Keys are case-sensitive — uppercase should return 'default'."""
        assert get_color("Talking_Head") == "default"
        assert get_color("TALKING_HEAD") == "default"


class TestGetEmoji:
    """Tests for the get_emoji() lookup function."""

    def test_talking_head_returns_red_circle(self):
        """talking_head maps to the red circle emoji."""
        assert get_emoji("talking_head") == "\U0001f534"

    def test_animation_returns_blue_circle(self):
        """animation maps to the blue circle emoji."""
        assert get_emoji("animation") == "\U0001f535"

    def test_broll_returns_green_circle(self):
        """broll maps to the green circle emoji."""
        assert get_emoji("broll") == "\U0001f7e2"

    def test_screen_recording_returns_yellow_circle(self):
        """screen_recording maps to the yellow circle emoji."""
        assert get_emoji("screen_recording") == "\U0001f7e1"

    def test_data_viz_returns_purple_circle(self):
        """data_viz maps to the purple circle emoji."""
        assert get_emoji("data_viz") == "\U0001f7e3"

    def test_shader_bg_returns_black_circle(self):
        """shader_bg maps to the black circle emoji."""
        assert get_emoji("shader_bg") == "\u26ab"

    def test_unknown_returns_white_square(self):
        """An unrecognised visual type returns the white square emoji."""
        assert get_emoji("nonexistent") == "\u2b1c"

    def test_empty_string_returns_white_square(self):
        """Empty string returns the white square default emoji."""
        assert get_emoji("") == "\u2b1c"

    def test_none_returns_white_square(self):
        """None key falls through to the default emoji."""
        assert get_emoji(None) == "\u2b1c"  # type: ignore[arg-type]


class TestConstants:
    """Tests for the VISUAL_TYPE_COLORS and EMOJI_MAP constant dicts."""

    def test_visual_type_colors_has_six_entries(self):
        """VISUAL_TYPE_COLORS must contain exactly 6 visual-type mappings."""
        assert len(VISUAL_TYPE_COLORS) == 6

    def test_emoji_map_has_six_entries(self):
        """EMOJI_MAP must contain exactly 6 visual-type mappings."""
        assert len(EMOJI_MAP) == 6

    def test_keys_match_between_dicts(self):
        """Both dicts must have identical key sets (same visual types)."""
        assert set(VISUAL_TYPE_COLORS.keys()) == set(EMOJI_MAP.keys())

    def test_all_keys_are_strings(self):
        """All keys in both dicts must be strings."""
        assert all(isinstance(k, str) for k in VISUAL_TYPE_COLORS)
        assert all(isinstance(k, str) for k in EMOJI_MAP)

    def test_all_values_are_strings(self):
        """All values in both dicts must be strings."""
        assert all(isinstance(v, str) for v in VISUAL_TYPE_COLORS.values())
        assert all(isinstance(v, str) for v in EMOJI_MAP.values())

    def test_known_visual_types_present(self):
        """All expected visual types must be present as keys."""
        expected = {"talking_head", "animation", "broll",
                    "screen_recording", "data_viz", "shader_bg"}
        assert set(VISUAL_TYPE_COLORS.keys()) == expected


class TestModuleImport:
    """Tests that the colors module imports cleanly."""

    def test_import_module(self):
        """The colors module should import without errors."""
        import packages.integrations.notion.colors as mod
        assert hasattr(mod, "get_color")
        assert hasattr(mod, "get_emoji")
        assert hasattr(mod, "VISUAL_TYPE_COLORS")
        assert hasattr(mod, "EMOJI_MAP")

    def test_functions_are_callable(self):
        """Both get_color and get_emoji must be callable."""
        assert callable(get_color)
        assert callable(get_emoji)
