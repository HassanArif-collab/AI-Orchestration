"""Tests for packages/content_factory/orchestration/state.py

Covers:
  - DiscoveryState: all required fields exist in __annotations__
  - ProductionState: all required fields exist in __annotations__
  - Field types and Optional markers
  - TypedDict total behavior (all keys required by default)
"""

import pytest

# state.py is loaded via the conftest fixture (importlib, no langgraph)


class TestDiscoveryState:
    """Verify DiscoveryState TypedDict has all expected fields."""

    def test_all_required_fields_present(self, orch_state):
        expected = {
            "card_id", "seed_hint", "zep_context", "search_results",
            "generated_topics", "graded_topics", "pipeline_status", "error",
        }
        actual = set(orch_state.DiscoveryState.__annotations__.keys())
        assert actual == expected

    def test_field_count(self, orch_state):
        assert len(orch_state.DiscoveryState.__annotations__) == 8

    def test_card_id_type(self, orch_state):
        assert orch_state.DiscoveryState.__annotations__["card_id"] is str

    def test_seed_hint_is_optional(self, orch_state):
        import typing
        ann = orch_state.DiscoveryState.__annotations__["seed_hint"]
        # Should be Optional[str] i.e. Union[str, None]
        assert typing.get_origin(ann) is typing.Union

    def test_error_is_optional(self, orch_state):
        import typing
        ann = orch_state.DiscoveryState.__annotations__["error"]
        assert typing.get_origin(ann) is typing.Union

    def test_search_results_type(self, orch_state):
        assert orch_state.DiscoveryState.__annotations__["search_results"] is list

    def test_pipeline_status_type(self, orch_state):
        assert orch_state.DiscoveryState.__annotations__["pipeline_status"] is str

    def test_usable_as_typed_dict(self, orch_state):
        """TypedDict can be used to create a valid dict."""
        state: orch_state.DiscoveryState = {
            "card_id": "card-123",
            "seed_hint": "AI in Pakistan",
            "zep_context": "",
            "search_results": [],
            "generated_topics": [],
            "graded_topics": [],
            "pipeline_status": "discovering",
            "error": None,
        }
        assert state["card_id"] == "card-123"


class TestProductionState:
    """Verify ProductionState TypedDict has all expected fields."""

    def test_all_required_fields_present(self, orch_state):
        expected = {
            "card_id", "topic_brief", "research_dossier", "research_sources",
            "zep_learnings", "current_draft", "best_draft", "best_score",
            "evaluation_score", "evaluation_feedback", "iteration_count",
            "visual_plan", "human_feedback", "approved", "revision_count",
            "pipeline_status", "error",
        }
        actual = set(orch_state.ProductionState.__annotations__.keys())
        assert actual == expected

    def test_field_count(self, orch_state):
        assert len(orch_state.ProductionState.__annotations__) == 17

    def test_card_id_type(self, orch_state):
        assert orch_state.ProductionState.__annotations__["card_id"] is str

    def test_topic_brief_type(self, orch_state):
        assert orch_state.ProductionState.__annotations__["topic_brief"] is dict

    def test_research_dossier_type(self, orch_state):
        assert orch_state.ProductionState.__annotations__["research_dossier"] is str

    def test_best_score_type(self, orch_state):
        assert orch_state.ProductionState.__annotations__["best_score"] is int

    def test_iteration_count_type(self, orch_state):
        assert orch_state.ProductionState.__annotations__["iteration_count"] is int

    def test_approved_type(self, orch_state):
        assert orch_state.ProductionState.__annotations__["approved"] is bool

    def test_human_feedback_is_optional(self, orch_state):
        import typing
        ann = orch_state.ProductionState.__annotations__["human_feedback"]
        assert typing.get_origin(ann) is typing.Union

    def test_error_is_optional(self, orch_state):
        import typing
        ann = orch_state.ProductionState.__annotations__["error"]
        assert typing.get_origin(ann) is typing.Union

    def test_revision_count_type(self, orch_state):
        assert orch_state.ProductionState.__annotations__["revision_count"] is int

    def test_visual_plan_type(self, orch_state):
        assert orch_state.ProductionState.__annotations__["visual_plan"] is str

    def test_usable_as_typed_dict(self, orch_state):
        """TypedDict can be used to create a valid dict."""
        state: orch_state.ProductionState = {
            "card_id": "card-456",
            "topic_brief": {"title": "Test"},
            "research_dossier": "",
            "research_sources": [],
            "zep_learnings": "",
            "current_draft": "",
            "best_draft": "",
            "best_score": 0,
            "evaluation_score": 0,
            "evaluation_feedback": "",
            "iteration_count": 0,
            "visual_plan": "",
            "human_feedback": None,
            "approved": False,
            "revision_count": 0,
            "pipeline_status": "researching",
            "error": None,
        }
        assert state["card_id"] == "card-456"
        assert state["approved"] is False
