"""Tests for orchestration/monitor.py — HealthMonitor (6-part dashboard aggregation)."""

import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

for mod_name in [
    "langgraph", "langgraph.graph", "langgraph.types",
    "langgraph.prebuilt", "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


def _make_master(active_cycles=None):
    """Create a mock MasterOrchestrator."""
    master = MagicMock()
    master.db = MagicMock()
    master.db.get_active_cycles.return_value = active_cycles or []
    return master


class TestGenerateDashboard:
    """Tests for generate_dashboard — assembles all 6 parts."""

    @patch("packages.content_factory.orchestration.monitor.get_supabase_optional", return_value=None)
    def test_returns_dashboard_model(self, mock_sb):
        """generate_dashboard should return a DashboardModel."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        with patch.object(HealthMonitor, "_get_pipeline_status", return_value=[]), \
             patch.object(HealthMonitor, "_get_reservoir_status", return_value={"total": 0}), \
             patch.object(HealthMonitor, "_get_quality_trends", return_value={}), \
             patch.object(HealthMonitor, "_get_learning_status", return_value={}), \
             patch.object(HealthMonitor, "_get_publish_performance", return_value=[]), \
             patch.object(HealthMonitor, "_get_sys_health", return_value={}):
            monitor = HealthMonitor(master)
            dashboard = monitor.generate_dashboard()

        assert dashboard.production_pipelines == []
        assert dashboard.reservoir_status == {"total": 0}
        assert dashboard.quality_trends == {}
        assert dashboard.learning_system == {}
        assert dashboard.published_performance == []
        assert dashboard.system_health == {}


class TestGetPipelineStatus:
    """Tests for _get_pipeline_status — active cycles with stall detection."""

    def test_returns_empty_list_when_no_active_cycles(self):
        """No active cycles → empty list."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        with patch("packages.content_factory.orchestration.monitor.get_supabase_optional", return_value=None):
            result = monitor._get_pipeline_status()
            assert result == []

    def test_detects_stalled_cycles(self):
        """Cycle with old updated_at should be marked stalled (>12h)."""
        cycle = MagicMock()
        cycle.cycle_id = "c1"
        cycle.topic_statement = "Test topic that is reasonably long"
        cycle.current_phase = "drafting"
        cycle.current_baseline_score = 75.0
        cycle.updated_at = datetime.now(timezone.utc) - timedelta(hours=24)

        master = _make_master(active_cycles=[cycle])
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        with patch("packages.content_factory.orchestration.monitor.get_supabase_optional", return_value=None):
            result = monitor._get_pipeline_status()
            assert len(result) == 1
            assert result[0]["stalled"] is True
            assert result[0]["cycle_id"] == "c1"

    def test_not_stalled_when_recent(self):
        """Cycle with recent updated_at should NOT be stalled."""
        cycle = MagicMock()
        cycle.cycle_id = "c1"
        cycle.topic_statement = "Test topic that is reasonably long"
        cycle.current_phase = "drafting"
        cycle.current_baseline_score = 75.0
        cycle.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)

        master = _make_master(active_cycles=[cycle])
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        with patch("packages.content_factory.orchestration.monitor.get_supabase_optional", return_value=None):
            result = monitor._get_pipeline_status()
            assert result[0]["stalled"] is False


