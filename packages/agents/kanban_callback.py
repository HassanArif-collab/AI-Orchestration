"""
KanbanCallbackHandler - Bridge between agents and Kanban dashboard.

Provides methods for agents to report progress, thoughts, and artifacts
directly to Supabase (no HTTP round-trip needed).

Usage:
    callback = KanbanCallbackHandler(task_id="abc-123")
    await callback.on_thought("Analyzing topic viability...")
    await callback.on_stage_change(3)  # Move to Researching
    await callback.on_artifact("research", research_content)
"""

import uuid
from typing import Optional
from datetime import datetime, timezone

from packages.core.logger import get_logger

logger = get_logger(__name__)

# Stage mapping: pipeline stage -> kanban column (1-6)
PIPELINE_TO_KANBAN_STAGE = {
    "trend_analysis": 1,        # Topic Finding
    "human_topic_approval": 2,  # Suggested Topics
    "research": 3,              # Researching
    "script_writing": 4,        # Script
    "visual_planning": 5,       # Visual
    "seo": 4,                   # Script (parallel)
    "human_review": 5,          # Visual (review)
    "asset_creation": 6,        # Notion
    "publish": 6,               # Notion (with URL)
}

# Valid Kanban stages
VALID_KANBAN_STAGES = {1, 2, 3, 4, 5, 6}

# Valid status values
VALID_STATUSES = {"idle", "thinking", "error", "complete", "waiting"}

# Valid artifact keys
VALID_ARTIFACT_KEYS = {"research", "script", "visual_cues", "notion_url", "content"}


