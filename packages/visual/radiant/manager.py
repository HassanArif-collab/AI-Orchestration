"""
radiant/manager.py — Manages Radiant shader animations.

Context: Radiant is 94 self-contained HTML canvas shader animations.
Each is a single .html file — no build step needed.
We clone the repo locally and serve shaders as iframe embeds.

GitHub: https://github.com/pbakaus/radiant

Mood → shader mapping lets agents pick a background based on video tone.
All methods return empty/None gracefully if shader directory doesn't exist.

Imports: subprocess, pathlib
Imported by: packages/visual/radiant/embedder.py, packages/pipeline/handlers.py
"""

from __future__ import annotations
import subprocess
from pathlib import Path
from packages.core.logger import get_logger

log = get_logger(__name__)

MOOD_TO_SHADER: dict[str, list[str]] = {
    "dramatic":   ["event-horizon", "black-hole", "dark-matter", "tunnel"],
    "optimistic": ["aurora", "gradient-flow", "sunrise", "fireflies"],
    "technical":  ["circuit-board", "hex-grid", "matrix", "network"],
    "organic":    ["fluid-sim", "coral", "water", "lava"],
    "energetic":  ["particle-swarm", "fireworks", "lightning", "confetti"],
    "calm":       ["breathing", "sine-wave", "fog", "waves"],
}


class RadiantManager:
    """Manages Radiant shader files for video backgrounds."""

    def __init__(self, shader_dir: str = "data/radiant-shaders") -> None:
        self.shader_dir = Path(shader_dir)

    def setup(self) -> bool:
        """Clone Radiant repo into shader_dir (or pull if exists).

        Returns:
            True on success, False if git unavailable
        """
        try:
            if self.shader_dir.exists():
                result = subprocess.run(
                    ["git", "pull"],
                    cwd=str(self.shader_dir),
                    capture_output=True, text=True, timeout=30,
                )
                log.info("radiant_updated")
                return result.returncode == 0

            self.shader_dir.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone",
                 "https://github.com/pbakaus/radiant",
                 str(self.shader_dir)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                log.info("radiant_cloned", path=str(self.shader_dir))
                return True
            log.warning("radiant_clone_failed", stderr=result.stderr[:200])
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.warning("radiant_setup_error", error=str(e))
            return False

    def list_shaders(self) -> list[dict]:
        """List all available shader HTML files.

        Returns:
            List of {"name": str, "path": str} dicts.
            Returns [] if directory doesn't exist.
        """
        static_dir = self.shader_dir / "static"
        if not static_dir.exists():
            # Also try root of shader_dir
            if not self.shader_dir.exists():
                return []
            html_files = list(self.shader_dir.rglob("*.html"))
        else:
            html_files = list(static_dir.rglob("*.html"))

        return [
            {"name": f.stem, "path": str(f)}
            for f in sorted(html_files)
            if not f.name.startswith("index")
        ]

    def get_shader_path(self, name: str) -> str | None:
        """Find a shader by name (case-insensitive partial match).

        Returns:
            Absolute path string, or None if not found
        """
        shaders = self.list_shaders()
        name_lower = name.lower()
        for shader in shaders:
            if name_lower in shader["name"].lower():
                return shader["path"]
        return None

    def get_shader_for_mood(self, mood: str) -> str | None:
        """Return first available shader name for a mood.

        Returns:
            Shader name string, or None if mood unknown
        """
        candidates = MOOD_TO_SHADER.get(mood.lower())
        if not candidates:
            return None
        # Return first name regardless of whether files exist
        # (caller uses get_shader_path to resolve)
        return candidates[0]
