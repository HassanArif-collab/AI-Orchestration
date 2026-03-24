"""
Zep Audience Model Store — Persistent Learning Memory.

Writes performance facts and learning events to Zep Cloud so the
system accumulates intelligence about what works for Pakistani audiences.

Two write points:
  1. After ExperimentLoop completes — writes script score and what zones improved
  2. After YouTube analytics are ingested — writes engagement performance facts

Two read points:
  1. TopicFinderAgent — reads audience resonance to calibrate topic scoring
  2. SynthesisEngine — reads learning log facts for weekly synthesis

All methods are safe — ZEP_ENABLED=False or missing API key = graceful no-op.

Usage:
    store = ZepAudienceModelStore()
    await store.write_experiment_result(script, loop_log)
    context = await store.read_audience_context(genre_id)
"""

from packages.core.config import get_settings
from packages.core.logger import get_logger

logger = get_logger(__name__)


class ZepAudienceModelStore:
    """Wraps ZepMemoryClient for content factory specific read/write patterns."""

    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self._enabled = bool(
            getattr(self.settings, 'ZEP_ENABLED', False) and
            self.settings.ZEP_API_KEY
        )
        if self._enabled:
            try:
                from packages.memory.client import ZepMemoryClient
                self._client = ZepMemoryClient()
            except Exception as e:
                logger.warning(f"zep_store_init_failed: {e}")
                self._enabled = False

    async def write_experiment_result(self, script, score: float, genre_id: str) -> None:
        """Write script scoring result to Zep after ExperimentLoop completes."""
        if not self._enabled or not self._client:
            return
        try:
            fact_text = (
                f"Script '{script.adapted_title}' in genre '{genre_id}' "
                f"scored {score:.1f}% after experiment loop. "
                f"Sections: {len(script.entries)}. "
                f"Passing questions: {int(score * 0.56)}/56."
            )
            self._client.add_facts(
                session_id=f"{self.settings.ZEP_LEARNING_USER_ID}_session",
                facts=[{"fact": fact_text, "type": "experiment_result", "genre": genre_id}]
            )
        except Exception as e:
            logger.debug(f"zep_write_experiment_result_failed: {e}")

    async def write_video_performance(self, video_id: str, genre_id: str,
                                      engagement_7d: float, retention_shape: str) -> None:
        """Write YouTube analytics performance facts to Zep."""
        if not self._enabled or not self._client:
            return
        try:
            fact_text = (
                f"Video {video_id} (genre: {genre_id}) achieved "
                f"{engagement_7d:.1f}% 7-day engagement. "
                f"Retention pattern: {retention_shape}."
            )
            self._client.add_facts(
                session_id=f"{self.settings.ZEP_AUDIENCE_USER_ID}_session",
                facts=[{"fact": fact_text, "type": "video_performance", "genre": genre_id}]
            )
        except Exception as e:
            logger.debug(f"zep_write_video_performance_failed: {e}")

    async def read_audience_context(self, genre_id: str) -> str:
        """Read accumulated audience intelligence for a genre (used by TopicFinder)."""
        if not self._enabled or not self._client:
            return "No audience data available yet."
        try:
            results = self._client.search_memory(
                session_id=f"{self.settings.ZEP_AUDIENCE_USER_ID}_session",
                query=f"Pakistani audience engagement patterns for {genre_id} videos",
                limit=5
            )
            if not results:
                return "No audience data available yet."
            facts = [r.get("fact", "") for r in results if isinstance(r, dict)]
            return "\n".join(facts[:3])
        except Exception as e:
            logger.debug(f"zep_read_audience_context_failed: {e}")
            return "No audience data available yet."

    async def read_learning_insights(self, genre_id: str) -> list[str]:
        """Read experiment results for synthesis engine."""
        if not self._enabled or not self._client:
            return []
        try:
            results = self._client.search_memory(
                session_id=f"{self.settings.ZEP_LEARNING_USER_ID}_session",
                query=f"script improvement patterns for {genre_id}",
                limit=10
            )
            return [r.get("fact", "") for r in (results or []) if isinstance(r, dict)]
        except Exception as e:
            logger.debug(f"zep_read_learning_insights_failed: {e}")
            return []
