"""
Zep memory client for AI Orchestration system.

This client provides a graceful degradation pattern - all methods return
empty/default values when Zep is unavailable, ensuring the pipeline never
crashes due to external service failures.

Zep Cloud is a long-term memory service for AI agents. It stores facts,
conversation messages, and supports semantic search — letting agents
"remember" what worked in past production cycles.

TWO ZEP USERS IN THIS SYSTEM:
  ZEP_AUDIENCE_USER_ID (default: "audience_model_v1")
    Session: "{user_id}_session"
    Stores: Pakistani audience intelligence facts
            (genre engagement, topic resonance, attention patterns)
    Written by: FeedbackLoop.ingest_analytics()
    Read by:    TopicFinderAgent.generate_candidate() via ZepAudienceModelStore

  ZEP_LEARNING_USER_ID (default: "learning_synthesis_v1")
    Session: "{user_id}_session"
    Stores: Experiment loop results, mutation outcomes, synthesis findings
    Written by: ZepAudienceModelStore.write_experiment_result()
    Read by:    SynthesisEngine._detect_patterns_semantic()

SESSION NAMING CONVENTION (never deviate from these):
  Audience session:  f"{settings.ZEP_AUDIENCE_USER_ID}_session"
  Learning session:  f"{settings.ZEP_LEARNING_USER_ID}_session"

GRACEFUL DEGRADATION:
  All methods return None/empty when:
    - ZEP_API_KEY is not set (operating in degraded mode)
    - zep-cloud package is not installed
    - Network call fails (after 3 retries with 1s/3s/9s backoff)
  The pipeline NEVER crashes due to Zep unavailability.

SETUP (one-time, run when ZEP_API_KEY is first configured):
  python packages/memory/init_zep.py
  This creates the two Zep users and migrates any existing
  audience_model.json and learning_log.jsonl data.

KEY METHODS:
  add_facts(session_id, facts)  — write structured learning data
  search_memory(session_id, query, limit)  — semantic search over facts
  create_user(user_id, metadata)  — one-time user setup
  create_session(session_id, user_id)  — one-time session setup
"""
import asyncio
import time
from functools import wraps

from packages.core.config import get_settings
from packages.core.logger import get_logger

logger = get_logger(__name__)


def with_retry(func):
    """Decorator to apply exponential backoff (1s, 3s, 9s).
    
    Wraps any Zep API call with automatic retry logic. The delays
    follow an exponential pattern: 1s → 3s → 9s.
    
    After all retries exhausted, logs a warning and returns None.
    The calling code must handle None gracefully.
    """
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
    """Safely run async coroutine from sync code.

    Zep Cloud SDK is async-first, but much of the pipeline is sync.
    This helper bridges the gap by running coroutines in a controlled
    event loop context.

    P2-03: Fixed resource leak by properly closing event loops in all paths.

    Uses nest_asyncio to allow nested loop execution when already
    inside an async context.
    """
    loop = None
    created_loop = False

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an existing loop, use a new thread or nested loop.
            import nest_asyncio
            nest_asyncio.apply()
    except RuntimeError:
        # No event loop exists, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        created_loop = True

    try:
        return loop.run_until_complete(coro)
    finally:
        # P2-03: Clean up resources properly
        # Only close loops we created ourselves to avoid breaking existing async contexts
        if created_loop and loop is not None:
            try:
                # Run any pending tasks before closing
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception as e:
                logger.debug(f"run_async_cleanup_warning: {e}")
            finally:
                try:
                    loop.close()
                except Exception as e:
                    logger.debug(f"run_async_close_warning: {e}")


