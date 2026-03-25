"""
pipeline/research_cache.py — Caching layer for research results.

Context: Research is expensive (multiple web searches + LLM calls).
This cache avoids re-researching the same topic within a TTL window.

Cache Structure:
    packages/data/research_cache/
        {topic_hash}.json  → ResearchDossier as JSON

TTL: 24 hours (configurable via RESEARCH_CACHE_TTL_HOURS env var)

Usage:
    from packages.pipeline.research_cache import ResearchCache

    cache = ResearchCache()
    dossier = cache.get(topic)
    if not dossier:
        dossier = await engine.research(topic)
        cache.set(topic, dossier)

Imports: json, hashlib, datetime, pathlib
Imported by: packages/pipeline/handlers.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from packages.core.config import get_settings
from packages.core.logger import get_logger

log = get_logger(__name__)


class ResearchCache:
    """
    File-based cache for research results.

    Uses topic hash as key to avoid filesystem issues with special characters.
    Thread-safe for read operations. Write operations use atomic file writes.
    """

    def __init__(
        self,
        ttl_hours: int = 24,
        cache_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize the research cache.

        Args:
            ttl_hours: Cache time-to-live in hours (default: 24)
            cache_dir: Override cache directory (default: packages/data/research_cache)
        """
        settings = get_settings()
        self.ttl = timedelta(hours=ttl_hours)

        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = Path(settings.DATA_DIR) / "research_cache"

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        log.debug(f"research_cache_initialized: dir={self.cache_dir}")

    def _hash_topic(self, topic: str) -> str:
        """Create a filesystem-safe hash for the topic."""
        normalized = topic.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _cache_path(self, topic: str) -> Path:
        """Get the cache file path for a topic."""
        return self.cache_dir / f"{self._hash_topic(topic)}.json"

    def get(self, topic: str) -> Optional[dict]:
        """
        Retrieve cached research for a topic.

        Args:
            topic: The research topic

        Returns:
            Cached ResearchDossier as dict, or None if not found/expired
        """
        cache_file = self._cache_path(topic)

        if not cache_file.exists():
            log.debug(f"cache_miss: topic='{topic[:50]}...' (no file)")
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check TTL
            cached_at_str = data.get("_cached_at")
            if cached_at_str:
                cached_at = datetime.fromisoformat(cached_at_str)
                age = datetime.now(timezone.utc) - cached_at

                if age > self.ttl:
                    log.info(
                        f"cache_expired: topic='{topic[:50]}...' "
                        f"age_hours={age.total_seconds() / 3600:.1f}"
                    )
                    # Remove expired cache
                    cache_file.unlink(missing_ok=True)
                    return None

            log.info(
                f"cache_hit: topic='{topic[:50]}...' "
                f"age_hours={age.total_seconds() / 3600:.1f if cached_at_str else 'unknown'}"
            )
            return data.get("dossier")

        except Exception as e:
            log.warning(f"cache_read_failed: {e}")
            return None

    def set(self, topic: str, dossier: dict) -> None:
        """
        Cache research results for a topic.

        Args:
            topic: The research topic
            dossier: ResearchDossier as dict (from model_dump())
        """
        cache_file = self._cache_path(topic)

        try:
            data = {
                "topic": topic,
                "dossier": dossier,
                "_cached_at": datetime.now(timezone.utc).isoformat(),
            }

            # Atomic write: write to temp file, then rename
            temp_file = cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            temp_file.rename(cache_file)
            log.info(f"cache_set: topic='{topic[:50]}...'")

        except Exception as e:
            log.warning(f"cache_write_failed: {e}")
            # Clean up temp file if it exists
            temp_file = cache_file.with_suffix(".tmp")
            temp_file.unlink(missing_ok=True)

    def delete(self, topic: str) -> bool:
        """
        Remove cached research for a topic.

        Args:
            topic: The research topic

        Returns:
            True if cache was deleted, False if not found
        """
        cache_file = self._cache_path(topic)

        if cache_file.exists():
            cache_file.unlink()
            log.info(f"cache_deleted: topic='{topic[:50]}...'")
            return True

        return False

    def clear(self) -> int:
        """
        Clear all cached research.

        Returns:
            Number of cache files removed
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1

        log.info(f"cache_cleared: removed={count} files")
        return count

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats: count, total_size_bytes, oldest_entry
        """
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files if f.exists())

        oldest = None
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                cached_at_str = data.get("_cached_at")
                if cached_at_str:
                    cached_at = datetime.fromisoformat(cached_at_str)
                    if oldest is None or cached_at < oldest:
                        oldest = cached_at
            except Exception:
                pass

        return {
            "count": len(files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_entry": oldest.isoformat() if oldest else None,
            "cache_dir": str(self.cache_dir),
            "ttl_hours": self.ttl.total_seconds() / 3600,
        }
