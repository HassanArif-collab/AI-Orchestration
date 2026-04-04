"""Tests for packages/visual/remotion/templates.py

Covers:
  - AnimationSpec: creation, defaults, component_name property
  - generate_composition: all 7 animation types produce valid TSX
  - generate_root_file: valid Root.tsx with multiple compositions
  - TSX output contains expected imports, hooks, and JSX
"""

import pytest

from packages.visual.remotion.templates import AnimationSpec, generate_composition, generate_root_file


# ---------------------------------------------------------------------------
# AnimationSpec model
# ---------------------------------------------------------------------------

class TestAnimationSpec:
    def test_defaults(self):
        spec = AnimationSpec(type="counter", title="GDP Counter", data={"target": 1000})
        assert spec.duration_frames == 150
        assert spec.width == 1920
        assert spec.height == 1080
        assert spec.fps == 30
        assert spec.colors["primary"] == "#FF6B6B"
        assert spec.colors["secondary"] == "#4ECDC4"
        assert spec.colors["background"] == "#1A1A2E"
        assert spec.colors["text"] == "#FFFFFF"

    def test_custom_colors(self):
        spec = AnimationSpec(
            type="bar_chart", title="Chart", data={},
            colors={"primary": "#00FF00", "background": "#000000", "text": "#CCCCCC"},
        )
        assert spec.colors["primary"] == "#00FF00"

    def test_component_name_single_word(self):
        spec = AnimationSpec(type="counter", title="Counter", data={})
        assert spec.component_name == "Counter"

    def test_component_name_multi_word(self):
        spec = AnimationSpec(type="counter", title="GDP Growth Counter", data={})
        assert spec.component_name == "GdpGrowthCounter"

    def test_component_name_with_numbers(self):
        spec = AnimationSpec(type="counter", title="2024 Budget", data={})
        assert spec.component_name == "2024Budget"

    def test_type_literal_validation(self):
        valid_types = ["bar_chart", "line_chart", "text_reveal", "counter", "comparison", "timeline", "map_highlight"]
        for t in valid_types:
            AnimationSpec(type=t, title="Test", data={})
        with pytest.raises(Exception):
            AnimationSpec(type="invalid", title="Test", data={})

    def test_custom_dimensions(self):
        spec = AnimationSpec(type="counter", title="C", data={}, width=1280, height=720, fps=60, duration_frames=300)
        assert spec.width == 1280
        assert spec.height == 720
        assert spec.fps == 60
        assert spec.duration_frames == 300


# ---------------------------------------------------------------------------
# generate_composition — common checks
# ---------------------------------------------------------------------------

class TestGenerateCompositionCommon:
    """Tests that apply to ALL composition types."""

    ANIMATION_TYPES = ["bar_chart", "line_chart", "text_reveal", "counter", "comparison", "timeline", "map_highlight"]

    def test_all_types_produce_string(self):
        for t in self.ANIMATION_TYPES:
            spec = AnimationSpec(type=t, title=f"Test {t}", data={})
            result = generate_composition(spec)
            assert isinstance(result, str), f"{t} did not produce a string"

    def test_all_types_have_remotion_imports(self):
        for t in self.ANIMATION_TYPES:
            spec = AnimationSpec(type=t, title=f"Test {t}", data={})
            result = generate_composition(spec)
            assert "useCurrentFrame" in result, f"{t} missing useCurrentFrame"
            assert "interpolate" in result, f"{t} missing interpolate"
            assert "AbsoluteFill" in result, f"{t} missing AbsoluteFill"

    def test_all_types_have_export_const(self):
        for t in self.ANIMATION_TYPES:
            spec = AnimationSpec(type=t, title=f"Test {t}", data={})
            result = generate_composition(spec)
            assert "export const" in result, f"{t} missing export const"
            assert "React.FC" in result, f"{t} missing React.FC"

    def test_all_types_use_custom_background_color(self):
        for t in self.ANIMATION_TYPES:
            spec = AnimationSpec(
                type=t, title=f"Test {t}", data={},
                colors={"background": "#FF0000", "text": "#000000", "primary": "#00FF00"},
            )
            result = generate_composition(spec)
            assert "#FF0000" in result, f"{t} missing custom background color"

    def test_component_name_in_output(self):
        for t in self.ANIMATION_TYPES:
            spec = AnimationSpec(type=t, title="My Component", data={})
            result = generate_composition(spec)
            assert "MyComponent" in result, f"{t} missing component name"


# ---------------------------------------------------------------------------
# generate_composition — type-specific checks
# ---------------------------------------------------------------------------

class TestCounterComposition:
    def test_counter_contains_target(self):
        spec = AnimationSpec(type="counter", title="C", data={"target": 5000, "prefix": "$", "suffix": " USD"})
        result = generate_composition(spec)
        assert "5000" in result
        assert "$" in result
        assert "USD" in result
        assert "interpolate(frame" in result
        assert "Math.floor(value).toLocaleString()" in result

    def test_counter_defaults(self):
        spec = AnimationSpec(type="counter", title="C", data={})
        result = generate_composition(spec)
        assert "1000" in result  # default target


