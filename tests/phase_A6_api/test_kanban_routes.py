"""
test_kanban_routes.py — Tests for the Kanban board management API.

NOTE: kanban_routes uses lazy imports inside functions (_get_supabase, get_thoughts_for_card, etc.)
and the conftest _mock_supabase_client patches at the source module level.
"""

import json
import sys
import pytest
from unittest.mock import MagicMock, patch


def _mod():
    key = "apps.api.routers.kanban_routes"
    if key not in sys.modules:
        __import__(key)
    return sys.modules[key]


class TestListTasks:
    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        resp = await client.get("/api/kanban/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    @pytest.mark.asyncio
    async def test_list_tasks_returns_tasks(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"id": "card-1", "title": "Test Card", "status": "idle", "column_index": 1, "color": "#1D9E75", "updated_at": "2025-01-01", "created_at": "2025-01-01", "metadata": {}}
        ]
        # Patch get_thoughts_for_card at source since _card_to_kanban_dict imports it lazily
        with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]):
            resp = await client.get("/api/kanban/tasks")
            assert resp.status_code == 200
            tasks = resp.json()["tasks"]
            assert len(tasks) == 1
            assert tasks[0]["id"] == "card-1"

    @pytest.mark.asyncio
    async def test_list_tasks_skips_soft_deleted(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"id": "card-1", "title": "Del", "status": "idle", "column_index": 1, "color": "#1D9E75", "updated_at": "2025-01-01", "created_at": "2025-01-01", "metadata": {"deleted_at": "2025-01-01"}},
            {"id": "card-2", "title": "Act", "status": "idle", "column_index": 1, "color": "#1D9E75", "updated_at": "2025-01-01", "created_at": "2025-01-01", "metadata": {}},
        ]
        with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]):
            resp = await client.get("/api/kanban/tasks")
            tasks = resp.json()["tasks"]
            assert len(tasks) == 1
            assert tasks[0]["id"] == "card-2"

    @pytest.mark.asyncio
    async def test_list_tasks_supabase_error(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.order.return_value.limit.return_value.execute.side_effect = Exception("DB error")
        resp = await client.get("/api/kanban/tasks")
        assert resp.json()["tasks"] == []


class TestGetTask:
    @pytest.mark.asyncio
    async def test_get_task_404(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        resp = await client.get("/api/kanban/tasks/nonexistent")
        assert resp.status_code == 404


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_update_task_404(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        resp = await client.patch("/api/kanban/tasks/nonexistent", json={"stage": 2})
        assert resp.status_code == 404


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_soft_delete_success(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"id": "card-1", "metadata": {}}
        resp = await client.delete("/api/kanban/tasks/card-1")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "soft"

    @pytest.mark.asyncio
    async def test_soft_delete_404(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        resp = await client.delete("/api/kanban/tasks/nonexistent")
        assert resp.status_code == 404


class TestHardDelete:
    @pytest.mark.asyncio
    async def test_hard_delete_success(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"id": "card-1"}
        with patch("packages.core.thoughts.delete_thoughts_for_card"):
            resp = await client.post("/api/kanban/tasks/card-1/hard-delete")
            assert resp.status_code == 200
            assert resp.json()["mode"] == "hard"

    @pytest.mark.asyncio
    async def test_hard_delete_404(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        resp = await client.post("/api/kanban/tasks/nonexistent/hard-delete")
        assert resp.status_code == 404


class TestUndoDelete:
    @pytest.mark.asyncio
    async def test_undo_delete_success(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "card-1", "metadata": {"deleted_at": "2025-01-01"}
        }
        with patch("packages.core.thoughts.delete_thoughts_for_card"):
            resp = await client.post("/api/kanban/tasks/undo-delete/card-1")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_undo_delete_not_deleted(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"id": "card-1", "metadata": {}}
        resp = await client.post("/api/kanban/tasks/undo-delete/card-1")
        assert resp.status_code == 400


class TestKanbanStats:
    @pytest.mark.asyncio
    async def test_stats_returns_counts(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"column_index": 1, "status": "idle", "metadata": {}},
        ]
        resp = await client.get("/api/kanban/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "by_stage" in data

    @pytest.mark.asyncio
    async def test_stats_error(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.order.return_value.limit.return_value.execute.side_effect = Exception("DB error")
        resp = await client.get("/api/kanban/stats")
        assert resp.json()["total_tasks"] == 0


class TestRecordKanbanEvent:
    @pytest.mark.asyncio
    async def test_record_thought_event(self, client):
        with patch("packages.core.thoughts.report_thought") as m_report:
            resp = await client.post("/api/kanban/events", json={
                "task_id": "card-1", "event_type": "thought",
                "data": {"content": "Thinking", "agent_name": "researcher"},
            })
            assert resp.status_code == 200
            assert resp.json()["event_type"] == "thought"
            m_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_stage_change_event(self, client):
        resp = await client.post("/api/kanban/events", json={
            "task_id": "card-1", "event_type": "stage_change",
            "data": {"from_stage": 1, "to_stage": 2},
        })
        assert resp.status_code == 200


class TestSaveCard:
    @pytest.mark.asyncio
    async def test_save_card(self, client, _mock_supabase_client):
        resp = await client.post("/api/kanban/cards/card-1/save")
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"


class TestExtendExpiration:
    @pytest.mark.asyncio
    async def test_extend_success(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.execute.return_value.data = [{"id": "card-1"}]
        resp = await client.post("/api/kanban/tasks/card-1/extend")
        assert resp.status_code == 200
        assert resp.json()["extended_by_hours"] == 3

    @pytest.mark.asyncio
    async def test_extend_404(self, client, _mock_supabase_client):
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.execute.return_value.data = []
        resp = await client.post("/api/kanban/tasks/nonexistent/extend")
        assert resp.status_code == 404


class TestMoveCard:
    @pytest.mark.asyncio
    async def test_move_card_success(self, client, _mock_supabase_client):
        resp = await client.put("/api/kanban/cards/card-1/move", json={"column": 3})
        assert resp.status_code == 200
        assert resp.json()["status"] == "moved"


class TestCardToKanbanDict:
    def test_basic_card_conversion(self):
        mod = _mod()
        with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]):
            card = {"id": "c1", "title": "Test", "status": "idle", "column_index": 2, "color": "#FF5733", "updated_at": "", "created_at": "", "metadata": {}}
            result = mod._card_to_kanban_dict(card)
            assert result["id"] == "c1"
            assert result["stage"] == 2

    def test_thinking_status(self):
        mod = _mod()
        with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]):
            card = {"id": "c1", "title": "T", "status": "thinking", "column_index": 1, "color": "#1D9E75", "updated_at": "2025-01-01", "created_at": "2025-01-01", "metadata": {}}
            result = mod._card_to_kanban_dict(card)
            assert result["status"] == "thinking"
            assert result["thinking_started_at"] == "2025-01-01"

    def test_error_status(self):
        mod = _mod()
        with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]):
            card = {"id": "c1", "title": "E", "status": "error", "column_index": 1, "color": "", "updated_at": "", "created_at": "", "metadata": {}, "error_message": "fail"}
            result = mod._card_to_kanban_dict(card)
            assert result["status"] == "error"

    def test_metadata_string(self):
        mod = _mod()
        with patch("packages.core.thoughts.get_thoughts_for_card", return_value=[]):
            card = {"id": "c1", "title": "T", "status": "idle", "column_index": 1, "color": "", "updated_at": "", "created_at": "", "metadata": json.dumps({"key": "val"})}
            result = mod._card_to_kanban_dict(card)
            assert result["id"] == "c1"
