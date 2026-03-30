"""Supabase client singleton for the pipeline backend.

This module provides a cached Supabase client that connects using
the SERVICE_ROLE_KEY (bypasses Row Level Security). This is correct
for server-side Python code. The React frontend (Phase 5) will use
SUPABASE_ANON_KEY directly via @supabase/supabase-js.

Usage:
    from packages.core.supabase_client import get_supabase
    
    db = get_supabase()
    result = db.table("kanban_cards").select("*").execute()
    cards = result.data  # list of dicts

IMPORTANT:
    - Raises RuntimeError if SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set
    - The client is cached (singleton) — safe to call get_supabase() many times
    - All Supabase calls are synchronous HTTP requests under the hood
    - When calling from async code, the brief blocking is acceptable
      (same pattern as the SQLite calls being replaced)
"""

from functools import lru_cache

from supabase import create_client, Client

from packages.core.config import get_settings
from packages.core.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return a cached Supabase client singleton.

    Uses SERVICE_ROLE_KEY for full backend access (bypasses RLS).
    Raises RuntimeError if Supabase is not configured.
    """
    settings = get_settings()

    if not settings.SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is not set. Add it to your .env file. "
            "See supabase/README.md for setup instructions."
        )
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not set. Add it to your .env file. "
            "Get it from: Supabase Dashboard → Settings → API → service_role key. "
            "NEVER expose this key to the frontend."
        )

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    logger.info("supabase_client_initialized", url=settings.SUPABASE_URL)
    return client
