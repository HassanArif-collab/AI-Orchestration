"""
Tests for packages/visual/remotion/renderer.py
RemotionRenderer unit tests.

Focuses on:
- render() — TSX write, render success/failure
- render_still() — single frame PNG render
- list_compositions()
- All subprocess.run mocked, tmp_path for file I/O
"""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.visual.remotion.renderer import RemotionRenderer
from packages.visual.remotion.templates import AnimationSpec


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def counter_spec():
    """Create a sample counter AnimationSpec."""
    return AnimationSpec(
        type="counter",
        title="Subscriber Count",
        data={"target": 10000, "prefix": "", "suffix": ""},
        duration_frames=90,
    )


@pytest.fixture()
def renderer(tmp_path):
    """Create a RemotionRenderer with tmp_path as project_dir."""
    return RemotionRenderer(project_dir=str(tmp_path / "visual-engine"))


# ═══════════════════════════════════════════════════════════════════════════════
# RemotionRenderer.__init__
# ═══════════════════════════════════════════════════════════════════════════════

class TestRemotionRendererInit:
    """Test renderer initialization."""

    def test_default_project_dir(self):
        renderer = RemotionRenderer()
        assert renderer.project_dir == Path("visual-engine")

    def test_custom_project_dir(self, tmp_path):
        renderer = RemotionRenderer(project_dir=str(tmp_path / "custom"))
        assert renderer.project_dir == Path(tmp_path / "custom")


# ═══════════════════════════════════════════════════════════════════════════════
# render()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRemotionRendererRender:
    """Test video rendering."""

    @pytest.mark.asyncio
    async def test_render_success(self, renderer, counter_spec, tmp_path):
        """Successful render returns output path."""
        output = str(tmp_path / "output.mp4")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result) as mock_run:
            result = await renderer.render(counter_spec, output)
            assert result == output
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_failure(self, renderer, counter_spec, tmp_path):
        """Failed render returns None."""
        output = str(tmp_path / "output.mp4")
        mock_result = MagicMock(returncode=1, stderr="Render error")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result):
            result = await renderer.render(counter_spec, output)
            assert result is None

    @pytest.mark.asyncio
    async def test_render_writes_tsx(self, renderer, counter_spec, tmp_path):
        """Render should write composition .tsx file."""
        output = str(tmp_path / "output.mp4")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result):
            await renderer.render(counter_spec, output)

        # Check .tsx file was written
        compositions_dir = renderer.project_dir / "src" / "compositions"
        tsx_file = compositions_dir / f"{counter_spec.component_name}.tsx"
        assert tsx_file.exists()
        content = tsx_file.read_text()
        assert "useCurrentFrame" in content
        assert "interpolate" in content
        assert counter_spec.component_name in content

    @pytest.mark.asyncio
    async def test_render_writes_root_tsx(self, renderer, counter_spec, tmp_path):
        """Render should write/update Root.tsx."""
        output = str(tmp_path / "output.mp4")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result):
            await renderer.render(counter_spec, output)

        root_file = renderer.project_dir / "src" / "Root.tsx"
        assert root_file.exists()
        content = root_file.read_text()
        assert "Composition" in content
        assert counter_spec.component_name in content

    @pytest.mark.asyncio
    async def test_render_creates_directories(self, renderer, counter_spec, tmp_path):
        """Render should create compositions directory."""
        output = str(tmp_path / "output.mp4")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result):
            await renderer.render(counter_spec, output)

        assert (renderer.project_dir / "src" / "compositions").exists()

    @pytest.mark.asyncio
    async def test_render_npx_not_found(self, renderer, counter_spec, tmp_path):
        """Returns None when npx is not found."""
        output = str(tmp_path / "output.mp4")
        with patch("packages.visual.remotion.renderer.subprocess.run", side_effect=FileNotFoundError("npx not found")):
            result = await renderer.render(counter_spec, output)
            assert result is None

    @pytest.mark.asyncio
    async def test_render_generic_exception(self, renderer, counter_spec, tmp_path):
        """Returns None on generic exception."""
        output = str(tmp_path / "output.mp4")
        with patch("packages.visual.remotion.renderer.subprocess.run", side_effect=RuntimeError("disk full")):
            result = await renderer.render(counter_spec, output)
            assert result is None

    @pytest.mark.asyncio
    async def test_render_command_args(self, renderer, counter_spec, tmp_path):
        """Verify correct npx remotion render command."""
        output = str(tmp_path / "output.mp4")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result) as mock_run:
            await renderer.render(counter_spec, output)

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert cmd[0] == "npx"
            assert cmd[1] == "remotion"
            assert cmd[2] == "render"
            assert cmd[3] == counter_spec.component_name
            assert cmd[4] == output
            assert call_args[1]["cwd"] == str(renderer.project_dir)
            assert call_args[1]["timeout"] == 300


