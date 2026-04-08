"""Supabase PostgreSQL Checkpointer for LangGraph.

This module provides the checkpointer that makes the pipeline crash-proof.
After every single node completes, LangGraph saves the entire state to Supabase.
If the server dies at iteration 14 of 20, restart picks up at iteration 14
with all previous work intact.

Uses:
- LangGraph's AsyncPostgresSaver.from_conn_string() for checkpoint storage
  (manages its own connection pool internally — no psycopg_pool needed)

Configuration:
- SUPABASE_DB_URL: Direct PostgreSQL connection string
  Find in: Supabase Dashboard → Settings → Database → Connection string (URI)
  Use Session mode (port 5432), NOT Transaction mode (port 6543)

Why session mode (5432)?
The LangGraph checkpointer uses PostgreSQL features that require persistent
session-level connections. Transaction-mode pooling (PgBouncer on 6543)
can break checkpoint writes.
"""

from __future__ import annotations

from typing import Optional

import logging

from packages.core.config import get_settings

logger = logging.getLogger(__name__)

# Module-level checkpointer — initialized once, reused across all graph invocations
_checkpointer = None
_checkpointer_cm = None  # Holds the async context manager reference


async def get_checkpointer():
    """
    Returns a singleton AsyncPostgresSaver backed by Supabase's PostgreSQL.

    Uses LangGraph's built-in connection pool management via from_conn_string().
    The .setup() call creates LangGraph's internal tables
    (checkpoints, checkpoint_writes, checkpoint_blobs) automatically.
    You do NOT need to create these tables manually in Supabase.

    Returns:
        AsyncPostgresSaver instance ready for use with LangGraph graphs

    Raises:
        RuntimeError: If SUPABASE_DB_URL is not configured
    """
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    db_url = get_settings().SUPABASE_DB_URL
    if not db_url:
        raise RuntimeError(
            "SUPABASE_DB_URL not set. "
            "Get it from: Supabase Dashboard → Settings → Database → Connection string (URI). "
            "Use Session mode (port 5432), NOT Transaction mode (port 6543)."
        )

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # from_conn_string manages its own connection pool internally
        cm = AsyncPostgresSaver.from_conn_string(db_url)
        _checkpointer = await cm.__aenter__()
        await _checkpointer.setup()  # Creates checkpoint tables if they don't exist

        # Store the context manager so we can close it on shutdown
        global _checkpointer_cm
        _checkpointer_cm = cm

        logger.info("langgraph_checkpointer_initialized: from_conn_string")
        return _checkpointer

    except ImportError as e:
        raise RuntimeError(
            f"Missing dependencies for LangGraph checkpointer: {e}. "
            "Install with: pip install langgraph-checkpoint-postgres"
        ) from e
    except Exception as e:
        logger.error(f"checkpointer_init_failed: {e}")
        raise


async def close_checkpointer():
    """
    Call this on FastAPI shutdown to clean up connections.

    Safe to call multiple times - will only close if open.
    """
    global _checkpointer, _checkpointer_cm

    if _checkpointer is not None and _checkpointer_cm is not None:
        try:
            await _checkpointer_cm.__aexit__(None, None, None)
            logger.info("langgraph_checkpointer_closed")
        except Exception as e:
            logger.warning(f"checkpointer_close_error: {e}")
        finally:
            _checkpointer = None
            _checkpointer_cm = None


async def get_checkpointer_status() -> dict:
    """
    Get the current status of the checkpointer for health checks.

    Returns:
        Dict with status information
    """
    global _checkpointer

    if _checkpointer is None:
        return {
            "status": "not_initialized",
        }

    try:
        return {
            "status": "ready",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


def get_memory_saver():
    """
    Get a MemorySaver for testing or development without Supabase.

    MemorySaver stores checkpoints in memory only - they are lost
    when the process restarts. Use only for local development or tests.

    Returns:
        MemorySaver instance
    """
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()
