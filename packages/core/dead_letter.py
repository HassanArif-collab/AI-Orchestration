"""
dead_letter.py — Dead Letter Queue for failed operations.

Provides a persistent queue for operations that failed after all retry attempts.
Allows manual or automatic retry of failed operations later.

All file operations use fcntl file locking to prevent corruption from
concurrent access. Each entry can carry an error_code and severity
for structured error handling by the frontend.

Usage:
    from packages.core.dead_letter import queue_for_retry, get_pending_retries

    # Queue a failed operation
    queue_for_retry("notion_publish", {"page_id": "abc", "content": "..."},
                    error_message="Connection timeout", error_code="NOTION_PUBLISH_FAILED",
                    severity="critical")

    # Get pending operations for manual retry
    pending = get_pending_retries("notion_publish")

    # Get a single entry
    entry = get_entry("some-uuid")

    # Delete a specific entry
    delete_entry("some-uuid")

Imports: json, datetime, pathlib
Imported by: packages/integrations/, apps/api/routers/
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.core.config import get_settings
from packages.core.logger import get_logger

log = get_logger(__name__)

# ─── Cross-platform file locking ──────────────────────────────────────
# fcntl is Unix-only. On Windows we use msvcrt.locking as a fallback.
# For simplicity, we provide no-op stubs on platforms without locking.

_IS_WIN = sys.platform == "win32"

try:
    import fcntl as _fcntl
except ImportError:
    _fcntl = None

try:
    import msvcrt as _msvcrt
except ImportError:
    _msvcrt = None


class _FileLock:
    """Cross-platform file lock context manager."""

    def __init__(self, file_obj, exclusive: bool = True):
        self._f = file_obj
        self._exclusive = exclusive

    def __enter__(self):
        if _fcntl is not None:
            lock_type = _fcntl.LOCK_EX if self._exclusive else _fcntl.LOCK_SH
            _fcntl.flock(self._f, lock_type)
        return self

    def __exit__(self, *args):
        if _fcntl is not None:
            _fcntl.flock(self._f, _fcntl.LOCK_UN)


def queue_for_retry(
    operation: str,
    payload: dict[str, Any],
    error_message: str = "",
    run_id: str | None = None,
    error_code: str = "",
    severity: str = "",
) -> str:
    """Queue a failed operation for later retry.

    Writes an entry to the dead letter queue file (JSONL format).
    Each entry includes operation type, payload, timestamps, and retry count.
    Uses exclusive file locking to prevent concurrent write corruption.

    Args:
        operation: Type of operation (e.g., "notion_publish", "youtube_upload").
        payload: The operation payload/data that failed.
        error_message: The error that caused the failure.
        run_id: Optional pipeline run ID for context.
        error_code: Optional structured error code (e.g., "NOTION_RATE_LIMIT").
        severity: Optional severity level (e.g., "critical", "warning").

    Returns:
        Entry ID (UUID) for the queued item.

    Example:
        queue_for_retry(
            operation="notion_publish",
            payload={"title": "My Video", "sections": [...]},
            error_message="Connection timeout",
            run_id="abc-123",
            error_code="NOTION_RATE_LIMIT",
            severity="warning",
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
        "error_code": error_code,
        "severity": severity,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "status": "pending",
    }

    with open(dlq_path, "a") as f:
        with _FileLock(f, exclusive=True):
            f.write(json.dumps(entry) + "\n")

    log.info(
        f"dead_letter_queued: operation={operation} id={entry_id}",
        extra={"operation": operation, "entry_id": entry_id, "run_id": run_id}
    )

    return entry_id


def get_pending_retries(operation: str | None = None) -> list[dict[str, Any]]:
    """Get all pending retry operations from the dead letter queue.

    Reads the dead letter queue file and returns entries with status "pending".
    Optionally filters by operation type. Uses shared lock for safe concurrent reads.

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
        - error_code: Structured error code (if any)
        - severity: Severity level (if any)
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
        with _FileLock(f, exclusive=False):
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
    Uses exclusive lock during read-modify-write cycle.

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

    # Read all entries with exclusive lock
    entries: list[dict[str, Any]] = []
    found = False

    with open(dlq_path, "r+") as f:
        with _FileLock(f, exclusive=True):
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
            f.seek(0)
            f.truncate()
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    return True


def get_entry(entry_id: str) -> dict[str, Any] | None:
    """Get a single entry from the dead letter queue by ID.

    Args:
        entry_id: The UUID of the entry to retrieve.

    Returns:
        Entry dictionary if found, None otherwise.

    Example:
        entry = get_entry("some-uuid")
        if entry:
            print(entry["operation"], entry["error_message"])
    """
    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"

    if not dlq_path.exists():
        return None

    with open(dlq_path) as f:
        with _FileLock(f, exclusive=False):
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("id") == entry_id:
                        return entry
                except json.JSONDecodeError:
                    continue

    return None


def delete_entry(entry_id: str) -> bool:
    """Remove a single entry from the dead letter queue by ID.

    Args:
        entry_id: The UUID of the entry to delete.

    Returns:
        True if entry was found and deleted, False otherwise.

    Example:
        success = delete_entry("some-uuid")
        if success:
            print("Entry removed from DLQ")
    """
    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"

    if not dlq_path.exists():
        return False

    entries: list[dict[str, Any]] = []
    found = False

    with open(dlq_path, "r+") as f:
        with _FileLock(f, exclusive=True):
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("id") == entry_id:
                        found = True
                        log.info(f"dead_letter_deleted: id={entry_id} operation={entry.get('operation')}")
                        continue  # Skip this entry (delete it)
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue

            if not found:
                return False

            # Write back remaining entries
            f.seek(0)
            f.truncate()
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    return True


def get_all_entries(include_completed: bool = False) -> list[dict[str, Any]]:
    """Get all entries from the dead letter queue.

    Uses shared lock for safe concurrent reads.

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
        with _FileLock(f, exclusive=False):
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

    Uses exclusive lock during read-filter-write cycle.

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

    with open(dlq_path, "r+") as f:
        with _FileLock(f, exclusive=True):
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
                f.seek(0)
                f.truncate()
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")

                log.info(f"dead_letter_cleanup: removed={removed_count}")

    return removed_count


def get_stats() -> dict[str, Any]:
    """Get statistics about the dead letter queue.

    Uses shared lock for safe concurrent reads.

    Returns:
        Dictionary with counts:
        - total: Total entries
        - pending: Pending entries
        - completed: Completed entries
        - by_operation: Dict of operation -> count
        - by_error_code: Dict of error_code -> count
        - by_severity: Dict of severity -> count
    """
    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"

    stats: dict[str, Any] = {
        "total": 0,
        "pending": 0,
        "completed": 0,
        "by_operation": {},
        "by_error_code": {},
        "by_severity": {},
    }

    if not dlq_path.exists():
        return stats

    with open(dlq_path) as f:
        with _FileLock(f, exclusive=False):
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

                    error_code = entry.get("error_code", "")
                    if error_code:
                        stats["by_error_code"][error_code] = stats["by_error_code"].get(error_code, 0) + 1

                    severity = entry.get("severity", "")
                    if severity:
                        stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
                except json.JSONDecodeError:
                    continue

    return stats
