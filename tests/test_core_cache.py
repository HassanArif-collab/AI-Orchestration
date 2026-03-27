"""Tests for the unified FileCache class.

These tests verify:
1. Basic set/get functionality
2. Cache miss returns None
3. TTL expiration works correctly
4. Multi-component keys work independently
5. Atomic write leaves no .tmp files
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest


class TestFileCache:
    """Tests for FileCache class."""

    def test_filecache_set_and_get(self):
        """cache.set("key", data); assert cache.get("key") == data"""
        from packages.core.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileCache(cache_dir=Path(tmpdir), ttl_hours=24)

            data = {"title": "Test Topic", "content": "Some content"}
            cache.set("my-topic", data)

            result = cache.get("my-topic")
            assert result is not None
            assert result == data

    def test_filecache_miss_returns_none(self):
        """get on non-existent key returns None"""
        from packages.core.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileCache(cache_dir=Path(tmpdir), ttl_hours=24)

            result = cache.get("non-existent-key")
            assert result is None

    def test_filecache_expired_returns_none(self):
        """TTL=0 hours, backdate file 2 hours, assert get returns None"""
        from packages.core.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileCache(cache_dir=Path(tmpdir), ttl_hours=0)

            data = {"title": "Test Topic"}
            cache.set("expiring-topic", data)

            # Find the cache file and backdate it
            cache_dir = Path(tmpdir)
            cache_files = list(cache_dir.glob("*.json"))
            assert len(cache_files) == 1

            cache_file = cache_files[0]

            # Read, modify _cached_at to 2 hours ago, write back
            with open(cache_file, "r", encoding="utf-8") as f:
                stored = json.load(f)

            two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            stored["_cached_at"] = two_hours_ago

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(stored, f)

            # Now get should return None because entry is expired
            result = cache.get("expiring-topic")
            assert result is None

    def test_filecache_multi_key_components(self):
        """set("topic","genre-a",data1) and set("topic","genre-b",data2) are independent keys"""
        from packages.core.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileCache(cache_dir=Path(tmpdir), ttl_hours=24)

            data_a = {"genre": "a", "content": "Content for genre A"}
            data_b = {"genre": "b", "content": "Content for genre B"}

            # Set with multi-component keys
            cache.set("topic", "genre-a", data_a)
            cache.set("topic", "genre-b", data_b)

            # Get should return independent values
            result_a = cache.get("topic", "genre-a")
            result_b = cache.get("topic", "genre-b")

            assert result_a == data_a
            assert result_b == data_b
            assert result_a != result_b

    def test_filecache_atomic_write_no_partial_file(self):
        """after set(), no .tmp files remain in cache_dir"""
        from packages.core.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileCache(cache_dir=Path(tmpdir), ttl_hours=24)

            data = {"title": "Test Topic"}
            cache.set("atomic-test", data)

            # Check no .tmp files exist
            cache_dir = Path(tmpdir)
            tmp_files = list(cache_dir.glob("*.tmp"))

            assert len(tmp_files) == 0, f"Found .tmp files: {tmp_files}"

            # Also verify the json file exists
            json_files = list(cache_dir.glob("*.json"))
            assert len(json_files) == 1
