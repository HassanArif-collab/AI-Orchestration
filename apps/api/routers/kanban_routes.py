"""
Kanban task management routes.

These endpoints handle the Kanban board operations for the YouTube Pipeline
dashboard. All operations use the kanban_cards Supabase table as the
canonical data source (the frontend subscribes via Supabase Realtime).

Phase 5: Migrated from pipeline_runs (RunStore) to kanban_cards.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Path, Body
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

from apps.api.events import emit_task_created
from packages.core.config import get_settings

router = APIRouter()


def _card_to_kanban_dict(card: dict) -> dict:
    """Convert a kanban_cards row to the frontend Kanban task format.

    Args:
        card: Row dict from kanban_cards table (Supabase response)

    Returns:
        Dictionary matching the frontend's expected Kanban task shape
    """
    card_id = card.get("id", "")
    status = card.get("status", "idle")
    column_index = card.get("column_index", 1)
    color = card.get("color", "#1D9E75")

    # Map card status to frontend visual state
    if status == "thinking":
        kanban_status = "thinking"
    elif status == "waiting":
        kanban_status = "waiting"
    elif status in ("complete", "completed"):
        kanban_status = "complete"
    elif status == "error":
        kanban_status = "error"
    else:
        kanban_status = "idle"

    # Load thoughts from centralized Supabase module
    thoughts = []
    try:
        from packages.core.thoughts import get_thoughts_for_card
        thoughts = get_thoughts_for_card(str(card_id))
    except Exception as e:
        logger.debug(f"Error loading thoughts for {card_id}: {e}")

    # BUGFIX: Include thinking_started_at for frontend elapsed timer
    thinking_started_at = None
    if status == "thinking":
        thinking_started_at = card.get("updated_at")

    # Extract notion_url from metadata if available
    metadata = card.get("metadata", {}) or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    notion_url = metadata.get("notion_url")

    # Extract error_message from metadata if available
    error_message = card.get("error_message", "") or metadata.get("error_message", "")

    return {
        "id": card_id,
        "title": card.get("title", "Untitled"),
        "stage": column_index,
        "column_index": column_index,  # React frontend expects this key
        "status": kanban_status,
        "color": color,
        "updated_at": card.get("updated_at"),
        "created_at": card.get("created_at"),
        "notion_url": notion_url,
        "research": "",          # Stage outputs not stored in kanban_cards
        "script": "",            # Frontend fetches these via LangGraph state
        "visual_cues": "",       # if needed
        "thoughts": json.dumps(thoughts),
        "expires_at": card.get("expires_at"),
        "thinking_started_at": thinking_started_at,
        "error_message": error_message,
    }


def _get_supabase():
    """Get Supabase client with lazy import."""
    from packages.core.supabase_client import get_supabase
    return get_supabase()


# ─── Pydantic Models ────────────────────────────────────────────────────────────

class KanbanTaskUpdate(BaseModel):
    """Request model for updating a Kanban task."""
    stage: Optional[int] = Field(default=None, ge=1, le=6)
    extend_expiration: Optional[bool] = Field(default=False, description="If true, extend card expiration by 3 hours")

class TopicFinderRequest(BaseModel):
    """Request model for triggering Topic Finder."""
    seed_query: str = Field(..., min_length=3, max_length=500)
    genre_id: str = Field(default="default", max_length=50)

class KanbanEventRequest(BaseModel):
    """Request model for Kanban events (thoughts, stage changes, artifacts)."""
    task_id: str = Field(..., description="The card ID")
    event_type: str = Field(..., description="Event type: thought, stage_change, artifact, status_change")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload")

# ─── API Endpoints ──────────────────────────────────────────────────────────────

KANBAN_MAX_LIST_LIMIT = 200

@router.get("/tasks")
async def list_tasks(limit: int = Query(default=100, ge=1, le=KANBAN_MAX_LIST_LIMIT)) -> dict:
    """List all kanban cards as tasks.

    Reads from the kanban_cards table (canonical data source for the frontend).
    Excludes soft-deleted cards.
    """
    try:
        sb = _get_supabase()
        result = (
            sb.table("kanban_cards")
            .select("*")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )

        tasks = []
        for card in (result.data or []):
            # Skip soft-deleted cards (marked via metadata.deleted_at)
            metadata = card.get("metadata", {}) or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            if metadata.get("deleted_at"):
                continue

            try:
                tasks.append(_card_to_kanban_dict(card))
            except Exception as e:
                logger.debug(f"Error processing card {card.get('id')}: {e}")
                continue

        return {"tasks": tasks}
    except Exception as e:
        logger.error(f"list_tasks_failed: {e}")
        return {"tasks": []}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Get a single kanban card as a task."""
    try:
        sb = _get_supabase()
        result = (
            sb.table("kanban_cards")
            .select("*")
            .eq("id", task_id)
            .maybe_single()
            .execute()
        )

        if not result.data:
            raise HTTPException(404, f"Task {task_id} not found")

        return _card_to_kanban_dict(result.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"Failed to load task: {e}")


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str = Path(..., min_length=1, max_length=100), data: KanbanTaskUpdate = Body(...), bg: BackgroundTasks = BackgroundTasks()) -> dict:
    """Update a Kanban task — supports moving cards between stages and extending expiration.

    NOTE: The legacy PipelineRunner gate approval flow was removed in Phase 3.
    Card movement now uses LangGraph's /langgraph/resume endpoint for human gate decisions.
    This endpoint handles expiration extension and column movement via Supabase.
    """
    try:
        sb = _get_supabase()

        # Load current card for the response
        result = sb.table("kanban_cards").select("*").eq("id", task_id).maybe_single().execute()
        if not result.data:
            raise HTTPException(404, f"Task {task_id} not found")

        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}

        if data.stage is not None:
            update_data["column_index"] = data.stage
            logger.info(f"kanban_card_moved: task={task_id} to_column={data.stage}")

        # Handle expiration extension
        if data.extend_expiration:
            new_expiration = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
            update_data["expires_at"] = new_expiration

        if update_data:
            sb.table("kanban_cards").update(update_data).eq("id", task_id).execute()

        # Re-fetch the updated card for the response
        updated = sb.table("kanban_cards").select("*").eq("id", task_id).maybe_single().execute()
        if not updated.data:
            raise HTTPException(404, f"Task {task_id} not found after update")

        return _card_to_kanban_dict(updated.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to update task: {e}")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Soft-delete a kanban card by setting metadata.deleted_at.

    Marks the card as deleted without permanently removing it.
    Use POST /tasks/{task_id}/hard-delete for permanent removal,
    or POST /tasks/undo-delete/{task_id} to restore.
    """
    try:
        sb = _get_supabase()

        # Verify card exists
        result = sb.table("kanban_cards").select("id,metadata").eq("id", task_id).maybe_single().execute()
        if not result.data:
            raise HTTPException(404, f"Task {task_id} not found")

        # Soft-delete via metadata
        deleted_at = datetime.now(timezone.utc).isoformat()
        metadata = result.data.get("metadata", {}) or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        metadata["deleted_at"] = deleted_at

        sb.table("kanban_cards").update({
            "metadata": metadata,
            "updated_at": deleted_at,
        }).eq("id", task_id).execute()

        logger.info(f"kanban_task_soft_deleted: task_id={task_id} deleted_at={deleted_at}")
        return {"success": True, "deleted_id": task_id, "deleted_at": deleted_at, "mode": "soft"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to soft-delete task: {e}")


@router.post("/tasks/{task_id}/soft-delete")
async def soft_delete_task(task_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Explicitly soft-delete a kanban task.

    Marks the task as deleted without permanently removing it.
    The task can be restored via POST /tasks/undo-delete/{task_id}.
    """
    return await delete_task(task_id)


@router.post("/tasks/undo-delete/{task_id}")
async def undo_delete_task(task_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Restore a soft-deleted kanban task.

    Clears the deleted_at timestamp from metadata, making the task visible again.
    """
    try:
        sb = _get_supabase()

        # Load current card
        result = sb.table("kanban_cards").select("id,metadata").eq("id", task_id).maybe_single().execute()
        if not result.data:
            raise HTTPException(404, f"Task {task_id} not found")

        # Check if it's actually soft-deleted
        metadata = result.data.get("metadata", {}) or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        previously_deleted_at = metadata.get("deleted_at")
        if not previously_deleted_at:
            raise HTTPException(400, f"Task {task_id} is not soft-deleted")

        # Clear the deleted flag
        del metadata["deleted_at"]
        sb.table("kanban_cards").update({
            "metadata": metadata,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", task_id).execute()

        logger.info(f"kanban_task_undeleted: task_id={task_id}")
        return {"success": True, "restored_id": task_id, "previously_deleted_at": previously_deleted_at}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to undo-delete task: {e}")


@router.post("/tasks/{task_id}/hard-delete")
async def hard_delete_task(task_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Permanently delete a kanban card and associated thoughts (irreversible).

    Unlike the default DELETE (soft-delete), this permanently removes
    the card from storage. Use with caution.
    """
    try:
        sb = _get_supabase()

        # Verify card exists
        result = sb.table("kanban_cards").select("id").eq("id", task_id).maybe_single().execute()
        if not result.data:
            raise HTTPException(404, f"Task {task_id} not found")

        # Delete from kanban_cards (cascade will delete thoughts via FK)
        sb.table("kanban_cards").delete().eq("id", task_id).execute()

        # Also delete associated thoughts explicitly via centralized module
        try:
            from packages.core.thoughts import delete_thoughts_for_card
            delete_thoughts_for_card(str(task_id))
        except Exception as e:
            logger.warning(f"kanban_hard_delete_thoughts_failed: {task_id}: {e}")

        logger.info(f"kanban_task_hard_deleted: task_id={task_id}")
        return {"success": True, "deleted_id": task_id, "mode": "hard"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to hard-delete task: {e}")


@router.post("/topic-finder")
async def trigger_topic_finder(data: TopicFinderRequest, bg: BackgroundTasks) -> dict:
    """Start a new LangGraph discovery pipeline with the user's seed query.

    NOTE: The legacy PipelineRunner was removed in Phase 3. This endpoint now
    delegates to the LangGraph discovery graph via Supabase Realtime for progress.
    """
    import uuid as _uuid
    card_id = str(_uuid.uuid4())

    # Create a placeholder kanban card in Column 1 (Topic Finding)
    try:
        sb = _get_supabase()
        sb.table("kanban_cards").insert({
            "id": card_id,
            "title": data.seed_query[:100],
            "column_index": 1,
            "status": "thinking",
            "seed_query": data.seed_query,
            "genre_id": data.genre_id,
        }).execute()
    except Exception as e:
        logger.warning(f"topic_finder_card_create_failed: {e}")

    # Trigger the LangGraph discovery graph
    try:
        from apps.api.routers.pipeline_routes import discover_topics
        await discover_topics(background_tasks=bg, seed_hint=data.seed_query)
    except Exception as e:
        logger.error(f"topic_finder_discover_failed: {e}")

    # Emit task_created for Kanban board
    try:
        await emit_task_created({
            "id": card_id,
            "title": data.seed_query[:100],
            "stage": 1,
            "status": "thinking",
        })
    except Exception as e:
        logger.warning(f"topic_finder_emit_failed: {e}")

    return {
        "id": card_id,
        "status": "thinking",
        "message": f"Discovery started for: {data.seed_query}"
    }

@router.get("/stats")
async def get_stats() -> dict:
    """Get statistics from the kanban_cards table."""
    try:
        sb = _get_supabase()
        result = (
            sb.table("kanban_cards")
            .select("column_index, status")
            .order("updated_at", desc=True)
            .limit(1000)
            .execute()
        )

        cards = result.data or []
        total = len(cards)
        by_stage = {}
        by_status = {}

        for card in cards:
            # Skip soft-deleted cards
            metadata = card.get("metadata", {}) or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            if metadata.get("deleted_at"):
                continue

            stage_num = card.get("column_index", 1)
            by_stage[stage_num] = by_stage.get(stage_num, 0) + 1
            status = card.get("status", "idle")
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total_tasks": total,
            "by_stage": by_stage,
            "by_status": by_status
        }
    except Exception as e:
        logger.error(f"get_stats_failed: {e}")
        return {"total_tasks": 0, "by_stage": {}, "by_status": {}}

@router.post("/events")
async def record_kanban_event(data: KanbanEventRequest) -> dict:
    """Record a Kanban event (thought, stage change, artifact, etc.).

    This endpoint is called by agents via KanbanCallbackHandler to report
    thoughts, stage changes, artifacts, and status changes.

    Args:
        data: The event request containing task_id, event_type, and data payload

    Returns:
        Success dict with event_type
    """
    if data.event_type == "thought":
        # Write thought directly to Supabase via centralized module
        from packages.core.thoughts import report_thought
        thought_text = data.data.get("content", data.data.get("text", ""))
        report_thought(
            card_id=data.task_id,
            agent_name=data.data.get("agent_name", "unknown"),
            thought_type="thinking",
            content=thought_text,
        )
        return {"success": True, "event_type": data.event_type, "recorded": "thought"}

    # For other event types, we just acknowledge them
    # In the future, we could store stage changes, artifacts, etc.
    return {"success": True, "event_type": data.event_type}


# ─── Card Management Endpoints (for React frontend) ──────────────────────────────

@router.post("/cards/{card_id}/save")
async def save_card(card_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Save a suggested topic card by removing the expires_at timestamp.
    
    This prevents the 3-hour auto-delete for Column 2 cards.
    """
    try:
        sb = _get_supabase()
        sb.table("kanban_cards").update({"expires_at": None}).eq("id", card_id).execute()
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(500, f"Failed to save card: {e}")


@router.post("/tasks/{task_id}/extend")
async def extend_card_expiration(task_id: str = Path(..., min_length=1, max_length=100)) -> dict:
    """Extend a card's expiration by 3 hours."""
    try:
        sb = _get_supabase()

        # Verify card exists
        result = sb.table("kanban_cards").select("id,expires_at").eq("id", task_id).execute()
        if not result.data:
            raise HTTPException(404, f"Card {task_id} not found")

        new_expiration = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        sb.table("kanban_cards").update({
            "expires_at": new_expiration,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", task_id).execute()

        return {
            "status": "extended",
            "id": task_id,
            "expires_at": new_expiration,
            "extended_by_hours": 3,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to extend expiration: {e}")


class MoveCardRequest(BaseModel):
    """Request model for moving a Kanban card to a different column."""
    column: int = Field(..., ge=1, le=6, description="Target column (1-6)")

@router.put("/cards/{card_id}/move")
async def move_card(card_id: str = Path(..., min_length=1, max_length=100), body: MoveCardRequest = Body(...)) -> dict:
    """Move a card to a different column."""
    try:
        sb = _get_supabase()
        sb.table("kanban_cards").update({
            "column_index": body.column,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", card_id).execute()
        return {"status": "moved"}
    except Exception as e:
        raise HTTPException(500, f"Failed to move card: {e}")
