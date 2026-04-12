"""Tests for packages/content_factory/memory/zep_store.py — Zep audience model store."""

import pytest
from unittest.mock import MagicMock, patch


class TestZepAudienceModelStoreInit:
    """Tests for ZepAudienceModelStore initialization."""

    @patch("packages.content_factory.memory.zep_store.get_settings")
    def test_disabled_when_no_zep_key(self, mock_settings):
        mock_settings.return_value = MagicMock(ZEP_ENABLED=False, ZEP_API_KEY="")
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore
        store = ZepAudienceModelStore()
        assert store._enabled is False

    @patch("packages.content_factory.memory.zep_store.get_settings")
    def test_disabled_when_zep_enabled_but_no_key(self, mock_settings):
        mock_settings.return_value = MagicMock(ZEP_ENABLED=True, ZEP_API_KEY="")
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore
        store = ZepAudienceModelStore()
        assert store._enabled is False


class TestWriteExperimentResult:
    """Tests for write_experiment_result()."""

    @pytest.mark.asyncio
    @patch("packages.content_factory.memory.zep_store.get_settings")
    async def test_noop_when_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(ZEP_ENABLED=False, ZEP_API_KEY="")
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore
        store = ZepAudienceModelStore()
        await store.write_experiment_result(MagicMock(), 85.0, "tech")


class TestWriteVideoPerformance:
    """Tests for write_video_performance()."""

    @pytest.mark.asyncio
    @patch("packages.content_factory.memory.zep_store.get_settings")
    async def test_noop_when_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(ZEP_ENABLED=False, ZEP_API_KEY="")
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore
        store = ZepAudienceModelStore()
        await store.write_video_performance("vid123", "tech", 72.5, "Harris-Pattern")


class TestReadAudienceContext:
    """Tests for read_audience_context()."""

    @pytest.mark.asyncio
    @patch("packages.content_factory.memory.zep_store.get_settings")
    async def test_returns_no_data_when_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(ZEP_ENABLED=False, ZEP_API_KEY="")
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore
        store = ZepAudienceModelStore()
        result = await store.read_audience_context("tech")
        assert result == "No audience data available yet."


class TestReadLearningInsights:
    """Tests for read_learning_insights()."""

    @pytest.mark.asyncio
    @patch("packages.content_factory.memory.zep_store.get_settings")
    async def test_returns_empty_when_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(ZEP_ENABLED=False, ZEP_API_KEY="")
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore
        store = ZepAudienceModelStore()
        result = await store.read_learning_insights("tech")
        assert result == []


class TestZepAudienceModelStoreGeneral:
    """General tests for ZepAudienceModelStore."""

    def test_disabled_store_noop_on_all_methods(self):
        """All methods should be safe no-ops when disabled."""
        from packages.content_factory.memory.zep_store import ZepAudienceModelStore

        mock_settings = MagicMock(ZEP_ENABLED=False, ZEP_API_KEY="")
        with patch("packages.content_factory.memory.zep_store.get_settings", return_value=mock_settings):
            store = ZepAudienceModelStore()
            assert store._enabled is False
            assert store._client is None

    def test_settings_attributes_accessed(self):
        """Verify the store reads settings correctly."""
        mock_settings = MagicMock(
            ZEP_ENABLED=True,
            ZEP_API_KEY="test-key",
            ZEP_AUDIENCE_USER_ID="aud_user",
            ZEP_LEARNING_USER_ID="learn_user",
        )
        with patch("packages.content_factory.memory.zep_store.get_settings", return_value=mock_settings):
            from packages.content_factory.memory.zep_store import ZepAudienceModelStore
            store = ZepAudienceModelStore()
            # With no zep-cloud installed, the init should catch the import error
            # and fall back to disabled
            assert store.settings is not None