# ═══════════════════════════════════════════════════════════════════════════════
# render_still()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRemotionRendererRenderStill:
    """Test single frame PNG rendering."""

    @pytest.mark.asyncio
    async def test_still_success(self, renderer, counter_spec, tmp_path):
        """Successful still render returns output path."""
        output = str(tmp_path / "frame.png")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result):
            result = await renderer.render_still(counter_spec, 30, output)
            assert result == output

    @pytest.mark.asyncio
    async def test_still_failure(self, renderer, counter_spec, tmp_path):
        """Failed still render returns None."""
        output = str(tmp_path / "frame.png")
        mock_result = MagicMock(returncode=1, stderr="Still render error")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result):
            result = await renderer.render_still(counter_spec, 30, output)
            assert result is None

    @pytest.mark.asyncio
    async def test_still_writes_tsx(self, renderer, counter_spec, tmp_path):
        """Still render should write composition .tsx file."""
        output = str(tmp_path / "frame.png")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result):
            await renderer.render_still(counter_spec, 30, output)

        tsx_file = renderer.project_dir / "src" / "compositions" / f"{counter_spec.component_name}.tsx"
        assert tsx_file.exists()

    @pytest.mark.asyncio
    async def test_still_command_args(self, renderer, counter_spec, tmp_path):
        """Verify correct npx remotion still command."""
        output = str(tmp_path / "frame.png")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result) as mock_run:
            await renderer.render_still(counter_spec, 45, output)

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert cmd[0] == "npx"
            assert cmd[1] == "remotion"
            assert cmd[2] == "still"
            assert cmd[3] == counter_spec.component_name
            assert cmd[4] == output
            assert "--frame" in cmd
            assert "45" in cmd
            assert call_args[1]["timeout"] == 120

    @pytest.mark.asyncio
    async def test_still_exception(self, renderer, counter_spec, tmp_path):
        """Returns None on exception."""
        output = str(tmp_path / "frame.png")
        with patch("packages.visual.remotion.renderer.subprocess.run", side_effect=RuntimeError("error")):
            result = await renderer.render_still(counter_spec, 30, output)
            assert result is None

    @pytest.mark.asyncio
    async def test_still_creates_directory(self, renderer, counter_spec, tmp_path):
        """Should create compositions directory if missing."""
        output = str(tmp_path / "frame.png")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result):
            await renderer.render_still(counter_spec, 0, output)

        assert (renderer.project_dir / "src" / "compositions").exists()


# ═══════════════════════════════════════════════════════════════════════════════
# list_compositions()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRemotionRendererListCompositions:
    """Test listing .tsx composition files."""

    def test_list_empty(self, renderer):
        """Returns empty list when no compositions exist."""
        result = renderer.list_compositions()
        assert result == []

    def test_list_with_files(self, renderer, tmp_path):
        """Returns list of composition names."""
        comp_dir = renderer.project_dir / "src" / "compositions"
        comp_dir.mkdir(parents=True)
        (comp_dir / "SubscriberCount.tsx").write_text("// component")
        (comp_dir / "PriceChart.tsx").write_text("// component")
        (comp_dir / "TextOverlay.tsx").write_text("// component")

        result = renderer.list_compositions()
        assert set(result) == {"SubscriberCount", "PriceChart", "TextOverlay"}

    def test_list_only_tsx(self, renderer, tmp_path):
        """Should only return .tsx files."""
        comp_dir = renderer.project_dir / "src" / "compositions"
        comp_dir.mkdir(parents=True)
        (comp_dir / "CompA.tsx").write_text("// component")
        (comp_dir / "CompB.ts").write_text("// not tsx")
        (comp_dir / "notes.txt").write_text("// not tsx")
        (comp_dir / "CompC.tsx").write_text("// component")

        result = renderer.list_compositions()
        assert set(result) == {"CompA", "CompC"}

    def test_list_no_compositions_dir(self, renderer):
        """Returns empty list when compositions directory doesn't exist."""
        result = renderer.list_compositions()
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# Integration-style tests with real file I/O
# ═══════════════════════════════════════════════════════════════════════════════

class TestRemotionRendererFileIO:
    """Test actual file writes (no subprocess mocking)."""

    def test_render_creates_valid_tsx_content(self, renderer, counter_spec, tmp_path):
        """Verify .tsx content is valid React code."""
        comp_dir = renderer.project_dir / "src" / "compositions"
        comp_dir.mkdir(parents=True)
        tsx_path = comp_dir / f"{counter_spec.component_name}.tsx"

        from packages.visual.remotion.templates import generate_composition
        tsx_path.write_text(generate_composition(counter_spec))

        content = tsx_path.read_text()
        assert "import" in content
        assert "export const" in content
        assert "React.FC" in content
        assert "useCurrentFrame" in content

    @pytest.mark.asyncio
    async def test_render_then_list(self, renderer, counter_spec, tmp_path):
        """After render, list_compositions should include the component."""
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.renderer.subprocess.run", return_value=mock_result):
            await renderer.render(counter_spec, str(tmp_path / "output.mp4"))

        compositions = renderer.list_compositions()
        assert counter_spec.component_name in compositions
