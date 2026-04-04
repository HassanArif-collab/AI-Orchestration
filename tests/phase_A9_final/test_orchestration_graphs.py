"""Tests for packages.content_factory.orchestration.graphs.

Tests the pure decision functions (_check_error, should_continue, after_review)
and graph assembly (with mocked langgraph).

NOTE: The pure functions are imported directly and tested without mocking.
Graph assembly tests reload the module with mocked langgraph dependencies.
"""

import sys
import importlib
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════
# Pure function tests — import BEFORE mocking langgraph
# ══════════════════════════════════════════════════════════════

# The module may already be imported (langgraph is installed).
# We just need the pure functions.
from packages.content_factory.orchestration.graphs import (
    _check_error,
    should_continue,
    after_review,
)


class TestCheckError:
    """Test _check_error routing function."""

    def test_no_error_returns_continue(self):
        assert _check_error({"pipeline_status": "researching"}) == "continue"
        assert _check_error({}) == "continue"

    def test_error_returns_error(self):
        assert _check_error({"error": "Something went wrong"}) == "error"

    def test_error_false_returns_continue(self):
        """If error is explicitly False or None, should continue."""
        assert _check_error({"error": None}) == "continue"


class TestShouldContinue:
    """Test the Karpathy loop decision function."""

    def test_error_routes_to_error(self):
        assert should_continue({"error": "LLM timeout"}) == "error"

    def test_high_score_exits_loop(self):
        assert should_continue({"evaluation_score": 90, "iteration_count": 1}) == "done"
        assert should_continue({"evaluation_score": 85, "iteration_count": 1}) == "done"

    def test_max_iterations_exits_loop(self):
        assert should_continue({"evaluation_score": 40, "iteration_count": 20}) == "done"
        assert should_continue({"evaluation_score": 40, "iteration_count": 25}) == "done"

    def test_mutate_on_low_score_and_low_iterations(self):
        assert should_continue({"evaluation_score": 50, "iteration_count": 1}) == "mutate"
        assert should_continue({"evaluation_score": 84, "iteration_count": 19}) == "mutate"

    def test_default_state_returns_mutate(self):
        """Empty state defaults to score=0, iterations=0 → mutate."""
        assert should_continue({}) == "mutate"

    def test_priority_error_over_score(self):
        """Even with high score, error should route to error."""
        assert should_continue({"error": "boom", "evaluation_score": 95}) == "error"

    def test_priority_iterations_over_score(self):
        """At 20 iterations, should exit even with low score."""
        assert should_continue({"evaluation_score": 0, "iteration_count": 20}) == "done"


class TestAfterReview:
    """Test the human review routing function."""

    def test_approved_routes_to_approve(self):
        assert after_review({"approved": True}) == "approve"

    def test_rejected_routes_to_revise(self):
        assert after_review({"approved": False}) == "revise"
        assert after_review({"approved": None}) == "revise"
        assert after_review({}) == "revise"

    def test_error_routes_to_error(self):
        assert after_review({"error": "Review failed"}) == "error"

    def test_approved_even_with_error(self):
        """Error takes priority."""
        assert after_review({"error": "err", "approved": True}) == "error"


# ══════════════════════════════════════════════════════════════
# Graph assembly tests — reload module with mocked langgraph
# ══════════════════════════════════════════════════════════════

def _make_mock_package(name, attrs):
    """Create a mock module that acts as a package (has __path__)."""
    mod = ModuleType(name)
    mod.__path__ = []  # Makes it a package
    mod.__package__ = name
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


def _reload_graphs_with_mocks():
    """Force-reload the graphs module with langgraph mocked."""
    mock_graph = MagicMock(name="WorkflowInstance")
    mock_sg = MagicMock(name="StateGraph", return_value=mock_graph)
    mock_end = MagicMock(name="END")
    mock_start = MagicMock(name="START")
    mock_retry_policy = MagicMock(name="RetryPolicy")

    # Create proper package-like mock modules for langgraph
    lg_mod = _make_mock_package("langgraph", {})
    lg_graph_mod = _make_mock_package("langgraph.graph", {
        "StateGraph": mock_sg,
        "END": mock_end,
        "START": mock_start,
    })
    lg_types_mod = _make_mock_package("langgraph.types", {
        "RetryPolicy": mock_retry_policy,
    })

    # Save originals
    saved = {}
    mods_to_save = [
        "packages.content_factory.orchestration.graphs",
        "packages.content_factory.orchestration.nodes",
        "packages.content_factory.orchestration.state",
        "langgraph",
        "langgraph.graph",
        "langgraph.types",
    ]
    for m in mods_to_save:
        if m in sys.modules:
            saved[m] = sys.modules.pop(m)

    # Inject mocks
    sys.modules["langgraph"] = lg_mod
    sys.modules["langgraph.graph"] = lg_graph_mod
    sys.modules["langgraph.types"] = lg_types_mod
    sys.modules["packages.content_factory.orchestration.nodes"] = MagicMock(name="nodes_module")
    sys.modules["packages.content_factory.orchestration.state"] = MagicMock(name="state_module")

    try:
        mod = importlib.import_module("packages.content_factory.orchestration.graphs")
    finally:
        # Restore originals
        for m in mods_to_save:
            if m in saved:
                sys.modules[m] = saved[m]
            elif m in sys.modules:
                del sys.modules[m]

    return mod, mock_graph, mock_sg, mock_end, mock_start, mock_retry_policy


