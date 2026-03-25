"""
dead_letter.py — Dead Letter Queue for failed operations.

Provides a persistent queue for operations that failed after all retry attempts.
Allows manual or automatic retry of failed operations later.

Usage:
    from packages.core.dead_letter import queue_for_retry, get_pending_retries

    # Queue a failed operation
    queue_for_retry("notion_publish", {"page_id": "abc", "content": "..."})

    # Get pending operations for manual retry
    pending = get_pending_retries("notion_publish")

Imports: json, datetime, pathlib
Imported by: packages/integrations/, apps/api/routers/
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.core.config import get_settings
from packages.core.logger import get_logger

log = get_logger(__name__)


def queue_for_retry(
    operation: str,
    payload: dict[str, Any],
    error_message: str = "",
    run_id: str | None = None,
) -> str:
    """Queue a failed operation for later retry.

    Writes an entry to the dead letter queue file (JSONL format).
    Each entry includes operation type, payload, timestamps, and retry count.

    Args:
        operation: Type of operation (e.g., "notion_publish", "youtube_upload").
        payload: The operation payload/data that failed.
        error_message: The error that caused the failure.
        run_id: Optional pipeline run ID for context.

    Returns:
        Entry ID (UUID) for the queued item.

    Example:
        queue_for_retry(
            operation="notion_publish",
            payload={"title": "My Video", "sections": [...]},
            error_message="Connection timeout",
            run_id="abc-123"
        )
    """
    import uuid

    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"
    dlq_path.parent.mkdir(parents=True, exist_ok=True)

    entry_id = str(uuid.uuid4())
    entry = {
        "id": entry_id,
        "operation": operation,
        "payload": payload,
        "error_message": error_message,
        "run_id": run_id,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "status": "pending",
    }

    with open(dlq_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    log.info(
        f"dead_letter_queued: operation={operation} id={entry_id}",
        extra={"operation": operation, "entry_id": entry_id, "run_id": run_id}
    )

    return entry_id


def get_pending_retries(operation: str | None = None) -> list[dict[str, Any]]:
    """Get all pending retry operations from the dead letter queue.

    Reads the dead letter queue file and returns entries with status "pending".
    Optionally filters by operation type.

    Args:
        operation: Optional operation type to filter by (e.g., "notion_publish").
                   If None, returns all pending operations.

    Returns:
        List of pending entry dictionaries, each containing:
        - id: Unique entry ID
        - operation: Operation type
        - payload: The operation data
        - error_message: What caused the failure
        - run_id: Associated pipeline run ID (if any)
        - queued_at: When the operation was queued
        - retry_count: Number of retry attempts so far
        - status: Current status (should be "pending")

    Example:
        pending = get_pending_retries("notion_publish")
        for entry in pending:
            print(f"Retry {entry['id']}: {entry['payload']['title']}")
    """
    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"

    if not dlq_path.exists():
        return []

    entries: list[dict[str, Any]] = []

    with open(dlq_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                if entry.get("status") == "pending":
                    if operation is None or entry.get("operation") == operation:
                        entries.append(entry)
            except json.JSONDecodeError as e:
                log.warning(f"dead_letter_parse_error: {e}")
                continue

    return entries


def mark_retry_attempt(entry_id: str, success: bool = False) -> bool:
    """Update an entry after a retry attempt.

    Increments the retry count and optionally marks as completed.

    Args:
        entry_id: The entry ID to update.
        success: Whether the retry succeeded. If True, marks as "completed".
                 If False, increments retry_count and keeps status "pending".

    Returns:
        True if entry was found and updated, False otherwise.
    """
    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"

    if not dlq_path.exists():
        return False

    # Read all entries
    entries: list[dict[str, Any]] = []
    found = False

    with open(dlq_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                if entry.get("id") == entry_id:
                    found = True
                    entry["retry_count"] = entry.get("retry_count", 0) + 1
                    entry["last_retry_at"] = datetime.now(timezone.utc).isoformat()

                    if success:
                        entry["status"] = "completed"
                        entry["completed_at"] = datetime.now(timezone.utc).isoformat()
                        log.info(f"dead_letter_completed: id={entry_id}")
                    else:
                        log.warning(
                            f"dead_letter_retry_failed: id={entry_id} "
                            f"retry_count={entry['retry_count']}"
                        )

                entries.append(entry)
            except json.JSONDecodeError:
                continue

    if not found:
        return False

    # Write back all entries
    with open(dlq_path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    return True


def get_all_entries(include_completed: bool = False) -> list[dict[str, Any]]:
    """Get all entries from the dead letter queue.

    Args:
        include_completed: If True, includes completed entries.
                          If False, only returns pending and failed entries.

    Returns:
        List of entry dictionaries.
    """
    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"

    if not dlq_path.exists():
        return []

    entries: list[dict[str, Any]] = []

    with open(dlq_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                if include_completed or entry.get("status") != "completed":
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

    return entries


def clear_completed_entries(max_age_hours: int = 24) -> int:
    """Remove completed entries older than the specified age.

    Args:
        max_age_hours: Maximum age in hours for completed entries to keep.

    Returns:
        Number of entries removed.
    """
    from datetime import timedelta

    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"

    if not dlq_path.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    entries: list[dict[str, Any]] = []
    removed_count = 0

    with open(dlq_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                if entry.get("status") == "completed":
                    completed_at_str = entry.get("completed_at", "")
                    if completed_at_str:
                        try:
                            completed_at = datetime.fromisoformat(completed_at_str)
                            if completed_at.replace(tzinfo=timezone.utc) < cutoff:
                                removed_count += 1
                                continue
                        except (ValueError, TypeError):
                            pass
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    if removed_count > 0:
        with open(dlq_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        log.info(f"dead_letter_cleanup: removed={removed_count}")

    return removed_count


def get_stats() -> dict[str, int]:
    """Get statistics about the dead letter queue.

    Returns:
        Dictionary with counts:
        - total: Total entries
        - pending: Pending entries
        - completed: Completed entries
        - by_operation: Dict of operation -> count
    """
    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"

    stats: dict[str, Any] = {
        "total": 0,
        "pending": 0,
        "completed": 0,
        "by_operation": {},
    }

    if not dlq_path.exists():
        return stats

    with open(dlq_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                stats["total"] += 1

                status = entry.get("status", "unknown")
                if status == "pending":
                    stats["pending"] += 1
                elif status == "completed":
                    stats["completed"] += 1

                operation = entry.get("operation", "unknown")
                stats["by_operation"][operation] = stats["by_operation"].get(operation, 0) + 1
            except json.JSONDecodeError:
                continue

    return stats
