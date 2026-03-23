"""
storage.py — Persistent SQLite storage for conversations and messages.

Context: Replaces the in-memory dict in web/app.py with a real local database.
All chat history survives server restarts. Database lives at:
  freerouter/data/conversations.db   (auto-created on first run)

Schema:
  conversations  — id, title, created_at, updated_at, model, provider
  messages       — id, conversation_id, role, content, provider, model, timestamp

This module is intentionally simple — no ORM, just sqlite3 with helper functions.
Each function opens and closes its own connection (safe for single-process use).

Imports: nothing internal
Imported by: web/app.py
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Database lives in freerouter/data/ next to src/
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "conversations.db"


def _connect() -> sqlite3.Connection:
    """Open a connection with row_factory so rows act like dicts."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safe concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT 'New Chat',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                model       TEXT DEFAULT '',
                provider    TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                provider        TEXT DEFAULT '',
                model           TEXT DEFAULT '',
                timestamp       TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conversation_id, timestamp);
        """)


# ─── Conversations ────────────────────────────────────────────────────────────

def create_conversation(title: str = "New Chat", model: str = "") -> dict:
    cid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, model) VALUES (?,?,?,?,?)",
            (cid, title, now, now, model)
        )
    return {"id": cid, "title": title, "created_at": now, "updated_at": now,
            "model": model, "message_count": 0}


def list_conversations() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("""
            SELECT c.*, COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_conversation(cid: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (cid,)
        ).fetchone()
        if not row:
            return None
        conv = dict(row)
        msgs = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp",
            (cid,)
        ).fetchall()
        conv["messages"] = [dict(m) for m in msgs]
    return conv


def delete_conversation(cid: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
    return cur.rowcount > 0


def update_conversation_title(cid: str, title: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE conversations SET title=?, updated_at=? WHERE id=?",
            (title, datetime.now().isoformat(), cid)
        )


# ─── Messages ─────────────────────────────────────────────────────────────────

def add_message(
    cid: str,
    role: str,
    content: str,
    provider: str = "",
    model: str = "",
) -> Optional[dict]:
    """Add a message to a conversation. Returns None if conversation not found."""
    with _connect() as conn:
        # Check conversation exists
        exists = conn.execute(
            "SELECT id FROM conversations WHERE id=?", (cid,)
        ).fetchone()
        if not exists:
            return None

        mid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, provider, model, timestamp) "
            "VALUES (?,?,?,?,?,?,?)",
            (mid, cid, role, content, provider, model, now)
        )
        # Update conversation metadata
        conn.execute(
            "UPDATE conversations SET updated_at=?, provider=?, model=? WHERE id=?",
            (now, provider, model, cid)
        )
        # Auto-title from first user message
        msg_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id=?", (cid,)
        ).fetchone()[0]
        if msg_count == 1 and role == "user":
            title = content[:50] + ("..." if len(content) > 50 else "")
            conn.execute(
                "UPDATE conversations SET title=? WHERE id=?", (title, cid)
            )

    return {"id": mid, "conversation_id": cid, "role": role, "content": content,
            "provider": provider, "model": model, "timestamp": now}


def get_db_path() -> str:
    return str(_DB_PATH)


def get_db_stats() -> dict:
    """Return basic stats about the database."""
    with _connect() as conn:
        conv_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        size_bytes = _DB_PATH.stat().st_size if _DB_PATH.exists() else 0
    return {
        "conversations": conv_count,
        "messages": msg_count,
        "db_path": str(_DB_PATH),
        "size_kb": round(size_bytes / 1024, 1),
    }
