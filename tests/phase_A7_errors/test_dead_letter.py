"""
test_dead_letter.py — Phase A.7: Tests for packages/core/dead_letter.py

Covers:
  - queue_for_retry() — all parameters, entry structure, file creation
  - get_pending_retries() — filter by operation, empty queue, malformed lines
  - mark_retry_attempt() — success=True/False, unknown entry id
  - get_entry() — found / not found
  - delete_entry() — found / not found, file removal
  - get_all_entries() — include_completed flag
  - clear_completed_entries() — age-based removal
  - get_stats() — count aggregation, by_operation, by_error_code, by_severity
  - Edge cases: missing file, empty file, malformed JSON
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


class TestQueueForRetry:
    """Tests for queue_for_retry() function."""

    def test_returns_entry_id(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry
        entry_id = queue_for_retry("test_op", {"key": "val"})
        assert isinstance(entry_id, str)
        assert len(entry_id) == 36  # UUID format

    def test_creates_dlq_file(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry
        dlq_file = tmp_dlq_dir / "dead_letter_queue.jsonl"
        queue_for_retry("test_op", {"key": "val"})
        assert dlq_file.exists()

    def test_entry_has_required_fields(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry
        entry_id = queue_for_retry(
            "notion_publish",
            {"page_id": "abc"},
            error_message="Connection timeout",
            run_id="run-123",
            error_code="NOTION_PUBLISH_FAILED",
            severity="critical",
        )
        # Read the file to check the entry
        dlq_file = tmp_dlq_dir / "dead_letter_queue.jsonl"
        with open(dlq_file) as f:
            entry = json.loads(f.readline())

        assert entry["id"] == entry_id
        assert entry["operation"] == "notion_publish"
        assert entry["payload"] == {"page_id": "abc"}
        assert entry["error_message"] == "Connection timeout"
        assert entry["run_id"] == "run-123"
        assert entry["error_code"] == "NOTION_PUBLISH_FAILED"
        assert entry["severity"] == "critical"
        assert entry["retry_count"] == 0
        assert entry["status"] == "pending"
        assert "queued_at" in entry

    def test_default_optional_params(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry
        queue_for_retry("test_op", {"data": 1})
        dlq_file = tmp_dlq_dir / "dead_letter_queue.jsonl"
        with open(dlq_file) as f:
            entry = json.loads(f.readline())

        assert entry["error_message"] == ""
        assert entry["run_id"] is None
        assert entry["error_code"] == ""
        assert entry["severity"] == ""

    def test_queued_at_is_iso_format(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry
        queue_for_retry("test_op", {})
        dlq_file = tmp_dlq_dir / "dead_letter_queue.jsonl"
        with open(dlq_file) as f:
            entry = json.loads(f.readline())
        # Should be parseable ISO format
        dt = datetime.fromisoformat(entry["queued_at"])
        assert dt.tzinfo is not None

    def test_multiple_entries_appended(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry
        ids = [queue_for_retry("op", {"i": i}) for i in range(3)]
        dlq_file = tmp_dlq_dir / "dead_letter_queue.jsonl"
        lines = dlq_file.read_text().strip().split("\n")
        assert len(lines) == 3
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert entry["id"] == ids[i]
            assert entry["payload"]["i"] == i

    def test_creates_parent_directory(self, mock_get_settings, tmp_path):
        """DATA_DIR subdirectory should be created if it doesn't exist."""
        deep_dir = tmp_path / "a" / "b" / "c"
        mock_settings = type("MockSettings", (), {"DATA_DIR": str(deep_dir)})()
        with patch("packages.core.dead_letter.get_settings", return_value=mock_settings):
            from packages.core.dead_letter import queue_for_retry
            queue_for_retry("test_op", {})
        assert deep_dir.exists()


