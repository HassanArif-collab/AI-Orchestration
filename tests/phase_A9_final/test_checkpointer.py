"""Tests for packages.content_factory.orchestration.checkpointer."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════
# get_memory_saver — should work without mocking if langgraph
# is installed, otherwise mock langgraph.checkpoint.memory
# ══════════════════════════════════════════════════════════════

class TestGetMemorySaver:
    """Test the get_memory_saver() function."""

    def test_returns_memory_saver_instance(self):
        """Mock langgraph to avoid real dependency."""
        mock_memory_saver_cls = MagicMock()
        with patch.dict("sys.modules", {
            "langgraph.checkpoint.memory": MagicMock(MemorySaver=mock_memory_saver_cls),
        }):
            # Reimport to pick up mocked module
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)
            saver = mod.get_memory_saver()

        mock_memory_saver_cls.assert_called_once()
        assert saver is mock_memory_saver_cls.return_value


# ══════════════════════════════════════════════════════════════
# get_checkpointer — PostgresSaver (fully mocked)
# ══════════════════════════════════════════════════════════════

class TestGetCheckpointer:

    @pytest.mark.asyncio
    async def test_raises_when_no_db_url(self):
        """Should raise RuntimeError if SUPABASE_DB_URL is not set."""
        mock_pool_cls = MagicMock()
        mock_saver_cls = MagicMock()
        mock_saver_instance = AsyncMock()
        mock_saver_cls.return_value = mock_saver_instance

        mock_settings = MagicMock()
        mock_settings.SUPABASE_DB_URL = None

        with patch.dict("sys.modules", {
            "psycopg_pool": MagicMock(AsyncConnectionPool=mock_pool_cls),
            "langgraph.checkpoint.postgres": MagicMock(),
            "langgraph.checkpoint.postgres.aio": MagicMock(AsyncPostgresSaver=mock_saver_cls),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            # Reset module globals
            mod._pool = None
            mod._checkpointer = None

            with patch.object(mod, "get_settings", return_value=mock_settings):
                with pytest.raises(RuntimeError, match="SUPABASE_DB_URL not set"):
                    await mod.get_checkpointer()

    @pytest.mark.asyncio
    async def test_initializes_checkpointer(self):
        """Should create pool, open it, create saver, and call setup."""
        mock_pool = AsyncMock()
        mock_pool_cls = MagicMock(return_value=mock_pool)

        mock_saver_instance = AsyncMock()
        mock_saver_cls = MagicMock(return_value=mock_saver_instance)

        mock_settings = MagicMock()
        mock_settings.SUPABASE_DB_URL = "postgresql://user:pass@host:5432/db"

        with patch.dict("sys.modules", {
            "psycopg_pool": MagicMock(AsyncConnectionPool=mock_pool_cls),
            "langgraph.checkpoint.postgres": MagicMock(),
            "langgraph.checkpoint.postgres.aio": MagicMock(AsyncPostgresSaver=mock_saver_cls),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            # Reset module globals
            mod._pool = None
            mod._checkpointer = None

            with patch.object(mod, "get_settings", return_value=mock_settings):
                result = await mod.get_checkpointer()

            assert result is mock_saver_instance
            mock_pool_cls.assert_called_once()
            call_kwargs = mock_pool_cls.call_args
            assert call_kwargs[0][0] == "postgresql://user:pass@host:5432/db"
            assert call_kwargs[1]["min_size"] == 2
            assert call_kwargs[1]["max_size"] == 10
            assert call_kwargs[1]["open"] is False
            mock_pool.open.assert_awaited_once()
            mock_saver_instance.setup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_singleton(self):
        """Should return the same instance on second call."""
        mock_pool = AsyncMock()
        mock_pool_cls = MagicMock(return_value=mock_pool)
        mock_saver_instance = AsyncMock()
        mock_saver_cls = MagicMock(return_value=mock_saver_instance)
        mock_settings = MagicMock()
        mock_settings.SUPABASE_DB_URL = "postgresql://u:p@h:5432/d"

        with patch.dict("sys.modules", {
            "psycopg_pool": MagicMock(AsyncConnectionPool=mock_pool_cls),
            "langgraph.checkpoint.postgres": MagicMock(),
            "langgraph.checkpoint.postgres.aio": MagicMock(AsyncPostgresSaver=mock_saver_cls),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            mod._pool = None
            mod._checkpointer = None

            with patch.object(mod, "get_settings", return_value=mock_settings):
                result1 = await mod.get_checkpointer()
                result2 = await mod.get_checkpointer()

            assert result1 is result2
            # Pool should only be created once
            mock_pool_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_race_condition_raises(self):
        """If pool exists but checkpointer doesn't, should raise RuntimeError."""
        mock_settings = MagicMock()
        mock_settings.SUPABASE_DB_URL = "postgresql://u:p@h:5432/d"

        with patch.dict("sys.modules", {
            "psycopg_pool": MagicMock(),
            "langgraph.checkpoint.postgres": MagicMock(),
            "langgraph.checkpoint.postgres.aio": MagicMock(),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            # Set pool to a non-None value but leave checkpointer as None
            mod._pool = MagicMock()
            mod._checkpointer = None

            with patch.object(mod, "get_settings", return_value=mock_settings):
                with pytest.raises(RuntimeError, match="initialization in progress"):
                    await mod.get_checkpointer()

            # Clean up
            mod._pool = None

    @pytest.mark.asyncio
    async def test_import_error_raises_runtime_error(self):
        """Missing psycopg_pool should raise RuntimeError with install hint."""
        mock_settings = MagicMock()
        mock_settings.SUPABASE_DB_URL = "postgresql://u:p@h:5432/d"

        # Make the import inside get_checkpointer fail
        with patch.dict("sys.modules", {
            "psycopg_pool": None,  # Will cause ImportError
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            mod._pool = None
            mod._checkpointer = None

            with patch.object(mod, "get_settings", return_value=mock_settings):
                with pytest.raises(RuntimeError, match="Missing dependencies"):
                    await mod.get_checkpointer()

            mod._pool = None
            mod._checkpointer = None


# ══════════════════════════════════════════════════════════════
# close_checkpointer
# ══════════════════════════════════════════════════════════════

class TestCloseCheckpointer:

    @pytest.mark.asyncio
    async def test_closes_open_pool(self):
        mock_pool = AsyncMock()
        with patch.dict("sys.modules", {
            "langgraph.checkpoint.memory": MagicMock(MemorySaver=MagicMock),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            mod._pool = mock_pool
            mod._checkpointer = MagicMock()

            await mod.close_checkpointer()

            mock_pool.close.assert_awaited_once()
            assert mod._pool is None
            assert mod._checkpointer is None

    @pytest.mark.asyncio
    async def test_idempotent_close(self):
        """Calling close twice should not raise."""
        mock_pool = AsyncMock()
        with patch.dict("sys.modules", {
            "langgraph.checkpoint.memory": MagicMock(MemorySaver=MagicMock),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            mod._pool = mock_pool
            mod._checkpointer = MagicMock()

            await mod.close_checkpointer()
            await mod.close_checkpointer()  # Second call — pool is now None

            mock_pool.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_handles_exception(self):
        """Should not raise if pool.close() throws."""
        mock_pool = AsyncMock()
        mock_pool.close.side_effect = Exception("connection error")
        with patch.dict("sys.modules", {
            "langgraph.checkpoint.memory": MagicMock(MemorySaver=MagicMock),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            mod._pool = mock_pool
            mod._checkpointer = MagicMock()

            # Should not raise
            await mod.close_checkpointer()

            assert mod._pool is None


# ══════════════════════════════════════════════════════════════
# get_checkpointer_status
# ══════════════════════════════════════════════════════════════

class TestGetCheckpointerStatus:

    async def test_not_initialized(self):
        with patch.dict("sys.modules", {
            "langgraph.checkpoint.memory": MagicMock(MemorySaver=MagicMock),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            mod._pool = None
            mod._checkpointer = None

            status = await mod.get_checkpointer_status()
            assert status["status"] == "not_initialized"
            assert status["pool_open"] is False

    async def test_ready(self):
        mock_pool = MagicMock()
        mock_pool._opened = True
        with patch.dict("sys.modules", {
            "langgraph.checkpoint.memory": MagicMock(MemorySaver=MagicMock),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            mod._pool = mock_pool
            mod._checkpointer = MagicMock()

            status = await mod.get_checkpointer_status()
            assert status["status"] == "ready"
            assert status["pool_open"] is True
            assert status["pool_min_size"] == 2
            assert status["pool_max_size"] == 10

    async def test_error_state(self):
        mock_pool = MagicMock()
        del mock_pool._opened  # Will cause AttributeError
        with patch.dict("sys.modules", {
            "langgraph.checkpoint.memory": MagicMock(MemorySaver=MagicMock),
        }):
            import importlib
            mod = importlib.import_module("packages.content_factory.orchestration.checkpointer")
            importlib.reload(mod)

            mod._pool = mock_pool
            mod._checkpointer = MagicMock()

            status = await mod.get_checkpointer_status()
            assert status["status"] == "error"
            assert "error" in status
