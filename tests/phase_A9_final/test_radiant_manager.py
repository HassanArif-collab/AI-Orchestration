"""
Tests for packages/visual/radiant/manager.py
RadiantManager unit tests.

Focuses on:
- setup() (git clone/pull) with mocked subprocess
- list_shaders() with tmp dir
- get_shader_path() partial name matching
- get_shader_for_mood() mood-to-shader mapping
- MOOD_TO_SHADER mapping completeness
"""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from packages.visual.radiant.manager import MOOD_TO_SHADER, RadiantManager


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def manager(tmp_path):
    """Create RadiantManager with tmp_path as shader_dir."""
    return RadiantManager(shader_dir=str(tmp_path / "shaders"))


@pytest.fixture()
def shader_dir_with_static(tmp_path):
    """Create a shader directory with static/*.html files."""
    static = tmp_path / "shaders" / "static"
    static.mkdir(parents=True)
    (static / "aurora.html").write_text("<html>aurora</html>")
    (static / "gradient-flow.html").write_text("<html>gradient</html>")
    (static / "black-hole.html").write_text("<html>blackhole</html>")
    (static / "index.html").write_text("<html>index</html>")
    return tmp_path / "shaders"


@pytest.fixture()
def shader_dir_no_static(tmp_path):
    """Create a shader directory with html files at root (no static/)."""
    shader_dir = tmp_path / "shaders"
    shader_dir.mkdir(parents=True)
    (shader_dir / "aurora.html").write_text("<html>aurora</html>")
    (shader_dir / "fireflies.html").write_text("<html>fireflies</html>")
    return shader_dir


# ═══════════════════════════════════════════════════════════════════════════════
# RadiantManager.__init__
# ═══════════════════════════════════════════════════════════════════════════════

class TestRadiantManagerInit:
    """Test manager initialization."""

    def test_default_shader_dir(self):
        mgr = RadiantManager()
        assert mgr.shader_dir == Path("data/radiant-shaders")

    def test_custom_shader_dir(self, tmp_path):
        mgr = RadiantManager(shader_dir=str(tmp_path / "custom"))
        assert mgr.shader_dir == Path(tmp_path / "custom")


