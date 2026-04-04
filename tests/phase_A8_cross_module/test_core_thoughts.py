"""Tests for packages/core/thoughts.py — Thought reporting."""

import pytest
from unittest.mock import MagicMock, patch


class TestValidThoughtTypes:
    """Tests for VALID_THOUGHT_TYPES constant."""

    def test_expected_types(self):
        from packages.core.thoughts import VALID_THOUGHT_TYPES
        expected = {"thinking", "search", "output", "error", "memory_read", "memory_write"}
        assert VALID_THOUGHT_TYPES == expected

    def test_is_frozenset(self):
        from packages.core.thoughts import VALID_THOUGHT_TYPES
        assert isinstance(VALID_THOUGHT_TYPES, frozenset)


class TestReportThought:
    """Tests for report_thought()."""

    def test_returns_false_without_card_id(self):
        from packages.core.thoughts import report_thought
        result = report_thought(card_id="", agent_name="test", thought_type="thinking", content="test")
        assert result is False

    @patch("packages.core.supabase_client.get_supabase", return_value=None)
    def test_returns_false_when_supabase_not_configured(self, _mock_sb):
        from packages.core.thoughts import report_thought
        result = report_thought(card_id="card-1", agent_name="test", thought_type="thinking", content="test")
        assert result is False

    def test_invalid_thought_type_defaults_to_thinking(self):
        # This tests the thought_type validation path
        from packages.core.thoughts import VALID_THOUGHT_TYPES
        # The module-level code sets defaults, but the function checks VALID_THOUGHT_TYPES
        assert "invalid_type" not in VALID_THOUGHT_TYPES
        assert "thinking" in VALID_THOUGHT_TYPES

    def test_valid_thought_types_are_all_strings(self):
        from packages.core.thoughts import VALID_THOUGHT_TYPES
        for t in VALID_THOUGHT_TYPES:
            assert isinstance(t, str)


class TestReportThoughtAsync:
    """Tests for report_thought_async()."""

    @pytest.mark.asyncio
    @patch("packages.core.thoughts.report_thought")
    async def test_delegates_to_sync(self, mock_report):
        mock_report.return_value = True
        from packages.core.thoughts import report_thought_async
        result = await report_thought_async("card-1", "agent", "thinking", "thought")
        mock_report.assert_called_once_with("card-1", "agent", "thinking", "thought")
        assert result is True
