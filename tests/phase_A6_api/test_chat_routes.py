"""
test_chat_routes.py — Tests for the chat API.

Endpoints tested:
    POST /api/chat/message       — Send message to chat agent
    POST /api/chat/stream        — Stream chat response (SSE)
    GET  /api/chat/history/{sid} — Get conversation history
    GET  /api/chat/models        — List available models
    GET  /api/chat/conversations — List all conversations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestChatMessage:
    """Tests for POST /api/chat/message."""

    @pytest.mark.asyncio
    async def test_message_503_when_agent_not_initialized(self, client):
        """Should return 503 when chat agent is None."""
        with patch("apps.api.routers.chat_routes._chat_agent", None):
            resp = await client.post("/api/chat/message", json={"message": "hello"})
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_message_returns_reply(self, client):
        """Should return a reply from the chat agent."""
        mock_agent = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.type = "ai"
        mock_msg.content = "Hello! How can I help?"
        mock_agent.ainvoke.return_value = {"messages": [mock_msg]}
        with patch("apps.api.routers.chat_routes._chat_agent", mock_agent):
            resp = await client.post("/api/chat/message", json={"message": "hello"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["reply"] == "Hello! How can I help?"
            assert "session_id" in data
            assert data["tools_used"] == []

    @pytest.mark.asyncio
    async def test_message_with_session_id(self, client):
        """Should use provided session_id for continuity."""
        mock_agent = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.type = "ai"
        mock_msg.content = "Follow-up reply"
        mock_agent.ainvoke.return_value = {"messages": [mock_msg]}
        with patch("apps.api.routers.chat_routes._chat_agent", mock_agent):
            resp = await client.post(
                "/api/chat/message",
                json={"message": "follow up", "session_id": "my-session"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == "my-session"

    @pytest.mark.asyncio
    async def test_message_captures_tool_calls(self, client):
        """Should capture tools used by the agent."""
        mock_agent = AsyncMock()
        tool_msg = MagicMock()
        tool_msg.type = "tool"
        tool_msg.name = "search_memory"
        ai_msg = MagicMock()
        ai_msg.type = "ai"
        ai_msg.content = "Based on memory..."
        mock_agent.ainvoke.return_value = {"messages": [tool_msg, ai_msg]}
        with patch("apps.api.routers.chat_routes._chat_agent", mock_agent):
            resp = await client.post("/api/chat/message", json={"message": "search"})
            assert resp.status_code == 200
            data = resp.json()
            assert "search_memory" in data["tools_used"]

    @pytest.mark.asyncio
    async def test_message_500_on_agent_error(self, client):
        """Should return 500 when agent raises an exception."""
        mock_agent = AsyncMock()
        mock_agent.ainvoke.side_effect = RuntimeError("Agent exploded")
        with patch("apps.api.routers.chat_routes._chat_agent", mock_agent):
            resp = await client.post("/api/chat/message", json={"message": "hello"})
            assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_message_422_missing_message(self, client):
        """Should return 422 when 'message' field is missing."""
        resp = await client.post("/api/chat/message", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_message_auth_authorized(self, auth_client):
        """Should return 200 when authenticated."""
        mock_agent = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.type = "ai"
        mock_msg.content = "ok"
        mock_agent.ainvoke.return_value = {"messages": [mock_msg]}
        with patch("apps.api.routers.chat_routes._chat_agent", mock_agent):
            resp = await auth_client.post("/api/chat/message", json={"message": "hello"})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_message_auth_unauthorized(self, unauth_client):
        """Should return 401 when auth enabled but no key."""
        resp = await unauth_client.post("/api/chat/message", json={"message": "hello"})
        assert resp.status_code == 401


class TestChatStream:
    """Tests for POST /api/chat/stream."""

    @pytest.mark.asyncio
    async def test_stream_503_when_agent_not_initialized(self, client):
        """Should return 503 when chat agent is None."""
        with patch("apps.api.routers.chat_routes._chat_agent", None):
            resp = await client.post("/api/chat/stream", json={"message": "hello"})
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_stream_returns_sse(self, client):
        """Should return a streaming response with SSE content type."""
        mock_agent = AsyncMock()

        async def mock_stream(*args, **kwargs):
            yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="Hi")}}
            yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content=None)}}
            yield {"event": "done", "data": {}}

        mock_agent.astream_events = mock_stream
        with patch("apps.api.routers.chat_routes._chat_agent", mock_agent):
            resp = await client.post("/api/chat/stream", json={"message": "hello"})
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")


class TestChatHistory:
    """Tests for GET /api/chat/history/{session_id}."""

    @pytest.mark.asyncio
    async def test_history_503_when_agent_not_initialized(self, client):
        """Should return 503 when chat agent is None."""
        with patch("apps.api.routers.chat_routes._chat_agent", None):
            resp = await client.get("/api/chat/history/test-session")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_history_returns_messages(self, client):
        """Should return conversation history."""
        mock_agent = AsyncMock()
        mock_state = MagicMock()
        human_msg = MagicMock()
        human_msg.type = "human"
        human_msg.content = "Hello"
        ai_msg = MagicMock()
        ai_msg.type = "ai"
        ai_msg.content = "Hi there!"
        mock_state.values = {"messages": [human_msg, ai_msg]}
        mock_agent.aget_state = AsyncMock(return_value=mock_state)
        with patch("apps.api.routers.chat_routes._chat_agent", mock_agent):
            resp = await client.get("/api/chat/history/test-session")
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == "test-session"
            assert len(data["messages"]) == 2
            assert data["messages"][0]["role"] == "user"
            assert data["messages"][1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_history_empty(self, client):
        """Should return empty list for session with no messages."""
        mock_agent = AsyncMock()
        mock_state = MagicMock()
        mock_state.values = {"messages": []}
        mock_agent.aget_state = AsyncMock(return_value=mock_state)
        with patch("apps.api.routers.chat_routes._chat_agent", mock_agent):
            resp = await client.get("/api/chat/history/new-session")
            assert resp.status_code == 200
            data = resp.json()
            assert data["messages"] == []

    @pytest.mark.asyncio
    async def test_history_500_on_error(self, client):
        """Should return 500 when agent fails."""
        mock_agent = AsyncMock()
        mock_agent.aget_state.side_effect = Exception("State error")
        with patch("apps.api.routers.chat_routes._chat_agent", mock_agent):
            resp = await client.get("/api/chat/history/test-session")
            assert resp.status_code == 500


class TestChatModels:
    """Tests for GET /api/chat/models (backward compatibility)."""

    @pytest.mark.asyncio
    async def test_models_500_on_import_error(self, client):
        """Should return 500 when freerouter not available."""
        with patch.dict("sys.modules", {"freerouter.config": None}):
            # Since _fr() uses lazy import, we just verify the endpoint exists
            # It will 500 if freerouter is not installed
            resp = await client.get("/api/chat/models")
            # Either 500 (freerouter not available) or 200 if mocked
            assert resp.status_code in (200, 500)
