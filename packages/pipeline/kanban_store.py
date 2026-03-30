"""Kanban card persistence store.

Handles the lifecycle of individual Kanban cards (Option B).
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from packages.core.config import get_settings


class KanbanCard:
    """A single card on the Kanban board."""

    def __init__(
        self,
        card_id: str,
        title: str,
        stage: int,
        status: str = "idle",
        parent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        color: Optional[str] = None,
        error_message: str = "",
        meta: Optional[dict] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.card_id = card_id
        self.title = title
        self.stage = stage
        self.status = status
        self.parent_id = parent_id
        self.run_id = run_id
        self.color = color
        self.error_message = error_message
        self.meta = meta or {}
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "card_id": self.card_id,
            "title": self.title,
            "stage": self.stage,
            "status": self.status,
            "parent_id": self.parent_id,
            "run_id": self.run_id,
            "color": self.color,
            "error_message": self.error_message,
            "meta": self.meta,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "KanbanCard":
        return cls(
            card_id=row["card_id"],
            title=row["title"],
            stage=row["stage"],
            status=row["status"],
            parent_id=row["parent_id"],
            run_id=row["run_id"],
            color=row["color"],
            error_message=row["error_message"],
            meta=json.loads(row["meta_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class KanbanStore:
    """SQLite persistence for KanbanCard objects."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            settings = get_settings()
            db_path = str(Path(settings.DATA_DIR) / "kanban_cards.db")

        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kanban_cards (
                    card_id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    run_id TEXT,
                    title TEXT NOT NULL,
                    stage INTEGER NOT NULL,
                    status TEXT DEFAULT 'idle',
                    color TEXT,
                    error_message TEXT DEFAULT '',
                    meta_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def create(
        self,
        title: str,
        stage: int,
        parent_id: Optional[str] = None,
        color: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> KanbanCard:
        card = KanbanCard(
            card_id=str(uuid.uuid4()),
            title=title,
            stage=stage,
            parent_id=parent_id,
            color=color,
            meta=meta,
        )
        self.save(card)
        return card

    def save(self, card: KanbanCard):
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO kanban_cards
                (card_id, parent_id, run_id, title, stage, status, color, error_message, meta_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card.card_id,
                    card.parent_id,
                    card.run_id,
                    card.title,
                    card.stage,
                    card.status,
                    card.color,
                    card.error_message,
                    json.dumps(card.meta),
                    card.created_at.isoformat(),
                    now,
                ),
            )
            conn.commit()

    def get(self, card_id: str) -> Optional[KanbanCard]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM kanban_cards WHERE card_id = ?", (card_id,)
            )
            row = cursor.fetchone()
            return KanbanCard.from_row(row) if row else None

    def list(self, stage: Optional[int] = None, limit: int = 100) -> list[KanbanCard]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if stage is not None:
                cursor = conn.execute(
                    "SELECT * FROM kanban_cards WHERE stage = ? ORDER BY created_at DESC LIMIT ?",
                    (stage, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM kanban_cards ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            return [KanbanCard.from_row(row) for row in cursor.fetchall()]

    def update(self, card_id: str, **fields) -> Optional[KanbanCard]:
        card = self.get(card_id)
        if not card:
            return None

        for key, value in fields.items():
            if hasattr(card, key):
                setattr(card, key, value)

        self.save(card)
        return card

    def delete(self, card_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM kanban_cards WHERE card_id = ?", (card_id,))
            conn.commit()

    def get_children(self, parent_id: str) -> list[KanbanCard]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM kanban_cards WHERE parent_id = ? ORDER BY created_at DESC",
                (parent_id,),
            )
            return [KanbanCard.from_row(row) for row in cursor.fetchall()]

    def link_run(self, card_id: str, run_id: str) -> bool:
        card = self.get(card_id)
        if not card:
            return False
        card.run_id = run_id
        self.save(card)
        return True

    def get_by_run(self, run_id: str) -> Optional[KanbanCard]:
        """Find card linked to a pipeline run."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM kanban_cards WHERE run_id = ?", (run_id,)
            )
            row = cursor.fetchone()
            return KanbanCard.from_row(row) if row else None

    def is_paused(self, run_id: str) -> bool:
        """Check if a run is currently paused via its Kanban card."""
        card = self.get_by_run(run_id)
        return card.status == "paused" if card else False
