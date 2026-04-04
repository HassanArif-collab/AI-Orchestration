"""
Phase A.9 Batch C — tests for packages/content_factory/chat/tools.py
5 @tool functions: query_kanban, query_memory, search_web, query_youtube, query_research.
Each returns string, never crashes.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.content_factory.chat.tools import (
    HAS_LANGCHAIN,
    query_kanban,
    query_memory,
    query_research,
    query_youtube,
    search_web,
)


# ─── Shared Helpers ───────────────────────────────────────────────────────


def _make_mock_supabase_module(get_supabase_fn):
    """Create a mock module for packages.core.supabase_client."""
    mod = ModuleType("mock_supabase_client")
    mod.get_supabase = get_supabase_fn
    return mod


async def _call_tool(tool_fn, **kwargs):
    """Invoke a LangChain StructuredTool or call a plain async function.

    When HAS_LANGCHAIN is True the @tool decorator wraps the async def
    into a StructuredTool instance which is not directly awaitable.
    We must use .ainvoke(dict) in that case.  When langchain is absent
    the decorator is a no-op and the raw async function accepts a single
    positional argument.
    """
    if HAS_LANGCHAIN:
        return await tool_fn.ainvoke(kwargs)
    else:
        arg = list(kwargs.values())[0]
        return await tool_fn(arg)


def _make_mock_zep_module(get_client_fn):
    """Create a mock module for packages.memory.client."""
    mod = ModuleType("mock_memory_client")
    mod.get_async_zep_client = get_client_fn
    return mod


def _make_mock_web_search_module(cls):
    """Create a mock module for packages.router.web_search."""
    mod = ModuleType("mock_web_search")
    mod.WebSearchClient = cls
    return mod


def _make_mock_youtube_module(cls):
    """Create a mock module for packages.integrations.youtube.client."""
    mod = ModuleType("mock_youtube")
    mod.YouTubeClient = cls
    return mod


# ─── Decorator Validation ─────────────────────────────────────────────────


class TestToolDecorator:
    """Verify the @tool decorator is applied correctly."""

    def test_all_functions_are_tools(self):
        """Each tool function should have _is_tool=True or be a langchain StructuredTool."""
        for fn in [query_kanban, query_memory, search_web, query_youtube, query_research]:
            if HAS_LANGCHAIN:
                # langchain @tool wraps into a StructuredTool
                assert callable(fn) or hasattr(fn, "invoke")
            else:
                assert getattr(fn, "_is_tool", False) is True

    @pytest.mark.asyncio
    async def test_all_functions_return_strings(self):
        """Quick smoke test: all tools return str even on error."""
        # Patch everything to raise
        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: (_ for _ in ()).throw(Exception("no db"))),
            "packages.memory.client": _make_mock_zep_module(
                MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=MagicMock(
                        search_memory=AsyncMock(side_effect=Exception("no zep"))
                    )),
                    __aexit__=AsyncMock(return_value=False),
                ))
            ),
            "packages.router.web_search": _make_mock_web_search_module(
                MagicMock(
                    return_value=AsyncMock(
                        __aenter__=AsyncMock(return_value=MagicMock(
                            search=AsyncMock(side_effect=Exception("no web"))
                        )),
                        __aexit__=AsyncMock(return_value=False),
                    )
                )
            ),
            "packages.integrations.youtube.client": _make_mock_youtube_module(
                MagicMock(side_effect=Exception("no yt"))
            ),
        }):
            # Each tool declares its own parameter name via the @tool signature.
            # When HAS_LANGCHAIN=True, ainvoke() validates the dict against the
            # auto-generated Pydantic schema, so we must use the exact key.
            tool_params = {
                query_kanban: {"question": "test query"},
                query_memory: {"question": "test query"},
                query_youtube: {"question": "test query"},
                search_web: {"query": "test query"},
                query_research: {"topic": "test query"},
            }
            for fn, kwargs in tool_params.items():
                result = await _call_tool(fn, **kwargs)
                assert isinstance(result, str)


# ─── query_kanban ─────────────────────────────────────────────────────────


class TestQueryKanban:
    """Test the query_kanban chat tool."""

    @pytest.mark.asyncio
    async def test_returns_board_summary(self):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.execute.return_value.data = [
            {
                "id": "card-abc123",
                "status": "in_progress",
                "column": 1,
                "topic_brief": '{"title": "AI Trends 2025"}',
                "viability_score": 92,
            }
        ]

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_kanban, question="what is on the board?")

        assert isinstance(result, str)
        assert "AI Trends 2025" in result
        assert "92" in result
        assert "1 cards" in result

    @pytest.mark.asyncio
    async def test_empty_board(self):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.execute.return_value.data = []

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_kanban, question="show board")

        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_none_data(self):
        """result.data is None should be handled."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.execute.return_value.data = None

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_kanban, question="status?")

        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_topic_brief_is_string_not_dict(self):
        """topic_brief can be a raw JSON string — should be parsed."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.execute.return_value.data = [
            {"id": "c1", "status": "new", "column": 0,
             "topic_brief": "NOT JSON!!!", "viability_score": 50}
        ]

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_kanban, question="board")

        assert isinstance(result, str)
        assert "Untitled" in result  # brief becomes {} -> title is Untitled

    @pytest.mark.asyncio
    async def test_error_fallback_string(self):
        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(
                lambda: (_ for _ in ()).throw(Exception("DB connection failed"))
            ),
        }):
            result = await _call_tool(query_kanban, question="anything")

        assert isinstance(result, str)
        assert "Could not query Kanban" in result


# ─── query_memory ─────────────────────────────────────────────────────────


class TestQueryMemory:
    """Test the query_memory chat tool."""

    @pytest.mark.asyncio
    async def test_returns_memories(self):
        mock_zep = MagicMock()
        mock_zep.search_memory = AsyncMock(return_value=[
            {"fact": "Audience prefers listicle formats"},
            {"fact": "Hook within first 3 seconds boosts retention"},
        ])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_zep)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.ZEP_AUDIENCE_USER_ID = "aud-1"
        mock_settings.ZEP_LEARNING_USER_ID = "learn-1"

        with patch.dict("sys.modules", {
            "packages.memory.client": _make_mock_zep_module(lambda: mock_ctx),
            "packages.core.config": MagicMock(get_settings=lambda: mock_settings),
        }):
            result = await _call_tool(query_memory, question="what hooks work?")

        assert isinstance(result, str)
        # audience_results (2) + learning_results (2) = 4 total
        assert "4 relevant memories" in result
        assert "listicle" in result

    @pytest.mark.asyncio
    async def test_no_results(self):
        mock_zep = MagicMock()
        mock_zep.search_memory = AsyncMock(return_value=[])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_zep)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.ZEP_AUDIENCE_USER_ID = "a"
        mock_settings.ZEP_LEARNING_USER_ID = "l"

        with patch.dict("sys.modules", {
            "packages.memory.client": _make_mock_zep_module(lambda: mock_ctx),
            "packages.core.config": MagicMock(get_settings=lambda: mock_settings),
        }):
            result = await _call_tool(query_memory, question="obscure topic")

        assert "No relevant memories" in result

    @pytest.mark.asyncio
    async def test_error_fallback(self):
        with patch.dict("sys.modules", {
            "packages.memory.client": _make_mock_zep_module(
                MagicMock(side_effect=Exception("Zep unavailable"))
            ),
            "packages.core.config": MagicMock(
                get_settings=MagicMock(side_effect=Exception("config error"))
            ),
        }):
            result = await _call_tool(query_memory, question="something")

        assert isinstance(result, str)
        assert "Could not query Zep" in result

    @pytest.mark.asyncio
    async def test_memory_uses_content_fallback(self):
        """Results without 'fact' key should use 'content' key."""
        mock_zep = MagicMock()
        mock_zep.search_memory = AsyncMock(return_value=[
            {"content": "Learned content text"},
        ])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_zep)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.ZEP_AUDIENCE_USER_ID = "a"
        mock_settings.ZEP_LEARNING_USER_ID = "l"

        with patch.dict("sys.modules", {
            "packages.memory.client": _make_mock_zep_module(lambda: mock_ctx),
            "packages.core.config": MagicMock(get_settings=lambda: mock_settings),
        }):
            result = await _call_tool(query_memory, question="test")

        assert isinstance(result, str)
        assert "Learned content text" in result


# ─── search_web ───────────────────────────────────────────────────────────


class TestSearchWeb:
    """Test the search_web chat tool."""

    @pytest.mark.asyncio
    async def test_returns_results(self):
        mock_result = MagicMock()
        mock_result.title = "AI in 2025"
        mock_result.url = "https://example.com/ai"
        mock_result.snippet = "Artificial intelligence continues to reshape industries."

        mock_client = MagicMock()
        mock_client.search = AsyncMock(return_value=[mock_result, mock_result])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        MockWSC = MagicMock(return_value=mock_ctx)

        with patch.dict("sys.modules", {
            "packages.router.web_search": _make_mock_web_search_module(MockWSC),
        }):
            result = await _call_tool(search_web, query="AI trends 2025")

        assert isinstance(result, str)
        assert "AI in 2025" in result
        assert "example.com" in result

    @pytest.mark.asyncio
    async def test_no_results(self):
        mock_client = MagicMock()
        mock_client.search = AsyncMock(return_value=[])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        MockWSC = MagicMock(return_value=mock_ctx)

        with patch.dict("sys.modules", {
            "packages.router.web_search": _make_mock_web_search_module(MockWSC),
        }):
            result = await _call_tool(search_web, query="very obscure query xyz")

        assert isinstance(result, str)
        assert "No web results" in result

    @pytest.mark.asyncio
    async def test_error_fallback(self):
        with patch.dict("sys.modules", {
            "packages.router.web_search": _make_mock_web_search_module(
                MagicMock(side_effect=Exception("Web search service down"))
            ),
        }):
            result = await _call_tool(search_web, query="test")

        assert isinstance(result, str)
        assert "Web search failed" in result

    @pytest.mark.asyncio
    async def test_snippet_truncation(self):
        """Snippet longer than 200 chars should be truncated."""
        mock_result = MagicMock()
        mock_result.title = "Long Article"
        mock_result.url = "https://example.com"
        mock_result.snippet = "x" * 300

        mock_client = MagicMock()
        mock_client.search = AsyncMock(return_value=[mock_result])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        MockWSC = MagicMock(return_value=mock_ctx)

        with patch.dict("sys.modules", {
            "packages.router.web_search": _make_mock_web_search_module(MockWSC),
        }):
            result = await _call_tool(search_web, query="test")

        # The snippet is sliced to [:200] in the tool
        assert "xxx" in result  # first 200 chars
        # The raw 300-char snippet should not appear verbatim
        assert result.count("x") < 300


# ─── query_youtube ────────────────────────────────────────────────────────


class TestQueryYouTube:
    """Test the query_youtube chat tool."""

    @pytest.mark.asyncio
    async def test_returns_competitor_videos(self):
        mock_yt = MagicMock()
        mock_yt.get_competitor_videos = MagicMock(return_value=[
            {"title": "Viral Video 1", "channel_title": "Creator A", "views": 1500000},
            {"title": "Viral Video 2", "channel_title": "Creator B", "views": 800000},
        ])

        MockYT = MagicMock(return_value=mock_yt)
        mock_settings = MagicMock()
        mock_settings.YOUTUBE_API_KEY = "fake-key"

        with patch.dict("sys.modules", {
            "packages.integrations.youtube.client": _make_mock_youtube_module(MockYT),
            "packages.core.config": MagicMock(get_settings=lambda: mock_settings),
        }):
            result = await _call_tool(query_youtube, question="competitor analysis")

        assert isinstance(result, str)
        assert "Viral Video 1" in result
        assert "1,500,000" in result
        assert "Recent Competitor Videos" in result

    @pytest.mark.asyncio
    async def test_no_competitor_data(self):
        mock_yt = MagicMock()
        mock_yt.get_competitor_videos = MagicMock(return_value=[])

        MockYT = MagicMock(return_value=mock_yt)
        mock_settings = MagicMock()
        mock_settings.YOUTUBE_API_KEY = "fake-key"

        with patch.dict("sys.modules", {
            "packages.integrations.youtube.client": _make_mock_youtube_module(MockYT),
            "packages.core.config": MagicMock(get_settings=lambda: mock_settings),
        }):
            result = await _call_tool(query_youtube, question="what's trending")

        assert isinstance(result, str)
        assert "No YouTube data" in result

    @pytest.mark.asyncio
    async def test_error_fallback(self):
        with patch.dict("sys.modules", {
            "packages.integrations.youtube.client": _make_mock_youtube_module(
                MagicMock(side_effect=Exception("YouTube API quota exceeded"))
            ),
            "packages.core.config": MagicMock(
                get_settings=MagicMock(side_effect=Exception("config error"))
            ),
        }):
            result = await _call_tool(query_youtube, question="channels")

        assert isinstance(result, str)
        assert "YouTube query failed" in result

    @pytest.mark.asyncio
    async def test_none_views_returns_error_fallback(self):
        """Video with None views causes format error — source code bug.
        
        The source code uses f"{v.get('views', 0):,}" which raises TypeError
        when views is None (NoneType doesn't support :,: format spec).
        This is caught by the outer try/except and returns an error string.
        """
        mock_yt = MagicMock()
        mock_yt.get_competitor_videos = MagicMock(return_value=[
            {"title": "Test", "channel_title": "Ch", "views": None},
        ])

        MockYT = MagicMock(return_value=mock_yt)
        mock_settings = MagicMock()
        mock_settings.YOUTUBE_API_KEY = "key"

        with patch.dict("sys.modules", {
            "packages.integrations.youtube.client": _make_mock_youtube_module(MockYT),
            "packages.core.config": MagicMock(get_settings=lambda: mock_settings),
        }):
            result = await _call_tool(query_youtube, question="test")

        assert isinstance(result, str)
        assert "YouTube query failed" in result


# ─── query_research ───────────────────────────────────────────────────────


class TestQueryResearch:
    """Test the query_research chat tool."""

    @pytest.mark.asyncio
    async def test_returns_dossiers(self):
        mock_sb = MagicMock()
        chain = mock_sb.table.return_value.select.return_value \
            .ilike.return_value.order.return_value.limit.return_value.execute.return_value
        chain.data = [
            {
                "topic": {"title": "AI in Healthcare"},
                "dossier": "Artificial intelligence is transforming healthcare...",
                "sources": [{"url": "https://a.com"}, {"url": "https://b.com"}],
                "created_at": "2025-01-15T10:00:00Z",
            }
        ]

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_research, topic="AI healthcare")

        assert isinstance(result, str)
        assert "1 research dossiers" in result
        assert "AI in Healthcare" in result
        assert "Sources: 2" in result

    @pytest.mark.asyncio
    async def test_no_results(self):
        mock_sb = MagicMock()
        chain = mock_sb.table.return_value.select.return_value \
            .ilike.return_value.order.return_value.limit.return_value.execute.return_value
        chain.data = []

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_research, topic="obscure topic xyz123")

        assert isinstance(result, str)
        assert "No research dossiers found" in result

    @pytest.mark.asyncio
    async def test_none_data(self):
        mock_sb = MagicMock()
        chain = mock_sb.table.return_value.select.return_value \
            .ilike.return_value.order.return_value.limit.return_value.execute.return_value
        chain.data = None

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_research, topic="test")

        assert "No research dossiers found" in result

    @pytest.mark.asyncio
    async def test_topic_is_string_not_dict(self):
        """topic field can be a string, not a dict."""
        mock_sb = MagicMock()
        chain = mock_sb.table.return_value.select.return_value \
            .ilike.return_value.order.return_value.limit.return_value.execute.return_value
        chain.data = [
            {
                "topic": "AI Trends Research",
                "dossier": "Some research text here about AI trends...",
                "sources": [],
                "created_at": "2025-03-01T12:00:00Z",
            }
        ]

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_research, topic="AI")

        assert isinstance(result, str)
        assert "AI Trends" in result

    @pytest.mark.asyncio
    async def test_empty_dossier(self):
        """Empty dossier string should show 'Empty'."""
        mock_sb = MagicMock()
        chain = mock_sb.table.return_value.select.return_value \
            .ilike.return_value.order.return_value.limit.return_value.execute.return_value
        chain.data = [
            {
                "topic": {"title": "Test"},
                "dossier": "",
                "sources": None,
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_research, topic="test")

        assert isinstance(result, str)
        assert "Empty" in result
        assert "Sources: 0" in result

    @pytest.mark.asyncio
    async def test_error_fallback(self):
        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(
                lambda: (_ for _ in ()).throw(Exception("Supabase down"))
            ),
        }):
            result = await _call_tool(query_research, topic="anything")

        assert isinstance(result, str)
        assert "Research query failed" in result

    @pytest.mark.asyncio
    async def test_dossier_preview_truncated(self):
        """Dossier text longer than 300 chars should be truncated with '...'."""
        mock_sb = MagicMock()
        chain = mock_sb.table.return_value.select.return_value \
            .ilike.return_value.order.return_value.limit.return_value.execute.return_value
        chain.data = [
            {
                "topic": {"title": "Long Topic"},
                "dossier": "x" * 500,
                "sources": [],
                "created_at": "2025-06-01T00:00:00Z",
            }
        ]

        with patch.dict("sys.modules", {
            "packages.core.supabase_client": _make_mock_supabase_module(lambda: mock_sb),
        }):
            result = await _call_tool(query_research, topic="long")

        assert "..." in result
        assert "Long Topic" in result
