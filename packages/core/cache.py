"""
core/cache.py — Generic file-based cache with TTL.

A unified caching solution that replaces the duplicate ScriptCache and
ResearchCache implementations. Uses atomic writes and SHA-256 key hashing.

Features:
  - TTL (time-to-live) based expiration
  - Atomic file writes to prevent corruption
  - Multi-component keys (e.g., topic + genre)
  - JSON envelope format with metadata

Usage:
    from packages.core.cache import FileCache

    # Simple single-key cache
    cache = FileCache(cache_dir=Path("data/cache"), ttl_hours=24)
    cache.set("my-topic", {"data": "value"})
    result = cache.get("my-topic")

    # Multi-component keys
    cache.set("topic", "genre-a", {"content": "A"})
    cache.set("topic", "genre-b", {"content": "B"})
    cache.get("topic", "genre-a")  # Returns {"content": "A"}

File Format:
    Each cache entry is a JSON file:
    {
        "data": <user_data>,
        "_cached_at": "<ISO UTC timestamp>"
    }

Imports: json, hashlib, datetime, pathlib
Imported by: packages/pipeline/handlers.py, packages/pipeline/research_cache.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from packages.core.logger import get_logger

log = get_logger(__name__)


class FileCache:
    """
    Generic file-based cache with TTL support.

    Uses SHA-256 hash of key components as the cache filename.
    Supports multi-component keys for namespacing.
    Thread-safe for read operations. Write operations use atomic file writes.

    Attributes:
        cache_dir: Directory where cache files are stored
        ttl: Time-to-live as timedelta
    """

    def __init__(
        self,
        cache_dir: Path,
        ttl_hours: int = 24,
    ) -> None:
        """
        Initialize the file cache.

        Args:
            cache_dir: Directory to store cache files (will be created if needed)
            ttl_hours: Cache time-to-live in hours (default: 24)
        """
        self.cache_dir = Path(cache_dir)
        self.ttl = timedelta(hours=ttl_hours)

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        log.debug(f"file_cache_initialized: dir={self.cache_dir} ttl_hours={ttl_hours}")

    def _hash_key(self, *key_components: str) -> str:
        """
        Create a filesystem-safe hash from key components.

        Args:
            *key_components: Variable number of strings that form the cache key

        Returns:
            SHA-256 hexdigest (first 16 chars) of the joined components
        """
        # Normalize and join components
        normalized = ":".join(str(c).lower().strip() for c in key_components)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _cache_path(self, *key_components: str) -> Path:
        """
        Get the cache file path for given key components.

        Args:
            *key_components: Variable number of strings that form the cache key

        Returns:
            Path to the cache JSON file
        """
        key_hash = self._hash_key(*key_components)
        return self.cache_dir / f"{key_hash}.json"

    def get(self, *key_components: str) -> Optional[dict]:
        """
        Retrieve cached data by key components.

        Checks TTL and returns None if the entry has expired.

        Args:
            *key_components: Variable number of strings that form the cache key

        Returns:
            Cached data dict, or None if not found/expired
        """
        cache_file = self._cache_path(*key_components)

        if not cache_file.exists():
            log.debug(f"cache_miss: key_components={key_components}")
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
                    log.debug(
                        f"cache_expired: key_components={key_components} "
                        f"age_hours={age.total_seconds() / 3600:.1f}"
                    )
                    cache_file.unlink(missing_ok=True)
                    return None

            log.debug(f"cache_hit: key_components={key_components}")
            return data.get("data")

        except Exception as e:
            log.warning(f"cache_read_failed: {e}")
            return None

    def set(self, *args) -> None:
        """
        Cache data with given key components.

        Uses atomic write: writes to .tmp file first, then renames.
        This prevents corruption from partial writes.

        Args:
            *args: Last argument is the data dict to cache,
                   all preceding arguments are key components.

        Example:
            cache.set("my-key", {"data": "value"})
            cache.set("topic", "genre", {"content": "..."})
        """
        if len(args) < 2:
            raise ValueError("set() requires at least one key component and data")

        # Last arg is data, rest are key components
        *key_components, data = args

        cache_file = self._cache_path(*key_components)

        try:
            envelope = {
                "data": data,
                "_cached_at": datetime.now(timezone.utc).isoformat(),
            }

            # Atomic write: write to temp file, then rename
            temp_file = cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2, ensure_ascii=False, default=str)

            temp_file.replace(cache_file)
            log.debug(f"cache_set: key_components={key_components}")

        except Exception as e:
            log.warning(f"cache_write_failed: {e}")
            # Clean up temp file if it exists
            temp_file = cache_file.with_suffix(".tmp")
            temp_file.unlink(missing_ok=True)

    def delete(self, *key_components: str) -> bool:
        """
        Remove cached data by key components.

        Args:
            *key_components: Variable number of strings that form the cache key

        Returns:
            True if cache was deleted, False if not found
        """
        cache_file = self._cache_path(*key_components)

        if cache_file.exists():
            cache_file.unlink()
            log.debug(f"cache_deleted: key_components={key_components}")
            return True

        return False

    def clear(self) -> int:
        """
        Clear all cached data.

        Returns:
            Number of cache files removed
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1

        log.info(f"cache_cleared: removed={count} files")
        return count
