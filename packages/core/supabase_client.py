"""Supabase client for the AI-Orchestration pipeline.

Provides a singleton Supabase client for database operations including
agent thoughts storage and research cache.

Usage:
    from packages.core.supabase_client import get_supabase

    supabase = get_supabase()
    result = supabase.table("agent_thoughts").select("*").execute()

Configuration:
    Requires SUPABASE_URL and SUPABASE_ANON_KEY in .env
    Get these from your Supabase project settings:
    https://app.supabase.com/project/_/settings/api

Tables Used:
    - agent_thoughts: Stores agent progress updates for Kanban drawer
    - research_cache: Permanent storage for research results
"""

from functools import lru_cache
from typing import Optional

from packages.core.config import get_settings
from packages.core.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_supabase():
    """Return a cached Supabase client singleton.

    Raises:
        RuntimeError: If Supabase is not configured (missing URL or key)

    Returns:
        Supabase client instance ready for database operations
    """
    settings = get_settings()

    if not settings.SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is not configured. Add it to your .env file. "
            "Get your project URL from https://app.supabase.com/project/_/settings/api"
        )

    if not settings.SUPABASE_ANON_KEY:
        raise RuntimeError(
            "SUPABASE_ANON_KEY is not configured. Add it to your .env file. "
            "Get your anon key from https://app.supabase.com/project/_/settings/api"
        )

    try:
        from supabase import create_client, Client

        client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY
        )

        logger.info("supabase_client_initialized")
        return client

    except ImportError:
        raise RuntimeError(
            "supabase-py package not installed. "
            "Add 'supabase' to your dependencies."
        )


def get_supabase_optional():
    """Return Supabase client or None if not configured.

    Use this in code that should work without Supabase.
    Returns None if SUPABASE_URL or SUPABASE_ANON_KEY is missing.

    Returns:
        Supabase client instance or None
    """
    settings = get_settings()

    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return None

    try:
        return get_supabase()
    except Exception as e:
        logger.warning(f"supabase_init_failed: {e}")
        return None


def is_supabase_configured() -> bool:
    """Check if Supabase is properly configured.

    Returns:
        True if both URL and key are set
    """
    settings = get_settings()
    return bool(settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY)
