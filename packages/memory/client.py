"""
Zep memory client for AI Orchestration system.

This client provides a graceful degradation pattern - all methods return
OperationResult[T] when Zep is unavailable, ensuring the pipeline never
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
  All methods return OperationResult with failure context when:
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
from functools import wraps

from packages.core.config import get_settings
from packages.core.logger import get_logger
from packages.core.operation_result import OperationResult, ErrorSeverity
from packages.core.dead_letter import queue_for_retry

logger = get_logger(__name__)


class ZepRetryExhaustedError(Exception):
    """Raised when all Zep API retries are exhausted."""
    pass


def with_retry_async(func):
    """Async decorator to apply exponential backoff (1s, 3s, 9s).

    Wraps any Zep API call with automatic retry logic. The delays
    follow an exponential pattern: 1s → 3s → 9s.

    After all retries exhausted, raises ZepRetryExhaustedError so the
    calling method can catch it and wrap in an OperationResult.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        delays = [1, 3, 9]
        last_error = None
        for delay in delays:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"zep_api_retry_async: Error '{e}' in {func.__name__}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
        # Last attempt
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            logger.warning(f"zep_api_exhausted_async: All retries failed for {func.__name__}. Error: {e}")
            raise ZepRetryExhaustedError(f"All retries exhausted for {func.__name__}: {e}") from e
    return wrapper


class AsyncZepMemoryClient:
    """
    Async-native Zep Cloud memory client with graceful degradation.

    Use this when calling from async code to avoid the overhead
    and complexity of run_async() bridging.

    Example:
        async with AsyncZepMemoryClient() as client:
            result = await client.search_memory("session_id", "query")
            if result.success:
                facts = result.data

    All methods return OperationResult[T] when Zep is unavailable, ensuring
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
            logger.warning("Zep API key not configured, operating in degraded mode")

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
            # Copy to avoid modifying original
            fact_copy = dict(f)
            content = fact_copy.pop("fact", "") or fact_copy.pop("content", "")
            if not content:
                continue
            messages.append(Message(role="system", content=content, metadata=fact_copy))

        chunk_size = 50
        for i in range(0, len(messages), chunk_size):
            chunk = messages[i:i+chunk_size]
            await self._client.thread.add_messages(thread_id=session_id, messages=chunk)
        logger.debug(f"zep_facts_added_batch: {len(facts)} facts to {session_id}")

    async def search_memory(self, session_id: str, query: str, limit: int = 5) -> OperationResult[list[dict]]:
        """Search memory for relevant information (async).

        Args:
            session_id: Session to search
            query: Natural language search query
            limit: Maximum results to return

        Returns:
            OperationResult[list[dict]] — success contains list of dicts
            with 'fact' and 'score' keys, fail on error.
        """
        if not self._client:
            return OperationResult.fail(
                message="Zep API key not configured. Memory search is unavailable.",
                code="ZEP_UNAVAILABLE",
                severity=ErrorSeverity.WARNING,
                user_message="Memory service is not configured. Topic discovery will use fallback mode.",
            )

        cache_key = (session_id, query, limit)
        if cache_key in self._query_cache:
            return OperationResult.ok(self._query_cache[cache_key])

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
            return OperationResult.ok(output, message=f"Found {len(output)} memory results.")
        except ZepRetryExhaustedError as e:
            logger.error(f"zep_search_failed_all_retries: session={session_id} query={query[:50]} error={e}")
            queue_for_retry(
                operation="zep_search_failed",
                payload={
                    "session_id": session_id,
                    "query": query,
                    "limit": limit,
                },
                error_message=str(e),
                error_code="ZEP_UNAVAILABLE",
                severity="warning",
            )
            return OperationResult.fail(
                message=f"Zep memory search failed after all retries: {e}",
                code="ZEP_UNAVAILABLE",
                severity=ErrorSeverity.WARNING,
                user_message="Memory service is temporarily unavailable. Using fallback discovery mode.",
                retryable=True,
                details={"session_id": session_id, "query": query[:100]},
            )
        except Exception as e:
            logger.warning(f"zep_error in search_memory_async: {e}")
            queue_for_retry(
                operation="zep_search_failed",
                payload={
                    "session_id": session_id,
                    "query": query,
                    "limit": limit,
                },
                error_message=str(e),
                error_code="ZEP_UNAVAILABLE",
                severity="warning",
            )
            return OperationResult.fail(
                message=f"Zep memory search failed: {e}",
                code="ZEP_UNAVAILABLE",
                severity=ErrorSeverity.WARNING,
                user_message="Memory search encountered an error. Using fallback mode.",
                retryable=True,
                details={"session_id": session_id, "query": query[:100]},
            )

    def clear_cache(self):
        """Clear the query result cache."""
        self._query_cache.clear()


def get_async_zep_client(api_key: str | None = None) -> AsyncZepMemoryClient:
    """Factory function to get an async Zep memory client.

    Args:
        api_key: Optional API key (defaults to settings.ZEP_API_KEY)

    Returns:
        AsyncZepMemoryClient instance
    """
    return AsyncZepMemoryClient(api_key=api_key)
