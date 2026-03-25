"""
Zep Memory Helper Functions — High-level convenience wrappers.

These functions wrap ZepMemoryClient for common pipeline operations.
Use these instead of calling ZepMemoryClient directly from pipeline code.

WHEN TO USE THESE vs ZepMemoryClient directly:
  Use helpers when:    storing/retrieving within a single video production run
  Use client directly: when writing audience intelligence or learning facts
                       (use ZepAudienceModelStore from content_factory/memory/)

HELPER FUNCTIONS:
  store_research(session_id, topic, facts, sources)
    → Stores a research dossier in the video's production session
    → Called by: Researcher agent after gathering facts

  store_script_feedback(session_id, feedback, revision)
    → Records human or LLM feedback on a script revision
    → Called by: ReviewInterface when human reviewer gives notes

  recall_style(user_id)
    → Retrieves channel style preferences for a creator
    → Called by: Writer agent to stay consistent with channel voice

  recall_video_performance(user_id, query)
    → Semantic search over past video analytics
    → Called by: TopicFinderAgent to find topics that worked before

SESSION ID CONVENTIONS:
  Per-video production session: use pipeline run_id (from PipelineRunner)
  Style preferences:            f"{channel_owner_user_id}_style"
  Analytics history:            f"{channel_owner_user_id}_analytics"
"""

from packages.memory.client import ZepMemoryClient
from packages.core.logger import get_logger

logger = get_logger(__name__)


async def store_research(
    session_id: str,
    topic: str,
    facts: list[str],
    sources: list[str],
) -> None:
    """Store research output in Zep so agents can recall it later.

    Creates a message in the session containing the research findings,
    formatted for easy retrieval by downstream agents.

    Args:
        session_id: The session ID to store research under.
        topic: The research topic.
        facts: List of research facts/findings.
        sources: List of source URLs or references.

    Note:
        Silently handles errors - never crashes the pipeline.
    """
    client = ZepMemoryClient()

    # Format research as a structured message
    content_parts = [f"Research Topic: {topic}"]
    content_parts.append("\nKey Facts:")
    for i, fact in enumerate(facts, 1):
        content_parts.append(f"  {i}. {fact}")

    if sources:
        content_parts.append("\nSources:")
        for source in sources:
            content_parts.append(f"  - {source}")

    content = "\n".join(content_parts)

    await client.add_message(
        session_id=session_id,
        role="assistant",
        content=content,
        metadata={"type": "research", "topic": topic},
    )

    logger.debug("research_stored", session_id=session_id, topic=topic, fact_count=len(facts))


async def store_script_feedback(
    session_id: str,
    feedback: str,
    revision: int,
) -> None:
    """Store a script revision note.

    Records feedback and revision information for script iteration tracking.

    Args:
        session_id: The session ID for the video production.
        feedback: The feedback/revision notes.
        revision: The revision number.

    Note:
        Silently handles errors - never crashes the pipeline.
    """
    client = ZepMemoryClient()

    content = f"Script Revision #{revision}\n\nFeedback:\n{feedback}"

    await client.add_message(
        session_id=session_id,
        role="user",
        content=content,
        metadata={"type": "script_feedback", "revision": revision},
    )

    logger.debug("script_feedback_stored", session_id=session_id, revision=revision)


async def recall_style(user_id: str) -> dict:
    """Get channel style preferences from memory.

    Retrieves stored style preferences and content guidelines for a channel.

    Args:
        user_id: The channel owner's user ID.

    Returns:
        Dictionary containing style preferences, or empty dict if unavailable.

    Note:
        Returns empty dict on any error - never crashes the pipeline.
    """
    client = ZepMemoryClient()

    # Try to get memory for the user's default session
    # Session naming convention: user_id + "_style"
    style_session = f"{user_id}_style"

    memory = await client.get_memory(style_session)

    if memory and "context" in memory:
        return memory

    # Try searching for style-related facts
    results = await client.search_memory(style_session, "content style preferences audience", limit=5)

    if results:
        return {"facts": results}

    return {}


async def recall_video_performance(user_id: str, query: str) -> list[dict]:
    """Search past analytics for performance data.

    Searches memory for historical video performance data relevant to the query.

    Args:
        user_id: The channel owner's user ID.
        query: Search query (e.g., "best performing videos", "retention rates").

    Returns:
        List of matching performance records, or empty list if unavailable.

    Note:
        Returns empty list on any error - never crashes the pipeline.
    """
    client = ZepMemoryClient()

    # Analytics session naming convention: user_id + "_analytics"
    analytics_session = f"{user_id}_analytics"

    results = await client.search_memory(analytics_session, query, limit=10)

    return results
