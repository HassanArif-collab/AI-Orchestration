"""
Tests for packages/visual/remotion/setup.py
check_prerequisites, scaffold_project, install_dependencies.

Focuses on:
- Prerequisite detection (Node.js, npm)
- Scaffold skip-if-exists, Node.js unavailable, create success/failure
- Install success/failure/exception
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from packages.visual.remotion.setup import check_prerequisites, scaffold_project, install_dependencies


# ═══════════════════════════════════════════════════════════════════════════════
# check_prerequisites()
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckPrerequisites:
    """Test Node.js and npm detection."""

    def test_node_and_npm_available(self):
        node_result = MagicMock(returncode=0, stdout="v18.17.0\n")
        npm_result = MagicMock(returncode=0, stdout="9.6.7\n")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[node_result, npm_result]):
            result = check_prerequisites()
            assert result["node"] is True
            assert result["npm"] is True
            assert result["node_version"] == "v18.17.0"

    def test_node_unavailable(self):
        node_result = MagicMock(returncode=1, stdout="")
        npm_result = MagicMock(returncode=0, stdout="9.6.7\n")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[node_result, npm_result]):
            result = check_prerequisites()
            assert result["node"] is False
            assert result["node_version"] == ""

    def test_npm_unavailable(self):
        node_result = MagicMock(returncode=0, stdout="v18.17.0\n")
        npm_result = MagicMock(returncode=1, stdout="")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[node_result, npm_result]):
            result = check_prerequisites()
            assert result["node"] is True
            assert result["npm"] is False

    def test_node_not_found_exception(self):
        npm_result = MagicMock(returncode=0, stdout="9.6.7\n")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[FileNotFoundError("not found"), npm_result]):
            result = check_prerequisites()
            assert result["node"] is False

    def test_npm_not_found_exception(self):
        node_result = MagicMock(returncode=0, stdout="v18.17.0\n")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[node_result, FileNotFoundError("not found")]):
            result = check_prerequisites()
            assert result["npm"] is False

    def test_node_timeout(self):
        npm_result = MagicMock(returncode=0, stdout="9.6.7\n")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[subprocess.TimeoutExpired("node", 5), npm_result]):
            result = check_prerequisites()
            assert result["node"] is False

    def test_npm_timeout(self):
        node_result = MagicMock(returncode=0, stdout="v18.17.0\n")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[node_result, subprocess.TimeoutExpired("npm", 5)]):
            result = check_prerequisites()
            assert result["npm"] is False

    def test_both_unavailable(self):
        node_result = MagicMock(returncode=1, stdout="")
        npm_result = MagicMock(returncode=1, stdout="")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[node_result, npm_result]):
            result = check_prerequisites()
            assert result["node"] is False
            assert result["npm"] is False

    def test_result_has_expected_keys(self):
        node_result = MagicMock(returncode=0, stdout="v20.0.0\n")
        npm_result = MagicMock(returncode=0, stdout="10.0.0\n")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[node_result, npm_result]):
            result = check_prerequisites()
            assert set(result.keys()) == {"node", "npm", "node_version"}

    def test_node_version_stripped(self):
        node_result = MagicMock(returncode=0, stdout="  v18.17.0  \n")
        npm_result = MagicMock(returncode=0, stdout="9.6.7\n")
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=[node_result, npm_result]):
            result = check_prerequisites()
            assert result["node_version"] == "v18.17.0"


# ═══════════════════════════════════════════════════════════════════════════════
# scaffold_project()
# ═══════════════════════════════════════════════════════════════════════════════

class TestScaffoldProject:
    """Test Remotion project scaffolding."""

    def test_skip_if_exists(self, tmp_path):
        """Should return True if project already exists."""
        (tmp_path / "visual-engine").mkdir()
        with patch("packages.visual.remotion.setup.check_prerequisites", return_value={"node": True}):
            with patch("packages.visual.remotion.setup.subprocess.run") as mock_run:
                result = scaffold_project(str(tmp_path / "visual-engine"))
                assert result is True
                mock_run.assert_not_called()

    def test_node_not_installed(self, tmp_path):
        """Should return False if Node.js not available."""
        with patch("packages.visual.remotion.setup.check_prerequisites", return_value={"node": False}):
            with patch("packages.visual.remotion.setup.subprocess.run") as mock_run:
                result = scaffold_project(str(tmp_path / "visual-engine"))
                assert result is False
                mock_run.assert_not_called()

    def test_create_success(self, tmp_path):
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.setup.check_prerequisites", return_value={"node": True}):
            with patch("packages.visual.remotion.setup.subprocess.run", return_value=mock_result) as mock_run:
                result = scaffold_project(str(tmp_path / "visual-engine"))
                assert result is True
                mock_run.assert_called_once()
                # Verify npx command
                call_args = mock_run.call_args
                assert call_args[0][0][0] == "npx"
                assert call_args[0][0][1] == "create-video@latest"

    def test_create_failure(self, tmp_path):
        mock_result = MagicMock(returncode=1, stderr="Scaffold failed")
        with patch("packages.visual.remotion.setup.check_prerequisites", return_value={"node": True}):
            with patch("packages.visual.remotion.setup.subprocess.run", return_value=mock_result):
                result = scaffold_project(str(tmp_path / "visual-engine"))
                assert result is False

    def test_create_exception(self, tmp_path):
        with patch("packages.visual.remotion.setup.check_prerequisites", return_value={"node": True}):
            with patch("packages.visual.remotion.setup.subprocess.run", side_effect=Exception("Unexpected error")):
                result = scaffold_project(str(tmp_path / "visual-engine"))
                assert result is False

    def test_default_output_dir(self, tmp_path):
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.setup.check_prerequisites", return_value={"node": True}):
            with patch("packages.visual.remotion.setup.subprocess.run", return_value=mock_result):
                result = scaffold_project("visual-engine")
                assert result is True

    def test_timeout_exception(self, tmp_path):
        with patch("packages.visual.remotion.setup.check_prerequisites", return_value={"node": True}):
            with patch("packages.visual.remotion.setup.subprocess.run", side_effect=subprocess.TimeoutExpired("npx", 120)):
                result = scaffold_project(str(tmp_path / "visual-engine"))
                assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# install_dependencies()
# ═══════════════════════════════════════════════════════════════════════════════

class TestInstallDependencies:
    """Test npm install in Remotion project."""

    def test_install_success(self, tmp_path):
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.setup.subprocess.run", return_value=mock_result) as mock_run:
            result = install_dependencies(str(tmp_path / "project"))
            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == ["npm", "install"]
            assert call_args[1]["cwd"] == str(tmp_path / "project")

    def test_install_failure(self, tmp_path):
        mock_result = MagicMock(returncode=1, stderr="Install failed")
        with patch("packages.visual.remotion.setup.subprocess.run", return_value=mock_result):
            result = install_dependencies(str(tmp_path / "project"))
            assert result is False

    def test_npm_not_found(self, tmp_path):
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=FileNotFoundError("npm not found")):
            result = install_dependencies(str(tmp_path / "project"))
            assert result is False

    def test_timeout(self, tmp_path):
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=subprocess.TimeoutExpired("npm", 120)):
            result = install_dependencies(str(tmp_path / "project"))
            assert result is False

    def test_generic_exception(self, tmp_path):
        with patch("packages.visual.remotion.setup.subprocess.run", side_effect=RuntimeError("disk full")):
            result = install_dependencies(str(tmp_path / "project"))
            assert result is False

    def test_default_project_dir(self):
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("packages.visual.remotion.setup.subprocess.run", return_value=mock_result) as mock_run:
            result = install_dependencies("visual-engine")
            assert result is True
            call_args = mock_run.call_args
            assert call_args[1]["cwd"] == "visual-engine"
