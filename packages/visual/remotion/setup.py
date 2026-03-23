"""
remotion/setup.py — Scaffold and manage a Remotion project.

Context: Remotion is a React framework for programmatic video generation.
We scaffold a local project, then generate TypeScript compositions
and render them to video files.

Requires Node.js. All functions return False/empty gracefully if Node missing.

Imports: subprocess, pathlib
Imported by: packages/visual/remotion/renderer.py
"""

from __future__ import annotations
import subprocess
from pathlib import Path
from packages.core.logger import get_logger

log = get_logger(__name__)


def check_prerequisites() -> dict:
    """Check if Node.js and npm are installed.

    Returns:
        {"node": bool, "npm": bool, "node_version": str}
    """
    result = {"node": False, "npm": False, "node_version": ""}
    try:
        node = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5
        )
        if node.returncode == 0:
            result["node"] = True
            result["node_version"] = node.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        log.warning("node_not_found")

    try:
        npm = subprocess.run(
            ["npm", "--version"], capture_output=True, text=True, timeout=5
        )
        result["npm"] = npm.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        log.warning("npm_not_found")

    return result


def scaffold_project(output_dir: str = "visual-engine") -> bool:
    """Create a new Remotion project if it doesn't exist.

    Returns:
        True if created or already exists, False if Node.js unavailable
    """
    prereqs = check_prerequisites()
    if not prereqs["node"]:
        log.warning("scaffold_skipped", reason="Node.js not installed")
        return False

    project_path = Path(output_dir)
    if project_path.exists():
        log.info("remotion_project_exists", path=str(project_path))
        return True

    try:
        result = subprocess.run(
            ["npx", "create-video@latest", output_dir, "--template", "blank"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            log.info("remotion_project_created", path=output_dir)
            return True
        log.warning("remotion_scaffold_failed", stderr=result.stderr[:200])
        return False
    except Exception as e:
        log.warning("remotion_scaffold_error", error=str(e))
        return False


def install_dependencies(project_dir: str = "visual-engine") -> bool:
    """Run npm install in the Remotion project.

    Returns:
        True on success, False on failure
    """
    try:
        result = subprocess.run(
            ["npm", "install"],
            cwd=project_dir, capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            log.info("npm_install_complete", project_dir=project_dir)
            return True
        log.warning("npm_install_failed", stderr=result.stderr[:200])
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        log.warning("npm_install_error", error=str(e))
        return False
