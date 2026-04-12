"""Tests for packages/router/capabilities.py — Model capabilities registry."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestCapabilityModels:
    """Tests for the CAPABILITY_MODELS constant."""

    def test_has_expected_capabilities(self):
        from packages.router.capabilities import CAPABILITY_MODELS
        expected = {"research", "scripting", "compression", "trend_analysis",
                     "code_generation", "quick", "creative", "seo", "visual_planning"}
        assert expected.issubset(set(CAPABILITY_MODELS.keys()))

    def test_values_are_strings(self):
        from packages.router.capabilities import CAPABILITY_MODELS
        for key, val in CAPABILITY_MODELS.items():
            assert isinstance(key, str)
            assert isinstance(val, str)
            assert len(val) > 0

    def test_values_use_provider_syntax(self):
        from packages.router.capabilities import CAPABILITY_MODELS
        for key, val in CAPABILITY_MODELS.items():
            assert "/" in val or val == "auto", f"{key}: '{val}' should use provider/model syntax"

    def test_research_capability(self):
        from packages.router.capabilities import CAPABILITY_MODELS
        assert CAPABILITY_MODELS["research"] == "openrouter/qwen/qwen3.6-plus:free"

    def test_scripting_capability(self):
        from packages.router.capabilities import CAPABILITY_MODELS
        assert CAPABILITY_MODELS["scripting"] == "openrouter/qwen/qwen3.6-plus:free"


class TestLoadOverrides:
    """Tests for _load_overrides()."""

    def test_returns_empty_when_no_file(self):
        from packages.router.capabilities import _load_overrides
        # capabilities.yaml should not exist in test env
        result = _load_overrides()
        assert result == {}

    @patch("packages.router.capabilities._OVERRIDE_PATH")
    def test_returns_empty_on_yaml_error(self, mock_path, tmp_path):
        from packages.router.capabilities import _load_overrides
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text(": invalid: yaml: content: [")
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = bad_file.read_text()
        result = _load_overrides()
        assert result == {}

    @patch("packages.router.capabilities._OVERRIDE_PATH")
    def test_returns_overrides_when_valid_yaml(self, mock_path, tmp_path):
        from packages.router.capabilities import _load_overrides
        override_file = tmp_path / "override.yaml"
        override_file.write_text("research: custom/model\nscripting: other/model\n")
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = override_file.read_text()
        result = _load_overrides()
        assert result == {"research": "custom/model", "scripting": "other/model"}

    @patch("packages.router.capabilities._OVERRIDE_PATH")
    def test_returns_empty_when_yaml_not_dict(self, mock_path, tmp_path):
        from packages.router.capabilities import _load_overrides
        list_file = tmp_path / "list.yaml"
        list_file.write_text("- item1\n- item2\n")
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = list_file.read_text()
        result = _load_overrides()
        assert result == {}


class TestGetModelForCapability:
    """Tests for get_model_for_capability()."""

    @patch("packages.router.capabilities._load_overrides", return_value={})
    def test_known_capability(self, mock_load):
        from packages.router.capabilities import get_model_for_capability
        model = get_model_for_capability("research")
        assert model == "openrouter/qwen/qwen3.6-plus:free"

    @patch("packages.router.capabilities._load_overrides", return_value={})
    def test_unknown_capability_falls_back_to_auto(self, mock_load):
        from packages.router.capabilities import get_model_for_capability
        model = get_model_for_capability("nonexistent_capability")
        assert model == "auto"

    @patch("packages.router.capabilities._load_overrides",
           return_value={"research": "custom/override-model"})
    def test_override_wins_over_default(self, mock_load):
        from packages.router.capabilities import get_model_for_capability
        model = get_model_for_capability("research")
        # Override from capabilities.yaml takes priority over ROUTES default
        assert model == "custom/override-model"

    @patch("packages.router.capabilities._load_overrides", return_value={})
    def test_all_known_capabilities_return_valid_model(self, mock_load):
        from packages.router.capabilities import get_model_for_capability, CAPABILITY_MODELS
        for cap in CAPABILITY_MODELS:
            model = get_model_for_capability(cap)
            assert model != "auto", f"{cap} should resolve to a real model"
            assert isinstance(model, str)

    @patch("packages.router.capabilities._load_overrides", return_value={})
    def test_empty_string_capability_returns_auto(self, mock_load):
        from packages.router.capabilities import get_model_for_capability
        model = get_model_for_capability("")
        assert model == "auto"


class TestListCapabilities:
    """Tests for list_capabilities()."""

    def test_returns_list(self):
        from packages.router.capabilities import list_capabilities
        result = list_capabilities()
        assert isinstance(result, list)

    def test_returns_all_known_capabilities(self):
        from packages.router.capabilities import list_capabilities, CAPABILITY_MODELS
        result = list_capabilities()
        assert set(result) == set(CAPABILITY_MODELS.keys())

    def test_does_not_include_auto(self):
        from packages.router.capabilities import list_capabilities
        result = list_capabilities()
        assert "auto" not in result
