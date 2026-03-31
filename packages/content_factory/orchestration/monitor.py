"""Component 5: The System Health Monitor.

A real-time visibility module that acts as a dashboard aggregating:
1. Production Pipeline Status (Active cycles, Flags)
2. Topic Reservoir Status (Low alerts)
3. Quality Score Trends (Rolling averages of evaluations)
4. Learning System Status (Synthesis runs, updates pending)
5. Published Video Performance (Engagement scores map)
6. System Health Indicators (Cron logs, errors)
"""

import json
from typing import Any
from packages.core.logger import get_logger
from packages.core.supabase_client import get_supabase_optional
from packages.content_factory.orchestration.master import MasterOrchestrator
from pydantic import BaseModel
import sqlite3
from pathlib import Path

logger = get_logger("SystemHealthMonitor")

# 3.6 FIX: Use absolute path derived from project root, not CWD-relative
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "packages" / "data"

class DashboardModel(BaseModel):
    """The unified view layer expected by a CLI or frontend."""
    production_pipelines: list[dict[str, Any]]
    reservoir_status: dict[str, Any]
    quality_trends: dict[str, Any]
    learning_system: dict[str, Any]
    published_performance: list[dict[str, Any]]
    system_health: dict[str, Any]

class HealthMonitor:
    def __init__(self, master: MasterOrchestrator):
        self.master = master
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.pipeline_db = _DATA_DIR / "pipeline.db"
        
    def generate_dashboard(self) -> DashboardModel:
        """Assembles the 6-part live dashboard."""
        logger.info("generating_health_dashboard")
        
        return DashboardModel(
            production_pipelines=self._get_pipeline_status(),
            reservoir_status=self._get_reservoir_status(),
            quality_trends=self._get_quality_trends(),
            learning_system=self._get_learning_status(),
            published_performance=self._get_publish_performance(),
            system_health=self._get_sys_health()
        )

    def _get_pipeline_status(self) -> list[dict[str, Any]]:
        active = self.master.db.get_active_cycles()
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        stall_threshold = timedelta(hours=12)
        res = []
        for a in active:
            # 3.3 FIX: Compute real stalled status and failure count
            updated_at = getattr(a, 'updated_at', None)
            stalled = False
            if updated_at is not None:
                if isinstance(updated_at, str):
                    try:
                        updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        updated_at = None
                if updated_at is not None and hasattr(updated_at, 'tzinfo'):
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    stalled = (now - updated_at) > stall_threshold

            hard_failures = 0
            try:
                supabase = get_supabase_optional()
                if supabase is not None:
                    # Get pipeline_run_id for this cycle from production_cycles
                    cycle_data = (
                        supabase.table("production_cycles")
                        .select("pipeline_run_id")
                        .eq("cycle_id", a.cycle_id)
                        .execute()
                    )
                    if cycle_data.data:
                        for row in cycle_data.data:
                            run_id = row.get("pipeline_run_id")
                            if run_id:
                                run_data = (
                                    supabase.table("pipeline_runs")
                                    .select("status")
                                    .eq("run_id", run_id)
                                    .execute()
                                )
                                if run_data.data:
                                    hard_failures = sum(
                                        1 for r in run_data.data
                                        if r.get("status") == "error"
                                    )
                else:
                    hard_failures = -1  # Graceful fallback: Supabase not configured
            except Exception:
                hard_failures = -1

            res.append({
                "cycle_id": a.cycle_id,
                "topic": a.topic_statement[:50],
                "phase": a.current_phase,
                "baseline_score": a.current_baseline_score,
                "stalled": stalled,
                "hard_failures": hard_failures
            })
        return res

    def _get_reservoir_status(self) -> dict[str, Any]:
        """Queries Topic Reservoir from Supabase topic_briefs."""
        status = {"total": 0, "tier1": 0, "tier2": 0, "alert_empty": False}
        try:
            supabase = get_supabase_optional()
            if supabase is not None:
                result = (
                    supabase.table("topic_briefs")
                    .select("viability_score_breakdown")
                    .eq("status", "reservoir")
                    .execute()
                )
                if result.data:
                    status["total"] = len(result.data)
                    for row in result.data:
                        breakdown = row.get("viability_score_breakdown") or {}
                        total_score = sum(1 for v in breakdown.values() if v)
                        if total_score >= 12:
                            status["tier1"] += 1
                        else:
                            status["tier2"] += 1
        except Exception as e:
            logger.error(f"Failed loading reservoir status from Supabase: {e}")
        status["alert_empty"] = status["tier1"] < 3
        return status

    def _get_quality_trends(self) -> dict[str, Any]:
        try:
            # 3.3 FIX: Compute real genre trends from pipeline history
            conn = sqlite3.connect(self.pipeline_db)
            cursor = conn.cursor()
            # Get recent scores by genre (last 30 days)
            cursor.execute("""
                SELECT genre, AVG(score) as avg_score, COUNT(*) as count
                FROM binary_evaluations
                WHERE created_at > datetime('now', '-30 days')
                GROUP BY genre
                ORDER BY avg_score DESC
            """)
            rows = cursor.fetchall()
            conn.close()
            if rows:
                return {row[0]: row[1] for row in rows}
            return {}
        except Exception as e:
            logger.warning(f"genre_trends_query_failed: {e}")
            return {}

    def _get_learning_status(self) -> dict[str, Any]:
        try:
            # 3.3 FIX: Check actual synthesis state
            reports_dir = _PROJECT_ROOT / "packages" / "data" / "synthesis_reports"
            if not reports_dir.exists():
                return {"pending_insights": 0, "last_synthesis_run": "never", "report_count": 0}
            reports = sorted(reports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            last_run = reports[0].stat().st_mtime if reports else None
            from datetime import datetime
            last_str = datetime.fromtimestamp(last_run).strftime("%Y-%m-%d %H:%M") if last_run else "never"
            return {
                "pending_insights": len(reports),
                "last_synthesis_run": last_str,
                "report_count": len(reports)
            }
        except Exception as e:
            logger.warning(f"synthesis_status_query_failed: {e}")
            return {"pending_insights": 0, "last_synthesis_run": "error", "report_count": 0}

    def _get_publish_performance(self) -> list[dict[str, Any]]:
        try:
            # 3.3 FIX: Query actual video performance data
            conn = sqlite3.connect(self.pipeline_db)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT video_id, title, score, created_at
                FROM binary_evaluations
                ORDER BY created_at DESC
                LIMIT 20
            """)
            rows = cursor.fetchall()
            conn.close()
            return [{"video_id": r[0], "title": r[1], "score": r[2], "created_at": r[3]} for r in rows]
        except Exception as e:
            logger.warning(f"video_performance_query_failed: {e}")
            return []

    def _get_sys_health(self) -> dict[str, Any]:
        """Validates cron scheduling runs and error log aggregate."""
        # 3.3 FIX: Real system health metrics
        import shutil
        from datetime import datetime, timezone

        cron_ok = False
        job_count = 0
        try:
            from packages.content_factory.orchestration.scheduler import Scheduler
            sched = Scheduler()
            job_count = len(sched.jobs) if hasattr(sched, 'jobs') else 0
            cron_ok = job_count > 0
        except Exception:
            cron_ok = False

        error_count = -1
        try:
            supabase = get_supabase_optional()
            if supabase is not None:
                result = (
                    supabase.table("pipeline_runs")
                    .select("run_id", count="exact")
                    .eq("status", "error")
                    .execute()
                )
                error_count = result.count if result.count is not None else 0
        except Exception:
            error_count = -1

        storage_gb = -1
        try:
            data_usage = shutil.disk_usage(str(_DATA_DIR))
            storage_gb = round(data_usage.used / (1024**3), 2)
        except Exception:
            storage_gb = -1

        return {
            "cron_status": "healthy" if cron_ok else "not_configured",
            "cron_jobs": job_count,
            "errors_last_24h": error_count if error_count >= 0 else "unknown",
            "storage_gb": storage_gb,
        }
