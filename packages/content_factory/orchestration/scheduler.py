"""Component 2: The Cron Scheduling System.

Handles Topic Finding, Experiment Looping,
Analytics Ingestions, and Learning Synthesis triggers.
"""

import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable
from packages.core.logger import get_logger
from packages.content_factory.orchestration.master import MasterOrchestrator
from packages.content_factory.topic_finder.db import TopicReservoirDB

logger = get_logger("CronScheduler")

class Scheduler:
    def __init__(self, master: MasterOrchestrator):
        self.master = master
        self.topic_db = TopicReservoirDB()
        self.jobs = []
        self._load_job_state()
        
    def _get_db_path(self) -> Path:
        """Return absolute path to pipeline.db."""
        return Path(__file__).resolve().parent.parent.parent.parent / "packages" / "data" / "pipeline.db"

    def _persist_job_state(self):
        """Save job execution timestamps to SQLite for crash recovery."""
        try:
            db_path = self._get_db_path()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scheduler_state (
                        job_name TEXT PRIMARY KEY,
                        last_run TEXT,
                        next_run TEXT,
                        is_enabled INTEGER DEFAULT 1
                    )
                """)
                conn.commit()
                for job in self.jobs:
                    last_run = job.get("last_run")
                    next_run = job.get("next_run")
                    conn.execute("""
                        INSERT OR REPLACE INTO scheduler_state (job_name, last_run, next_run, is_enabled)
                        VALUES (?, ?, ?, ?)
                    """, (job["name"],
                          last_run.isoformat() if last_run else None,
                          next_run.isoformat() if next_run else None,
                          1))
                conn.commit()
        except Exception as e:
            logger.warning(f"scheduler_persist_failed: {e}")

    def _load_job_state(self):
        """Load job execution timestamps from SQLite on startup."""
        try:
            db_path = self._get_db_path()
            if not db_path.exists():
                return
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT job_name, last_run, next_run FROM scheduler_state").fetchall()
                if not rows:
                    return
                loaded = {row["job_name"]: row for row in rows}
                logger.info(f"scheduler_loading_state | {len(loaded)} jobs found in DB")
        except Exception as e:
            logger.debug(f"scheduler_load_state_failed: {e}")
            loaded = {}
            return

        # Store loaded state to apply after boot_schedule registers the jobs
        self._loaded_state = loaded

    def _apply_loaded_state(self):
        """Apply previously loaded state to registered jobs. Call after boot_schedule()."""
        if not hasattr(self, '_loaded_state'):
            return
        for job in self.jobs:
            state = self._loaded_state.get(job["name"])
            if state:
                if state["last_run"]:
                    try:
                        job["last_run"] = datetime.fromisoformat(state["last_run"])
                    except (ValueError, TypeError):
                        pass
                if state["next_run"]:
                    try:
                        job["next_run"] = datetime.fromisoformat(state["next_run"])
                    except (ValueError, TypeError):
                        pass
                logger.info(f"scheduler_state_restored | job={job['name']} last_run={job.get('last_run')} next_run={job.get('next_run')}")
        # Clean up
        self._loaded_state = {}

    def register_cron_job(self, name: str, interval_hours: int, action: Callable, failure_behavior: str = "retry"):
        """Register a cron job with the scheduler."""
        self.jobs.append({
            "name": name,
            "interval_hours": interval_hours,
            "action": action,
            "failure_behavior": failure_behavior,
            "last_run": None,
            "next_run": datetime.now(timezone.utc) + timedelta(hours=interval_hours)
        })
        logger.info(f"cron_registered | job_name={name} interval={interval_hours}h")

    def run_topic_finder_cycle(self):
        """Interval: Every 24 hours. Scans signals, scores topics, saves to reservoir."""
        try:
            logger.info("topic_finder_cycle_starting")
            from packages.content_factory.topic_finder.finder import TopicFinderAgent
            # This is a sync stub — actual implementation needs async context
            # TODO: Move to async and call TopicFinderAgent.scan() with Exa search
            logger.info("topic_finder_cycle_completed: stub")
        except Exception as e:
            logger.error(f"topic_finder_cycle_failed: {e}")
        
    def run_learning_synthesis(self):
        """Interval: Weekly (Every 168 hours)."""
        try:
            logger.info("learning_synthesis_starting")
            from packages.content_factory.orchestration.synthesis import SynthesisEngine
            # TODO: Need async context for SynthesisEngine.execute_synthesis_cycle()
            # For now, log that synthesis is needed
            logger.info("learning_synthesis_cycle_completed: stub — async implementation pending")
        except Exception as e:
            logger.error(f"learning_synthesis_failed: {e}")
        
    async def run_health_check(self):
        """Now async."""
        logger.info("Executing System Health Check")
        active = self.master.db.get_active_cycles()
        if not active:
            logger.info("system_health | status=no_active_cycles")

        try:
            topics = self.topic_db.get_top_topics(limit=1)
            if not topics:
                logger.warning("system_health | reservoir_empty")
                await self.master.handle_escalation("SYS", "reservoir_low", "medium", {"available": 0})
        except Exception as e:
            logger.error(f"system_health | reservoir_check_failed: {e}")

    async def trigger_production_cycle(self):
        """Event-based polling. Now async."""
        logger.info("Executing Production Cycle Polling")
        try:
            topics = self.topic_db.get_top_topics(limit=5)
            if topics:
                logger.info(f"production_cycle | found {len(topics)} topics")
                await self.master.check_and_start_new_cycle(topics)
            else:
                logger.info("production_cycle | no_topics_in_reservoir")
        except Exception as e:
            logger.error(f"production_cycle | error: {e}")

    def trigger_analytics_ingestion(self):
        """Daily sweep of Analytics API pipelines."""
        try:
            logger.info("analytics_ingestion_starting")
            from packages.integrations.youtube.analytics import YouTubeAnalytics
            analytics = YouTubeAnalytics()
            # TODO: Call analytics.fetch_channel_stats() and save to video_performance table
            logger.info("analytics_ingestion_completed: stub — async implementation pending")
        except Exception as e:
            logger.error(f"analytics_ingestion_failed: {e}")

    def boot_schedule(self):
        """Initializes all Phase 7 prescribed cron definitions."""
        self.register_cron_job("TopicFinder_Daily", 24, self.run_topic_finder_cycle, "retry")
        self.register_cron_job("Production_Polling", 6, self.trigger_production_cycle, "skip")
        self.register_cron_job("Learning_Synthesis_Weekly", 168, self.run_learning_synthesis, "escalate")
        self.register_cron_job("Health_Check_Hourly", 1, self.run_health_check, "escalate")
        self.register_cron_job("Analytics_Sweep_Daily", 24, self.trigger_analytics_ingestion, "retry")
        self.register_cron_job("Maintenance_Weekly", 168, lambda: logger.info("Weekly Archive & Maintenance"), "escalate")
        # Restore persisted timing state from previous runs
        self._apply_loaded_state()

    async def simulate_tick(self):
        """Execute only jobs whose next_run has been reached.

        C8 FIX: Previously all jobs fired every tick regardless of interval.
        Now checks job['next_run'] against current time before executing.
        Updates last_run/next_run after each execution (success or failure).
        """
        now = datetime.now(timezone.utc)
        logger.info("scheduler_tick")
        
        for job in self.jobs:
            next_run = job.get("next_run")
            
            # Skip if not yet time to run
            if next_run and now < next_run:
                logger.debug(f"cron_skip | job={job['name']} next_run={next_run}")
                continue
            
            logger.info(f"cron_trigger | job={job['name']}")
            try:
                action = job['action']
                if asyncio.iscoroutinefunction(action):
                    await action()
                else:
                    action()
                
                # Update timing after successful execution
                job["last_run"] = now
                job["next_run"] = now + timedelta(hours=job.get("interval_hours", 24))
                self._persist_job_state()
                
            except Exception as e:
                logger.error(f"cron_failure | job={job['name']} error={str(e)}")
                # Still update timing to prevent retry storm
                job["last_run"] = now
                job["next_run"] = now + timedelta(hours=1)  # Retry after 1h on failure
                self._persist_job_state()
                
                if job['failure_behavior'] == "escalate":
                    await self.master.handle_escalation("SYS", "cron_failure", "high", {"job": job['name']})
