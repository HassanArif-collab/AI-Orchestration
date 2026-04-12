"""Centralized agent thought reporting via Supabase.

Every thought inserted here is automatically pushed to the React
frontend via Supabase Realtime (postgres_changes on agent_thoughts).

This module provides the core CRUD operations for agent thoughts:
- report_thought() / report_thought_async() — write thoughts
- get_thoughts_for_card() — retrieve thoughts for a card
- delete_thoughts_for_card() — delete thoughts for a card

Pipeline-specific utilities (stage mapping, @pipeline_node decorator,
milestone/error reporting) live in:
    packages.content_factory.orchestration.thoughts

Usage from any agent:
    from packages.core.thoughts import report_thought
    report_thought(
        card_id="uuid-of-kanban-card",
        agent_name="topic_finder",
        thought_type="thinking",
        content="Evaluating The Anchor Test..."
    )

Valid agent_name values:
    'topic_finder', 'researcher', 'script_writer', 'evaluator',
    'challenger', 'visual_annotator', 'chat_assistant', 'orchestrator'

Valid thought_type values:
    'thinking'     -- internal reasoning / monologue
    'search'       -- web or memory search performed
    'output'       -- produced a result or artifact
    'error'        -- something failed
    'memory_read'  -- read from Zep memory
    'memory_write' -- wrote to Zep memory
"""

from typing import Optional
from packages.core.logger import get_logger
from packages.core.config import get_settings

logger = get_logger(__name__)

VALID_THOUGHT_TYPES = frozenset({
    "thinking", "search", "output", "error", "memory_read", "memory_write"
})


def report_thought(
    card_id: str,
    agent_name: str,
    thought_type: str,
    content: str,
) -> bool:
    """Insert an agent thought into Supabase agent_thoughts table.

    This is a synchronous call (HTTP under the hood). It is safe to call
    from async context -- the blocking is minimal (~50ms to Supabase).

    NEVER raises -- logs errors and returns False. Agent work must
    never be interrupted by a logging failure.

    Args:
        card_id: The Kanban card ID to associate the thought with
        agent_name: Name of the agent (e.g., "topic_finder", "script_writer")
        thought_type: Category of thought (search, analysis, output, error, info)
        content: The thought content/message

    Returns:
        True if thought was successfully recorded, False otherwise
    """
    if not card_id:
        logger.debug("report_thought skipped: no card_id provided")
        return False

    if thought_type not in VALID_THOUGHT_TYPES:
        logger.warning(f"invalid_thought_type: '{thought_type}', defaulting to 'thinking'")
        thought_type = "thinking"

    settings = get_settings()

    # Check if Supabase is configured
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        logger.debug(
            f"report_thought skipped: Supabase not configured "
            f"(agent={agent_name}, type={thought_type})"
        )
        return False

    try:
        from packages.core.supabase_client import get_supabase

        result = get_supabase().table("agent_thoughts").insert({
            "card_id": card_id,
            "agent_name": agent_name,
            "thought_type": thought_type,
            "content": content,
        }).execute()

        logger.debug(
            f"thought_reported: agent={agent_name}, "
            f"type={thought_type}, card={card_id[:8]}..."
        )
        return True

    except Exception as e:
        # CRITICAL: Never crash the pipeline because thought logging failed
        logger.warning(
            f"report_thought_failed_non_blocking: {e} "
            f"(agent={agent_name}, card={card_id[:8] if card_id else 'none'}...)"
        )
        return False


async def report_thought_async(
    card_id: str,
    agent_name: str,
    thought_type: str,
    content: str,
) -> bool:
    """Async version of report_thought for use in async agents.

    Same behavior as report_thought but compatible with async code.
    """
    return report_thought(card_id, agent_name, thought_type, content)


def get_thoughts_for_card(card_id: str, limit: int = 50) -> list[dict]:
    """Retrieve thoughts for a card, newest first.

    Returns list of dicts with keys: agent_name, thought_type, content, created_at.
    Returns empty list on failure.
    """
    try:
        from packages.core.supabase_client import get_supabase
        result = (
            get_supabase()
            .table("agent_thoughts")
            .select("agent_name, thought_type, content, created_at")
            .eq("card_id", card_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"thoughts_fetch_failed: {e}")
        return []


def delete_thoughts_for_card(card_id: str) -> int:
    """Delete all thoughts for a card. Returns count deleted."""
    try:
        from packages.core.supabase_client import get_supabase
        result = (
            get_supabase()
            .table("agent_thoughts")
            .delete()
            .eq("card_id", card_id)
            .execute()
        )
        return len(result.data) if result.data else 0
    except Exception as e:
        logger.error(f"thoughts_delete_failed: {e}")
        return 0
