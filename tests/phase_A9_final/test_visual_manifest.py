"""Tests for packages/visual/manifest.py

Covers:
  - AssetEntry: model creation, defaults, Literal constraints
  - AssetManifest: add_asset, get_pending, get_by_type, mark_complete, mark_failed
  - AssetManifest: summary, save/load round-trip (tmp_path)
  - Edge cases: marking nonexistent assets, empty manifest
"""

import json

import pytest

from packages.visual.manifest import AssetEntry, AssetManifest


# ---------------------------------------------------------------------------
# AssetEntry
# ---------------------------------------------------------------------------

class TestAssetEntry:
    def test_defaults(self):
        entry = AssetEntry(
            asset_id="a1",
            asset_type="remotion_animation",
            description="Bar chart animation",
            source_tool="remotion",
        )
        assert entry.status == "planned"
        assert entry.file_path is None
        assert entry.error == ""
        assert entry.spec == {}

    def test_all_asset_types(self):
        valid_types = ["remotion_animation", "radiant_shader", "stock_footage", "screenshot", "thumbnail"]
        for at in valid_types:
            entry = AssetEntry(asset_id="a", asset_type=at, description="d", source_tool="s")
            assert entry.asset_type == at

    def test_invalid_asset_type(self):
        with pytest.raises(Exception):
            AssetEntry(asset_id="a", asset_type="invalid_type", description="d", source_tool="s")

    def test_all_statuses(self):
        valid_statuses = ["planned", "generating", "complete", "failed"]
        for st in valid_statuses:
            entry = AssetEntry(asset_id="a", asset_type="remotion_animation", description="d", source_tool="s", status=st)
            assert entry.status == st

    def test_invalid_status(self):
        with pytest.raises(Exception):
            AssetEntry(asset_id="a", asset_type="remotion_animation", description="d", source_tool="s", status="done")

    def test_full_creation(self):
        entry = AssetEntry(
            asset_id="a1",
            asset_type="screenshot",
            description="Main title screenshot",
            source_tool="manual",
            status="complete",
            file_path="/tmp/title.png",
            error="",
            spec={"width": 1920},
        )
        assert entry.file_path == "/tmp/title.png"
        assert entry.spec == {"width": 1920}


# ---------------------------------------------------------------------------
# AssetManifest — basic operations
# ---------------------------------------------------------------------------

class TestAssetManifest:
    def test_empty_manifest(self):
        m = AssetManifest(video_title="Test Video")
        assert m.video_title == "Test Video"
        assert m.assets == []

    def test_add_asset(self):
        m = AssetManifest(video_title="Video")
        entry = AssetEntry(asset_id="a1", asset_type="remotion_animation", description="d", source_tool="remotion")
        m.add_asset(entry)
        assert len(m.assets) == 1
        assert m.assets[0].asset_id == "a1"

    def test_add_multiple_assets(self):
        m = AssetManifest(video_title="Video")
        for i in range(5):
            m.add_asset(AssetEntry(asset_id=f"a{i}", asset_type="remotion_animation", description="d", source_tool="remotion"))
        assert len(m.assets) == 5


# ---------------------------------------------------------------------------
# AssetManifest — get_pending
# ---------------------------------------------------------------------------

class TestGetPending:
    def test_all_planned(self):
        m = AssetManifest(video_title="V")
        m.add_asset(AssetEntry(asset_id="a1", asset_type="remotion_animation", description="d", source_tool="r"))
        m.add_asset(AssetEntry(asset_id="a2", asset_type="remotion_animation", description="d", source_tool="r"))
        pending = m.get_pending()
        assert len(pending) == 2

    def test_mixed_statuses(self):
        m = AssetManifest(video_title="V")
        m.add_asset(AssetEntry(asset_id="a1", asset_type="remotion_animation", description="d", source_tool="r", status="planned"))
        m.add_asset(AssetEntry(asset_id="a2", asset_type="remotion_animation", description="d", source_tool="r", status="generating"))
        m.add_asset(AssetEntry(asset_id="a3", asset_type="remotion_animation", description="d", source_tool="r", status="complete"))
        m.add_asset(AssetEntry(asset_id="a4", asset_type="remotion_animation", description="d", source_tool="r", status="failed"))
        pending = m.get_pending()
        assert len(pending) == 1
        assert pending[0].asset_id == "a1"


# ---------------------------------------------------------------------------
# AssetManifest — get_by_type
# ---------------------------------------------------------------------------

class TestGetByType:
    def test_filter_by_type(self):
        m = AssetManifest(video_title="V")
        m.add_asset(AssetEntry(asset_id="a1", asset_type="remotion_animation", description="d", source_tool="r"))
        m.add_asset(AssetEntry(asset_id="a2", asset_type="radiant_shader", description="d", source_tool="r"))
        m.add_asset(AssetEntry(asset_id="a3", asset_type="remotion_animation", description="d", source_tool="r"))
        result = m.get_by_type("remotion_animation")
        assert len(result) == 2
        result = m.get_by_type("radiant_shader")
        assert len(result) == 1
        result = m.get_by_type("screenshot")
        assert len(result) == 0


# ---------------------------------------------------------------------------
# AssetManifest — mark_complete / mark_failed
# ---------------------------------------------------------------------------

