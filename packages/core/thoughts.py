"""Centralized agent thought reporting via Supabase.

Every thought inserted here is automatically pushed to the React
frontend via Supabase Realtime (postgres_changes on agent_thoughts).

This replaces:
    - ThoughtsStore class in apps/api/routers/kanban_routes.py
    - KanbanCallbackHandler.on_thought() HTTP POST pattern
    - The /api/kanban/events SSE broadcasting

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

from packages.core.logger import get_logger

logger = get_logger(__name__)

VALID_THOUGHT_TYPES = frozenset({
    "thinking", "search", "output", "error", "memory_read", "memory_write"
})


def report_thought(
    card_id: str,
    agent_name: str,
    thought_type: str,
    content: str,
) -> None:
    """Insert an agent thought into Supabase agent_thoughts table.

    This is a synchronous call (HTTP under the hood). It is safe to call
    from async context -- the blocking is minimal (~50ms to Supabase).

    NEVER raises -- logs errors and returns silently. Agent work must
    never be interrupted by a logging failure.
    """
    if thought_type not in VALID_THOUGHT_TYPES:
        logger.warning(f"invalid_thought_type: '{thought_type}', defaulting to 'thinking'")
        thought_type = "thinking"

    try:
        from packages.core.supabase_client import get_supabase
        get_supabase().table("agent_thoughts").insert({
            "card_id": card_id,
            "agent_name": agent_name,
            "thought_type": thought_type,
            "content": content,
        }).execute()
    except Exception as e:
        # CRITICAL: Never crash the pipeline because thought logging failed
        logger.error(f"thought_report_failed: {e}")


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
