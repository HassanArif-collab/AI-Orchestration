"""Tests for packages/visual/radiant/embedder.py

Covers:
  - COLOR_SCHEMES: all 6 schemes present with correct values
  - generate_iframe_embed: default and custom color scheme, custom shader_dir
  - generate_overlay_html: default and custom text styles, all positions
  - generate_remotion_background: default and custom color scheme, dash handling
  - Edge cases: unknown color scheme falls back to "none"
"""

import pytest

from packages.visual.radiant.embedder import (
    COLOR_SCHEMES,
    generate_iframe_embed,
    generate_overlay_html,
    generate_remotion_background,
)


# ---------------------------------------------------------------------------
# COLOR_SCHEMES
# ---------------------------------------------------------------------------

class TestColorSchemes:
    def test_all_schemes_present(self):
        expected_keys = {"amber", "mono", "blue", "rose", "emerald", "arctic"}
        assert set(COLOR_SCHEMES.keys()) == expected_keys

    def test_amber_is_none(self):
        assert COLOR_SCHEMES["amber"] == "none"

    def test_mono_is_grayscale(self):
        assert COLOR_SCHEMES["mono"] == "grayscale(1)"

    def test_blue_hue_rotate(self):
        assert "hue-rotate" in COLOR_SCHEMES["blue"]

    def test_rose_hue_rotate(self):
        assert "hue-rotate" in COLOR_SCHEMES["rose"]
        assert "300" in COLOR_SCHEMES["rose"]

    def test_emerald_hue_rotate(self):
        assert "hue-rotate" in COLOR_SCHEMES["emerald"]
        assert "90" in COLOR_SCHEMES["emerald"]

    def test_arctic_combined_filters(self):
        assert "hue-rotate" in COLOR_SCHEMES["arctic"]
        assert "saturate" in COLOR_SCHEMES["arctic"]
        assert "brightness" in COLOR_SCHEMES["arctic"]

    def test_values_are_strings(self):
        for k, v in COLOR_SCHEMES.items():
            assert isinstance(v, str), f"{k} value is not a string"


# ---------------------------------------------------------------------------
# generate_iframe_embed
# ---------------------------------------------------------------------------

class TestGenerateIframeEmbed:
    def test_basic_embed(self):
        html = generate_iframe_embed("aurora")
        assert '<iframe' in html
        assert 'src="data/radiant-shaders/static/aurora.html"' in html
        assert 'border:none' in html
        assert 'pointer-events:none' in html
        assert 'width:100%' in html
        assert 'height:100%' in html
        assert 'title="Background: aurora"' in html

    def test_amber_no_filter(self):
        html = generate_iframe_embed("aurora", color_scheme="amber")
        assert "filter:" not in html

    def test_mono_has_filter(self):
        html = generate_iframe_embed("aurora", color_scheme="mono")
        assert "filter: grayscale(1);" in html

    def test_blue_has_filter(self):
        html = generate_iframe_embed("aurora", color_scheme="blue")
        assert "filter: hue-rotate(175deg);" in html

    def test_rose_has_filter(self):
        html = generate_iframe_embed("aurora", color_scheme="rose")
        assert "filter: hue-rotate(300deg) saturate(1.1);" in html

    def test_emerald_has_filter(self):
        html = generate_iframe_embed("aurora", color_scheme="emerald")
        assert "filter: hue-rotate(90deg) saturate(1.2);" in html

    def test_arctic_has_filter(self):
        html = generate_iframe_embed("aurora", color_scheme="arctic")
        assert "filter: hue-rotate(180deg) saturate(0.5) brightness(1.1);" in html

    def test_unknown_scheme_fallback(self):
        html = generate_iframe_embed("aurora", color_scheme="nonexistent")
        assert "filter:" not in html  # falls back to "none"

    def test_custom_shader_dir(self):
        html = generate_iframe_embed("aurora", shader_dir="custom/path")
        assert 'src="custom/path/static/aurora.html"' in html


# ---------------------------------------------------------------------------
# generate_overlay_html
# ---------------------------------------------------------------------------

