"""
test_dlq_routes.py — Tests for the Dead Letter Queue management API.

Endpoints tested:
    GET    /api/dlq/stats              — DLQ statistics
    GET    /api/dlq/items              — List all DLQ items
    POST   /api/dlq/items/{id}/retry   — Retry a failed item
    DELETE /api/dlq/items/{id}         — Delete a DLQ item

NOTE: DLQ routes are registered WITHOUT a prefix (routes have /api/dlq/... in
      their path definitions directly), so the URL is just /api/dlq/stats.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDlqStats:
    """Tests for GET /api/dlq/stats."""

    @pytest.mark.asyncio
    async def test_stats_returns_success(self, client, mock_dead_letter):
        """Should return DLQ statistics."""
        mock_dead_letter["get_stats"].return_value = {
            "total": 5,
            "pending": 3,
            "completed": 2,
            "by_operation": {"notion_publish": 3, "youtube_upload": 2},
            "by_error_code": {},
            "by_severity": {"critical": 1},
        }

        resp = await client.get("/api/dlq/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total"] == 5
        assert data["data"]["pending"] == 3

    @pytest.mark.asyncio
    async def test_stats_empty_queue(self, client, mock_dead_letter):
        """Should return zeros for empty queue."""
        mock_dead_letter["get_stats"].return_value = {
            "total": 0, "pending": 0, "completed": 0,
            "by_operation": {}, "by_error_code": {}, "by_severity": {},
        }

        resp = await client.get("/api/dlq/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_stats_error(self, client, mock_dead_letter):
        """Should return 500 on error."""
        mock_dead_letter["get_stats"].side_effect = Exception("DB error")

        resp = await client.get("/api/dlq/stats")
        assert resp.status_code == 500


class TestDlqListItems:
    """Tests for GET /api/dlq/items."""

    @pytest.mark.asyncio
    async def test_list_items_all(self, client, mock_dead_letter):
        """Should list all pending items by default."""
        mock_dead_letter["get_all_entries"].return_value = [
            {"id": "item-1", "operation": "notion_publish", "status": "pending"},
            {"id": "item-2", "operation": "youtube_upload", "status": "pending"},
        ]

        resp = await client.get("/api/dlq/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_list_items_empty(self, client, mock_dead_letter):
        """Should return empty list for no items."""
        mock_dead_letter["get_all_entries"].return_value = []

        resp = await client.get("/api/dlq/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_list_items_filter_pending(self, client, mock_dead_letter):
        """Should filter by status=pending."""
        mock_dead_letter["get_all_entries"].return_value = [
            {"id": "item-1", "status": "pending"},
            {"id": "item-2", "status": "completed"},
        ]

        resp = await client.get("/api/dlq/items?status=pending")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["data"][0]["id"] == "item-1"

    @pytest.mark.asyncio
    async def test_list_items_filter_completed(self, client, mock_dead_letter):
        """Should filter by status=completed."""
        mock_dead_letter["get_all_entries"].return_value = [
            {"id": "item-1", "status": "pending"},
            {"id": "item-2", "status": "completed"},
        ]

        resp = await client.get("/api/dlq/items?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["data"][0]["id"] == "item-2"

    @pytest.mark.asyncio
    async def test_list_items_invalid_status(self, client, mock_dead_letter):
        """Should return 400 for invalid status filter."""
        resp = await client.get("/api/dlq/items?status=invalid")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_items_include_completed(self, client, mock_dead_letter):
        """Should include completed entries when requested."""
        mock_dead_letter["get_all_entries"].return_value = [
            {"id": "item-1", "status": "pending"},
            {"id": "item-2", "status": "completed"},
        ]

        resp = await client.get("/api/dlq/items?include_completed=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_list_items_error(self, client, mock_dead_letter):
        """Should return 500 on error."""
        mock_dead_letter["get_all_entries"].side_effect = Exception("Read error")

        resp = await client.get("/api/dlq/items")
        assert resp.status_code == 500


class TestDlqRetryItem:
    """Tests for POST /api/dlq/items/{item_id}/retry."""

    @pytest.mark.asyncio
    async def test_retry_success(self, client, mock_dead_letter):
        """Should mark an item as retried/completed."""
        # Use side_effect so first call returns pending, second returns completed
        mock_dead_letter["get_entry"].side_effect = [
            {"id": "item-1", "operation": "notion_publish", "status": "pending"},
            {"id": "item-1", "operation": "notion_publish", "status": "completed", "retry_count": 1},
        ]
        mock_dead_letter["mark_retry_attempt"].return_value = True

        resp = await client.post("/api/dlq/items/item-1/retry")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "marked as completed" in data["message"]

    @pytest.mark.asyncio
    async def test_retry_not_found(self, client, mock_dead_letter):
        """Should return 404 for nonexistent item."""
        mock_dead_letter["get_entry"].return_value = None

        resp = await client.post("/api/dlq/items/nonexistent/retry")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_already_completed(self, client, mock_dead_letter):
        """Should return 400 for already-completed item."""
        mock_dead_letter["get_entry"].return_value = {
            "id": "item-1", "operation": "notion_publish", "status": "completed",
        }

        resp = await client.post("/api/dlq/items/item-1/retry")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_mark_fails(self, client, mock_dead_letter):
        """Should return 500 when mark_retry_attempt fails."""
        mock_dead_letter["get_entry"].return_value = {
            "id": "item-1", "status": "pending",
        }
        mock_dead_letter["mark_retry_attempt"].return_value = False

        resp = await client.post("/api/dlq/items/item-1/retry")
        assert resp.status_code == 500


class TestDlqDeleteItem:
    """Tests for DELETE /api/dlq/items/{item_id}."""

    @pytest.mark.asyncio
    async def test_delete_success(self, client, mock_dead_letter):
        """Should delete an item."""
        mock_dead_letter["get_entry"].return_value = {
            "id": "item-1", "operation": "notion_publish",
            "error_message": "Connection timeout",
        }
        mock_dead_letter["delete_entry"].return_value = True

        resp = await client.delete("/api/dlq/items/item-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["deleted_entry"]["id"] == "item-1"
        assert data["deleted_entry"]["operation"] == "notion_publish"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client, mock_dead_letter):
        """Should return 404 for nonexistent item."""
        mock_dead_letter["get_entry"].return_value = None

        resp = await client.delete("/api/dlq/items/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_fails(self, client, mock_dead_letter):
        """Should return 500 when delete_entry fails."""
        mock_dead_letter["get_entry"].return_value = {"id": "item-1"}
        mock_dead_letter["delete_entry"].return_value = False

        resp = await client.delete("/api/dlq/items/item-1")
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_error(self, client, mock_dead_letter):
        """Should return 500 on exception."""
        mock_dead_letter["get_entry"].side_effect = Exception("DB error")

        resp = await client.delete("/api/dlq/items/item-1")
        assert resp.status_code == 500
