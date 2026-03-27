"""
pipeline/research_cache.py — Caching layer for research results.

Context: Research is expensive (multiple web searches + LLM calls).
This cache avoids re-researching the same topic within a TTL window.

NOTE: This is now a thin wrapper around the unified FileCache class.
The FileCache provides the core caching functionality with TTL support.

Cache Structure:
    packages/data/research_cache/
        {topic_hash}.json  → data with metadata

TTL: 24 hours (configurable via ttl_hours parameter)

Usage:
    from packages.pipeline.research_cache import ResearchCache

    cache = ResearchCache()
    dossier = cache.get(topic)
    if not dossier:
        dossier = await engine.research(topic)
        cache.set(topic, dossier)

Imports: pathlib
Imported by: packages/pipeline/handlers.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from packages.core.cache import FileCache
from packages.core.config import get_settings
from packages.core.logger import get_logger

log = get_logger(__name__)


class ResearchCache:
    """
    File-based cache for research results.

    This is a thin wrapper around FileCache that maintains the existing
    ResearchCache interface for backward compatibility.

    Uses topic hash as key to avoid filesystem issues with special characters.
    Thread-safe for read operations. Write operations use atomic file writes.
    """

    def __init__(
        self,
        ttl_hours: int = 24,
        cache_dir: Optional[Path] = None,
        refresh_ttl_on_access: bool = True,  # Kept for API compatibility, not used
        max_refreshes: int = 10,  # Kept for API compatibility, not used
    ) -> None:
        """
        Initialize the research cache.

        Args:
            ttl_hours: Cache time-to-live in hours (default: 24)
            cache_dir: Override cache directory (default: packages/data/research_cache)
            refresh_ttl_on_access: Kept for API compatibility (not used in new implementation)
            max_refreshes: Kept for API compatibility (not used in new implementation)
        """
        settings = get_settings()
        dir_path = cache_dir or Path(settings.DATA_DIR) / "research_cache"

        self._cache = FileCache(cache_dir=dir_path, ttl_hours=ttl_hours)
        log.debug(f"research_cache_initialized: dir={dir_path}")

    def get(self, topic: str) -> Optional[dict]:
        """
        Retrieve cached research for a topic.

        Args:
            topic: The research topic

        Returns:
            Cached ResearchDossier as dict, or None if not found/expired
        """
        result = self._cache.get(topic)
        if result:
            log.info(f"cache_hit: topic='{topic[:50]}...'")
        return result

    def set(self, topic: str, dossier: dict) -> None:
        """
        Cache research results for a topic.

        Args:
            topic: The research topic
            dossier: ResearchDossier as dict (from model_dump())
        """
        self._cache.set(topic, dossier)
        log.info(f"cache_set: topic='{topic[:50]}...'")

    def delete(self, topic: str) -> bool:
        """
        Remove cached research for a topic.

        Args:
            topic: The research topic

        Returns:
            True if cache was deleted, False if not found
        """
        return self._cache.delete(topic)

    def clear(self) -> int:
        """
        Clear all cached research.

        Returns:
            Number of cache files removed
        """
        return self._cache.clear()

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        # Simplified stats for the new implementation
        files = list(self._cache.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files if f.exists())
        return {
            "count": len(files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(self._cache.cache_dir),
            "ttl_hours": self._cache.ttl.total_seconds() / 3600,
        }

    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries.

        Note: In the new implementation, expired entries are cleaned up
        on access. This method is kept for API compatibility.

        Returns:
            0 (expired entries are cleaned on access)
        """
        return 0
