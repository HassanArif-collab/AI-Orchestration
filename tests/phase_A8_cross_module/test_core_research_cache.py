"""Tests for packages/core/research_cache.py — Research-specific caching."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


class TestMakeKey:
    """Tests for ResearchCache.make_key() static method."""

    def test_from_brief_id(self):
        from packages.core.research_cache import ResearchCache
        key = ResearchCache.make_key(brief_id="brief-abc-123")
        assert key == "brief-abc-123"

    def test_from_topic_statement(self):
        from packages.core.research_cache import ResearchCache
        key = ResearchCache.make_key(topic_statement="AI in Pakistan")
        assert isinstance(key, str)
        assert len(key) == 32  # first 32 chars of SHA-256

    def test_brief_id_takes_precedence(self):
        from packages.core.research_cache import ResearchCache
        key = ResearchCache.make_key(brief_id="brief-123", topic_statement="Topic")
        assert key == "brief-123"

    def test_neither_raises(self):
        from packages.core.research_cache import ResearchCache
        with pytest.raises(ValueError, match="Either brief_id or topic_statement"):
            ResearchCache.make_key()

    def test_topic_normalization(self):
        from packages.core.research_cache import ResearchCache
        k1 = ResearchCache.make_key(topic_statement="AI in Pakistan")
        k2 = ResearchCache.make_key(topic_statement="ai in pakistan")
        assert k1 == k2

    def test_topic_whitespace_stripped(self):
        from packages.core.research_cache import ResearchCache
        k1 = ResearchCache.make_key(topic_statement="  topic  ")
        k2 = ResearchCache.make_key(topic_statement="topic")
        assert k1 == k2


class TestResearchCacheGet:
    """Tests for ResearchCache.get()."""

    @patch("packages.core.research_cache.ResearchCache._db")
    def test_returns_none_on_miss(self, mock_db):
        from packages.core.research_cache import ResearchCache
        mock_table = MagicMock()
        mock_result = MagicMock()
        mock_result.data = None
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_result
        mock_db.return_value = mock_table

        cache = ResearchCache()
        result = cache.get(topic_statement="nonexistent")
        assert result is None

    @patch("packages.core.research_cache.ResearchCache._db")
    def test_returns_cached_data(self, mock_db):
        from packages.core.research_cache import ResearchCache
        now = datetime.now(timezone.utc)
        mock_table = MagicMock()
        mock_result = MagicMock()
        mock_result.data = {
            "cache_key": "key123",
            "dossier": {"findings": ["fact1"]},
            "source_urls": ["https://source.com"],
            "source_count": 1,
            "topic_statement": "AI in Pakistan",
            "created_at": now.isoformat(),
        }
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_result
        mock_db.return_value = mock_table

        cache = ResearchCache()
        result = cache.get(topic_statement="AI in Pakistan")
        assert result is not None
        assert result["dossier"]["findings"] == ["fact1"]
        assert result["from_cache"] is True
        assert result["source_count"] == 1

    @patch("packages.core.research_cache.ResearchCache._db")
    def test_handles_supabase_error(self, mock_db):
        from packages.core.research_cache import ResearchCache
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_table

        cache = ResearchCache()
        result = cache.get(topic_statement="test")
        assert result is None


class TestResearchCacheSave:
    """Tests for ResearchCache.save()."""

    @patch("packages.core.research_cache.ResearchCache._db")
    def test_calls_upsert(self, mock_db):
        from packages.core.research_cache import ResearchCache
        mock_table = MagicMock()
        mock_table.upsert.return_value.execute.return_value = None
        mock_db.return_value = mock_table

        cache = ResearchCache()
        cache.save(
            cache_key="key123",
            topic_statement="Test Topic",
            dossier={"findings": ["fact"]},
            source_urls=["https://source.com"],
        )

        mock_table.upsert.assert_called_once()

    @patch("packages.core.research_cache.ResearchCache._db")
    def test_handles_supabase_error(self, mock_db):
        from packages.core.research_cache import ResearchCache
        mock_table = MagicMock()
        mock_table.upsert.return_value.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_table

        cache = ResearchCache()
        # Should not raise
        cache.save(cache_key="key", topic_statement="t", dossier={})


class TestResearchCacheDelete:
    """Tests for ResearchCache.delete()."""

    @patch("packages.core.research_cache.ResearchCache._db")
    def test_returns_true_on_delete(self, mock_db):
        from packages.core.research_cache import ResearchCache
        mock_table = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "1"}]
        mock_table.delete.return_value.eq.return_value.execute.return_value = mock_result
        mock_db.return_value = mock_table

        cache = ResearchCache()
        result = cache.delete("test topic")
        assert result is True

    @patch("packages.core.research_cache.ResearchCache._db")
    def test_returns_false_on_miss(self, mock_db):
        from packages.core.research_cache import ResearchCache
        mock_table = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_table.delete.return_value.eq.return_value.execute.return_value = mock_result
        mock_db.return_value = mock_table

        cache = ResearchCache()
        result = cache.delete("nonexistent topic")
        assert result is False


class TestResearchCacheStats:
    """Tests for ResearchCache.stats()."""

    @patch("packages.core.research_cache.ResearchCache._db")
    def test_returns_stats(self, mock_db):
        from packages.core.research_cache import ResearchCache
        mock_table = MagicMock()
        mock_result = MagicMock()
        mock_result.count = 42
        mock_result.data = []
        mock_table.select.return_value.execute.return_value = mock_result
        mock_db.return_value = mock_table

        cache = ResearchCache()
        stats = cache.stats()
        assert stats["count"] == 42
        assert stats["storage"] == "supabase"
        assert stats["ttl"] == "permanent"


class TestResearchCacheCleanupExpired:
    """Tests for cleanup_expired()."""

    def test_returns_zero(self):
        from packages.core.research_cache import ResearchCache
        cache = ResearchCache()
        assert cache.cleanup_expired() == 0


class TestLegacyMethods:
    """Tests for legacy compatibility methods."""

    @patch("packages.core.research_cache.ResearchCache.save")
    def test_set_method_calls_save(self, mock_save):
        from packages.core.research_cache import ResearchCache
        cache = ResearchCache()
        cache.set("my topic", {"findings": ["fact1"], "sources": ["https://source.com"]})
        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args.kwargs
        assert call_kwargs["topic_statement"] == "my topic"

    @patch("packages.core.research_cache.ResearchCache.clear")
    def test_clear_calls_db_clear(self, mock_clear):
        from packages.core.research_cache import ResearchCache
        cache = ResearchCache()
        cache.clear()
        mock_clear.assert_called_once()
