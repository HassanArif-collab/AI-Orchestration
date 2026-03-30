"""Permanent research dossier storage backed by Supabase.

Every successful research is saved forever.
Repeated runs of the same topic return the cached dossier instantly.

This replaces the previous file-based cache with TTL. Now all research
is stored permanently in Supabase - no expiration, no cleanup.

Usage:
    from packages.pipeline.research_cache import ResearchCache

    cache = ResearchCache()
    cached = cache.get(topic_statement="Pakistan AI policy")
    if cached:
        dossier = cached["dossier"]
    else:
        dossier = await engine.research(topic)
        cache.save(
            cache_key=ResearchCache.make_key(topic_statement=topic),
            topic_statement=topic,
            dossier=dossier.model_dump(),
            source_urls=list_of_urls,
        )

Imports: packages.core.supabase_client, hashlib
Imported by: packages/pipeline/handlers.py, packages/content_factory/production/workflow.py
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from packages.core.logger import get_logger

logger = get_logger(__name__)


class ResearchCache:
    """Supabase-backed permanent research cache.

    No TTL, no expiration. All research is stored forever.
    Provides instant cache hits on repeated topics to save API tokens.
    """

    def _db(self):
        """Get the Supabase table client lazily."""
        from packages.core.supabase_client import get_supabase
        return get_supabase().table("research_cache")

    @staticmethod
    def make_key(
        brief_id: Optional[str] = None,
        topic_statement: Optional[str] = None
    ) -> str:
        """Generate a cache key from brief_id or topic statement.

        Args:
            brief_id: Optional TopicBrief ID (used directly if provided)
            topic_statement: Topic text (hashed if no brief_id)

        Returns:
            Cache key string

        Raises:
            ValueError: If neither argument is provided
        """
        if brief_id:
            return brief_id
        if topic_statement:
            normalized = topic_statement.strip().lower()
            return hashlib.sha256(normalized.encode()).hexdigest()[:32]
        raise ValueError("Either brief_id or topic_statement must be provided")

    def get(
        self,
        brief_id: Optional[str] = None,
        topic_statement: Optional[str] = None,
    ) -> Optional[dict]:
        """Retrieve cached research for a topic.

        Args:
            brief_id: Optional TopicBrief ID for lookup
            topic_statement: Topic text for lookup (hashed)

        Returns:
            Dict with dossier and metadata, or None if not found.
            Keys: dossier, source_urls, source_count, age_hours,
                topic_statement, from_cache
        """
        cache_key = self.make_key(brief_id=brief_id, topic_statement=topic_statement)

        try:
            result = (
                self._db()
                .select("*")
                .eq("cache_key", cache_key)
                .maybe_single()
                .execute()
            )

            if not result.data:
                logger.debug(f"research_cache_miss: key={cache_key[:12]}...")
                return None

            row = result.data
            created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600

            logger.info(
                f"research_cache_hit: key={cache_key[:12]}..., "
                f"age={age_hours:.1f}h old (PERMANENT)"
            )

            return {
                "dossier": row["dossier"],
                "source_urls": row.get("source_urls", []),
                "source_count": row.get("source_count", 0),
                "age_hours": round(age_hours, 1),
                "topic_statement": row["topic_statement"],
                "from_cache": True,
            }

        except Exception as e:
            logger.warning(f"research_cache_get_failed: {e}")
            return None

    def save(
        self,
        cache_key: str,
        topic_statement: str,
        dossier: dict,
        source_urls: Optional[list[str]] = None,
        brief_id: Optional[str] = None,
    ) -> None:
        """Save research results to the permanent cache.

        Args:
            cache_key: Unique key for this research
            topic_statement: The topic text
            dossier: ResearchDossier as dict (from model_dump())
            source_urls: List of source URLs consulted
            brief_id: Optional TopicBrief ID for reference
        """
        try:
            self._db().upsert(
                {
                    "cache_key": cache_key,
                    "topic_statement": topic_statement,
                    "dossier": dossier,
                    "source_urls": source_urls or [],
                    "source_count": len(source_urls) if source_urls else 0,
                    "brief_id": brief_id,
                },
                on_conflict="cache_key",
            ).execute()

            logger.info(
                f"research_cache_saved: key={cache_key[:12]}..., "
                f"sources={len(source_urls or [])} (PERMANENT)"
            )

        except Exception as e:
            logger.warning(f"research_cache_save_failed: {e}")

    # Legacy compatibility methods (for smooth migration)

    def set(self, topic: str, dossier: dict) -> None:
        """Legacy method for backward compatibility.

        Args:
            topic: The research topic
            dossier: ResearchDossier as dict
        """
        cache_key = self.make_key(topic_statement=topic)
        self.save(
            cache_key=cache_key,
            topic_statement=topic,
            dossier=dossier,
            source_urls=dossier.get("sources", []),
        )

    def delete(self, topic: str) -> bool:
        """Remove cached research for a topic.

        Note: In permanent storage mode, this is rarely used.

        Args:
            topic: The research topic

        Returns:
            True if deleted, False if not found
        """
        cache_key = self.make_key(topic_statement=topic)
        try:
            result = (
                self._db()
                .delete()
                .eq("cache_key", cache_key)
                .execute()
            )
            deleted = len(result.data) > 0
            if deleted:
                logger.info(f"research_cache_deleted: key={cache_key[:12]}...")
            return deleted
        except Exception as e:
            logger.warning(f"research_cache_delete_failed: {e}")
            return False

    def clear(self) -> int:
        """Clear all cached research.

        WARNING: This removes all research from the database.
        Use with caution.

        Returns:
            Number of entries deleted
        """
        try:
            # Get count first
            count_result = self._db().select("id", count="exact").execute()
            count = count_result.count if hasattr(count_result, 'count') else 0

            # Delete all
            self._db().delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

            logger.warning(f"research_cache_cleared: {count} entries removed")
            return count
        except Exception as e:
            logger.warning(f"research_cache_clear_failed: {e}")
            return 0

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with count and other stats
        """
        try:
            result = self._db().select("id", count="exact").execute()
            count = result.count if hasattr(result, 'count') else len(result.data)

            return {
                "count": count,
                "storage": "supabase",
                "ttl": "permanent",
                "cache_type": "database",
            }
        except Exception as e:
            logger.warning(f"research_cache_stats_failed: {e}")
            return {
                "count": 0,
                "storage": "supabase",
                "error": str(e),
            }

    def cleanup_expired(self) -> int:
        """No-op for permanent storage.

        Kept for backward compatibility with existing code.
        Research never expires in this implementation.

        Returns:
            Always 0 (nothing to clean up)
        """
        return 0
