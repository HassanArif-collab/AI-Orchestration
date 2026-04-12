"""Tests for packages/memory/helpers.py — Memory helper functions.

NOTE: The helper functions have a known pattern where they return the raw
OperationResult object rather than the data. Tests verify the actual behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestStoreResearch:
    """Tests for store_research()."""

    @pytest.mark.asyncio
    @patch("packages.memory.helpers._get_client")
    async def test_store_research_calls_add_message(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.add_message = AsyncMock()
        mock_get_client.return_value = mock_client

        from packages.memory.helpers import store_research
        await store_research(
            session_id="test-session",
            topic="AI in Pakistan",
            facts=["Fact 1", "Fact 2", "Fact 3"],
            sources=["https://source1.com", "https://source2.com"],
        )

        mock_client.add_message.assert_called_once()
        call_kwargs = mock_client.add_message.call_args.kwargs
        assert call_kwargs["session_id"] == "test-session"
        assert call_kwargs["role"] == "assistant"
        assert "AI in Pakistan" in call_kwargs["content"]
        assert "Fact 1" in call_kwargs["content"]
        assert "Fact 2" in call_kwargs["content"]
        assert "Fact 3" in call_kwargs["content"]
        assert "https://source1.com" in call_kwargs["content"]
        assert call_kwargs["metadata"]["type"] == "research"

    @pytest.mark.asyncio
    @patch("packages.memory.helpers._get_client")
    async def test_store_research_without_sources(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.add_message = AsyncMock()
        mock_get_client.return_value = mock_client

        from packages.memory.helpers import store_research
        await store_research(
            session_id="test-session",
            topic="Test Topic",
            facts=["Only fact"],
            sources=[],
        )

        content = mock_client.add_message.call_args.kwargs["content"]
        assert "Sources:" not in content

    @pytest.mark.asyncio
    @patch("packages.memory.helpers._get_client")
    async def test_store_research_formats_facts_numbered(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.add_message = AsyncMock()
        mock_get_client.return_value = mock_client

        from packages.memory.helpers import store_research
        await store_research("sid", "topic", ["A", "B", "C"], [])

        content = mock_client.add_message.call_args.kwargs["content"]
        assert "1. A" in content
        assert "2. B" in content
        assert "3. C" in content


class TestStoreScriptFeedback:
    """Tests for store_script_feedback()."""

    @pytest.mark.asyncio
    @patch("packages.memory.helpers._get_client")
    async def test_calls_add_message_with_feedback(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.add_message = AsyncMock()
        mock_get_client.return_value = mock_client

        from packages.memory.helpers import store_script_feedback
        await store_script_feedback(
            session_id="test-session",
            feedback="The hook needs more energy",
            revision=2,
        )

        mock_client.add_message.assert_called_once()
        call_kwargs = mock_client.add_message.call_args.kwargs
        assert call_kwargs["session_id"] == "test-session"
        assert call_kwargs["role"] == "user"
        assert "Revision #2" in call_kwargs["content"]
        assert "The hook needs more energy" in call_kwargs["content"]
        assert call_kwargs["metadata"]["type"] == "script_feedback"
        assert call_kwargs["metadata"]["revision"] == 2


class TestRecallStyle:
    """Tests for recall_style()."""

    @pytest.mark.asyncio
    @patch("packages.memory.helpers._get_client")
    async def test_searches_with_style_session(self, mock_get_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = [{"fact": "Use formal tone"}]
        mock_client.search_memory = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client

        from packages.memory.helpers import recall_style
        result = await recall_style("user-123")

        mock_client.search_memory.assert_called_once()
        call_args = mock_client.search_memory.call_args
        # search_memory(session_id, query, limit=5)
        assert call_args[0][0] == "user-123_style"
        assert "content style preferences" in call_args[0][1]
        assert call_args.kwargs["limit"] == 5
        # The code returns {"facts": result.data} (extracted from OperationResult)
        assert "facts" in result
        assert result["facts"] == mock_result.data

    @pytest.mark.asyncio
    @patch("packages.memory.helpers._get_client")
    async def test_returns_empty_when_no_results(self, mock_get_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = []
        mock_client.search_memory = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client

        from packages.memory.helpers import recall_style
        result = await recall_style("user-123")
        # When result.data is [], the function returns empty dict (falsy data)
        assert result == {}


class TestRecallVideoPerformance:
    """Tests for recall_video_performance()."""

    @pytest.mark.asyncio
    @patch("packages.memory.helpers._get_client")
    async def test_searches_with_analytics_session(self, mock_get_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = [
            {"fact": "Video X had 72% retention"},
            {"fact": "Video Y performed well"},
        ]
        mock_client.search_memory = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client

        from packages.memory.helpers import recall_video_performance
        result = await recall_video_performance("user-456", "best performing videos")

        mock_client.search_memory.assert_called_once()
        call_args = mock_client.search_memory.call_args
        assert call_args[0][0] == "user-456_analytics"
        assert call_args[0][1] == "best performing videos"
        assert call_args.kwargs["limit"] == 10
        # Function returns result.data (extracted from OperationResult)
        assert result == mock_result.data

    @pytest.mark.asyncio
    @patch("packages.memory.helpers._get_client")
    async def test_returns_empty_on_no_results(self, mock_get_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = []
        mock_client.search_memory = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client

        from packages.memory.helpers import recall_video_performance
        result = await recall_video_performance("user-456", "test query")
        # When result.data is [], the function returns empty list (falsy data)
        assert result == []


class TestGetClient:
    """Tests for _get_client() singleton behavior."""

    def test_creates_client_on_first_call(self):
        import packages.memory.helpers as helpers_mod
        helpers_mod._shared_client = None

        instance = MagicMock()

        with patch("packages.memory.helpers.AsyncZepMemoryClient", return_value=instance):
            from packages.memory.helpers import _get_client
            client = _get_client()
            assert client is instance
            assert helpers_mod._shared_client is instance

        # Reset
        helpers_mod._shared_client = None
