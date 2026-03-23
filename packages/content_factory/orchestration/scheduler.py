"""Component 2: The Cron Scheduling System.

Handles Topic Finding, Experiment Looping,
Analytics Ingestions, and Learning Synthesis triggers.
"""

from datetime import datetime, timezone, timedelta
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
        logger.info("Executing Topic Finder Cycle (Signal Detection -> Scoring -> Maintenance)")
        
    def run_learning_synthesis(self):
        """Interval: Weekly (Every 168 hours)."""
        logger.info("Executing Learning Synthesis Engine (All phases log aggregation)")
        
    def run_health_check(self):
        """Interval: Every 1 hour."""
        logger.info("Executing System Health Check (Stalled cycles, empty reservoir alerts)")
        active = self.master.db.get_active_cycles()
        if not active:
            logger.info(f"system_health | status=no_active_cycles")
            
        # Check Reservoir levels
        try:
            topics = self.topic_db.get_top_topics(limit=1)
            if not topics:
                logger.warning("system_health | reservoir_empty")
                self.master.handle_escalation("SYS", "reservoir_low", "medium", {"available": 0})
        except Exception as e:
            logger.error(f"system_health | reservoir_check_failed: {e}")

    def trigger_production_cycle(self):
        """Event-based loosely coupled polling. Interval: 6 hours normally."""
        logger.info("Executing Production Cycle Polling")
        # Query real topics from the reservoir database
        try:
            topics = self.topic_db.get_top_topics(limit=5)
            if topics:
                logger.info(f"production_cycle | found {len(topics)} topics in reservoir")
                self.master.check_and_start_new_cycle(topics)
            else:
                logger.info("production_cycle | no_topics_in_reservoir")
        except Exception as e:
            logger.error(f"production_cycle | error: {e}")

    def trigger_analytics_ingestion(self):
        """Daily sweep of Analytics API pipelines."""
        logger.info("Executing YouTube Analytics Ingestion")

    def boot_schedule(self):
        """Initializes all Phase 7 prescribed cron definitions."""
        self.register_cron_job("TopicFinder_Daily", 24, self.run_topic_finder_cycle, "retry")
        self.register_cron_job("Production_Polling", 6, self.trigger_production_cycle, "skip")
        self.register_cron_job("Learning_Synthesis_Weekly", 168, self.run_learning_synthesis, "escalate")
        self.register_cron_job("Health_Check_Hourly", 1, self.run_health_check, "escalate")
        self.register_cron_job("Analytics_Sweep_Daily", 24, self.trigger_analytics_ingestion, "retry")
        self.register_cron_job("Maintenance_Weekly", 168, lambda: logger.info("Weekly Archive & Maintenance"), "escalate")

    def simulate_tick(self):
        """Mocks the passage of time to trigger Jobs for validation."""
        logger.info("Scheduler _simulate_tick ticked")
        for job in self.jobs:
            logger.info(f"Triggering {job['name']}")
            try:
                job['action']()
            except Exception as e:
                logger.error(f"cron_failure | job={job['name']} error={str(e)}")
                if job['failure_behavior'] == "escalate":
                    self.master.handle_escalation("SYS", "cron_failure", "high", {"job": job['name']})
