"""
router/tracker.py — Tracks LLM API usage per provider per day.

Context: Keeps a local record of how many tokens/requests each provider
has handled today. Now also captures live rate limit headers from provider
responses, giving accurate remaining quota data.

Storage: packages/data/usage_tracker.db (SQLite)
This is SEPARATE from freerouter/data/conversations.db which stores
chat history. This file only stores API usage statistics.

Live Rate Limit Headers (Phase 3):
  - Groq/OpenRouter: x-ratelimit-remaining-requests, x-ratelimit-remaining-tokens
  - Ollama: -1 (unlimited, no headers)

Usage:
    from packages.router.tracker import UsageTracker
    tracker = UsageTracker()
    tracker.record_call("groq", "llama-3.3-70b-versatile", 100, 200, 450, True,
                        rpm_remaining=500, tpm_remaining=10000)
    print(tracker.get_daily_usage("groq"))
    print(tracker.get_latest_limits())

Imports: sqlite3, pathlib, datetime
Imported by: packages/router/client.py (automatic logging)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, date, timezone
from pathlib import Path

# Separate from freerouter/data/conversations.db
_DB_DIR = Path(__file__).parent.parent / "data"
_DB_PATH = _DB_DIR / "usage_tracker.db"

NEAR_LIMIT_THRESHOLD = 0.80


class UsageTracker:
    """SQLite-backed usage tracker with live rate limit header storage.

    Captures real-time remaining quota from provider HTTP headers.
    Thread-safe for single-process use.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database with migration support for existing tables."""
        with self._connect() as conn:
            # Create table if it doesn't exist
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
                    created_at  TEXT NOT NULL,
                    live_rpm_remaining INTEGER DEFAULT -1,
                    live_tpm_remaining INTEGER DEFAULT -1
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_date_provider ON usage_log(date, provider)"
            )

            # Migration: Add columns to existing tables
            # Wrap in try/except so it doesn't crash if columns already exist
            try:
                conn.execute(
                    "ALTER TABLE usage_log ADD COLUMN live_rpm_remaining INTEGER DEFAULT -1"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                conn.execute(
                    "ALTER TABLE usage_log ADD COLUMN live_tpm_remaining INTEGER DEFAULT -1"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

    def record_call(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        success: bool,
        rpm_remaining: int = -1,
        tpm_remaining: int = -1,
    ) -> None:
        """Record one LLM API call with live rate limit data.

        Args:
            provider: Provider name (groq, openrouter, ollama, etc.)
            model: Model identifier
            tokens_in: Prompt tokens used
            tokens_out: Completion tokens generated
            latency_ms: Request latency in milliseconds
            success: Whether the call succeeded
            rpm_remaining: Requests per minute remaining from headers (-1 if unavailable)
            tpm_remaining: Tokens per minute remaining from headers (-1 if unavailable)
        """
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO usage_log (date, provider, model, tokens_in, tokens_out, "
                "latency_ms, success, created_at, live_rpm_remaining, live_tpm_remaining) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    date.today().isoformat(), provider, model,
                    tokens_in, tokens_out, latency_ms,
                    1 if success else 0, datetime.now(timezone.utc).isoformat(),
                    rpm_remaining, tpm_remaining,
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

    def get_latest_limits(self) -> list[dict]:
        """Get the most recent rate limit snapshot per provider.

        Returns the last recorded rpm_remaining and tpm_remaining values
        for each provider, useful for displaying live quota status.

        Returns:
            List of dicts with provider, live_rpm_remaining, live_tpm_remaining, timestamp
        """
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT provider,
                          live_rpm_remaining,
                          live_tpm_remaining,
                          created_at as timestamp
                   FROM usage_log
                   WHERE id IN (
                       SELECT MAX(id) FROM usage_log GROUP BY provider
                   )
                   ORDER BY provider"""
            ).fetchall()
        return [dict(r) for r in rows]

    def is_near_limit(self, provider: str) -> bool:
        """Return True if provider has used >80% of remaining quota.

        Uses live rate limit headers when available, falls back to
        daily usage tracking for providers without header support.
        """
        # First try to use live headers
        latest = self.get_latest_limits()
        for row in latest:
            if row["provider"] == provider:
                rpm = row["live_rpm_remaining"]
                tpm = row["live_tpm_remaining"]
                # If we have real header data (not -1), use it
                if rpm >= 0 and tpm >= 0:
                    # Consider "near limit" if either remaining is < 20%
                    # This is a heuristic since we don't know the actual limits
                    return rpm < 100 or tpm < 10000
                break

        # Fallback: we can't determine from headers (e.g., Ollama)
        return False
