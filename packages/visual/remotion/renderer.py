"""
remotion/renderer.py — Render Remotion compositions to video files.

Context: Takes an AnimationSpec, generates TypeScript, writes it to the
Remotion project, and runs the render command.

Requires Node.js and a scaffolded Remotion project (see setup.py).
All methods return None gracefully if prerequisites are missing.

Imports: subprocess, pathlib, remotion/templates.py
Imported by: packages/pipeline/handlers.py (asset_creation stage)
"""

from __future__ import annotations
import asyncio
import subprocess
from pathlib import Path
from packages.visual.remotion.templates import AnimationSpec, generate_composition, generate_root_file
from packages.core.logger import get_logger

log = get_logger(__name__)


class RemotionRenderer:
    """Renders Remotion animations to video files."""

    def __init__(self, project_dir: str = "visual-engine") -> None:
        self.project_dir = Path(project_dir)

    async def render(
        self, spec: AnimationSpec, output_path: str
    ) -> str | None:
        """Generate TypeScript and render to video.

        Steps:
          1. Write composition .tsx
          2. Update Root.tsx
          3. Run npx remotion render
          4. Return output_path on success

        Returns:
            output_path on success, None on failure
        """
        try:
            compositions_dir = self.project_dir / "src" / "compositions"
            compositions_dir.mkdir(parents=True, exist_ok=True)

            tsx_path = compositions_dir / f"{spec.component_name}.tsx"
            tsx_path.write_text(generate_composition(spec))
            log.info("composition_written", path=str(tsx_path))

            # Update Root.tsx
            existing = list(compositions_dir.glob("*.tsx"))
            loaded_specs = [spec]
            root_path = self.project_dir / "src" / "Root.tsx"
            root_path.write_text(generate_root_file(loaded_specs))

            # Run render
            result = await asyncio.to_thread(
                subprocess.run,
                ["npx", "remotion", "render", spec.component_name, output_path],
                cwd=str(self.project_dir),
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                log.info("render_complete", output=output_path)
                return output_path
            log.warning("render_failed", stderr=result.stderr[:300])
            return None
        except FileNotFoundError:
            log.warning("render_skipped", reason="Node.js or npx not found")
            return None
        except Exception as e:
            log.warning("render_error", error=str(e))
            return None

    async def render_still(
        self, spec: AnimationSpec, frame: int, output_path: str
    ) -> str | None:
        """Render a single frame as PNG (useful for thumbnails)."""
        try:
            tsx_code = generate_composition(spec)
            compositions_dir = self.project_dir / "src" / "compositions"
            compositions_dir.mkdir(parents=True, exist_ok=True)
            (compositions_dir / f"{spec.component_name}.tsx").write_text(tsx_code)

            result = await asyncio.to_thread(
                subprocess.run,
                ["npx", "remotion", "still", spec.component_name,
                 output_path, "--frame", str(frame)],
                cwd=str(self.project_dir),
                capture_output=True, text=True, timeout=120,
            )
            return output_path if result.returncode == 0 else None
        except Exception as e:
            log.warning("still_render_error", error=str(e))
            return None

    def list_compositions(self) -> list[str]:
        """List all .tsx composition files."""
        compositions_dir = self.project_dir / "src" / "compositions"
        if not compositions_dir.exists():
            return []
        return [f.stem for f in compositions_dir.glob("*.tsx")]