class TestMarkStatus:
    def test_mark_complete(self):
        m = AssetManifest(video_title="V")
        m.add_asset(AssetEntry(asset_id="a1", asset_type="remotion_animation", description="d", source_tool="r"))
        m.mark_complete("a1", "/output/anim.mp4")
        assert m.assets[0].status == "complete"
        assert m.assets[0].file_path == "/output/anim.mp4"

    def test_mark_failed(self):
        m = AssetManifest(video_title="V")
        m.add_asset(AssetEntry(asset_id="a1", asset_type="remotion_animation", description="d", source_tool="r"))
        m.mark_failed("a1", "Render timed out")
        assert m.assets[0].status == "failed"
        assert m.assets[0].error == "Render timed out"

    def test_mark_complete_nonexistent(self):
        """Should silently do nothing if asset_id not found."""
        m = AssetManifest(video_title="V")
        m.mark_complete("nonexistent", "/path")  # no exception
        assert len(m.assets) == 0

    def test_mark_failed_nonexistent(self):
        """Should silently do nothing if asset_id not found."""
        m = AssetManifest(video_title="V")
        m.mark_failed("nonexistent", "error")  # no exception
        assert len(m.assets) == 0

    def test_mark_updates_correct_asset(self):
        m = AssetManifest(video_title="V")
        m.add_asset(AssetEntry(asset_id="a1", asset_type="remotion_animation", description="d", source_tool="r"))
        m.add_asset(AssetEntry(asset_id="a2", asset_type="remotion_animation", description="d", source_tool="r"))
        m.mark_complete("a2", "/path.mp4")
        assert m.assets[0].status == "planned"
        assert m.assets[1].status == "complete"


# ---------------------------------------------------------------------------
# AssetManifest — summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_empty_summary(self):
        m = AssetManifest(video_title="V")
        s = m.summary()
        assert s == {"total": 0, "planned": 0, "generating": 0, "complete": 0, "failed": 0}

    def test_mixed_summary(self):
        m = AssetManifest(video_title="V")
        m.add_asset(AssetEntry(asset_id="a1", asset_type="remotion_animation", description="d", source_tool="r", status="planned"))
        m.add_asset(AssetEntry(asset_id="a2", asset_type="remotion_animation", description="d", source_tool="r", status="planned"))
        m.add_asset(AssetEntry(asset_id="a3", asset_type="remotion_animation", description="d", source_tool="r", status="generating"))
        m.add_asset(AssetEntry(asset_id="a4", asset_type="remotion_animation", description="d", source_tool="r", status="complete"))
        m.add_asset(AssetEntry(asset_id="a5", asset_type="remotion_animation", description="d", source_tool="r", status="failed"))
        s = m.summary()
        assert s == {"total": 5, "planned": 2, "generating": 1, "complete": 1, "failed": 1}


# ---------------------------------------------------------------------------
# AssetManifest — save / load round-trip
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_round_trip(self, tmp_path):
        m = AssetManifest(video_title="My Video")
        m.add_asset(AssetEntry(
            asset_id="a1", asset_type="remotion_animation", description="Bar chart",
            source_tool="remotion", status="complete", file_path="/out/bar.mp4",
            spec={"type": "bar_chart", "title": "GDP Growth"},
        ))
        m.add_asset(AssetEntry(
            asset_id="a2", asset_type="radiant_shader", description="Background",
            source_tool="radiant", status="planned",
        ))

        filepath = str(tmp_path / "manifest.json")
        m.save(filepath)

        loaded = AssetManifest.load(filepath)
        assert loaded.video_title == "My Video"
        assert len(loaded.assets) == 2
        assert loaded.assets[0].asset_id == "a1"
        assert loaded.assets[0].status == "complete"
        assert loaded.assets[0].file_path == "/out/bar.mp4"
        assert loaded.assets[0].spec == {"type": "bar_chart", "title": "GDP Growth"}
        assert loaded.assets[1].asset_id == "a2"
        assert loaded.assets[1].status == "planned"

    def test_save_creates_parent_dirs(self, tmp_path):
        m = AssetManifest(video_title="V")
        filepath = str(tmp_path / "nested" / "dir" / "manifest.json")
        m.save(filepath)
        loaded = AssetManifest.load(filepath)
        assert loaded.video_title == "V"

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(Exception):
            AssetManifest.load(str(tmp_path / "nonexistent.json"))

    def test_save_produces_valid_json(self, tmp_path):
        m = AssetManifest(video_title="V")
        filepath = str(tmp_path / "m.json")
        m.save(filepath)
        data = json.loads((tmp_path / "m.json").read_text())
        assert data["video_title"] == "V"
        assert data["assets"] == []


# ---------------------------------------------------------------------------
# AssetManifest — to_dict
# ---------------------------------------------------------------------------

class TestToDict:
    def test_to_dict(self):
        m = AssetManifest(video_title="V")
        m.add_asset(AssetEntry(asset_id="a1", asset_type="remotion_animation", description="d", source_tool="r"))
        d = m.to_dict()
        assert d["video_title"] == "V"
        assert len(d["assets"]) == 1
        assert d["assets"][0]["asset_id"] == "a1"