class TestGenerateOverlayHtml:
    def test_basic_overlay(self):
        html = generate_overlay_html("aurora", "Climate Change")
        assert "<!DOCTYPE html>" in html
        assert "<html>" in html
        assert "Climate Change" in html
        assert '<iframe' in html
        assert "position: absolute" in html
        assert "z-index: 10" in html

    def test_text_style_font(self):
        html = generate_overlay_html("aurora", "Title", text_style={"font": "Arial, sans-serif"})
        assert "font-family: Arial, sans-serif" in html

    def test_text_style_size(self):
        html = generate_overlay_html("aurora", "Title", text_style={"size": "72px"})
        assert "font-size: 72px" in html

    def test_text_style_color(self):
        html = generate_overlay_html("aurora", "Title", text_style={"color": "#FF0000"})
        assert "color: #FF0000" in html

    def test_text_style_none_uses_defaults(self):
        html = generate_overlay_html("aurora", "Title")
        assert "font-family: Inter, sans-serif" in html
        assert "font-size: 48px" in html
        assert "color: white" in html

    def test_position_center(self):
        html = generate_overlay_html("aurora", "Title", text_style={"position": "center"})
        assert "align-items: center" in html
        assert "justify-content: center" in html
        assert "text-align: center" in html

    def test_position_top(self):
        html = generate_overlay_html("aurora", "Title", text_style={"position": "top"})
        assert "align-items: flex-start" in html
        assert "justify-content: flex-start" in html

    def test_position_bottom(self):
        html = generate_overlay_html("aurora", "Title", text_style={"position": "bottom"})
        assert "align-items: flex-end" in html
        assert "justify-content: flex-end" in html

    def test_position_left(self):
        html = generate_overlay_html("aurora", "Title", text_style={"position": "left"})
        assert "align-items: center" in html
        assert "justify-content: flex-start" in html

    def test_position_right(self):
        html = generate_overlay_html("aurora", "Title", text_style={"position": "right"})
        assert "align-items: center" in html
        assert "justify-content: flex-end" in html

    def test_color_scheme_passed_to_iframe(self):
        html = generate_overlay_html("aurora", "Title", color_scheme="mono")
        assert "filter: grayscale(1);" in html

    def test_custom_shader_dir(self):
        html = generate_overlay_html("aurora", "Title", shader_dir="my/dir")
        assert "my/dir/static/aurora.html" in html

    def test_text_shadow_present(self):
        html = generate_overlay_html("aurora", "Title")
        assert "text-shadow" in html
        assert "rgba(0,0,0,0.8)" in html

    def test_body_dimensions(self):
        html = generate_overlay_html("aurora", "Title")
        assert "1920px" in html
        assert "1080px" in html


# ---------------------------------------------------------------------------
# generate_remotion_background
# ---------------------------------------------------------------------------

class TestGenerateRemotionBackground:
    def test_basic_output(self):
        tsx = generate_remotion_background("aurora")
        assert "import {AbsoluteFill} from 'remotion'" in tsx
        assert "<AbsoluteFill>" in tsx
        assert "<iframe" in tsx
        assert "data/radiant-shaders/static/aurora.html" in tsx
        assert "position: 'absolute'" in tsx
        assert "pointerEvents: 'none'" in tsx

    def test_component_name_dash_replaced(self):
        tsx = generate_remotion_background("my-shader")
        assert "myshaderBackground" in tsx

    def test_component_name_no_dash(self):
        tsx = generate_remotion_background("aurora")
        assert "auroraBackground" in tsx

    def test_amber_no_filter(self):
        tsx = generate_remotion_background("aurora", color_scheme="amber")
        assert "filter:" not in tsx

    def test_mono_has_filter(self):
        tsx = generate_remotion_background("aurora", color_scheme="mono")
        assert "filter: 'grayscale(1)'" in tsx

    def test_blue_has_filter(self):
        tsx = generate_remotion_background("aurora", color_scheme="blue")
        assert "filter: 'hue-rotate(175deg)'" in tsx

    def test_unknown_scheme_fallback(self):
        tsx = generate_remotion_background("aurora", color_scheme="nonexistent")
        assert "filter:" not in tsx

    def test_custom_shader_dir(self):
        tsx = generate_remotion_background("aurora", shader_dir="custom/dir")
        assert "custom/dir/static/aurora.html" in tsx

    def test_export_const(self):
        tsx = generate_remotion_background("aurora")
        assert "export const auroraBackground: React.FC" in tsx


# ---------------------------------------------------------------------------
# Cross-function consistency
# ---------------------------------------------------------------------------

class TestCrossFunctionConsistency:
    def test_iframe_embedded_in_overlay(self):
        """Overlay HTML should contain the iframe generated by generate_iframe_embed."""
        iframe = generate_iframe_embed("aurora", "mono")
        overlay = generate_overlay_html("aurora", "Title", color_scheme="mono")
        assert iframe in overlay

    def test_all_color_schemes_in_iframe(self):
        for scheme in COLOR_SCHEMES:
            html = generate_iframe_embed("aurora", scheme)
            assert '<iframe' in html, f"Failed for scheme: {scheme}"

    def test_all_color_schemes_in_remotion(self):
        for scheme in COLOR_SCHEMES:
            tsx = generate_remotion_background("aurora", scheme)
            assert "AbsoluteFill" in tsx, f"Failed for scheme: {scheme}"

    def test_all_color_schemes_in_overlay(self):
        for scheme in COLOR_SCHEMES:
            html = generate_overlay_html("aurora", "Title", color_scheme=scheme)
            assert "overlay" in html, f"Failed for scheme: {scheme}"
