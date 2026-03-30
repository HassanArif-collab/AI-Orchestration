"""Tests for visual system: Remotion, Radiant, AssetManifest."""

import pytest
from unittest.mock import AsyncMock, patch

# ─── Remotion templates ───────────────────────────────────────────────────────

from packages.visual.remotion.templates import AnimationSpec, generate_composition, generate_root_file


def test_animation_spec_counter():
    spec = AnimationSpec(type="counter", title="View Count",
                         data={"target": 1_000_000})
    assert spec.duration_frames == 150
    assert spec.component_name == "ViewCount"


def test_generate_counter_contains_required_strings():
    spec = AnimationSpec(type="counter", title="Test", data={"target": 500})
    code = generate_composition(spec)
    assert "useCurrentFrame" in code
    assert "interpolate" in code
    assert "AbsoluteFill" in code
    assert "export" in code
    assert "import" in code


def test_generate_bar_chart():
    spec = AnimationSpec(
        type="bar_chart", title="Stats",
        data={"labels": ["A", "B"], "values": [100, 200]}
    )
    code = generate_composition(spec)
    assert "useCurrentFrame" in code
    assert "DATA" in code


def test_generate_text_reveal():
    spec = AnimationSpec(type="text_reveal", title="Reveal",
                         data={"text": "Hello World"})
    code = generate_composition(spec)
    assert "WORDS" in code
    assert "useCurrentFrame" in code


def test_generate_comparison():
    spec = AnimationSpec(
        type="comparison", title="Compare",
        data={"left": {"label": "A", "value": "60%"},
              "right": {"label": "B", "value": "40%"}}
    )
    code = generate_composition(spec)
    assert "VS" in code


def test_generate_root_file():
    specs = [
        AnimationSpec(type="counter", title="Views", data={"target": 100}),
        AnimationSpec(type="bar_chart", title="Stats",
                      data={"labels": ["A"], "values": [1]}),
    ]
    root = generate_root_file(specs)
    assert "Views" in root
    assert "Stats" in root
    assert "Composition" in root
    assert "RemotionRoot" in root


def test_all_animation_types_generate():
    types_data = {
        "bar_chart":    {"labels": ["A"], "values": [1]},
        "line_chart":   {"points": [[0, 0], [1, 10]]},
        "text_reveal":  {"text": "Hello"},
        "counter":      {"target": 100},
        "comparison":   {"left": {"label": "A", "value": "1"},
                         "right": {"label": "B", "value": "2"}},
        "timeline":     {"events": [{"year": 2020, "label": "E"}]},
        "map_highlight": {"region": "Pakistan"},
    }
    for atype, data in types_data.items():
        spec = AnimationSpec(type=atype, title=f"Test {atype}", data=data)
        code = generate_composition(spec)
        assert "useCurrentFrame" in code, f"{atype} missing useCurrentFrame"
        assert "export" in code, f"{atype} missing export"


# ─── Radiant manager ──────────────────────────────────────────────────────────

from packages.visual.radiant.manager import RadiantManager, MOOD_TO_SHADER


def test_list_shaders_returns_empty_when_dir_missing():
    manager = RadiantManager(shader_dir="/nonexistent/path")
    assert manager.list_shaders() == []


def test_get_shader_path_returns_none_when_missing():
    manager = RadiantManager(shader_dir="/nonexistent/path")
    assert manager.get_shader_path("event-horizon") is None


def test_get_shader_for_each_mood():
    manager = RadiantManager()
    for mood in MOOD_TO_SHADER:
        result = manager.get_shader_for_mood(mood)
        assert result is not None, f"No shader for mood: {mood}"
        assert isinstance(result, str)


def test_get_shader_for_unknown_mood():
    manager = RadiantManager()
    assert manager.get_shader_for_mood("nonexistent_mood") is None


# ─── Radiant embedder ─────────────────────────────────────────────────────────

from packages.visual.radiant.embedder import (
    COLOR_SCHEMES, generate_iframe_embed,
    generate_overlay_html, generate_remotion_background,
)


def test_color_schemes_has_all_six():
    assert set(COLOR_SCHEMES.keys()) == {
        "amber", "mono", "blue", "rose", "emerald", "arctic"
    }


def test_generate_iframe_contains_iframe():
    html = generate_iframe_embed("event-horizon")
    assert "<iframe" in html
    assert "event-horizon" in html


def test_generate_iframe_applies_filter():
    html = generate_iframe_embed("event-horizon", color_scheme="blue")
    assert "hue-rotate" in html


def test_generate_overlay_contains_both():
    html = generate_overlay_html("event-horizon", "Test text")
    assert "iframe" in html
    assert "Test text" in html


def test_generate_remotion_background():
    tsx = generate_remotion_background("event-horizon", "amber")
    assert "AbsoluteFill" in tsx
    assert "iframe" in tsx
    assert "event-horizon" in tsx


# ─── Asset Manifest ───────────────────────────────────────────────────────────

from packages.visual.manifest import AssetManifest, AssetEntry


def test_manifest_add_and_get_pending():
    m = AssetManifest(video_title="Test Video")
    m.add_asset(AssetEntry(
        asset_id="a1", asset_type="remotion_animation",
        description="Intro animation", source_tool="remotion"
    ))
    assert len(m.get_pending()) == 1


def test_manifest_mark_complete():
    m = AssetManifest(video_title="Test")
    m.add_asset(AssetEntry(
        asset_id="a1", asset_type="thumbnail",
        description="Thumb", source_tool="manual"
    ))
    m.mark_complete("a1", "/output/thumb.png")
    assert m.assets[0].status == "complete"
    assert m.assets[0].file_path == "/output/thumb.png"


def test_manifest_mark_failed():
    m = AssetManifest(video_title="Test")
    m.add_asset(AssetEntry(
        asset_id="a1", asset_type="remotion_animation",
        description="Anim", source_tool="remotion"
    ))
    m.mark_failed("a1", "Node.js not found")
    assert m.assets[0].status == "failed"
    assert "Node.js" in m.assets[0].error


def test_manifest_summary():
    m = AssetManifest(video_title="Test")
    m.add_asset(AssetEntry(
        asset_id="a1", asset_type="thumbnail",
        description="T", source_tool="manual"
    ))
    m.add_asset(AssetEntry(
        asset_id="a2", asset_type="remotion_animation",
        description="A", source_tool="remotion"
    ))
    m.mark_complete("a1", "/path")
    s = m.summary()
    assert s["total"] == 2
    assert s["complete"] == 1
    assert s["planned"] == 1


def test_manifest_save_and_load(tmp_path):
    m = AssetManifest(video_title="Save Test")
    m.add_asset(AssetEntry(
        asset_id="a1", asset_type="screenshot",
        description="Frame", source_tool="manual"
    ))
    filepath = str(tmp_path / "manifest.json")
    m.save(filepath)
    loaded = AssetManifest.load(filepath)
    assert loaded.video_title == "Save Test"
    assert len(loaded.assets) == 1
    assert loaded.assets[0].asset_id == "a1"
