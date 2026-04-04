"""Tests for packages/core/cache.py — File-based caching layer."""

import pytest
import json
import time
from pathlib import Path


class TestFileCacheInit:
    """Tests for FileCache initialization."""

    def test_creates_cache_dir(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        assert tmp_cache_dir.exists()

    def test_custom_ttl(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir, ttl_hours=48)
        assert cache.ttl.total_seconds() == 48 * 3600


class TestHashKey:
    """Tests for _hash_key()."""

    def test_deterministic(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        h1 = cache._hash_key("test-key")
        h2 = cache._hash_key("test-key")
        assert h1 == h2

    def test_different_keys_differ(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        h1 = cache._hash_key("key-one")
        h2 = cache._hash_key("key-two")
        assert h1 != h2

    def test_case_insensitive(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        h1 = cache._hash_key("MyKey")
        h2 = cache._hash_key("mykey")
        assert h1 == h2

    def test_whitespace_stripped(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        h1 = cache._hash_key(" key ")
        h2 = cache._hash_key("key")
        assert h1 == h2

    def test_multi_component_key(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        h1 = cache._hash_key("topic", "genre")
        h2 = cache._hash_key("topic:genre")
        assert h1 == h2

    def test_hash_length(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        h = cache._hash_key("test")
        assert len(h) == 16  # first 16 chars of SHA-256


class TestSetAndGet:
    """Tests for set() and get() methods."""

    def test_set_and_get(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir, ttl_hours=24)
        cache.set("my-key", {"data": "value"})
        result = cache.get("my-key")
        assert result == {"data": "value"}

    def test_get_miss(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        result = cache.get("nonexistent")
        assert result is None

    def test_multi_component_key(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        cache.set("topic", "genre-a", {"content": "A"})
        cache.set("topic", "genre-b", {"content": "B"})
        assert cache.get("topic", "genre-a")["content"] == "A"
        assert cache.get("topic", "genre-b")["content"] == "B"

    def test_overwrite(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        cache.set("key", {"v": 1})
        cache.set("key", {"v": 2})
        assert cache.get("key")["v"] == 2


class TestTTLExpiration:
    """Tests for TTL-based cache expiration."""

    def test_expired_entry_returns_none(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir, ttl_hours=0)  # 0 hours = instant expiry
        cache.set("key", {"data": "value"})
        # Even with 0 ttl, we need a tiny delay to ensure the timestamp differs
        time.sleep(0.01)
        result = cache.get("key")
        # With 0 hours TTL, should be expired immediately
        assert result is None

    def test_valid_entry_within_ttl(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir, ttl_hours=24)
        cache.set("key", {"data": "fresh"})
        result = cache.get("key")
        assert result == {"data": "fresh"}


class TestDelete:
    """Tests for delete() method."""

    def test_delete_existing(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        cache.set("key", {"data": "value"})
        assert cache.delete("key") is True
        assert cache.get("key") is None

    def test_delete_nonexistent(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        assert cache.delete("nonexistent") is False


class TestClear:
    """Tests for clear() method."""

    def test_clear_all(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        cache.set("key1", {"d": 1})
        cache.set("key2", {"d": 2})
        cache.set("key3", {"d": 3})
        count = cache.clear()
        assert count == 3
        assert cache.get("key1") is None

    def test_clear_empty(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        count = cache.clear()
        assert count == 0


class TestSetValidation:
    """Tests for set() input validation."""

    def test_requires_at_least_one_key_and_data(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        with pytest.raises(ValueError, match="at least one key component"):
            cache.set()

    def test_set_with_only_data_raises(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        with pytest.raises(ValueError):
            cache.set({"data": "value"})


class TestAtomicWrite:
    """Tests for atomic write behavior."""

    def test_no_corruption_on_write(self, tmp_cache_dir):
        from packages.core.cache import FileCache
        cache = FileCache(cache_dir=tmp_cache_dir)
        cache.set("key", {"nested": {"deep": {"value": True}}})
        result = cache.get("key")
        assert result["nested"]["deep"]["value"] is True
