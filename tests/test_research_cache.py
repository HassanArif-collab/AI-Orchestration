"""Tests for permanent research cache."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from packages.core.research_cache import ResearchCache


def test_make_key_with_brief_id():
    """Test that brief_id is used directly as key."""
    key = ResearchCache.make_key(brief_id="brief-123")
    assert key == "brief-123"


def test_make_key_with_topic_statement():
    """Test that topic_statement is hashed."""
    key1 = ResearchCache.make_key(topic_statement="Pakistan AI Policy")
    key2 = ResearchCache.make_key(topic_statement="pakistan ai policy")  # Same, lowercased
    
    assert len(key1) == 32
    assert key1 == key2  # Normalized to same key


def test_make_key_requires_arguments():
    """Test that make_key raises without arguments."""
    with pytest.raises(ValueError, match="Either brief_id or topic_statement"):
        ResearchCache.make_key()


@patch("packages.core.research_cache.get_settings")
def test_get_returns_cached_research(mock_settings):
    """Test that get returns cached research from Supabase."""
    mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
    mock_settings.return_value.SUPABASE_ANON_KEY = "test-key"

    # Mock Supabase response
    mock_result = MagicMock()
    mock_result.data = {
        "cache_key": "test-key-123",
        "topic_statement": "Pakistan AI Policy",
        "dossier": {"topic": "Pakistan AI Policy", "facts": []},
        "source_urls": ["https://example.com"],
        "source_count": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch.object(ResearchCache, "_db") as mock_db:
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_result
        mock_db.return_value = mock_table

        cache = ResearchCache()
        result = cache.get(topic_statement="Pakistan AI Policy")

        assert result is not None
        assert result["from_cache"] is True
        assert "dossier" in result
        assert result["source_count"] == 1


@patch("packages.core.research_cache.get_settings")
def test_get_returns_none_on_cache_miss(mock_settings):
    """Test that get returns None when cache miss."""
    mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
    mock_settings.return_value.SUPABASE_ANON_KEY = "test-key"

    mock_result = MagicMock()
    mock_result.data = None  # Cache miss

    with patch.object(ResearchCache, "_db") as mock_db:
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_result
        mock_db.return_value = mock_table

        cache = ResearchCache()
        result = cache.get(topic_statement="New Topic")

        assert result is None


@patch("packages.core.research_cache.get_settings")
def test_get_handles_exception_gracefully(mock_settings):
    """Test that get returns None on exception (non-blocking)."""
    mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
    mock_settings.return_value.SUPABASE_ANON_KEY = "test-key"

    with patch.object(ResearchCache, "_db") as mock_db:
        mock_db.side_effect = Exception("Database connection failed")

        cache = ResearchCache()
        result = cache.get(topic_statement="Any Topic")

        assert result is None  # Should not crash


@patch("packages.core.research_cache.get_settings")
def test_save_stores_research_permanently(mock_settings):
    """Test that save stores research in Supabase."""
    mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
    mock_settings.return_value.SUPABASE_ANON_KEY = "test-key"

    mock_result = MagicMock()

    with patch.object(ResearchCache, "_db") as mock_db:
        mock_table = MagicMock()
        mock_table.upsert.return_value.execute.return_value = mock_result
        mock_db.return_value = mock_table

        cache = ResearchCache()
        cache.save(
            cache_key="test-key-123",
            topic_statement="Pakistan AI Policy",
            dossier={"topic": "Pakistan AI Policy", "facts": ["fact1"]},
            source_urls=["https://example.com"],
        )

        # Verify upsert was called with correct data
        mock_table.upsert.assert_called_once()
        call_args = mock_table.upsert.call_args[0][0]
        assert call_args["cache_key"] == "test-key-123"
        assert call_args["topic_statement"] == "Pakistan AI Policy"
        assert call_args["source_count"] == 1


@patch("packages.core.research_cache.get_settings")
def test_save_handles_exception_gracefully(mock_settings):
    """Test that save doesn't crash on exception."""
    mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
    mock_settings.return_value.SUPABASE_ANON_KEY = "test-key"

    with patch.object(ResearchCache, "_db") as mock_db:
        mock_db.side_effect = Exception("Database error")

        cache = ResearchCache()
        # Should not raise
        cache.save(
            cache_key="test-key",
            topic_statement="Topic",
            dossier={"topic": "Topic"},
        )


@patch("packages.core.research_cache.get_settings")
def test_stats_returns_cache_info(mock_settings):
    """Test that stats returns cache statistics."""
    mock_settings.return_value.SUPABASE_URL = "https://test.supabase.co"
    mock_settings.return_value.SUPABASE_ANON_KEY = "test-key"

    mock_result = MagicMock()
    mock_result.count = 42

    with patch.object(ResearchCache, "_db") as mock_db:
        mock_table = MagicMock()
        mock_table.select.return_value.execute.return_value = mock_result
        mock_db.return_value = mock_table

        cache = ResearchCache()
        stats = cache.stats()

        assert stats["count"] == 42
        assert stats["storage"] == "supabase"
        assert stats["ttl"] == "permanent"


def test_cleanup_expired_returns_zero():
    """Test that cleanup_expired is a no-op (permanent storage)."""
    cache = ResearchCache()
    result = cache.cleanup_expired()
    assert result == 0


def test_legacy_set_method():
    """Test backward compatibility with set() method."""
    with patch.object(ResearchCache, "save") as mock_save:
        cache = ResearchCache()
        cache.set("Test Topic", {"topic": "Test Topic", "facts": []})
        
        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["topic_statement"] == "Test Topic"
        assert "cache_key" in call_kwargs