class ZepMemoryClient:
    """
    Zep Cloud memory client with graceful degradation.

    Zep Cloud is a long-term memory service for AI agents. It stores facts,
    conversation messages, and supports semantic search — letting agents
    "remember" what worked in past production cycles.

    TWO ZEP USERS IN THIS SYSTEM:
      ZEP_AUDIENCE_USER_ID (default: "audience_model_v1")
        Session: "{user_id}_session"
        Stores: Pakistani audience intelligence facts
                (genre engagement, topic resonance, attention patterns)
        Written by: FeedbackLoop.ingest_analytics()
        Read by:    TopicFinderAgent.generate_candidate() via ZepAudienceModelStore

      ZEP_LEARNING_USER_ID (default: "learning_synthesis_v1")
        Session: "{user_id}_session"
        Stores: Experiment loop results, mutation outcomes, synthesis findings
        Written by: ZepAudienceModelStore.write_experiment_result()
        Read by:    SynthesisEngine._detect_patterns_semantic()

    SESSION NAMING CONVENTION (never deviate from these):
      Audience session:  f"{settings.ZEP_AUDIENCE_USER_ID}_session"
      Learning session:  f"{settings.ZEP_LEARNING_USER_ID}_session"

    GRACEFUL DEGRADATION:
      All methods return None/empty when:
        - ZEP_API_KEY is not set (operating in degraded mode)
        - zep-cloud package is not installed
        - Network call fails (after 3 retries with 1s/3s/9s backoff)
      The pipeline NEVER crashes due to Zep unavailability.

    SETUP (one-time, run when ZEP_API_KEY is first configured):
      python packages/memory/init_zep.py
      This creates the two Zep users and migrates any existing
      audience_model.json and learning_log.jsonl data.

    KEY METHODS:
      add_facts(session_id, facts)  — write structured learning data
      search_memory(session_id, query, limit)  — semantic search over facts
      create_user(user_id, metadata)  — one-time user setup
      create_session(session_id, user_id)  — one-time session setup
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
        """Create a Zep user for organizing sessions.
        
        Called once during init_zep.py setup. Each user represents
        a logical grouping of related sessions (audience, learning).
        
        Args:
          user_id: Unique identifier for the user
          metadata: Optional metadata dict (purpose, description, etc.)
        """
        if not self._client:
            return
        run_async(self._client.user.add(user_id=user_id, metadata=metadata or {}))
        logger.debug(f"zep_user_created: {user_id}")

    @with_retry
    def create_session(self, session_id: str, user_id: str, metadata: dict | None = None) -> None:
        """Create a Zep session (called 'thread' in zep-cloud).
        
        Sessions contain the actual memory data. Each session is owned
        by a user and can be searched semantically.
        
        Args:
          session_id: Unique session identifier
          user_id: Owner user ID
          metadata: Optional session metadata
        """
        if not self._client:
            return
        # Threads are essentially sessions in zep-cloud
        run_async(self._client.thread.create(thread_id=session_id, user_id=user_id))
        logger.debug(f"zep_session_created: {session_id} for user {user_id}")

    @with_retry
    def add_message(self, session_id: str, role: str, content: str, metadata: dict | None = None) -> None:
        """Add a single message to a session.
        
        Messages are the basic unit of Zep memory. They support
        semantic search and can be retrieved contextually.
        
        Args:
          session_id: Target session
          role: Message role (user, assistant, system)
          content: Message content
          metadata: Optional metadata
        """
        if not self._client:
            return
        from zep_cloud import Message
        message = Message(role=role, content=content, metadata=metadata)
        run_async(self._client.thread.add_messages(thread_id=session_id, messages=[message]))
        logger.debug(f"zep_message_added: {session_id} role={role}")

    @with_retry
    def add_facts(self, session_id: str, facts: list[dict]) -> None:
        """Adds a batch of facts as system messages to a session.
        
        Facts are structured pieces of information that Zep indexes
        for semantic retrieval. Use this for bulk ingestion of
        audience intelligence or learning log entries.
        
        Args:
          session_id: Target session
          facts: List of dicts, each with 'fact' key and optional metadata
        """
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
        """Search memory for relevant information with session caching.
        
        Performs semantic search over the session's memory graph.
        Results are cached per (session_id, query, limit) tuple to
        minimize redundant API calls.
        
        Args:
          session_id: Session to search
          query: Natural language search query
          limit: Maximum results to return
          
        Returns:
          List of dicts with 'fact' and 'score' keys, or empty list on error
        """
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
        """Clear the query result cache.
        
        Call this after ingesting new facts to ensure fresh search results.
        """
        self._query_cache.clear()


# ─── P2-07: Async-Native ZepMemoryClient ─────────────────────────────────────────

def with_retry_async(func):
    """Async decorator to apply exponential backoff (1s, 3s, 9s).

    P2-07: Async version of with_retry for the async-native client.
    Wraps any Zep API call with automatic retry logic. The delays
    follow an exponential pattern: 1s → 3s → 9s.

    After all retries exhausted, logs a warning and returns None.
    The calling code must handle None gracefully.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        delays = [1, 3, 9]
        for delay in delays:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"zep_api_retry_async: Error '{e}' in {func.__name__}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
        # Last attempt
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"zep_api_exhausted_async: All retries failed for {func.__name__}. Error: {e}")
            return None
    return wrapper


