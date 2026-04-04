"""
Phase A.9 Batch C — tests for apps/api/background_tasks.py
JSON I/O helpers, start_research_for_topic, evaluate_script, run_daily_scan,
start_scheduler, cleanup_expired_cards.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.background_tasks import (
    _cleanup_task,
    _load_json_file,
    _save_json_file,
    _update_script_status,
    _update_topic_status,
    cleanup_expired_cards,
    evaluate_script,
    get_scheduler,
    run_daily_scan,
    start_cleanup_task,
    start_research_for_topic,
    start_scheduler,
    stop_cleanup_task,
)


# ─── Helpers ──────────────────────────────────────────────────────────────


def _make_settings(tmp_path):
    """Create a mock Settings object with DATA_DIR pointing to tmp_path."""
    settings = MagicMock()
    settings.DATA_DIR = str(tmp_path)
    return settings


def _write_topics_file(tmp_path, topics):
    """Write topics.json in the reservoir path."""
    d = tmp_path / "topic_reservoir"
    d.mkdir(parents=True, exist_ok=True)
    (d / "topics.json").write_text(json.dumps(topics, indent=2))


def _write_scripts_file(tmp_path, scripts):
    """Write scripts.json in the reservoir path."""
    d = tmp_path / "topic_reservoir"
    d.mkdir(parents=True, exist_ok=True)
    (d / "scripts.json").write_text(json.dumps(scripts, indent=2))


def _make_mock_supabase_module(get_supabase_fn):
    """Create a mock module for packages.core.supabase_client."""
    from types import ModuleType
    mod = ModuleType("mock_supabase_client")
    mod.get_supabase = get_supabase_fn
    return mod


# ─── JSON I/O ─────────────────────────────────────────────────────────────


class TestLoadJsonFile:
    """Test _load_json_file."""

    def test_load_existing_file(self, tmp_path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps([{"id": 1}]))
        result = _load_json_file(p)
        assert result == [{"id": 1}]

    def test_load_missing_file_returns_default(self, tmp_path):
        p = tmp_path / "nope.json"
        result = _load_json_file(p)
        assert result == []

    def test_load_missing_file_with_custom_default(self, tmp_path):
        p = tmp_path / "nope.json"
        result = _load_json_file(p, default={"key": "val"})
        assert result == {"key": "val"}

    def test_load_corrupt_json_returns_default(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("NOT VALID JSON{{{")
        result = _load_json_file(p)
        assert result == []

    def test_load_empty_file_returns_default(self, tmp_path):
        p = tmp_path / "empty.json"
        p.write_text("")
        result = _load_json_file(p)
        assert result == []  # json.loads("") raises JSONDecodeError


class TestSaveJsonFile:
    """Test _save_json_file."""

    def test_save_creates_file(self, tmp_path):
        p = tmp_path / "sub" / "out.json"
        assert not p.exists()
        ok = _save_json_file(p, {"data": [1, 2, 3]})
        assert ok is True
        assert p.exists()
        loaded = json.loads(p.read_text())
        assert loaded == {"data": [1, 2, 3]}

    def test_save_overwrites_existing(self, tmp_path):
        p = tmp_path / "out.json"
        p.write_text('{"old": true}')
        ok = _save_json_file(p, {"new": True})
        assert ok is True
        loaded = json.loads(p.read_text())
        assert loaded == {"new": True}

    def test_save_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "a" / "b" / "c" / "deep.json"
        ok = _save_json_file(p, [])
        assert ok is True
        assert p.exists()

    def test_save_handles_permission_error(self, tmp_path):
        p = tmp_path / "readonly_dir" / "out.json"
        p.parent.mkdir()
        # Make the directory read-only
        p.parent.chmod(0o444)
        try:
            ok = _save_json_file(p, {"x": 1})
            assert ok is False
        finally:
            p.parent.chmod(0o755)  # restore for cleanup


# ─── Topic Status Update ─────────────────────────────────────────────────


class TestUpdateTopicStatus:
    """Test _update_topic_status."""

    def test_update_existing_topic(self, tmp_path):
        topics = [{"id": "t1", "status": "new", "title": "AI in 2025"}]
        _write_topics_file(tmp_path, topics)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            ok = _update_topic_status("t1", "researching")

        assert ok is True
        updated = json.loads((tmp_path / "topic_reservoir" / "topics.json").read_text())
        assert updated[0]["status"] == "researching"
        assert "updated_at" in updated[0]

    def test_update_topic_not_found(self, tmp_path):
        topics = [{"id": "t1", "status": "new"}]
        _write_topics_file(tmp_path, topics)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            ok = _update_topic_status("nonexistent", "researching")

        assert ok is False

    def test_update_topic_with_extra_fields(self, tmp_path):
        topics = [{"id": "t1", "status": "new"}]
        _write_topics_file(tmp_path, topics)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            ok = _update_topic_status("t1", "researching", extra={"score": 90})

        assert ok is True
        updated = json.loads((tmp_path / "topic_reservoir" / "topics.json").read_text())
        assert updated[0]["score"] == 90

    def test_update_topic_empty_reservoir(self, tmp_path):
        _write_topics_file(tmp_path, [])

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            ok = _update_topic_status("t1", "researching")

        assert ok is False


# ─── Script Status Update ─────────────────────────────────────────────────


class TestUpdateScriptStatus:
    """Test _update_script_status."""

    def test_update_existing_script(self, tmp_path):
        scripts = [{"id": "s1", "status": "draft"}]
        _write_scripts_file(tmp_path, scripts)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            ok = _update_script_status("s1", "evaluating")

        assert ok is True
        updated = json.loads((tmp_path / "topic_reservoir" / "scripts.json").read_text())
        assert updated[0]["status"] == "evaluating"
        assert "updated_at" in updated[0]

    def test_update_script_not_found(self, tmp_path):
        scripts = [{"id": "s1", "status": "draft"}]
        _write_scripts_file(tmp_path, scripts)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            ok = _update_script_status("nonexistent", "evaluating")

        assert ok is False

    def test_update_script_with_extra(self, tmp_path):
        scripts = [{"id": "s1", "status": "draft"}]
        _write_scripts_file(tmp_path, scripts)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            ok = _update_script_status("s1", "production_ready", extra={"score": 95})

        assert ok is True
        updated = json.loads((tmp_path / "topic_reservoir" / "scripts.json").read_text())
        assert updated[0]["score"] == 95


# ─── start_research_for_topic ─────────────────────────────────────────────


class TestStartResearchForTopic:
    """Test the research background task."""

    @pytest.mark.asyncio
    async def test_research_success(self, tmp_path):
        topics = [{"id": "t1", "status": "approved", "title": "AI Trends"}]
        _write_topics_file(tmp_path, topics)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            await start_research_for_topic("t1")

        updated = json.loads((tmp_path / "topic_reservoir" / "topics.json").read_text())
        assert updated[0]["status"] == "researched"
        assert updated[0]["method"] == "langgraph_discovery"

    @pytest.mark.asyncio
    async def test_research_topic_not_found(self, tmp_path):
        topics = [{"id": "t1", "status": "approved"}]
        _write_topics_file(tmp_path, topics)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            await start_research_for_topic("nonexistent")

        # nonexistent id -> _update_topic_status fails (topic not found)
        # so t1 remains "approved"
        updated = json.loads((tmp_path / "topic_reservoir" / "topics.json").read_text())
        assert updated[0]["status"] == "approved"

    @pytest.mark.asyncio
    async def test_research_error_updates_to_failed(self, tmp_path):
        topics = [{"id": "t1", "status": "approved"}]
        _write_topics_file(tmp_path, topics)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings), \
             patch("apps.api.background_tasks._run_research_pipeline", side_effect=RuntimeError("boom")):
            await start_research_for_topic("t1")

        updated = json.loads((tmp_path / "topic_reservoir" / "topics.json").read_text())
        assert updated[0]["status"] == "research_failed"
        assert "boom" in updated[0].get("error", "")


# ─── evaluate_script ──────────────────────────────────────────────────────


class TestEvaluateScript:
    """Test the script evaluation background task."""

    @pytest.mark.asyncio
    async def test_evaluate_success(self, tmp_path):
        scripts = [{"id": "s1", "status": "draft"}]
        _write_scripts_file(tmp_path, scripts)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            await evaluate_script("s1")

        updated = json.loads((tmp_path / "topic_reservoir" / "scripts.json").read_text())
        assert updated[0]["status"] == "production_ready"
        assert updated[0]["score"] == 85.0
        assert updated[0]["evaluation_method"] == "langgraph_inline_scorer"

    @pytest.mark.asyncio
    async def test_evaluate_script_not_found(self, tmp_path):
        scripts = [{"id": "s1", "status": "draft"}]
        _write_scripts_file(tmp_path, scripts)

        mock_settings = _make_settings(tmp_path)
        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings):
            await evaluate_script("nonexistent")

        updated = json.loads((tmp_path / "topic_reservoir" / "scripts.json").read_text())
        # nonexistent id -> _update_script_status fails (script not found)
        # so s1 remains "draft"
        assert updated[0]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_evaluate_error_updates_to_failed(self, tmp_path):
        """When _run_research_pipeline equivalent fails, status should update to evaluation_failed."""
        scripts = [{"id": "s1", "status": "draft"}]
        _write_scripts_file(tmp_path, scripts)

        mock_settings = _make_settings(tmp_path)
        call_count = 0

        def load_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # 1st call: _update_script_status("evaluating") succeeds
                # 2nd call: evaluate_script body loads scripts -> raise
                if call_count == 2:
                    raise RuntimeError("DB read error")
                return scripts
            else:
                # 3rd call: _update_script_status("evaluation_failed") succeeds
                return [{"id": "s1", "status": "evaluating"}]

        with patch("apps.api.background_tasks.get_settings", return_value=mock_settings), \
             patch("apps.api.background_tasks._load_json_file", side_effect=load_side_effect):
            await evaluate_script("s1")

        updated = json.loads((tmp_path / "topic_reservoir" / "scripts.json").read_text())
        assert updated[0]["status"] == "evaluation_failed"
        assert "DB read error" in updated[0].get("error", "")


# ─── run_daily_scan ───────────────────────────────────────────────────────


class TestRunDailyScan:
    """Test the daily scan task."""

    @pytest.mark.asyncio
    async def test_scan_returns_count_on_success(self):
        mock_scan = AsyncMock(return_value=42)
        with patch.dict("sys.modules", {"scripts.daily_topic_scan": MagicMock(run_daily_scan=mock_scan)}):
            result = await run_daily_scan(["tech", "gaming"])
        assert result == 42

    @pytest.mark.asyncio
    async def test_scan_returns_none_on_import_error(self):
        import builtins
        real_import = builtins.__import__
        def fake_import(name, *a, **kw):
            if "scripts.daily_topic_scan" in name:
                raise ImportError("scripts.daily_topic_scan not found")
            return real_import(name, *a, **kw)
        with patch("builtins.__import__", side_effect=fake_import):
            result = await run_daily_scan()
        assert result is None

    @pytest.mark.asyncio
    async def test_scan_returns_none_on_runtime_error(self):
        mock_scan = AsyncMock(side_effect=RuntimeError("scan blew up"))
        mod = MagicMock(run_daily_scan=mock_scan)
        with patch.dict("sys.modules", {"scripts.daily_topic_scan": mod}):
            result = await run_daily_scan(["finance"])
        assert result is None

    @pytest.mark.asyncio
    async def test_scan_default_genres_none(self):
        mock_scan = AsyncMock(return_value=0)
        mod = MagicMock(run_daily_scan=mock_scan)
        with patch.dict("sys.modules", {"scripts.daily_topic_scan": mod}):
            result = await run_daily_scan()
        mock_scan.assert_called_once_with(None)
        assert result == 0


# ─── start_scheduler / get_scheduler ──────────────────────────────────────


class TestScheduler:
    """Test the (deprecated) scheduler functions."""

    def test_start_scheduler_returns_false(self):
        # Reset module-level state
        import apps.api.background_tasks as bt
        bt._scheduler = None
        assert start_scheduler() is False

    def test_start_scheduler_already_running(self):
        import apps.api.background_tasks as bt
        bt._scheduler = MagicMock()
        assert start_scheduler() is True
        bt._scheduler = None  # cleanup

    def test_get_scheduler_returns_none_initially(self):
        import apps.api.background_tasks as bt
        bt._scheduler = None
        assert get_scheduler() is None

    def test_get_scheduler_returns_instance(self):
        import apps.api.background_tasks as bt
        fake = MagicMock()
        bt._scheduler = fake
        assert get_scheduler() is fake
        bt._scheduler = None  # cleanup


# ─── cleanup_expired_cards ────────────────────────────────────────────────


class TestCleanupExpiredCards:
    """Test the expired card cleanup background task."""
    # get_supabase is lazily imported inside cleanup_expired_cards, so
    # we must patch at the source module level via sys.modules.

    @pytest.mark.asyncio
    async def test_cleanup_deletes_expired_cards(self):
        """Verify Supabase delete query is called correctly."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "card-1"}, {"id": "card-2"}]
        mock_sb.table.return_value.delete.return_value.eq.return_value \
            .not_.return_value.is_.return_value.lt.return_value.execute.return_value = mock_result

        mock_sb_mod = _make_mock_supabase_module(lambda: mock_sb)
        with patch.dict("sys.modules", {"packages.core.supabase_client": mock_sb_mod}), \
             patch("apps.api.background_tasks.asyncio.sleep", new_callable=AsyncMock, side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await cleanup_expired_cards()

        mock_sb.table.assert_called_once_with("kanban_cards")
        mock_sb.table().delete.assert_called_once()
        mock_sb.table().delete().eq.assert_called_once_with("column_index", 2)

    @pytest.mark.asyncio
    async def test_cleanup_handles_supabase_error(self):
        """Non-fatal: errors are caught and logged."""
        mock_sb_mod = _make_mock_supabase_module(
            lambda: (_ for _ in ()).throw(Exception("DB down"))
        )
        with patch.dict("sys.modules", {"packages.core.supabase_client": mock_sb_mod}), \
             patch("apps.api.background_tasks.asyncio.sleep", new_callable=AsyncMock, side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await cleanup_expired_cards()

    @pytest.mark.asyncio
    async def test_cleanup_no_expired_cards(self):
        """When no cards are expired, result.data is empty/None."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb.table.return_value.delete.return_value.eq.return_value \
            .not_.return_value.is_.return_value.lt.return_value.execute.return_value = mock_result

        mock_sb_mod = _make_mock_supabase_module(lambda: mock_sb)
        with patch.dict("sys.modules", {"packages.core.supabase_client": mock_sb_mod}), \
             patch("apps.api.background_tasks.asyncio.sleep", new_callable=AsyncMock, side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await cleanup_expired_cards()


class TestStartStopCleanupTask:
    """Test start_cleanup_task and stop_cleanup_task."""

    @pytest.mark.asyncio
    async def test_start_cleanup_task(self):
        import apps.api.background_tasks as bt
        bt._cleanup_task = None

        # Patch cleanup_expired_cards to immediately raise CancelledError
        async def fake_cleanup():
            raise asyncio.CancelledError()

        with patch("apps.api.background_tasks.cleanup_expired_cards", side_effect=fake_cleanup):
            result = start_cleanup_task()

        assert result is True
        assert bt._cleanup_task is not None
        bt._cleanup_task = None

    def test_start_cleanup_task_no_loop(self):
        import apps.api.background_tasks as bt
        bt._cleanup_task = None

        # No running event loop
        with pytest.raises(RuntimeError):
            start_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task(self):
        import apps.api.background_tasks as bt

        # Create a task that sleeps forever
        async def forever():
            await asyncio.sleep(1000)

        bt._cleanup_task = asyncio.create_task(forever())
        await stop_cleanup_task()
        assert bt._cleanup_task is None

    @pytest.mark.asyncio
    async def test_stop_cleanup_task_none(self):
        import apps.api.background_tasks as bt
        bt._cleanup_task = None
        await stop_cleanup_task()  # Should not raise
        assert bt._cleanup_task is None
