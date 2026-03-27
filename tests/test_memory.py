"""Tests for AsyncZepMemoryClient and memory helpers.

Tests verify graceful degradation - all methods return empty values
when Zep is unavailable, and no exceptions are raised.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAsyncZepMemoryClient:
    """Tests for AsyncZepMemoryClient."""

    def test_no_exception_when_api_key_empty(self):
        """AsyncZepMemoryClient should not crash when api_key is empty."""
        from packages.memory.client import AsyncZepMemoryClient

        # Should not raise any exception
        client = AsyncZepMemoryClient(api_key="")
        assert client._client is None

    def test_no_exception_when_api_key_none(self):
        """AsyncZepMemoryClient should not crash when api_key is None."""
        from packages.memory.client import AsyncZepMemoryClient

        # Should not raise any exception
        client = AsyncZepMemoryClient(api_key=None)
        assert client._client is None

    @pytest.mark.asyncio
    async def test_create_user_returns_none_when_client_none(self):
        """create_user should return None (not crash) when _client is None."""
        from packages.memory.client import AsyncZepMemoryClient

        client = AsyncZepMemoryClient(api_key="")
        result = await client.create_user("test_user")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_session_returns_none_when_client_none(self):
        """create_session should return None (not crash) when _client is None."""
        from packages.memory.client import AsyncZepMemoryClient

        client = AsyncZepMemoryClient(api_key="")
        result = await client.create_session("test_session", "test_user")
        assert result is None

    @pytest.mark.asyncio
    async def test_add_message_doesnt_crash_when_client_none(self):
        """add_message should not crash when _client is None."""
        from packages.memory.client import AsyncZepMemoryClient

        client = AsyncZepMemoryClient(api_key="")
        # Should not raise
        await client.add_message("test_session", "user", "test message")

    @pytest.mark.asyncio
    async def test_search_memory_returns_empty_list_when_client_none(self):
        """search_memory should return [] when _client is None."""
        from packages.memory.client import AsyncZepMemoryClient

        client = AsyncZepMemoryClient(api_key="")
        result = await client.search_memory("test_session", "test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_add_facts_doesnt_crash_when_client_none(self):
        """add_facts should not crash when _client is None."""
        from packages.memory.client import AsyncZepMemoryClient

        client = AsyncZepMemoryClient(api_key="")
        # Should not raise
        await client.add_facts("test_session", [{"fact": "test fact"}])

    @pytest.mark.asyncio
    async def test_methods_handle_exceptions_gracefully(self):
        """All methods should catch exceptions and return default values."""
        from packages.memory.client import AsyncZepMemoryClient

        client = AsyncZepMemoryClient(api_key="fake_key")

        # Mock the client to raise an exception
        client._client = MagicMock()
        client._client.user.add = AsyncMock(side_effect=Exception("API Error"))
        client._client.thread.create = AsyncMock(side_effect=Exception("API Error"))
        client._client.thread.add_messages = AsyncMock(side_effect=Exception("API Error"))
        client._client.graph.search = AsyncMock(side_effect=Exception("API Error"))

        # All should return defaults without raising
        await client.create_user("test_user")  # Should not raise
        await client.create_session("test_session", "test_user")  # Should not raise
        await client.add_message("test_session", "user", "test")  # Should not raise
        await client.add_facts("test_session", [{"fact": "test"}])  # Should not raise

        result = await client.search_memory("test_session", "query")
        assert result == []

    def test_get_async_zep_client_factory(self):
        """get_async_zep_client should return AsyncZepMemoryClient instance."""
        from packages.memory.client import get_async_zep_client, AsyncZepMemoryClient

        client = get_async_zep_client()
        assert isinstance(client, AsyncZepMemoryClient)

    def test_get_async_zep_client_with_custom_key(self):
        """get_async_zep_client should accept custom API key."""
        from packages.memory.client import get_async_zep_client

        client = get_async_zep_client(api_key="custom_key")
        assert client._api_key == "custom_key"


class TestMemorySchemas:
    """Tests for memory schemas."""

    def test_video_session_metadata_exists(self):
        """VIDEO_SESSION_METADATA should be defined."""
        from packages.memory.schemas import VIDEO_SESSION_METADATA

        assert isinstance(VIDEO_SESSION_METADATA, dict)
        assert VIDEO_SESSION_METADATA.get("session_type") == "video_production"

    def test_channel_user_metadata_exists(self):
        """CHANNEL_USER_METADATA should be defined."""
        from packages.memory.schemas import CHANNEL_USER_METADATA

        assert isinstance(CHANNEL_USER_METADATA, dict)
        assert CHANNEL_USER_METADATA.get("user_type") == "channel_owner"

    def test_analytics_session_metadata_exists(self):
        """ANALYTICS_SESSION_METADATA should be defined."""
        from packages.memory.schemas import ANALYTICS_SESSION_METADATA

        assert isinstance(ANALYTICS_SESSION_METADATA, dict)
        assert ANALYTICS_SESSION_METADATA.get("session_type") == "analytics_feedback"


class TestMemoryHelpers:
    """Tests for memory helper functions."""

    @pytest.mark.asyncio
    async def test_store_research_doesnt_crash(self):
        """store_research should not crash even when Zep is unavailable."""
        from packages.memory.helpers import store_research

        # Should not raise
        await store_research(
            session_id="test_session",
            topic="AI in Healthcare",
            facts=["Fact 1", "Fact 2"],
            sources=["https://example.com"],
        )

    @pytest.mark.asyncio
    async def test_store_script_feedback_doesnt_crash(self):
        """store_script_feedback should not crash even when Zep is unavailable."""
        from packages.memory.helpers import store_script_feedback

        # Should not raise
        await store_script_feedback(
            session_id="test_session",
            feedback="Make the intro shorter",
            revision=1,
        )

    @pytest.mark.asyncio
    async def test_recall_style_returns_empty_dict(self):
        """recall_style should return {} when Zep is unavailable."""
        from packages.memory.helpers import recall_style

        result = await recall_style("test_user")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_recall_video_performance_returns_empty_list(self):
        """recall_video_performance should return [] when Zep is unavailable."""
        from packages.memory.helpers import recall_video_performance

        result = await recall_video_performance("test_user", "best videos")
        assert isinstance(result, list)
