"""
router/tracker.py — Tracks LLM API usage per provider per day.

Context: Keeps a local record of how many tokens/requests each provider
has handled today. Helps avoid hitting free tier limits by warning when
a provider is approaching 80% of its daily quota.

Storage: packages/data/usage_tracker.db (SQLite)
This is SEPARATE from freerouter/data/conversations.db which stores
chat history. This file only stores API usage statistics.

Known free tier daily limits (approximate):
  Groq:       14,400 requests / 500,000 tokens
  OpenRouter: ~200 requests (varies by model)
  Ollama:     unlimited (local)

Usage:
    from packages.router.tracker import UsageTracker
    tracker = UsageTracker()
    tracker.record_call("groq", "llama-3.3-70b-versatile", 100, 200, 450, True)
    print(tracker.get_daily_usage("groq"))
    print(tracker.is_near_limit("groq"))

Imports: sqlite3, pathlib, datetime
Imported by: packages/router/client.py (optional instrumentation)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, date, timezone
from pathlib import Path

# Separate from freerouter/data/conversations.db
_DB_DIR = Path(__file__).parent.parent / "data"
_DB_PATH = _DB_DIR / "usage_tracker.db"

# Known free tier daily limits
DAILY_LIMITS: dict[str, dict[str, int]] = {
    "groq":       {"requests": 14_400, "tokens": 500_000},
    "openrouter": {"requests": 200,    "tokens": 100_000},
    "together":   {"requests": 500,    "tokens": 200_000},
    "deepinfra":  {"requests": 500,    "tokens": 200_000},
    "ollama":     {"requests": 999_999, "tokens": 999_999_999},  # local, unlimited
}

NEAR_LIMIT_THRESHOLD = 0.80


class UsageTracker:
    """SQLite-backed usage tracker. Thread-safe for single-process use."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    date        TEXT NOT NULL,
                    provider    TEXT NOT NULL,
                    model       TEXT NOT NULL,
                    tokens_in   INTEGER DEFAULT 0,
                    tokens_out  INTEGER DEFAULT 0,
                    latency_ms  INTEGER DEFAULT 0,
                    success     INTEGER DEFAULT 1,
                    created_at  TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_date_provider ON usage_log(date, provider)"
            )

    def record_call(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        success: bool,
    ) -> None:
        """Record one LLM API call."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO usage_log (date, provider, model, tokens_in, tokens_out, "
                "latency_ms, success, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    date.today().isoformat(), provider, model,
                    tokens_in, tokens_out, latency_ms,
                    1 if success else 0, datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_daily_usage(self, provider: str) -> dict:
        """Return today's usage totals for a provider."""
        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as requests,
                          SUM(tokens_in + tokens_out) as total_tokens,
                          AVG(latency_ms) as avg_latency_ms
                   FROM usage_log
                   WHERE date=? AND provider=? AND success=1""",
                (today, provider),
            ).fetchone()
        return {
            "provider": provider,
            "date": today,
            "requests": row["requests"] or 0,
            "total_tokens": row["total_tokens"] or 0,
            "avg_latency_ms": round(row["avg_latency_ms"] or 0),
        }

    def get_all_usage_today(self) -> list[dict]:
        """Return today's usage for all providers."""
        today = date.today().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT provider,
                          COUNT(*) as requests,
                          SUM(tokens_in + tokens_out) as total_tokens
                   FROM usage_log
                   WHERE date=? AND success=1
                   GROUP BY provider""",
                (today,),
            ).fetchall()
        return [dict(r) for r in rows]

    def is_near_limit(self, provider: str) -> bool:
        """Return True if provider has used >80% of known daily free tier limits."""
        limits = DAILY_LIMITS.get(provider)
        if not limits:
            return False
        usage = self.get_daily_usage(provider)
        req_pct = usage["requests"] / limits["requests"]
        tok_pct = usage["total_tokens"] / limits["tokens"]
        return max(req_pct, tok_pct) >= NEAR_LIMIT_THRESHOLD
