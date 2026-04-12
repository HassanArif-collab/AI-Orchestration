"""
dlq_routes.py — Dead Letter Queue admin routes.

Provides endpoints for managing the Dead Letter Queue (DLQ), allowing
operators to view, retry, and delete failed operations.

Endpoints:
    GET  /api/dlq/stats           - DLQ statistics
    GET  /api/dlq/items           - List all DLQ items (with optional status filter)
    POST /api/dlq/items/{id}/retry - Retry a failed item
    DELETE /api/dlq/items/{id}     - Delete a DLQ item

All endpoints require authentication (X-API-Key header).
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from packages.core.dead_letter import (
    get_stats,
    get_all_entries,
    get_entry,
    delete_entry,
    mark_retry_attempt,
    clear_completed_entries,
)

router = APIRouter()


@router.get("/api/dlq/stats")
async def dlq_stats():
    """Get Dead Letter Queue statistics.

    Returns aggregated counts and breakdowns by operation type,
    error code, and severity level.
    """
    try:
        stats = get_stats()
        return {
            "success": True,
            "data": stats,
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to retrieve DLQ stats: {e}")


@router.get("/api/dlq/items")
async def dlq_list_items(
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: 'pending' or 'completed'",
    ),
    include_completed: bool = Query(
        default=False,
        description="Whether to include completed entries in results.",
    ),
):
    """List all Dead Letter Queue items.

    Args:
        status: Optional status filter ('pending' or 'completed').
                If provided, overrides include_completed parameter.
        include_completed: If True and no status filter, includes completed entries.

    Returns:
        List of DLQ entry dictionaries.
    """
    try:
        # If status filter is provided, determine include_completed
        if status is not None:
            if status == "pending":
                entries = get_all_entries(include_completed=False)
                entries = [e for e in entries if e.get("status") == "pending"]
            elif status == "completed":
                entries = get_all_entries(include_completed=True)
                entries = [e for e in entries if e.get("status") == "completed"]
            else:
                raise HTTPException(
                    400,
                    f"Invalid status filter '{status}'. Must be 'pending' or 'completed'."
                )
        else:
            entries = get_all_entries(include_completed=include_completed)

        return {
            "success": True,
            "data": entries,
            "count": len(entries),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to list DLQ items: {e}")


@router.post("/api/dlq/items/{item_id}/retry")
async def dlq_retry_item(item_id: str):
    """Mark a DLQ item as retried (success).

    This marks the entry as "completed" in the DLQ. The actual retry
    logic must be handled separately by the service that owns the operation.

    Args:
        item_id: The UUID of the DLQ entry to retry.

    Returns:
        Updated entry status.
    """
    try:
        entry = get_entry(item_id)
        if entry is None:
            raise HTTPException(404, f"DLQ item '{item_id}' not found.")

        if entry.get("status") == "completed":
            raise HTTPException(
                400,
                f"DLQ item '{item_id}' is already marked as completed.",
            )

        success = mark_retry_attempt(item_id, success=True)
        if not success:
            raise HTTPException(500, f"Failed to update DLQ item '{item_id}'.")

        updated_entry = get_entry(item_id)
        return {
            "success": True,
            "message": f"DLQ item '{item_id}' marked as completed (retried).",
            "data": updated_entry,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to retry DLQ item: {e}")


@router.delete("/api/dlq/items/{item_id}")
async def dlq_delete_item(item_id: str):
    """Delete a DLQ item.

    Permanently removes the entry from the dead letter queue.

    Args:
        item_id: The UUID of the DLQ entry to delete.

    Returns:
        Confirmation of deletion.
    """
    try:
        entry = get_entry(item_id)
        if entry is None:
            raise HTTPException(404, f"DLQ item '{item_id}' not found.")

        success = delete_entry(item_id)
        if not success:
            raise HTTPException(500, f"Failed to delete DLQ item '{item_id}'.")

        return {
            "success": True,
            "message": f"DLQ item '{item_id}' deleted.",
            "deleted_entry": {
                "id": item_id,
                "operation": entry.get("operation"),
                "error_message": entry.get("error_message"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to delete DLQ item: {e}")
