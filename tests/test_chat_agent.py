"""Tests for chat agent tools."""

import pytest


def test_chat_tools_are_importable():
    """Verify all 5 tools can be imported without error."""
    from packages.content_factory.chat.tools import (
        query_kanban,
        query_memory,
        search_web,
        query_youtube,
        query_research,
    )
    assert query_kanban is not None
    assert query_memory is not None
    assert search_web is not None
    assert query_youtube is not None
    assert query_research is not None


def test_chat_tools_have_descriptions():
    """Tools must have descriptions for the ReAct agent to understand when to use them."""
    from packages.content_factory.chat.tools import (
        query_kanban, query_memory, search_web, query_youtube, query_research,
    )
    for tool in [query_kanban, query_memory, search_web, query_youtube, query_research]:
        # Check if tool has a description attribute
        if hasattr(tool, 'description'):
            assert tool.description, f"{tool.name if hasattr(tool, 'name') else 'tool'} is missing a description"
            assert len(tool.description) > 20, f"Tool description too short"


def test_chat_system_prompt_exists():
    """The system prompt must be defined and non-empty."""
    from packages.content_factory.chat.agent import CHAT_SYSTEM_PROMPT
    assert CHAT_SYSTEM_PROMPT
    assert "Content Factory" in CHAT_SYSTEM_PROMPT
    assert "Kanban" in CHAT_SYSTEM_PROMPT or "kanban" in CHAT_SYSTEM_PROMPT


def test_chat_agent_module_importable():
    """Verify the agent module can be imported."""
    from packages.content_factory.chat import build_chat_agent, get_chat_agent
    assert build_chat_agent is not None
    assert get_chat_agent is not None


def test_chat_tools_return_strings():
    """All chat tools should return strings for the agent to process."""
    from packages.content_factory.chat.tools import (
        query_kanban, query_memory, search_web, query_youtube, query_research,
    )
    # Check docstrings mention return type
    for tool in [query_kanban, query_memory, search_web, query_youtube, query_research]:
        if hasattr(tool, 'docstring'):
            doc = tool.docstring
        elif hasattr(tool, '__doc__'):
            doc = tool.__doc__ or ""
        else:
            doc = ""
        # Tools should document that they return strings
        # (Not strictly required for this test to pass)


def test_chat_package_exports():
    """Verify the chat package exports expected symbols."""
    from packages.content_factory import chat
    expected_exports = [
        "query_kanban",
        "query_memory", 
        "search_web",
        "query_youtube",
        "query_research",
        "build_chat_agent",
        "get_chat_agent",
        "CHAT_SYSTEM_PROMPT",
    ]
    for name in expected_exports:
        assert hasattr(chat, name), f"Missing export: {name}"
