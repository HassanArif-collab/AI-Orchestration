"""Phase 7: Orchestration Database Strategy.

Maintains the persistent Production Cycle Registry using SQLite.
Includes Optimistic Locking mechanism for State Synchronization.

DATABASE TABLES:

  production_registry
    One row per production cycle. Tracks lifecycle from topic_selected
    through all production rounds to completed/failed.
    Key fields: cycle_id, topic_statement, genre, current_phase,
                current_baseline_score, experiment_iterations,
                pipeline_run_id (links to PipelineRunner run_id)
    Locking: lock_expires_at prevents concurrent phase advances.
             Locks expire after 30 seconds to prevent deadlocks.

  human_escalations
    Items requiring human decision before the system can proceed.
    Created by: MasterOrchestrator.handle_escalation()
    Read by: ReviewInterface.get_pending_escalations()
    Status flow: pending → approved/rejected/modified

  instruction_versions
    Audit trail of all agent instruction changes.
    Created by: UpdatePipeline._activate_version()
    Used by: rollback monitor when post-update scores drop

ALL DATA IN packages/data/pipeline.db — same file used by:
  - PipelineRunner (pipeline_runs table)
  - SourceVideoLibrary (source_videos table)
  - TopicReservoirDB (topic_reservoir, video_performance tables)
  - BaselineManager (baselines table)
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from packages.content_factory.orchestration.models import ProductionCycleRecord, EscalationItem

DB_PATH = Path("packages/data/pipeline.db")

class OrchestrationDB:
    """
    SQLite persistence layer for the orchestration system.
    
    Handles all database operations for production cycle state,
    human escalations, and instruction version tracking.
    
    THREAD SAFETY:
      SQLite handles concurrent reads. Writes use explicit transactions.
      For multi-process environments, the optimistic lock (lock_expires_at)
      prevents concurrent modifications to the same cycle.
    
    USAGE:
      db = OrchestrationDB()
      db.create_cycle(record)
      db.acquire_lock(cycle_id)  # before modifying
      # ... make changes ...
      db.release_lock(cycle_id)
    """
    def __init__(self):
        self._init_db()
        
    def _init_db(self):
        """Initialize all tables with proper schema.
        
        Safe to call multiple times — uses IF NOT EXISTS.
        Migration-safe: new columns can be added via ALTER TABLE
        in the calling code if needed.
        """
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 1. Production Cycle Registry
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS production_registry (
                    cycle_id TEXT PRIMARY KEY,
                    topic_statement TEXT,
                    genre TEXT,
                    source TEXT,
                    current_phase TEXT,
                    status TEXT,
                    current_baseline_score REAL,
                    experiment_iterations INTEGER,
                    music_architecture_id TEXT,
                    published_video_id TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    lock_expires_at TEXT,
                    pipeline_run_id TEXT
                )
            ''')
            
            # 2. Human Escalation Queue
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS human_escalations (
                    escalation_id TEXT PRIMARY KEY,
                    cycle_id TEXT,
                    type TEXT,
                    severity TEXT,
                    context_payload TEXT,
                    status TEXT,
                    created_at TEXT
                )
            ''')
            conn.commit()
        
        # Safe migration — add pipeline_run_id column if it doesn't exist
        with sqlite3.connect(DB_PATH) as conn:
            try:
                conn.execute(
                    "ALTER TABLE production_registry ADD COLUMN pipeline_run_id TEXT DEFAULT NULL"
                )
            except Exception:
                pass  # Column already exists
            conn.commit()

    def create_cycle(self, record: ProductionCycleRecord):
        """Insert a new production cycle record.
        
        Called by MasterOrchestrator.check_and_start_new_cycle()
        when a Tier 1 topic is selected for production.
        
        Args:
          record: ProductionCycleRecord with all required fields
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO production_registry (
                    cycle_id, topic_statement, genre, source, current_phase, status,
                    current_baseline_score, experiment_iterations, music_architecture_id,
                    published_video_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.cycle_id, record.topic_statement, record.genre, record.source,
                record.current_phase, record.status, record.current_baseline_score,
                record.experiment_iterations, record.music_architecture_id,
                record.published_video_id, record.created_at.isoformat(),
                record.updated_at.isoformat()
            ))
            conn.commit()

    def acquire_lock(self, cycle_id: str, timeout_seconds: int = 30) -> bool:
        """Optimistic locking for safe concurrent access.
        
        Attempts to acquire an exclusive lock on a cycle record.
        Returns True if the lock was acquired, False if already locked.
        
        Locks automatically expire after timeout_seconds to prevent
        deadlocks if a process crashes while holding a lock.
        
        Args:
          cycle_id: The cycle to lock
          timeout_seconds: Lock expiration time (default 30s)
        
        Returns:
          True if lock acquired, False if already locked by another process
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc)
            expires = (now + timedelta(seconds=timeout_seconds)).isoformat()
            
            # Only acquire if lock_expires_at is NULL or in the past
            cursor.execute('''
                UPDATE production_registry 
                SET lock_expires_at = ?
                WHERE cycle_id = ? AND (lock_expires_at IS NULL OR lock_expires_at < ?)
            ''', (expires, cycle_id, now.isoformat()))
            
            conn.commit()
            return cursor.rowcount > 0

    def release_lock(self, cycle_id: str):
        """Release a previously acquired lock.
        
        Always call this after completing a modification, even if
        the operation failed — prevents lock buildup.
        
        Args:
          cycle_id: The cycle to unlock
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE production_registry 
                SET lock_expires_at = NULL
                WHERE cycle_id = ?
            ''', (cycle_id,))
            conn.commit()
            
    def get_active_cycles(self) -> list[ProductionCycleRecord]:
        """Fetch all cycles currently in active production.
        
        Used by MasterOrchestrator to enforce the max 2 concurrent
        cycles limit.
        
        Returns:
          List of ProductionCycleRecord objects with status='active'
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM production_registry WHERE status = 'active'")
            rows = cursor.fetchall()
            
            results = []
            for r in rows:
                results.append(ProductionCycleRecord(
                    cycle_id=r['cycle_id'],
                    topic_statement=r['topic_statement'],
                    genre=r['genre'],
                    source=r['source'],
                    current_phase=r['current_phase'],
                    status=r['status'],
                    current_baseline_score=r['current_baseline_score'],
                    experiment_iterations=r['experiment_iterations'],
                    music_architecture_id=r['music_architecture_id'],
                    published_video_id=r['published_video_id'],
                    created_at=datetime.fromisoformat(r['created_at']),
                    updated_at=datetime.fromisoformat(r['updated_at'])
                ))
            return results

    def escalate(self, item: EscalationItem):
        """Create a human escalation record.
        
        Called by MasterOrchestrator.handle_escalation() when the system
        encounters a situation requiring human judgment.
        
        Args:
          item: EscalationItem with all required fields
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO human_escalations (
                    escalation_id, cycle_id, type, severity, context_payload, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.escalation_id, item.cycle_id, item.type, item.severity,
                json.dumps(item.context_payload), item.status, item.created_at.isoformat()
            ))
            conn.commit()

    def update_pipeline_run_id(self, cycle_id: str, pipeline_run_id: str) -> None:
        """Link a pipeline run to a production cycle."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE production_registry SET pipeline_run_id = ? WHERE cycle_id = ?",
                (pipeline_run_id, cycle_id)
            )
            conn.commit()
