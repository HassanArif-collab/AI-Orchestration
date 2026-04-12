"""Tests for orchestration/__init__.py — Graph factory functions."""

import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Mock langgraph before import
for mod_name in [
    "langgraph", "langgraph.graph", "langgraph.types",
    "langgraph.prebuilt", "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


class TestGetDiscoveryGraph:
    """Tests for get_discovery_graph() — returns compiled discovery graph."""

    @pytest.mark.asyncio
    async def test_calls_get_checkpointer_and_build_and_compile(self):
        """Should get checkpointer, build graph, and compile with it."""
        mock_checkpointer = MagicMock()
        mock_workflow = MagicMock()
        mock_compiled = MagicMock()

        with patch("packages.content_factory.orchestration.get_checkpointer", new_callable=AsyncMock, return_value=mock_checkpointer) as mock_gc, \
             patch("packages.content_factory.orchestration.build_discovery_graph", return_value=mock_workflow) as mock_bg:
            mock_workflow.compile.return_value = mock_compiled
            from packages.content_factory.orchestration import get_discovery_graph
            result = await get_discovery_graph()

            mock_gc.assert_called_once()
            mock_bg.assert_called_once()
            mock_workflow.compile.assert_called_once_with(checkpointer=mock_checkpointer)
            assert result is mock_compiled


class TestGetProductionGraph:
    """Tests for get_production_graph() — returns compiled production graph with interrupt_before."""

    @pytest.mark.asyncio
    async def test_compiles_with_interrupt_before(self):
        """Should compile with interrupt_before=['human_review']."""
        mock_checkpointer = MagicMock()
        mock_workflow = MagicMock()
        mock_compiled = MagicMock()

        with patch("packages.content_factory.orchestration.get_checkpointer", new_callable=AsyncMock, return_value=mock_checkpointer) as mock_gc, \
             patch("packages.content_factory.orchestration.build_production_graph", return_value=mock_workflow) as mock_bg:
            mock_workflow.compile.return_value = mock_compiled
            from packages.content_factory.orchestration import get_production_graph
            result = await get_production_graph()

            mock_gc.assert_called_once()
            mock_bg.assert_called_once()
            mock_workflow.compile.assert_called_once_with(
                checkpointer=mock_checkpointer,
                interrupt_before=["human_review"],
            )
            assert result is mock_compiled


class TestGetDiscoveryGraphMemory:
    """Tests for get_discovery_graph_memory() — testing graph without Supabase."""

    def test_uses_memory_saver(self):
        """Should get MemorySaver and compile with it."""
        mock_saver = MagicMock()
        mock_workflow = MagicMock()
        mock_compiled = MagicMock()

        with patch("packages.content_factory.orchestration.get_memory_saver", return_value=mock_saver), \
             patch("packages.content_factory.orchestration.build_discovery_graph", return_value=mock_workflow):
            mock_workflow.compile.return_value = mock_compiled
            from packages.content_factory.orchestration import get_discovery_graph_memory
            result = get_discovery_graph_memory()

            mock_workflow.compile.assert_called_once_with(checkpointer=mock_saver)
            assert result is mock_compiled


class TestGetProductionGraphMemory:
    """Tests for get_production_graph_memory() — testing graph without Supabase."""

    def test_uses_memory_saver_with_interrupt(self):
        """Should compile with MemorySaver and interrupt_before."""
        mock_saver = MagicMock()
        mock_workflow = MagicMock()
        mock_compiled = MagicMock()

        with patch("packages.content_factory.orchestration.get_memory_saver", return_value=mock_saver), \
             patch("packages.content_factory.orchestration.build_production_graph", return_value=mock_workflow):
            mock_workflow.compile.return_value = mock_compiled
            from packages.content_factory.orchestration import get_production_graph_memory
            result = get_production_graph_memory()

            mock_workflow.compile.assert_called_once_with(
                checkpointer=mock_saver,
                interrupt_before=["human_review"],
            )
            assert result is mock_compiled


class TestModuleExports:
    """Verify __all__ exports are accessible."""

    def test_all_exports_exist(self):
        """All items listed in __all__ should be importable from the package."""
        from packages.content_factory.orchestration import (
            DiscoveryState,
            ProductionState,
            build_discovery_graph,
            build_production_graph,
            get_discovery_graph,
            get_production_graph,
            get_discovery_graph_memory,
            get_production_graph_memory,
            get_checkpointer,
            close_checkpointer,
            get_memory_saver,
        )
        # All imports succeeded
        assert DiscoveryState is not None
        assert ProductionState is not None