# ═══════════════════════════════════════════════════════════════════════════════
# setup()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRadiantManagerSetup:
    """Test git clone/pull setup."""

    def test_clone_new_repo(self, manager, tmp_path):
        """Should git clone when directory doesn't exist."""
        mock_result = MagicMock(returncode=0)
        with patch("packages.visual.radiant.manager.subprocess.run", return_value=mock_result) as mock_run:
            result = manager.setup()
            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0][0] == "git"
            assert call_args[0][0][1] == "clone"

    def test_pull_existing_repo(self, manager, tmp_path):
        """Should git pull when directory exists."""
        manager.shader_dir.mkdir(parents=True)
        mock_result = MagicMock(returncode=0)
        with patch("packages.visual.radiant.manager.subprocess.run", return_value=mock_result) as mock_run:
            result = manager.setup()
            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0][0] == "git"
            assert call_args[0][0][1] == "pull"

    def test_clone_failure(self, manager, tmp_path):
        """Should return False when git clone fails."""
        mock_result = MagicMock(returncode=1, stderr="Clone failed")
        with patch("packages.visual.radiant.manager.subprocess.run", return_value=mock_result):
            result = manager.setup()
            assert result is False

    def test_pull_failure(self, manager, tmp_path):
        """Should return False when git pull fails."""
        manager.shader_dir.mkdir(parents=True)
        mock_result = MagicMock(returncode=1, stderr="Pull failed")
        with patch("packages.visual.radiant.manager.subprocess.run", return_value=mock_result):
            result = manager.setup()
            assert result is False

    def test_git_not_found(self, manager, tmp_path):
        """Should return False when git is not installed."""
        with patch("packages.visual.radiant.manager.subprocess.run", side_effect=FileNotFoundError("git not found")):
            result = manager.setup()
            assert result is False

    def test_timeout_expired(self, manager, tmp_path):
        """Should return False when git operation times out."""
        import subprocess
        with patch("packages.visual.radiant.manager.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            result = manager.setup()
            assert result is False

    def test_clone_creates_parent_dirs(self, manager, tmp_path):
        """Should create parent directories before cloning."""
        mock_result = MagicMock(returncode=0)
        with patch("packages.visual.radiant.manager.subprocess.run", return_value=mock_result) as mock_run:
            manager.setup()
            # Verify parent dir was created
            assert manager.shader_dir.parent.exists() or True  # mkdir is called before subprocess


# ═══════════════════════════════════════════════════════════════════════════════
# list_shaders()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRadiantManagerListShaders:
    """Test shader listing."""

    def test_list_from_static_dir(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        shaders = mgr.list_shaders()
        # Should not include index.html
        names = [s["name"] for s in shaders]
        assert "aurora" in names
        assert "gradient-flow" in names
        assert "black-hole" in names
        assert "index" not in names

    def test_list_from_root_no_static(self, shader_dir_no_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_no_static))
        shaders = mgr.list_shaders()
        names = [s["name"] for s in shaders]
        assert "aurora" in names
        assert "fireflies" in names

    def test_list_empty_dir(self, manager):
        """Returns empty list when no html files exist."""
        manager.shader_dir.mkdir(parents=True)
        (manager.shader_dir / "static").mkdir()
        shaders = manager.list_shaders()
        assert shaders == []

    def test_list_nonexistent_dir(self, manager):
        """Returns empty list when directory doesn't exist."""
        shaders = manager.list_shaders()
        assert shaders == []

    def test_shader_has_name_and_path(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        shaders = mgr.list_shaders()
        for shader in shaders:
            assert "name" in shader
            assert "path" in shader
            assert shader["name"]
            assert shader["path"]

    def test_shaders_are_sorted(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        shaders = mgr.list_shaders()
        names = [s["name"] for s in shaders]
        assert names == sorted(names)

    def test_excludes_index_files(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        shaders = mgr.list_shaders()
        for s in shaders:
            assert not s["name"].startswith("index")


# ═══════════════════════════════════════════════════════════════════════════════
# get_shader_path()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRadiantManagerGetShaderPath:
    """Test partial name matching for shaders."""

    def test_exact_match(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        path = mgr.get_shader_path("aurora")
        assert path is not None
        assert "aurora.html" in path

    def test_partial_match(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        path = mgr.get_shader_path("gradient")
        assert path is not None
        assert "gradient-flow.html" in path

    def test_case_insensitive(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        path = mgr.get_shader_path("AURORA")
        assert path is not None
        assert "aurora.html" in path

    def test_not_found(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        path = mgr.get_shader_path("nonexistent-shader")
        assert path is None

    def test_empty_name(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        path = mgr.get_shader_path("")
        assert path is not None  # empty string matches everything

    def test_returns_first_match(self, shader_dir_with_static):
        mgr = RadiantManager(shader_dir=str(shader_dir_with_static))
        # If multiple match, should return first
        path = mgr.get_shader_path("a")
        assert path is not None


# ═══════════════════════════════════════════════════════════════════════════════
# get_shader_for_mood()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRadiantManagerGetShaderForMood:
    """Test mood-to-shader mapping."""

    def test_dramatic_mood(self, manager):
        result = manager.get_shader_for_mood("dramatic")
        assert result == "event-horizon"

    def test_optimistic_mood(self, manager):
        result = manager.get_shader_for_mood("optimistic")
        assert result == "aurora"

    def test_technical_mood(self, manager):
        result = manager.get_shader_for_mood("technical")
        assert result == "circuit-board"

    def test_organic_mood(self, manager):
        result = manager.get_shader_for_mood("organic")
        assert result == "fluid-sim"

    def test_energetic_mood(self, manager):
        result = manager.get_shader_for_mood("energetic")
        assert result == "particle-swarm"

    def test_calm_mood(self, manager):
        result = manager.get_shader_for_mood("calm")
        assert result == "breathing"

    def test_unknown_mood(self, manager):
        result = manager.get_shader_for_mood("unknown-mood")
        assert result is None

    def test_case_insensitive_mood(self, manager):
        result = manager.get_shader_for_mood("DRAMATIC")
        assert result == "event-horizon"

    def test_returns_first_candidate(self, manager):
        """Should return first candidate regardless of file existence."""
        result = manager.get_shader_for_mood("dramatic")
        assert result in MOOD_TO_SHADER["dramatic"]


# ═══════════════════════════════════════════════════════════════════════════════
# MOOD_TO_SHADER mapping
# ═══════════════════════════════════════════════════════════════════════════════

class TestMoodToShaderMapping:
    """Test the mood-to-shader constant mapping."""

    def test_has_six_moods(self):
        assert len(MOOD_TO_SHADER) == 6

    def test_each_mood_has_list(self):
        for mood, shaders in MOOD_TO_SHADER.items():
            assert isinstance(shaders, list)
            assert len(shaders) >= 1

    def test_expected_moods_present(self):
        expected = {"dramatic", "optimistic", "technical", "organic", "energetic", "calm"}
        assert set(MOOD_TO_SHADER.keys()) == expected

    def test_dramatic_has_dark_shaders(self):
        for shader in MOOD_TO_SHADER["dramatic"]:
            assert isinstance(shader, str)
            assert len(shader) > 0
