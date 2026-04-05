"""
test_memory_routes.py — Tests for the memory management API.

Endpoints tested:
    GET  /api/memory/sessions          — List all Zep sessions
    GET  /api/memory/sessions/{id}     — Get messages + facts for a session
    POST /api/memory/search            — Semantic search across memory
    GET  /api/memory/facts/{session_id} — Get structured facts for a session

NOTE: memory_routes does `from apps.api.dependencies import get_memory_client`
at module level. Since routers/__init__.py shadows module names, we must patch
using sys.modules to access the actual module's namespace.
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mod():
    """Get the memory_routes module via sys.modules."""
    return sys.modules["apps.api.routers.memory_routes"]


class TestListSessions:
    """Tests for GET /api/memory/sessions."""

    @pytest.mark.asyncio
    async def test_sessions_returns_empty_when_no_client(self, client):
        """Should return help message when memory client is None."""
        mod = _mod()
        with patch.object(mod, "get_memory_client", return_value=None):
            resp = await client.get("/api/memory/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert data["error"] == "Zep not configured"
            assert data["sessions"] == []

    @pytest.mark.asyncio
    async def test_sessions_returns_session_ids(self, client):
        """Should return session IDs from Zep."""
        mod = _mod()
        mock_client = AsyncMock()
        mock_client._client = MagicMock()
        mock_session = MagicMock()
        mock_session.session_id = "session-1"
        mock_client._client.session.list.return_value = [mock_session]

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.get("/api/memory/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert data["sessions"] == ["session-1"]

    @pytest.mark.asyncio
    async def test_sessions_empty_list(self, client):
        """Should return empty list when no sessions exist."""
        mod = _mod()
        mock_client = AsyncMock()
        mock_client._client = MagicMock()
        mock_client._client.session.list.return_value = []

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.get("/api/memory/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert data["sessions"] == []

    @pytest.mark.asyncio
    async def test_sessions_no_zep_key(self, client):
        """Should return error when ZEP_API_KEY not set."""
        mod = _mod()
        mock_client = AsyncMock()
        mock_client._client = None

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.get("/api/memory/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert "Zep API key not set" in data["error"]

    @pytest.mark.asyncio
    async def test_sessions_500_on_error(self, client):
        """Should return 500 on unexpected error."""
        mod = _mod()
        mock_client = AsyncMock()
        mock_client._client = MagicMock()
        mock_client._client.session.list.side_effect = Exception("Zep connection failed")

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.get("/api/memory/sessions")
            assert resp.status_code == 500


class TestGetSessionMemory:
    """Tests for GET /api/memory/sessions/{session_id}."""

    @pytest.mark.asyncio
    async def test_session_memory_no_client(self, client):
        """Should return empty response when memory client is None."""
        mod = _mod()
        with patch.object(mod, "get_memory_client", return_value=None):
            resp = await client.get("/api/memory/sessions/test-session")
            assert resp.status_code == 200
            data = resp.json()
            assert data["summary"] == ""
            assert data["facts"] == []
            assert data["message_count"] == 0

    @pytest.mark.asyncio
    async def test_session_memory_returns_data(self, client):
        """Should return summary, facts, and message count."""
        mod = _mod()
        mock_client = AsyncMock()
        mock_client._client = MagicMock()
        # search_memory now returns OperationResult with .success and .data
        mock_op_result = MagicMock()
        mock_op_result.success = True
        mock_op_result.data = [{"fact": "Learned fact 1"}]
        mock_client.search_memory = AsyncMock(return_value=mock_op_result)
        mock_client._client.message.list.return_value = [MagicMock(), MagicMock()]

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.get("/api/memory/sessions/test-session")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["facts"]) == 1
            assert data["message_count"] == 2

    @pytest.mark.asyncio
    async def test_session_memory_message_count_error(self, client):
        """Should still return data even if message count fails."""
        mod = _mod()
        mock_client = AsyncMock()
        mock_client._client = MagicMock()
        # search_memory returns OperationResult
        mock_op_result = MagicMock()
        mock_op_result.success = True
        mock_op_result.data = []
        mock_client.search_memory = AsyncMock(return_value=mock_op_result)
        mock_client._client.message.list.side_effect = Exception("msg error")

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.get("/api/memory/sessions/test-session")
            assert resp.status_code == 200
            data = resp.json()
            assert data["message_count"] == 0


class TestSearchMemory:
    """Tests for POST /api/memory/search."""

    @pytest.mark.asyncio
    async def test_search_no_client(self, client):
        """Should return empty list when memory client is None."""
        mod = _mod()
        with patch.object(mod, "get_memory_client", return_value=None):
            resp = await client.post("/api/memory/search", params={"query": "test"})
            assert resp.status_code == 200
            assert resp.json() == []

    @pytest.mark.asyncio
    async def test_search_returns_results(self, client):
        """Should return search results."""
        mod = _mod()
        mock_client = AsyncMock()
        # search_memory returns OperationResult
        mock_op_result = MagicMock()
        mock_op_result.success = True
        mock_op_result.data = [{"fact": "AI topic trending", "score": 0.9}]
        mock_client.search_memory = AsyncMock(return_value=mock_op_result)

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.post("/api/memory/search", params={"query": "AI trends"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["fact"] == "AI topic trending"

    @pytest.mark.asyncio
    async def test_search_with_session_id(self, client):
        """Should pass session_id to the memory client."""
        mod = _mod()
        mock_client = AsyncMock()
        # search_memory returns OperationResult
        mock_op_result = MagicMock()
        mock_op_result.success = True
        mock_op_result.data = []
        mock_client.search_memory = AsyncMock(return_value=mock_op_result)

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.post(
                "/api/memory/search",
                params={"query": "test", "session_id": "my-session"},
            )
            assert resp.status_code == 200
            mock_client.search_memory.assert_called_once_with("my-session", "test")

    @pytest.mark.asyncio
    async def test_search_empty_query(self, client):
        """Should handle empty query string."""
        mod = _mod()
        mock_client = AsyncMock()
        # search_memory returns OperationResult
        mock_op_result = MagicMock()
        mock_op_result.success = True
        mock_op_result.data = []
        mock_client.search_memory = AsyncMock(return_value=mock_op_result)

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.post("/api/memory/search", params={"query": ""})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_auth_authorized(self, auth_client):
        """Should return 200 when authenticated."""
        mod = _mod()
        mock_client = AsyncMock()
        # search_memory returns OperationResult
        mock_op_result = MagicMock()
        mock_op_result.success = True
        mock_op_result.data = []
        mock_client.search_memory = AsyncMock(return_value=mock_op_result)
        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await auth_client.post("/api/memory/search", params={"query": "test"})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_auth_unauthorized(self, unauth_client):
        """Should return 401 when auth enabled but no key."""
        resp = await unauth_client.post("/api/memory/search", params={"query": "test"})
        assert resp.status_code == 401


class TestGetFacts:
    """Tests for GET /api/memory/facts/{session_id}."""

    @pytest.mark.asyncio
    async def test_facts_no_client(self, client):
        """Should return empty list when memory client is None."""
        mod = _mod()
        with patch.object(mod, "get_memory_client", return_value=None):
            resp = await client.get("/api/memory/facts/test-session")
            assert resp.status_code == 200
            assert resp.json() == []

    @pytest.mark.asyncio
    async def test_facts_returns_data(self, client):
        """Should return facts for a session."""
        mod = _mod()
        mock_client = AsyncMock()
        # search_memory now returns OperationResult
        mock_op_result = MagicMock()
        mock_op_result.success = True
        mock_op_result.data = [
            {"fact": "Pakistani audience prefers Urdu"},
            {"fact": "Trending topic: AI in education"},
        ]
        mock_client.search_memory = AsyncMock(return_value=mock_op_result)

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.get("/api/memory/facts/test-session")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert "Urdu" in data[0]["fact"]

    @pytest.mark.asyncio
    async def test_facts_empty_session(self, client):
        """Should return empty list for session with no facts."""
        mod = _mod()
        mock_client = AsyncMock()
        # search_memory returns OperationResult
        mock_op_result = MagicMock()
        mock_op_result.success = True
        mock_op_result.data = []
        mock_client.search_memory = AsyncMock(return_value=mock_op_result)

        with patch.object(mod, "get_memory_client", return_value=mock_client):
            resp = await client.get("/api/memory/facts/empty-session")
            assert resp.status_code == 200
            assert resp.json() == []