class TestBuildDiscoveryGraph:
    """Test that build_discovery_graph wires nodes and edges correctly."""

    def test_registers_all_discovery_nodes(self):
        mod, mock_graph, mock_sg, mock_end, mock_start, mock_rp = _reload_graphs_with_mocks()
        mod.build_discovery_graph()

        add_node_calls = [c[0][0] for c in mock_graph.add_node.call_args_list]
        assert "gather_context" in add_node_calls
        assert "search_web" in add_node_calls
        assert "generate_topics" in add_node_calls
        assert "grade_viability" in add_node_calls
        assert "save_topics" in add_node_calls
        assert "error_handler" in add_node_calls

    def test_discovery_entry_point(self):
        mod, mock_graph, mock_sg, mock_end, mock_start, mock_rp = _reload_graphs_with_mocks()
        mod.build_discovery_graph()

        mock_graph.set_entry_point.assert_called_once_with("gather_context")

    def test_discovery_has_conditional_edges(self):
        mod, mock_graph, mock_sg, mock_end, mock_start, mock_rp = _reload_graphs_with_mocks()
        mod.build_discovery_graph()

        cond_edge_calls = mock_graph.add_conditional_edges.call_args_list
        assert len(cond_edge_calls) == 4
        assert cond_edge_calls[0][0][0] == "gather_context"

    def test_discovery_terminal_edges(self):
        mod, mock_graph, mock_sg, mock_end, mock_start, mock_rp = _reload_graphs_with_mocks()
        mod.build_discovery_graph()

        add_edge_calls = [c[0] for c in mock_graph.add_edge.call_args_list]
        assert ("save_topics", mock_end) in add_edge_calls
        assert ("error_handler", mock_end) in add_edge_calls


class TestBuildProductionGraph:
    """Test that build_production_graph wires nodes and edges correctly."""

    def test_registers_all_production_nodes(self):
        mod, mock_graph, mock_sg, mock_end, mock_start, mock_rp = _reload_graphs_with_mocks()
        mod.build_production_graph()

        add_node_calls = [c[0][0] for c in mock_graph.add_node.call_args_list]
        expected_nodes = [
            "load_learnings", "research", "draft", "score", "mutate",
            "capture_learning", "visuals", "human_review", "publish", "error_handler"
        ]
        for name in expected_nodes:
            assert name in add_node_calls

    def test_production_entry_point(self):
        mod, mock_graph, mock_sg, mock_end, mock_start, mock_rp = _reload_graphs_with_mocks()
        mod.build_production_graph()

        mock_graph.set_entry_point.assert_called_once_with("load_learnings")

    def test_production_linear_flow(self):
        mod, mock_graph, mock_sg, mock_end, mock_start, mock_rp = _reload_graphs_with_mocks()
        mod.build_production_graph()

        add_edge_calls = [c[0] for c in mock_graph.add_edge.call_args_list]
        assert ("load_learnings", "research") in add_edge_calls
        assert ("research", "draft") in add_edge_calls
        assert ("draft", "score") in add_edge_calls
        assert ("mutate", "score") in add_edge_calls
        assert ("capture_learning", "visuals") in add_edge_calls
        assert ("visuals", "human_review") in add_edge_calls
        assert ("publish", mock_end) in add_edge_calls
        assert ("error_handler", mock_end) in add_edge_calls

    def test_production_conditional_edges(self):
        mod, mock_graph, mock_sg, mock_end, mock_start, mock_rp = _reload_graphs_with_mocks()
        mod.build_production_graph()

        cond_edge_calls = mock_graph.add_conditional_edges.call_args_list
        assert len(cond_edge_calls) == 2
        assert cond_edge_calls[0][0][0] == "score"
        assert cond_edge_calls[1][0][0] == "human_review"

    def test_production_retry_policies(self):
        """Verify that RetryPolicy is used for nodes making API calls."""
        mod, mock_graph, mock_sg, mock_end, mock_start, mock_rp = _reload_graphs_with_mocks()
        mod.build_production_graph()

        # RetryPolicy should be instantiated at least twice (LLM_RETRY + PUBLISH_RETRY)
        assert mock_rp.call_count >= 2


class TestRetryPolicies:
    """Test that LLM_RETRY and PUBLISH_RETRY are defined."""

    def test_retry_constants_exist(self):
        from packages.content_factory.orchestration.graphs import LLM_RETRY, PUBLISH_RETRY
        assert LLM_RETRY is not None
        assert PUBLISH_RETRY is not None
