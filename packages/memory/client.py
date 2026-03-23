"""Zep memory client for AI Orchestration system.

This client provides a graceful degradation pattern - all methods return
empty/default values when Zep is unavailable, ensuring the pipeline never
crashes due to external service failures.
"""
import asyncio
import time
from functools import wraps

from packages.core.config import get_settings
from packages.core.logger import get_logger

logger = get_logger(__name__)


def with_retry(func):
    """Decorator to apply exponential backoff (1s, 3s, 9s)."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        delays = [1, 3, 9]
        for delay in delays:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"zep_api_retry: Error '{e}' in {func.__name__}. Retrying in {delay}s...")
                time.sleep(delay)
        # Last attempt
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"zep_api_exhausted: All retries failed for {func.__name__}. Error: {e}")
            return None
    return wrapper

def run_async(coro):
    """Safely run async coroutine from sync code."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        # Inside an existing loop, use a new thread or nested loop.
        import nest_asyncio
        nest_asyncio.apply()
    return loop.run_until_complete(coro)


class ZepMemoryClient:
    """Client for Zep memory operations with graceful degradation.

    Provides synchronous methods that wrap the underlying async Zep SDK.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or get_settings().ZEP_API_KEY
        self._client = None
        self._query_cache = {}

        if self._api_key:
            try:
                from zep_cloud import AsyncZep
                self._client = AsyncZep(api_key=self._api_key)
            except Exception as e:
                logger.warning(f"zep_init_failed: {e}")
                self._client = None
        else:
            logger.debug("Zep API key not configured, operating in degraded mode")

    @with_retry
    def create_user(self, user_id: str, metadata: dict | None = None) -> None:
        if not self._client:
            return
        run_async(self._client.user.add(user_id=user_id, metadata=metadata or {}))
        logger.debug(f"zep_user_created: {user_id}")

    @with_retry
    def create_session(self, session_id: str, user_id: str, metadata: dict | None = None) -> None:
        if not self._client:
            return
        # Threads are essentially sessions in zep-cloud
        run_async(self._client.thread.create(thread_id=session_id, user_id=user_id))
        logger.debug(f"zep_session_created: {session_id} for user {user_id}")

    @with_retry
    def add_message(self, session_id: str, role: str, content: str, metadata: dict | None = None) -> None:
        if not self._client:
            return
        from zep_cloud import Message
        message = Message(role=role, content=content, metadata=metadata)
        run_async(self._client.thread.add_messages(thread_id=session_id, messages=[message]))
        logger.debug(f"zep_message_added: {session_id} role={role}")

    @with_retry
    def add_facts(self, session_id: str, facts: list[dict]) -> None:
        """Adds a batch of facts as system messages to a session."""
        if not self._client or not facts:
            return
        from zep_cloud import Message
        messages = []
        for f in facts:
            content = f.pop("fact", "") or f.pop("content", "")
            if not content:
                continue
            messages.append(Message(role="system", content=content, metadata=f))
            
        chunk_size = 50
        for i in range(0, len(messages), chunk_size):
            chunk = messages[i:i+chunk_size]
            run_async(self._client.thread.add_messages(thread_id=session_id, messages=chunk))
        logger.debug(f"zep_facts_added_batch: {len(facts)} facts to {session_id}")

    def search_memory(self, session_id: str, query: str, limit: int = 5) -> list[dict]:
        """Search memory for relevant information with session caching."""
        if not self._client:
            return []

        cache_key = (session_id, query, limit)
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        try:
            # We search the graph associated with the thread_id
            results = run_async(self._client.graph.search(
                query=query,
                graph_id=session_id,
                limit=limit,
            ))
            
            output = []
            if results and hasattr(results, "edges") and results.edges:
                output = [
                    {
                        "fact": edge.fact if hasattr(edge, "fact") else str(edge),
                        "score": getattr(edge, "score", 1.0),
                    }
                    for edge in results.edges
                ]
            
            self._query_cache[cache_key] = output
            return output
        except Exception as e:
            logger.warning(f"zep_error in search_memory: {e}")
            return []

    def clear_cache(self):
        self._query_cache.clear()

