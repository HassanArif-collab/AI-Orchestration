"""
Chat Agent Package

Provides a ReAct conversational assistant that can:
- Query the Kanban board state
- Search Zep long-term memory
- Search the web for current information
- Query YouTube analytics
- Search research dossiers
"""

from .tools import (
    query_kanban,
    query_memory,
    search_web,
    query_youtube,
    query_research,
)

from .agent import (
    build_chat_agent,
    get_chat_agent,
    CHAT_SYSTEM_PROMPT,
)

__all__ = [
    # Tools
    "query_kanban",
    "query_memory",
    "search_web",
    "query_youtube",
    "query_research",
    # Agent
    "build_chat_agent",
    "get_chat_agent",
    "CHAT_SYSTEM_PROMPT",
]
