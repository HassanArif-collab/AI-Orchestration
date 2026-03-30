"""Supabase PostgreSQL Checkpointer for LangGraph.

This module provides the checkpointer that makes the pipeline crash-proof.
After every single node completes, LangGraph saves the entire state to Supabase.
If the server dies at iteration 14 of 20, restart picks up at iteration 14
with all previous work intact.

Uses:
- psycopg[binary] v3 for async PostgreSQL connections
- psycopg-pool for connection pooling
- LangGraph's AsyncPostgresSaver for checkpoint storage

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

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level pool — initialized once, reused across all graph invocations
_pool = None
_checkpointer = None


async def get_checkpointer():
    """
    Returns a singleton AsyncPostgresSaver backed by Supabase's PostgreSQL.
    
    Uses connection pooling so we don't open/close connections per request.
    The .setup() call creates LangGraph's internal tables 
    (checkpoints, checkpoint_writes, checkpoint_blobs) automatically.
    You do NOT need to create these tables manually in Supabase.
    
    Returns:
        AsyncPostgresSaver instance ready for use with LangGraph graphs
        
    Raises:
        RuntimeError: If SUPABASE_DB_URL is not configured
    """
    global _pool, _checkpointer
    
    if _checkpointer is not None:
        return _checkpointer
    
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError(
            "SUPABASE_DB_URL not set. "
            "Get it from: Supabase Dashboard → Settings → Database → Connection string (URI). "
            "Use Session mode (port 5432), NOT Transaction mode (port 6543)."
        )
    
    try:
        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        
        _pool = AsyncConnectionPool(
            db_url,
            min_size=2,      # Keep 2 connections warm
            max_size=10,     # Scale up under load
            open=False,      # Don't connect until first use
        )
        await _pool.open()
        
        _checkpointer = AsyncPostgresSaver(pool=_pool)
        await _checkpointer.setup()  # Creates checkpoint tables if they don't exist
        
        logger.info("langgraph_checkpointer_initialized: pool_size=2-10")
        return _checkpointer
        
    except ImportError as e:
        raise RuntimeError(
            f"Missing dependencies for LangGraph checkpointer: {e}. "
            "Install with: pip install langgraph psycopg[binary] psycopg-pool"
        ) from e
    except Exception as e:
        logger.error(f"checkpointer_init_failed: {e}")
        raise


async def close_checkpointer():
    """
    Call this on FastAPI shutdown to clean up connections.
    
    Safe to call multiple times - will only close if open.
    """
    global _pool, _checkpointer
    
    if _pool is not None:
        try:
            await _pool.close()
            logger.info("langgraph_checkpointer_closed")
        except Exception as e:
            logger.warning(f"checkpointer_close_error: {e}")
        finally:
            _pool = None
            _checkpointer = None


async def get_checkpointer_status() -> dict:
    """
    Get the current status of the checkpointer for health checks.
    
    Returns:
        Dict with status information
    """
    global _pool, _checkpointer
    
    if _checkpointer is None:
        return {
            "status": "not_initialized",
            "pool_open": False,
        }
    
    try:
        pool_open = _pool is not None and _pool._opened
        return {
            "status": "ready",
            "pool_open": pool_open,
            "pool_min_size": 2,
            "pool_max_size": 10,
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
