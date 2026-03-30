"""
Chat agent tools — each function is a LangGraph tool that the ReAct agent
can call to answer user questions.

CRITICAL: Every tool must:
1. Return a STRING (not dict/list) — the agent feeds this into its next reasoning step
2. Handle errors gracefully — return "I couldn't access X because Y" instead of crashing
3. Be lightweight — these run during real-time conversation, not batch processing
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# Try to import langchain_core.tools, fall back to a simple decorator if not available
try:
    from langchain_core.tools import tool
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    def tool(func):
        """Fallback decorator if langchain is not installed."""
        func._is_tool = True
        return func


@tool
async def query_kanban(question: str) -> str:
    """
    Query the Kanban board for information about cards, pipeline status,
    scores, iterations, and topics. Use this when the user asks about
    the current state of any content in the pipeline.

    Args:
        question: Natural language question about the pipeline state
    """
    try:
        from packages.core.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("kanban_cards").select("*").execute()
        cards = result.data or []

        if not cards:
            return "The Kanban board is currently empty. No cards in any column."

        # Build a concise summary for the LLM to reason over
        summary_parts = []
        for card in cards:
            brief = card.get("topic_brief", {})
            if isinstance(brief, str):
                try:
                    brief = json.loads(brief)
                except:
                    brief = {}
            summary_parts.append(
                f"- [{card.get('status', 'unknown')}] Column {card.get('column', '?')}: "
                f"'{brief.get('title', 'Untitled')}' "
                f"(Score: {card.get('viability_score', 'N/A')}%, "
                f"ID: {card.get('id', '?')[:8] if card.get('id') else '?'})"
            )

        return f"Current Kanban Board ({len(cards)} cards):\n" + "\n".join(summary_parts)
    except Exception as e:
        return f"Could not query Kanban board: {str(e)}"


@tool
async def query_memory(question: str) -> str:
    """
    Search the Zep long-term memory for past learnings, audience preferences,
    winning script mutations, and historical context. Use this when the user
    asks about what worked before or wants historical insights.

    Args:
        question: What to search for in memory
    """
    try:
        from packages.memory.client import get_async_zep_client
        from packages.core.config import get_settings

        settings = get_settings()

        async with get_async_zep_client() as zep:
            # Search both audience and learning sessions
            audience_session = f"{settings.ZEP_AUDIENCE_USER_ID}_session"
            learning_session = f"{settings.ZEP_LEARNING_USER_ID}_session"

            audience_results = await zep.search_memory(audience_session, question, limit=3)
            learning_results = await zep.search_memory(learning_session, question, limit=3)

        all_results = (audience_results or []) + (learning_results or [])

        if not all_results:
            return "No relevant memories found in Zep for this query."

        memory_text = []
        for r in all_results[:5]:
            memory_text.append(f"- {r.get('fact', r.get('content', str(r)))}")

        return f"Found {len(all_results)} relevant memories:\n" + "\n".join(memory_text)
    except Exception as e:
        return f"Could not query Zep memory (it may be unavailable): {str(e)}"


@tool
async def search_web(query: str) -> str:
    """
    Search the internet for current information about topics,
    trends, news, and analysis. Use this when the user asks about current
    events or needs fresh information not in memory.

    Args:
        query: Search query string
    """
    try:
        from packages.router.web_search import WebSearchClient

        async with WebSearchClient() as client:
            results = await client.search(query, num_results=5)

        if not results:
            return f"No web results found for: {query}"

        text_parts = []
        for r in results:
            text_parts.append(
                f"- [{r.title}]({r.url}): {r.snippet[:200]}"
            )

        return f"Web search results for '{query}':\n" + "\n".join(text_parts)
    except Exception as e:
        return f"Web search failed: {str(e)}"


@tool
async def query_youtube(question: str) -> str:
    """
    Query YouTube data — either your own channel analytics or competitor
    channel information. Use this when the user asks about video performance,
    competitor analysis, or channel stats.

    Args:
        question: What YouTube data to look up
    """
    try:
        from packages.integrations.youtube.client import YouTubeClient
        from packages.core.config import get_settings

        settings = get_settings()
        yt = YouTubeClient(api_key=settings.YOUTUBE_API_KEY)

        # Get competitor videos (hardcoded competitor list)
        competitors = ["UCmGSJVG3mCRXVOP4yZrU1Dw", "UC3_hsOmAsodJwo5SIy6Jxng"]
        competitor_videos = yt.get_competitor_videos(competitors, max_results=5)

        parts = []

        if competitor_videos:
            video_list = []
            for v in competitor_videos[:5]:
                video_list.append(
                    f"- '{v.get('title', 'Untitled')}' by {v.get('channel_title', 'Unknown')} "
                    f"- {v.get('views', 0):,} views"
                )
            parts.append(f"Recent Competitor Videos:\n" + "\n".join(video_list))

        if not parts:
            return "No YouTube data available. Check if YOUTUBE_API_KEY is configured."

        return "\n---\n".join(parts)
    except Exception as e:
        return f"YouTube query failed: {str(e)}"


@tool
async def query_research(topic: str) -> str:
    """
    Search the permanently stored research dossiers for past research
    on any topic. Use this when the user wants to review what was
    researched before or find specific source material.

    Args:
        topic: Topic or keyword to search research dossiers for
    """
    try:
        from packages.core.supabase_client import get_supabase
        sb = get_supabase()

        # Search dossiers — use ILIKE for basic text matching
        result = sb.table("research_dossiers") \
            .select("topic, dossier, sources, created_at") \
            .ilike("dossier", f"%{topic}%") \
            .order("created_at", desc=True) \
            .limit(3) \
            .execute()

        dossiers = result.data or []

        if not dossiers:
            return f"No research dossiers found matching '{topic}'."

        parts = []
        for d in dossiers:
            topic_data = d.get("topic", "")
            if isinstance(topic_data, dict):
                title = topic_data.get("title", "Untitled")
            else:
                title = str(topic_data)[:50]

            text_preview = (d.get("dossier", "")[:300] + "...") if d.get("dossier") else "Empty"
            sources_count = len(d.get("sources", [])) if d.get("sources") else 0
            parts.append(
                f"📄 '{title}' ({d.get('created_at', 'unknown date')[:10]})\n"
                f"   Sources: {sources_count} | Preview: {text_preview}"
            )

        return f"Found {len(dossiers)} research dossiers:\n\n" + "\n\n".join(parts)
    except Exception as e:
        return f"Research query failed: {str(e)}"