class KanbanCallbackHandler:
    """Bridge between CrewAI agents and the Kanban dashboard.

    This class provides a clean interface for agents to report their
    progress directly to Supabase. No HTTP round-trip needed.

    Attributes:
        task_id: The UUID of the Kanban task this handler is associated with

    Example:
        callback = KanbanCallbackHandler(task_id="abc-123")
        await callback.on_thought("Starting research...")
        await callback.on_status_change("thinking")
        await callback.on_artifact("research", research_content)
        await callback.on_status_change("idle")
    """

    def __init__(
        self,
        task_id: str,
        base_url: str = "http://localhost:3000"  # kept for backward compat; unused
    ):
        """Initialize the callback handler.

        Args:
            task_id: The UUID of the Kanban task
            base_url: Kept for backward compatibility; no longer used for HTTP
        """
        self.task_id = task_id
        self.base_url = base_url

    # Async context manager — kept for backward compatibility (no-op now)
    async def __aenter__(self) -> "KanbanCallbackHandler":
        return self

    async def __aexit__(self, *args) -> None:
        pass

    async def on_thought(self, thought: str, metadata: Optional[dict] = None) -> bool:
        """Report an agent thought/monologue directly to Supabase.

        Thoughts appear in the task drawer's "Agent Monologue" section
        via Supabase Realtime.

        Args:
            thought: The thought/monologue text to report
            metadata: Optional additional metadata (agent_name, etc.)

        Returns:
            True if the thought was reported successfully
        """
        from packages.core.thoughts import report_thought
        try:
            report_thought(
                card_id=self.task_id,
                agent_name=metadata.get("agent_name", "unknown") if metadata else "unknown",
                thought_type="thinking",
                content=thought,
            )
            return True
        except Exception as e:
            logger.warning(f"thought_report_failed: {e}")
            return False

    async def on_stage_change(self, stage: int) -> bool:
        """Report task moving to a new stage. Writes directly to Supabase.

        Stages are numbered 1-6:
            1. Topic Finding
            2. Suggested Topics
            3. Researching
            4. Script
            5. Visual
            6. Notion

        Args:
            stage: The new stage number (1-6)

        Returns:
            True if the stage change was applied successfully
        """
        if stage not in VALID_KANBAN_STAGES:
            logger.warning(f"invalid_kanban_stage: {stage} (must be 1-6)")
            return False
        try:
            from packages.core.supabase_client import get_supabase
            get_supabase().table("kanban_cards").update(
                {"column_index": stage, "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", self.task_id).execute()
            return True
        except Exception as e:
            logger.warning(f"stage_change_failed: {e}")
            return False

    async def on_status_change(self, status: str) -> bool:
        """Report status change. Writes directly to Supabase.

        Valid statuses:
            - idle: Task is waiting, not actively processing
            - thinking: Agent is actively working on this task
            - error: Task encountered an error
            - complete: Task is finished
            - waiting: Task is waiting for human input

        Args:
            status: The new status value

        Returns:
            True if the status change was applied successfully
        """
        if status not in VALID_STATUSES:
            logger.warning(f"invalid_kanban_status: {status}")
            return False
        try:
            from packages.core.supabase_client import get_supabase
            get_supabase().table("kanban_cards").update(
                {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", self.task_id).execute()
            return True
        except Exception as e:
            logger.warning(f"status_change_failed: {e}")
            return False

    async def on_artifact(self, key: str, value: str) -> bool:
        """Report artifact output. Writes to Supabase thoughts as type "output".

        Valid keys:
            - research: Research content (stage 3)
            - script: Script content (stage 4)
            - visual_cues: Visual planning notes (stage 5)
            - notion_url: URL to published Notion page (stage 6)
            - content: General content field

        Args:
            key: The artifact key (research, script, visual_cues, notion_url, content)
            value: The artifact content/value

        Returns:
            True if the artifact was reported successfully
        """
        if key not in VALID_ARTIFACT_KEYS:
            logger.warning(f"invalid_artifact_key: {key}")
            return False
        from packages.core.thoughts import report_thought
        try:
            report_thought(
                card_id=self.task_id,
                agent_name="unknown",
                thought_type="output",
                content=f"[{key}] {value[:500]}",
            )
            return True
        except Exception as e:
            logger.warning(f"artifact_report_failed: {e}")
            return False

    async def create_child_task(
        self,
        title: str,
        stage: int = 2,
        color: Optional[str] = None
    ) -> Optional[str]:
        """Create a child task (e.g., suggested topic from topic finder).

        Inserts directly into Supabase kanban_cards.

        Args:
            title: The title for the new task
            stage: The stage for the new task (default: 2 for Suggested Topics)
            color: Optional hex color code (e.g., "#0066cc")

        Returns:
            The new task ID or None on failure
        """
        try:
            from packages.core.supabase_client import get_supabase
            new_id = str(uuid.uuid4())
            get_supabase().table("kanban_cards").insert({
                "id": new_id,
                "title": title,
                "column_index": stage,
                "parent_id": self.task_id,
                "color": color,
            }).execute()
            logger.info(f"kanban_child_task_created: {new_id[:8]} -> stage {stage}")
            return new_id
        except Exception as e:
            logger.warning(f"create_child_task_error: {e}")
            return None

    async def update_title(self, title: str) -> bool:
        """Update the task title directly in Supabase.

        Args:
            title: The new title for the task

        Returns:
            True if successful
        """
        try:
            from packages.core.supabase_client import get_supabase
            get_supabase().table("kanban_cards").update(
                {"title": title, "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", self.task_id).execute()
            return True
        except Exception as e:
            logger.warning(f"update_title_error: {e}")
            return False

    async def delete_task(self) -> bool:
        """Delete this task directly in Supabase.

        Returns:
            True if successful
        """
        try:
            from packages.core.supabase_client import get_supabase
            get_supabase().table("kanban_cards").delete().eq("id", self.task_id).execute()
            return True
        except Exception as e:
            logger.warning(f"delete_task_error: {e}")
            return False


async def create_kanban_task(
    title: str,
    stage: int = 1,
    base_url: str = "http://localhost:3000",  # kept for backward compat; unused
    color: Optional[str] = None
) -> Optional[str]:
    """Create a new Kanban task directly in Supabase.

    This is a convenience function for creating a Kanban task
    without needing to instantiate a handler.

    Args:
        title: The task title
        stage: The initial stage (1-6, default: 1 for Topic Finding)
        base_url: Kept for backward compatibility; no longer used
        color: Optional hex color code

    Returns:
        The new task ID or None on failure
    """
    try:
        from packages.core.supabase_client import get_supabase
        task_id = str(uuid.uuid4())
        get_supabase().table("kanban_cards").insert({
            "id": task_id,
            "title": title,
            "column_index": stage,
            "color": color,
        }).execute()
        logger.info(f"kanban_task_created: {task_id[:8]} - '{title[:30]}'")
        return task_id
    except Exception as e:
        logger.warning(f"create_kanban_task_error: {e}")
        return None


def get_kanban_stage(pipeline_stage: str) -> int:
    """Convert a pipeline stage name to Kanban column number.

    Args:
        pipeline_stage: The pipeline stage name (e.g., "research")

    Returns:
        The corresponding Kanban stage number (1-6), defaults to 1
    """
    return PIPELINE_TO_KANBAN_STAGE.get(pipeline_stage, 1)
