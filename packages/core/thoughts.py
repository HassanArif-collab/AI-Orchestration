"""Agent thoughts reporting module.

Provides a centralized function for agents to report thoughts, progress,
and status updates to the Kanban card drawer via Supabase.

Usage:
    from packages.core.thoughts import report_thought

    report_thought(
        card_id="card-123",
        agent_name="topic_finder",
        thought_type="search",
        content="Searching for trending topics..."
    )

Thought Types:
    - "search": Web search or API query in progress
    - "analysis": Processing or analyzing data
    - "output": Producing a result or artifact
    - "error": Error or warning message
    - "info": General informational message

Database Table (agent_thoughts):
    - id: UUID (auto-generated)
    - card_id: TEXT (Kanban card ID)
    - agent_name: TEXT
    - thought_type: TEXT
    - content: TEXT
    - created_at: TIMESTAMP (auto-generated)
"""

from typing import Optional
from packages.core.logger import get_logger
from packages.core.config import get_settings

logger = get_logger(__name__)


def report_thought(
    card_id: str,
    agent_name: str,
    thought_type: str,
    content: str,
) -> bool:
    """Report an agent thought to the Supabase agent_thoughts table.

    This function is designed to be non-blocking and fail gracefully.
    If Supabase is not configured or the insert fails, the error is
    logged and the function returns False without crashing the pipeline.

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

        supabase = get_supabase()

        result = supabase.table("agent_thoughts").insert({
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
