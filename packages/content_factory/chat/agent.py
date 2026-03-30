"""
Chat Agent — A ReAct conversational assistant embedded in the dashboard.

Uses LangGraph's prebuilt ReAct agent pattern:
  User question → LLM decides which tool to call → Tool returns data → LLM answers

The agent has access to:
  - Kanban board state (Supabase)
  - Zep long-term memory (past learnings, audience data)
  - Web search (z-ai-web-dev-sdk)
  - YouTube analytics (existing integration)
  - Research dossiers (Supabase)

It uses the same FreeRouter client as all other agents,
routed to the model specified in Phase 3c (gpt-4o-mini or gemini-flash).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# System prompt that defines the chat agent's personality and boundaries
CHAT_SYSTEM_PROMPT = """You are the AI Content Factory Assistant for a Pakistani YouTube documentary channel.

Your role:
- Answer questions about the current pipeline state (what's being researched, written, scored)
- Recall past learnings and audience preferences from memory
- Search the web for current events when asked
- Provide YouTube analytics insights
- Help the human orchestrator make decisions about topics and scripts

Rules:
1. Always cite your source (which tool you used to find information)
2. If you don't know something, say so — don't make up data
3. When discussing scores, always mention the iteration count for context
4. Keep responses concise but actionable
5. If the user asks about a topic, check research dossiers first before searching the web
6. Speak naturally — you're a helpful colleague, not a robot

You have access to these tools:
- query_kanban: Check the pipeline board status
- query_memory: Search past learnings and audience data
- search_web: Search the internet via z-ai-web-dev-sdk
- query_youtube: Look up YouTube channel and competitor stats
- query_research: Search stored research dossiers
"""

# Module-level agent holder
_chat_agent = None


async def build_chat_agent():
    """
    Build and return a compiled ReAct agent with tool access.

    Uses FreeRouter for LLM calls. The model choice:
    - Primary: gemini-flash via OpenRouter (fast, good at tool calling)
    - The ChatOpenAI wrapper works with any OpenAI-compatible API
      (which FreeRouter/OpenRouter/Groq all provide)
    """
    global _chat_agent

    if _chat_agent is not None:
        return _chat_agent

    # Check if langgraph is available
    try:
        from langgraph.prebuilt import create_react_agent
    except ImportError:
        logger.warning("langgraph not installed — chat agent unavailable")
        return None

    # Check if langchain_openai is available
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        logger.warning("langchain_openai not installed — chat agent unavailable")
        return None

    # Import tools
    from .tools import (
        query_kanban,
        query_memory,
        search_web,
        query_youtube,
        query_research,
    )

    # Get checkpointer (optional - for conversation persistence)
    checkpointer = None
    try:
        from packages.content_factory.orchestration.checkpointer import get_checkpointer
        checkpointer = await get_checkpointer()
    except Exception as e:
        logger.debug(f"Checkpointer unavailable for chat: {e}")

    # Use the FreeRouter proxy URL so all calls go through our rate-limit tracking
    freerouter_url = os.getenv("FREEROUTER_URL", "http://localhost:4000")
    chat_model = os.getenv("CHAT_MODEL", "openrouter/google/gemini-2.0-flash-001")
    freerouter_api_key = os.getenv("FREEROUTER_API_KEY", "sk-free")

    llm = ChatOpenAI(
        model=chat_model,
        openai_api_base=f"{freerouter_url}/v1",
        openai_api_key=freerouter_api_key,
        temperature=0.3,  # Lower temperature for factual tool-calling
        max_tokens=1024,
    )

    tools = [query_kanban, query_memory, search_web, query_youtube, query_research]

    try:
        agent = create_react_agent(
            model=llm,
            tools=tools,
            state_modifier=CHAT_SYSTEM_PROMPT,
            checkpointer=checkpointer,
        )

        _chat_agent = agent
        logger.info("chat_agent_initialized")
        return agent
    except Exception as e:
        logger.error(f"chat_agent_build_failed: {e}")
        return None


def get_chat_agent():
    """Get the current chat agent instance."""
    return _chat_agent
