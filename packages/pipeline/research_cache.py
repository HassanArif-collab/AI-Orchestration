"""
pipeline/research_cache.py — Caching layer for research results.

Context: Research is expensive (multiple web searches + LLM calls).
This cache avoids re-researching the same topic within a TTL window.

FIXES APPLIED:
1. Added TTL refresh for frequently-accessed topics
2. Added access tracking (count, last accessed time)
3. Added max refresh limit to prevent indefinite caching

Cache Structure:
    packages/data/research_cache/
        {topic_hash}.json  → ResearchDossier as JSON

TTL: 24 hours (configurable via RESEARCH_CACHE_TTL_HOURS env var)
TTL Refresh: Enabled by default, refreshes on access up to max_refreshes times

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
    File-based cache for research results with TTL refresh support.

    Uses topic hash as key to avoid filesystem issues with special characters.
    Thread-safe for read operations. Write operations use atomic file writes.

    TTL Refresh Behavior:
        - When a cached topic is accessed, its TTL is refreshed
        - This keeps frequently-used topics in cache longer
        - Max refreshes prevents indefinite caching of stale data
    """

    def __init__(
        self,
        ttl_hours: int = 24,
        cache_dir: Optional[Path] = None,
        refresh_ttl_on_access: bool = True,
        max_refreshes: int = 10,
    ) -> None:
        """
        Initialize the research cache.

        Args:
            ttl_hours: Cache time-to-live in hours (default: 24)
            cache_dir: Override cache directory (default: packages/data/research_cache)
            refresh_ttl_on_access: Whether to refresh TTL on cache hit (default: True)
            max_refreshes: Maximum TTL refreshes before forced expiry (default: 10)
        """
        settings = get_settings()
        self.ttl = timedelta(hours=ttl_hours)
        self._refresh_ttl_on_access = refresh_ttl_on_access
        self._max_refreshes = max_refreshes

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

        If refresh_ttl_on_access is enabled and the cache entry has been
        refreshed fewer than max_refreshes times, the TTL is refreshed.

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
            refresh_count = data.get("_refresh_count", 0)

            if cached_at_str:
                cached_at = datetime.fromisoformat(cached_at_str)
                age = datetime.now(timezone.utc) - cached_at

                if age > self.ttl:
                    # Cache entry is older than TTL
                    if self._refresh_ttl_on_access and refresh_count < self._max_refreshes:
                        # Refresh TTL by updating cached_at timestamp
                        data["_cached_at"] = datetime.now(timezone.utc).isoformat()
                        data["_refresh_count"] = refresh_count + 1
                        data["_last_accessed"] = datetime.now(timezone.utc).isoformat()
                        data["_access_count"] = data.get("_access_count", 1) + 1

                        # Re-save with refreshed TTL (atomic write)
                        temp_file = cache_file.with_suffix(".tmp")
                        with open(temp_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        temp_file.rename(cache_file)

                        log.info(
                            f"cache_ttl_refreshed: topic='{topic[:50]}...' "
                            f"refresh_count={refresh_count + 1}/{self._max_refreshes} "
                            f"age_hours={age.total_seconds() / 3600:.1f}"
                        )
                    else:
                        # Max refreshes reached or refresh disabled - expire
                        log.info(
                            f"cache_expired: topic='{topic[:50]}...' "
                            f"age_hours={age.total_seconds() / 3600:.1f} "
                            f"refresh_count={refresh_count}"
                        )
                        cache_file.unlink(missing_ok=True)
                        return None
                else:
                    # Cache is still within TTL - update access tracking
                    data["_last_accessed"] = datetime.now(timezone.utc).isoformat()
                    data["_access_count"] = data.get("_access_count", 1) + 1

                    # Update access tracking (non-blocking, don't fail if this errors)
                    try:
                        temp_file = cache_file.with_suffix(".tmp")
                        with open(temp_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        temp_file.rename(cache_file)
                    except Exception as e:
                        log.debug(f"access_tracking_update_failed: {e}")

                    log.info(
                        f"cache_hit: topic='{topic[:50]}...' "
                        f"age_hours={age.total_seconds() / 3600:.1f} "
                        f"access_count={data['_access_count']}"
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
                "_refresh_count": 0,
                "_last_accessed": datetime.now(timezone.utc).isoformat(),
                "_access_count": 1,
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
            Dict with cache stats: count, total_size_bytes, oldest_entry, etc.
        """
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files if f.exists())

        oldest = None
        total_access_count = 0
        total_refresh_count = 0

        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                cached_at_str = data.get("_cached_at")
                if cached_at_str:
                    cached_at = datetime.fromisoformat(cached_at_str)
                    if oldest is None or cached_at < oldest:
                        oldest = cached_at
                total_access_count += data.get("_access_count", 0)
                total_refresh_count += data.get("_refresh_count", 0)
            except Exception:
                pass

        return {
            "count": len(files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_entry": oldest.isoformat() if oldest else None,
            "cache_dir": str(self.cache_dir),
            "ttl_hours": self.ttl.total_seconds() / 3600,
            "ttl_refresh_enabled": self._refresh_ttl_on_access,
            "max_refreshes": self._max_refreshes,
            "total_access_count": total_access_count,
            "total_refresh_count": total_refresh_count,
        }

    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries (including those past max refreshes).

        Returns:
            Number of cache files removed
        """
        count = 0
        now = datetime.now(timezone.utc)

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                cached_at_str = data.get("_cached_at")
                refresh_count = data.get("_refresh_count", 0)

                if cached_at_str:
                    cached_at = datetime.fromisoformat(cached_at_str)
                    age = now - cached_at

                    # Remove if expired AND (max refreshes reached OR refresh disabled)
                    if age > self.ttl:
                        if not self._refresh_ttl_on_access or refresh_count >= self._max_refreshes:
                            cache_file.unlink()
                            count += 1
                            log.debug(f"cleanup_removed: {cache_file.name}")

            except Exception as e:
                log.warning(f"cleanup_error: {cache_file.name} -> {e}")

        if count > 0:
            log.info(f"cleanup_complete: removed={count} expired entries")

        return count
