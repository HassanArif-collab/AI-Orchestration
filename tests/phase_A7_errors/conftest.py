"""
conftest.py — Shared fixtures for Phase A.7 Error Handling tests.

Provides:
  - tmp_dlq_dir: Temporary directory for dead letter queue tests
  - mock_get_settings: Patches get_settings to use temp data dir
  - clear_cb_registry: Cleans up global circuit breaker registry
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def tmp_dlq_dir(tmp_path):
    """Provide a temporary directory for DLQ file operations."""
    return tmp_path


@pytest.fixture
def mock_get_settings(tmp_dlq_dir):
    """Patch get_settings to use a temporary DATA_DIR."""
    mock_settings = type("MockSettings", (), {"DATA_DIR": str(tmp_dlq_dir)})()
    with patch("packages.core.dead_letter.get_settings", return_value=mock_settings):
        yield mock_settings


@pytest.fixture(autouse=True)
def clear_cb_registry():
    """Clear global circuit breaker registry before/after each test."""
    from packages.core import circuit_breaker
    circuit_breaker._circuit_breakers.clear()
    yield
    circuit_breaker._circuit_breakers.clear()