class TestTextRevealComposition:
    def test_text_reveal_contains_words(self):
        spec = AnimationSpec(type="text_reveal", title="TR", data={"text": "Hello World Pakistan"})
        result = generate_composition(spec)
        assert "Hello" in result
        assert "World" in result
        assert "Pakistan" in result
        assert "WORDS" in result
        assert "visibleCount" in result

    def test_text_reveal_empty_text(self):
        spec = AnimationSpec(type="text_reveal", title="TR", data={"text": ""})
        result = generate_composition(spec)
        assert "const WORDS = []" in result


class TestBarChartComposition:
    def test_bar_chart_contains_data(self):
        spec = AnimationSpec(
            type="bar_chart", title="BC",
            data={"labels": ["A", "B", "C"], "values": [100, 200, 150]},
        )
        result = generate_composition(spec)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "200" in result  # MAX value

    def test_bar_chart_progress(self):
        spec = AnimationSpec(type="bar_chart", title="BC", data={"labels": ["X"], "values": [50]})
        result = generate_composition(spec)
        assert "progress" in result


class TestLineChartComposition:
    def test_line_chart_contains_points(self):
        spec = AnimationSpec(type="line_chart", title="LC", data={"points": [[0, 0], [1, 50], [2, 100]]})
        result = generate_composition(spec)
        assert "POINTS" in result
        assert "pathD" in result
        assert "stroke" in result

    def test_line_chart_is_default(self):
        """line_chart is the default/fallthrough for unknown types."""
        spec = AnimationSpec(type="line_chart", title="LC", data={"points": [[0, 10]]})
        result = generate_composition(spec)
        assert "POINTS" in result


class TestComparisonComposition:
    def test_comparison_contains_labels(self):
        spec = AnimationSpec(
            type="comparison", title="Comp",
            data={"left": {"label": "Option A", "value": "50%"}, "right": {"label": "Option B", "value": "50%"}},
        )
        result = generate_composition(spec)
        assert "VS" in result
        assert "Option A" in result
        assert "Option B" in result

    def test_comparison_defaults(self):
        spec = AnimationSpec(type="comparison", title="Comp", data={})
        result = generate_composition(spec)
        assert "VS" in result


class TestTimelineComposition:
    def test_timeline_contains_events(self):
        spec = AnimationSpec(
            type="timeline", title="TL",
            data={"events": [{"year": 2020, "label": "COVID"}, {"year": 2022, "label": "Floods"}]},
        )
        result = generate_composition(spec)
        assert "EVENTS" in result
        assert "2020" in result
        assert "2022" in result

    def test_timeline_defaults(self):
        spec = AnimationSpec(type="timeline", title="TL", data={})
        result = generate_composition(spec)
        assert "EVENTS" in result


class TestMapHighlightComposition:
    def test_map_contains_region(self):
        spec = AnimationSpec(type="map_highlight", title="MH", data={"region": "Pakistan", "highlight_color": "#FF0000"})
        result = generate_composition(spec)
        assert "Pakistan" in result
        assert "#FF0000" in result
        assert "scale" in result
        assert "opacity" in result

    def test_map_defaults(self):
        spec = AnimationSpec(type="map_highlight", title="MH", data={})
        result = generate_composition(spec)
        assert "Pakistan" in result  # default region


# ---------------------------------------------------------------------------
# generate_root_file
# ---------------------------------------------------------------------------

class TestGenerateRootFile:
    def test_single_composition(self):
        specs = [AnimationSpec(type="counter", title="Counter", data={"target": 100})]
        root = generate_root_file(specs)
        assert "import {Composition} from 'remotion'" in root
        assert "import {Counter} from './compositions/Counter'" in root
        assert 'id="Counter"' in root
        assert "durationInFrames={150}" in root
        assert "fps={30}" in root
        assert "width={1920}" in root
        assert "height={1080}" in root
        assert "RemotionRoot" in root

    def test_multiple_compositions(self):
        specs = [
            AnimationSpec(type="counter", title="Counter", data={}),
            AnimationSpec(type="bar_chart", title="Bar Chart", data={}),
            AnimationSpec(type="text_reveal", title="Text Reveal", data={"text": "Hello"}),
        ]
        root = generate_root_file(specs)
        assert "import {Counter}" in root
        assert "import {BarChart}" in root
        assert "import {TextReveal}" in root
        assert 'id="Counter"' in root
        assert 'id="BarChart"' in root
        assert 'id="TextReveal"' in root

    def test_custom_dimensions_in_root(self):
        specs = [AnimationSpec(type="counter", title="C", data={}, width=1280, height=720, fps=60, duration_frames=300)]
        root = generate_root_file(specs)
        assert "durationInFrames={300}" in root
        assert "fps={60}" in root
        assert "width={1280}" in root
        assert "height={720}" in root

    def test_empty_list(self):
        root = generate_root_file([])
        assert "import {Composition} from 'remotion'" in root
        assert "RemotionRoot" in root
        # No Composition registrations
        assert "<Composition" not in root