class TestGetPendingRetries:
    """Tests for get_pending_retries() function."""

    def test_empty_queue_returns_empty_list(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import get_pending_retries
        result = get_pending_retries()
        assert result == []

    def test_returns_pending_entries(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, get_pending_retries
        queue_for_retry("op_a", {"x": 1})
        queue_for_retry("op_b", {"x": 2})
        pending = get_pending_retries()
        assert len(pending) == 2

    def test_filter_by_operation(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, get_pending_retries
        queue_for_retry("op_a", {"x": 1})
        queue_for_retry("op_b", {"x": 2})
        queue_for_retry("op_a", {"x": 3})
        pending_a = get_pending_retries("op_a")
        pending_b = get_pending_retries("op_b")
        assert len(pending_a) == 2
        assert len(pending_b) == 1

    def test_excludes_completed_entries(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, get_pending_retries, mark_retry_attempt
        entry_id = queue_for_retry("op", {"x": 1})
        mark_retry_attempt(entry_id, success=True)
        pending = get_pending_retries()
        assert len(pending) == 0

    def test_skips_malformed_json_lines(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import get_pending_retries
        dlq_file = tmp_dlq_dir / "dead_letter_queue.jsonl"
        dlq_file.write_text('{"id":"1","operation":"op","status":"pending"}\nnot-json\n')
        pending = get_pending_retries()
        assert len(pending) == 1

    def test_skips_empty_lines(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import get_pending_retries
        dlq_file = tmp_dlq_dir / "dead_letter_queue.jsonl"
        dlq_file.write_text('\n\n{"id":"1","operation":"op","status":"pending"}\n\n')
        pending = get_pending_retries()
        assert len(pending) == 1

    def test_none_operation_returns_all(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, get_pending_retries
        queue_for_retry("op_a", {})
        queue_for_retry("op_b", {})
        pending = get_pending_retries(operation=None)
        assert len(pending) == 2


class TestMarkRetryAttempt:
    """Tests for mark_retry_attempt() function."""

    def test_success_marks_completed(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, mark_retry_attempt, get_entry
        entry_id = queue_for_retry("op", {"x": 1})
        result = mark_retry_attempt(entry_id, success=True)
        assert result is True
        entry = get_entry(entry_id)
        assert entry["status"] == "completed"
        assert entry["retry_count"] == 1
        assert "completed_at" in entry
        assert "last_retry_at" in entry

    def test_failure_increments_count(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, mark_retry_attempt, get_entry
        entry_id = queue_for_retry("op", {"x": 1})
        mark_retry_attempt(entry_id, success=False)
        entry = get_entry(entry_id)
        assert entry["status"] == "pending"
        assert entry["retry_count"] == 1
        assert "last_retry_at" in entry
        assert "completed_at" not in entry

    def test_unknown_entry_returns_false(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import mark_retry_attempt
        result = mark_retry_attempt("nonexistent-uuid", success=True)
        assert result is False

    def test_missing_file_returns_false(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import mark_retry_attempt
        result = mark_retry_attempt("any-id")
        assert result is False

    def test_multiple_retry_attempts(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, mark_retry_attempt, get_entry
        entry_id = queue_for_retry("op", {"x": 1})
        for _ in range(5):
            mark_retry_attempt(entry_id, success=False)
        entry = get_entry(entry_id)
        assert entry["retry_count"] == 5
        assert entry["status"] == "pending"

    def test_final_success_after_failures(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, mark_retry_attempt, get_entry
        entry_id = queue_for_retry("op", {"x": 1})
        mark_retry_attempt(entry_id, success=False)
        mark_retry_attempt(entry_id, success=False)
        mark_retry_attempt(entry_id, success=True)
        entry = get_entry(entry_id)
        assert entry["retry_count"] == 3
        assert entry["status"] == "completed"


class TestGetEntry:
    """Tests for get_entry() function."""

    def test_returns_entry_by_id(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, get_entry
        entry_id = queue_for_retry("op", {"key": "val"})
        entry = get_entry(entry_id)
        assert entry is not None
        assert entry["id"] == entry_id
        assert entry["operation"] == "op"

    def test_returns_none_for_unknown_id(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import get_entry
        entry = get_entry("nonexistent-id")
        assert entry is None

    def test_returns_none_when_file_missing(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import get_entry
        entry = get_entry("any-id")
        assert entry is None

    def test_finds_entry_among_many(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, get_entry
        ids = [queue_for_retry("op", {"i": i}) for i in range(5)]
        entry = get_entry(ids[2])
        assert entry["payload"]["i"] == 2


class TestDeleteEntry:
    """Tests for delete_entry() function."""

    def test_deletes_existing_entry(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, delete_entry, get_entry
        entry_id = queue_for_retry("op", {"key": "val"})
        result = delete_entry(entry_id)
        assert result is True
        assert get_entry(entry_id) is None

    def test_unknown_entry_returns_false(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import delete_entry
        result = delete_entry("nonexistent-id")
        assert result is False

    def test_missing_file_returns_false(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import delete_entry
        result = delete_entry("any-id")
        assert result is False

    def test_preserves_other_entries(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, delete_entry, get_pending_retries
        id1 = queue_for_retry("op", {"keep": True})
        id2 = queue_for_retry("op", {"delete": True})
        id3 = queue_for_retry("op", {"keep": True})
        delete_entry(id2)
        pending = get_pending_retries()
        assert len(pending) == 2
        remaining_ids = {e["id"] for e in pending}
        assert id1 in remaining_ids
        assert id3 in remaining_ids
        assert id2 not in remaining_ids


class TestGetAllEntries:
    """Tests for get_all_entries() function."""

    def test_returns_all_entries(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, mark_retry_attempt, get_all_entries
        queue_for_retry("op", {"i": 1})
        id2 = queue_for_retry("op", {"i": 2})
        queue_for_retry("op", {"i": 3})
        mark_retry_attempt(id2, success=True)

        all_entries = get_all_entries(include_completed=True)
        assert len(all_entries) == 3

    def test_excludes_completed_by_default(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, mark_retry_attempt, get_all_entries
        queue_for_retry("op", {"i": 1})
        id2 = queue_for_retry("op", {"i": 2})
        queue_for_retry("op", {"i": 3})
        mark_retry_attempt(id2, success=True)

        active = get_all_entries(include_completed=False)
        assert len(active) == 2

    def test_empty_queue(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import get_all_entries
        assert get_all_entries() == []


class TestClearCompletedEntries:
    """Tests for clear_completed_entries() function."""

    def test_removes_old_completed(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import (
            queue_for_retry, mark_retry_attempt, clear_completed_entries, get_all_entries,
        )
        # Create a completed entry
        entry_id = queue_for_retry("op", {"x": 1})
        mark_retry_attempt(entry_id, success=True)

        # Manually set completed_at to be older than the max_age
        dlq_file = tmp_dlq_dir / "dead_letter_queue.jsonl"
        old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        content = dlq_file.read_text()
        content = content.replace(
            '"completed_at":',
            f'"completed_at": "{old_time}", "completed_at_original":'
        )
        # Simpler: rewrite the file with old completed_at
        import json as _json
        lines = dlq_file.read_text().strip().split("\n")
        with open(dlq_file, "w") as f:
            for line in lines:
                entry = _json.loads(line)
                if entry["status"] == "completed":
                    entry["completed_at"] = old_time
                f.write(_json.dumps(entry) + "\n")

        removed = clear_completed_entries(max_age_hours=24)
        assert removed == 1
        assert len(get_all_entries(include_completed=True)) == 0

    def test_keeps_recent_completed(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import (
            queue_for_retry, mark_retry_attempt, clear_completed_entries, get_all_entries,
        )
        entry_id = queue_for_retry("op", {"x": 1})
        mark_retry_attempt(entry_id, success=True)

        removed = clear_completed_entries(max_age_hours=24)
        assert removed == 0
        assert len(get_all_entries(include_completed=True)) == 1

    def test_missing_file_returns_zero(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import clear_completed_entries
        assert clear_completed_entries() == 0

    def test_does_not_remove_pending(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import (
            queue_for_retry, clear_completed_entries, get_pending_retries,
        )
        queue_for_retry("op", {"x": 1})
        queue_for_retry("op", {"x": 2})
        removed = clear_completed_entries(max_age_hours=0)
        assert removed == 0
        assert len(get_pending_retries()) == 2


class TestGetStats:
    """Tests for get_stats() function."""

    def test_empty_queue_stats(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import get_stats
        stats = get_stats()
        assert stats["total"] == 0
        assert stats["pending"] == 0
        assert stats["completed"] == 0
        assert stats["by_operation"] == {}
        assert stats["by_error_code"] == {}
        assert stats["by_severity"] == {}

    def test_counts_correct(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, mark_retry_attempt, get_stats
        queue_for_retry("notion_publish", {"p": 1}, error_code="NOTION_PUBLISH_FAILED", severity="critical")
        id2 = queue_for_retry("youtube_upload", {"p": 2}, error_code="YOUTUBE_AUTH_FAILED", severity="warning")
        queue_for_retry("notion_publish", {"p": 3}, error_code="NOTION_RATE_LIMIT", severity="warning")
        mark_retry_attempt(id2, success=True)

        stats = get_stats()
        assert stats["total"] == 3
        assert stats["pending"] == 2
        assert stats["completed"] == 1
        assert stats["by_operation"]["notion_publish"] == 2
        assert stats["by_operation"]["youtube_upload"] == 1
        assert stats["by_error_code"]["NOTION_PUBLISH_FAILED"] == 1
        assert stats["by_error_code"]["NOTION_RATE_LIMIT"] == 1
        assert stats["by_error_code"]["YOUTUBE_AUTH_FAILED"] == 1
        assert stats["by_severity"]["critical"] == 1
        assert stats["by_severity"]["warning"] == 2

    def test_empty_error_code_not_counted(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, get_stats
        queue_for_retry("op", {}, error_code="")
        stats = get_stats()
        assert "by_error_code" not in stats or "" not in stats["by_error_code"]

    def test_empty_severity_not_counted(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import queue_for_retry, get_stats
        queue_for_retry("op", {}, severity="")
        stats = get_stats()
        assert "by_severity" not in stats or "" not in stats["by_severity"]

    def test_missing_file_returns_empty_stats(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import get_stats
        stats = get_stats()
        assert stats["total"] == 0


class TestFileLock:
    """Tests for the _FileLock context manager."""

    def test_file_lock_enter_exit(self, tmp_path):
        from packages.core.dead_letter import _FileLock
        lock_file = tmp_path / "lock_test.txt"
        lock_file.write_text("data")
        with open(lock_file) as f:
            lock = _FileLock(f, exclusive=True)
            lock.__enter__()
            lock.__exit__(None, None, None)
        # Should not raise

    def test_file_lock_non_exclusive(self, tmp_path):
        from packages.core.dead_letter import _FileLock
        lock_file = tmp_path / "lock_test_shared.txt"
        lock_file.write_text("data")
        with open(lock_file) as f:
            lock = _FileLock(f, exclusive=False)
            lock.__enter__()
            lock.__exit__(None, None, None)
        # Should not raise


class TestMalformedData:
    """Tests for handling malformed data in the DLQ file."""

    def test_corrupt_lines_skipped_gracefully(self, mock_get_settings, tmp_dlq_dir):
        from packages.core.dead_letter import get_pending_retries, get_all_entries, get_stats
        dlq_file = tmp_dlq_dir / "dead_letter_queue.jsonl"
        dlq_file.write_text(
            '{"id":"1","operation":"op","status":"pending"}\n'
            '{broken json\n'
            '{"id":"2","operation":"op","status":"pending"}\n'
            'totally not json\n'
            '{"id":"3","operation":"op","status":"pending"}\n'
        )
        pending = get_pending_retries()
        assert len(pending) == 3
        all_entries = get_all_entries()
        assert len(all_entries) == 3
        stats = get_stats()
        assert stats["total"] == 3