class AsyncZepMemoryClient:
    """
    Async-native Zep Cloud memory client with graceful degradation.

    P2-07: This is the async-native version of ZepMemoryClient.
    Use this when calling from async code to avoid the overhead
    and complexity of run_async() bridging.

    Prefer this class over ZepMemoryClient when:
      - You are already in an async context
      - You want to use async/await natively
      - You want to avoid event loop bridging issues

    Example:
        async with AsyncZepMemoryClient() as client:
            results = await client.search_memory("session_id", "query")

    All methods return None/empty when Zep is unavailable, ensuring
    the pipeline never crashes due to external service failures.
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

    async def __aenter__(self) -> "AsyncZepMemoryClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        self.clear_cache()

    @with_retry_async
    async def create_user(self, user_id: str, metadata: dict | None = None) -> None:
        """Create a Zep user for organizing sessions (async).

        Args:
            user_id: Unique identifier for the user
            metadata: Optional metadata dict (purpose, description, etc.)
        """
        if not self._client:
            return
        await self._client.user.add(user_id=user_id, metadata=metadata or {})
        logger.debug(f"zep_user_created: {user_id}")

    @with_retry_async
    async def create_session(self, session_id: str, user_id: str, metadata: dict | None = None) -> None:
        """Create a Zep session/thread (async).

        Args:
            session_id: Unique session identifier
            user_id: Owner user ID
            metadata: Optional session metadata
        """
        if not self._client:
            return
        await self._client.thread.create(thread_id=session_id, user_id=user_id)
        logger.debug(f"zep_session_created: {session_id} for user {user_id}")

    @with_retry_async
    async def add_message(self, session_id: str, role: str, content: str, metadata: dict | None = None) -> None:
        """Add a single message to a session (async).

        Args:
            session_id: Target session
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
        """
        if not self._client:
            return
        from zep_cloud import Message
        message = Message(role=role, content=content, metadata=metadata)
        await self._client.thread.add_messages(thread_id=session_id, messages=[message])
        logger.debug(f"zep_message_added: {session_id} role={role}")

    @with_retry_async
    async def add_facts(self, session_id: str, facts: list[dict]) -> None:
        """Adds a batch of facts as system messages to a session (async).

        Args:
            session_id: Target session
            facts: List of dicts, each with 'fact' key and optional metadata
        """
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
            await self._client.thread.add_messages(thread_id=session_id, messages=chunk)
        logger.debug(f"zep_facts_added_batch: {len(facts)} facts to {session_id}")

    async def search_memory(self, session_id: str, query: str, limit: int = 5) -> list[dict]:
        """Search memory for relevant information (async).

        Args:
            session_id: Session to search
            query: Natural language search query
            limit: Maximum results to return

        Returns:
            List of dicts with 'fact' and 'score' keys, or empty list on error
        """
        if not self._client:
            return []

        cache_key = (session_id, query, limit)
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        try:
            results = await self._client.graph.search(
                query=query,
                graph_id=session_id,
                limit=limit,
            )

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
            logger.warning(f"zep_error in search_memory_async: {e}")
            return []

    def clear_cache(self):
        """Clear the query result cache."""
        self._query_cache.clear()


def get_async_zep_client(api_key: str | None = None) -> AsyncZepMemoryClient:
    """Factory function to get an async Zep memory client.

    P2-07: Convenience function for creating async-native clients.

    Args:
        api_key: Optional API key (defaults to settings.ZEP_API_KEY)

    Returns:
        AsyncZepMemoryClient instance
    """
    return AsyncZepMemoryClient(api_key=api_key)
