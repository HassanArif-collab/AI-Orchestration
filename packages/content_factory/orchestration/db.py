"""Phase 7: Orchestration Database Strategy.

Maintains the persistent Production Cycle Registry using SQLite.
Includes Optimistic Locking mechanism for State Synchronization.
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
    def __init__(self):
        self._init_db()
        
    def _init_db(self):
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
                    lock_expires_at TEXT
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

    def create_cycle(self, record: ProductionCycleRecord):
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
        """Optimistic locking. Returns True if lock acquired."""
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
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE production_registry 
                SET lock_expires_at = NULL
                WHERE cycle_id = ?
            ''', (cycle_id,))
            conn.commit()
            
    def get_active_cycles(self) -> list[ProductionCycleRecord]:
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