class TestGetReservoirStatus:
    """Tests for _get_reservoir_status — topic reservoir counts."""

    def test_empty_reservoir_alerts_when_tier1_below_3(self):
        """When tier1 count < 3, alert_empty should be True."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {"viability_score_breakdown": {"q1": True}},  # score=1 < 12 → tier2
            {"viability_score_breakdown": {"q1": True}},  # tier2
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("packages.content_factory.orchestration.monitor.get_supabase_optional", return_value=mock_sb):
            result = monitor._get_reservoir_status()
            assert result["total"] == 2
            assert result["tier1"] == 0
            assert result["tier2"] == 2
            assert result["alert_empty"] is True

    def test_no_alert_when_tier1_above_3(self):
        """When tier1 count >= 3, alert_empty should be False."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        mock_sb = MagicMock()
        mock_result = MagicMock()
        # 3 items with 12+ true keys → tier1
        breakdown = {f"q{i}": True for i in range(15)}
        mock_result.data = [
            {"viability_score_breakdown": breakdown},
            {"viability_score_breakdown": breakdown},
            {"viability_score_breakdown": breakdown},
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("packages.content_factory.orchestration.monitor.get_supabase_optional", return_value=mock_sb):
            result = monitor._get_reservoir_status()
            assert result["tier1"] == 3
            assert result["alert_empty"] is False


class TestGetQualityTrends:
    """Tests for _get_quality_trends — SQLite query for genre trends."""

    def test_returns_empty_dict_on_error(self):
        """When SQLite query fails, return empty dict."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        # pipeline_db doesn't exist → SQLite connect will fail
        with patch("packages.content_factory.orchestration.monitor.sqlite3.connect", side_effect=Exception("no db")):
            result = monitor._get_quality_trends()
            assert result == {}

    def test_returns_empty_dict_when_no_rows(self):
        """When no rows, return empty dict."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        with patch("packages.content_factory.orchestration.monitor.sqlite3.connect", return_value=mock_conn):
            result = monitor._get_quality_trends()
            assert result == {}


class TestGetLearningStatus:
    """Tests for _get_learning_status — synthesis reports directory."""

    def test_returns_never_when_no_reports_dir(self):
        """When reports directory doesn't exist, return 'never'."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        with patch("packages.content_factory.orchestration.monitor.Path") as mock_path_cls:
            mock_project_root = MagicMock()
            mock_reports_dir = MagicMock()
            mock_reports_dir.exists.return_value = False
            mock_project_root.__truediv__ = MagicMock(return_value=mock_reports_dir)
            mock_path_cls.return_value = mock_project_root
            # Patch the module-level _PROJECT_ROOT
            with patch("packages.content_factory.orchestration.monitor._PROJECT_ROOT", mock_project_root):
                result = monitor._get_learning_status()
                assert result["last_synthesis_run"] == "never"
                assert result["pending_insights"] == 0


class TestGetPublishPerformance:
    """Tests for _get_publish_performance — SQLite query for video data."""

    def test_returns_empty_list_on_error(self):
        """When SQLite fails, return empty list."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        with patch("packages.content_factory.orchestration.monitor.sqlite3.connect", side_effect=Exception("no db")):
            result = monitor._get_publish_performance()
            assert result == []


class TestGetSysHealth:
    """Tests for _get_sys_health — cron status, error count, storage."""

    def test_returns_not_configured_when_no_cron_jobs(self):
        """When scheduler has no jobs, cron_status should be 'not_configured'."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        with patch("packages.content_factory.orchestration.monitor.get_supabase_optional", return_value=None), \
             patch("shutil.disk_usage", side_effect=Exception("no disk")):
            with patch("packages.content_factory.orchestration.scheduler.Scheduler") as mock_sched_cls:
                mock_sched = MagicMock()
                mock_sched.jobs = []
                mock_sched_cls.return_value = mock_sched
                result = monitor._get_sys_health()
                assert result["cron_status"] == "not_configured"

    def test_returns_healthy_when_cron_jobs_exist(self):
        """When scheduler has jobs, cron_status should be 'healthy'."""
        master = _make_master()
        from packages.content_factory.orchestration.monitor import HealthMonitor

        monitor = HealthMonitor(master)
        with patch("packages.content_factory.orchestration.monitor.get_supabase_optional", return_value=None), \
             patch("shutil.disk_usage") as mock_du:
            mock_usage = MagicMock()
            mock_usage.used = 1024 * 1024 * 500  # 500MB
            mock_du.return_value = mock_usage
            with patch("packages.content_factory.orchestration.scheduler.Scheduler") as mock_sched_cls:
                mock_sched = MagicMock()
                mock_sched.jobs = [{"name": "job1"}]
                mock_sched_cls.return_value = mock_sched
                result = monitor._get_sys_health()
                assert result["cron_status"] == "healthy"
                assert result["cron_jobs"] == 1
                assert "storage_gb" in result
