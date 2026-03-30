"""Supabase client singleton for the AI Orchestration pipeline.

Provides a lazy-initialized Supabase client that all store modules
use to interact with the remote Postgres database.

Usage:
    from packages.core.supabase_client import get_supabase
    table = get_supabase().table("kanban_cards")
    result = table.select("*").execute()
"""

from __future__ import annotations

import os

_supabase_client = None


def get_supabase():
    """Return the singleton Supabase client, initializing on first call."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required. "
            "Set them in your .env file or environment."
        )

    _supabase_client = create_client(url, key)
    return _supabase_client
