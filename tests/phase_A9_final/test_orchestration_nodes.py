"""Tests for orchestration/nodes.py — LangGraph Node Functions.

Tests 6 representative nodes out of 13 total:
  - gather_context_node (discovery, Zep integration)
  - search_web_node (discovery, Exa integration)
  - generate_topics_node (discovery, RouterClient + LLM)
  - draft_node (production, human_feedback logic)
  - capture_learning_node (production, best-draft swap + Zep learning)
  - human_review_node (production, risk tier + interrupt)
"""

import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

# langgraph must be mocked before importing nodes
for mod_name in [
    "langgraph", "langgraph.graph", "langgraph.types",
    "langgraph.prebuilt", "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Now import the module under test
from packages.content_factory.orchestration.nodes import (
    gather_context_node,
    search_web_node,
    generate_topics_node,
    draft_node,
    capture_learning_node,
    human_review_node,
)


# ═══════════════════════════════════════════════════════════════
# gather_context_node
# ═══════════════════════════════════════════════════════════════

class TestGatherContextNode:
    """Tests for gather_context_node — loads Zep audience context."""

    @pytest.mark.asyncio
    async def test_returns_zep_context_on_success(self):
        """When Zep returns context, it should be in state."""
        state = {"card_id": "card-1"}
        mock_zep = AsyncMock()
        mock_zep.read_audience_context.return_value = "audience data here"

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.memory.zep_store.ZepAudienceModelStore", return_value=mock_zep):
            result = await gather_context_node.__wrapped__(state)
            assert result["zep_context"] == "audience data here"
            assert result["pipeline_status"] == "discovering"

    @pytest.mark.asyncio
    async def test_empty_context_defaults_to_empty_string(self):
        """When Zep returns None/empty, context should be empty string."""
        state = {"card_id": "card-2"}
        mock_zep = AsyncMock()
        mock_zep.read_audience_context.return_value = None

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.memory.zep_store.ZepAudienceModelStore", return_value=mock_zep):
            result = await gather_context_node.__wrapped__(state)
            assert result["zep_context"] == ""

    @pytest.mark.asyncio
    async def test_exception_returns_empty_context(self):
        """When Zep throws, node should not crash — return empty context."""
        state = {"card_id": "card-3"}
        mock_zep = MagicMock()
        mock_zep.read_audience_context = AsyncMock(side_effect=RuntimeError("Zep down"))

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.memory.zep_store.ZepAudienceModelStore", return_value=mock_zep):
            result = await gather_context_node.__wrapped__(state)
            assert result["zep_context"] == ""
            assert result["pipeline_status"] == "discovering"


# ═══════════════════════════════════════════════════════════════
# search_web_node
# ═══════════════════════════════════════════════════════════════

class TestSearchWebNode:
    """Tests for search_web_node — queries Exa.ai for trending topics."""

    @pytest.mark.asyncio
    async def test_returns_search_results(self):
        """Should return results from Exa search."""
        state = {"card_id": "card-1", "seed_hint": "AI", "zep_context": ""}
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=[
            {"title": "AI in Pakistan", "snippet": "Pakistan leads in AI"}
        ])

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.integrations.exa.client.ExaResearchClient", return_value=mock_client), \
             patch("packages.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(EXA_API_KEY="key")
            result = await search_web_node.__wrapped__(state)
            assert "search_results" in result
            assert len(result["search_results"]) == 3  # 1 seed_hint + 2 default queries

    @pytest.mark.asyncio
    async def test_exception_returns_empty_results_and_error(self):
        """On exception, return empty list with error message."""
        state = {"card_id": "card-1"}

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.integrations.exa.client.ExaResearchClient", side_effect=RuntimeError("Exa down")):
            result = await search_web_node.__wrapped__(state)
            assert result["search_results"] == []
            assert "error" in result

    @pytest.mark.asyncio
    async def test_uses_seed_hint_in_queries(self):
        """When seed_hint is provided, it should be part of the query."""
        state = {"card_id": "card-1", "seed_hint": "cricket", "zep_context": ""}
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=[])

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.integrations.exa.client.ExaResearchClient", return_value=mock_client), \
             patch("packages.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(EXA_API_KEY="key")
            await search_web_node.__wrapped__(state)
            # Verify that search was called — the first query should include the seed_hint
            calls = mock_client.search.call_args_list
            assert len(calls) > 0
            first_call_query = calls[0][0][0]
            assert "cricket" in first_call_query


# ═══════════════════════════════════════════════════════════════
# generate_topics_node
# ═══════════════════════════════════════════════════════════════

class TestGenerateTopicsNode:
    """Tests for generate_topics_node — sends results to LLM for topic generation."""

    @pytest.mark.asyncio
    async def test_returns_parsed_topics(self):
        """Should return list of topics from LLM response."""
        state = {
            "card_id": "card-1",
            "search_results": [{"title": "Result1", "snippet": "text"}],
            "zep_context": "",
            "seed_hint": "",
        }
        llm_response = '[{"title":"Topic 1","description":"desc","gap_type":"Hidden Mechanism","mainstream_assumption":"wrong","reality":"right","urgency":"now"}]'

        mock_router_cm = AsyncMock()
        mock_router = AsyncMock()
        mock_router.complete_text = AsyncMock(return_value=llm_response)
        mock_router_cm.__aenter__ = AsyncMock(return_value=mock_router)
        mock_router_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.router.client.RouterClient", return_value=mock_router_cm), \
             patch("packages.core.json_utils.extract_json_array", return_value=llm_response):
            result = await generate_topics_node.__wrapped__(state)
            assert "generated_topics" in result
            assert len(result["generated_topics"]) == 1
            assert result["generated_topics"][0]["title"] == "Topic 1"

    @pytest.mark.asyncio
    async def test_exception_returns_empty_topics_and_error(self):
        """On failure, return empty list with error."""
        state = {
            "card_id": "card-1",
            "search_results": [],
            "zep_context": "",
            "seed_hint": "",
        }

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.router.client.RouterClient", side_effect=RuntimeError("Router down")):
            result = await generate_topics_node.__wrapped__(state)
            assert result["generated_topics"] == []
            assert "error" in result


# ═══════════════════════════════════════════════════════════════
# draft_node
# ═══════════════════════════════════════════════════════════════

class TestDraftNode:
    """Tests for draft_node — generates script draft with human feedback logic."""

    @pytest.mark.asyncio
    async def test_first_draft(self):
        """First draft (no human_feedback, iteration=0) should have standard state return."""
        state = {
            "card_id": "card-1",
            "topic_brief": {"title": "Test Topic"},
            "research_dossier": "research",
            "zep_learnings": "",
            "human_feedback": None,
            "evaluation_feedback": None,
            "iteration_count": 0,
            "revision_count": 0,
        }

        mock_router_cm = AsyncMock()
        mock_router = AsyncMock()
        mock_router.complete_text = AsyncMock(return_value="Here is the script draft with five words exactly.")
        mock_router_cm.__aenter__ = AsyncMock(return_value=mock_router)
        mock_router_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.router.client.RouterClient", return_value=mock_router_cm):
            result = await draft_node.__wrapped__(state)
            assert result["current_draft"] == "Here is the script draft with five words exactly."
            assert result["iteration_count"] == 0
            assert result["pipeline_status"] == "drafting"
            assert result["human_feedback"] is None

    @pytest.mark.asyncio
    async def test_human_feedback_resets_iteration(self):
        """When human_feedback is set, iteration should reset to 0 and revision_count increments."""
        state = {
            "card_id": "card-1",
            "topic_brief": {"title": "Test Topic"},
            "research_dossier": "research",
            "zep_learnings": "",
            "human_feedback": "Make it more engaging",
            "evaluation_feedback": "",
            "iteration_count": 5,
            "revision_count": 2,
        }

        mock_router_cm = AsyncMock()
        mock_router = AsyncMock()
        mock_router.complete_text = AsyncMock(return_value="Revised script.")
        mock_router_cm.__aenter__ = AsyncMock(return_value=mock_router)
        mock_router_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.router.client.RouterClient", return_value=mock_router_cm):
            result = await draft_node.__wrapped__(state)
            assert result["iteration_count"] == 0  # Reset for fresh mutation budget
            assert result["revision_count"] == 3   # Incremented
            assert result["human_feedback"] is None  # Cleared after use

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        """On failure, return error in state."""
        state = {
            "card_id": "card-1",
            "topic_brief": {"title": "Test"},
            "research_dossier": "",
            "zep_learnings": "",
            "human_feedback": None,
            "evaluation_feedback": None,
            "iteration_count": 0,
        }

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.router.client.RouterClient", side_effect=RuntimeError("fail")):
            result = await draft_node.__wrapped__(state)
            assert "error" in result


# ═══════════════════════════════════════════════════════════════
# capture_learning_node
# ═══════════════════════════════════════════════════════════════

class TestCaptureLearningNode:
    """Tests for capture_learning_node — best-draft swap and learning capture."""

    @pytest.mark.asyncio
    async def test_swaps_to_best_draft_when_better(self):
        """When best_score > current_score, should swap in best draft and update score."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 70,
            "best_score": 85,
            "best_draft": "BEST DRAFT",
            "current_draft": "LAST DRAFT",
            "topic_brief": {"title": "Test"},
            "evaluation_feedback": "good",
        }

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock):
            result = await capture_learning_node.__wrapped__(state)
            assert result["current_draft"] == "BEST DRAFT"
            assert result["evaluation_score"] == 85

    @pytest.mark.asyncio
    async def test_keeps_current_draft_when_best_not_better(self):
        """When current_score >= best_score, keep current draft."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 90,
            "best_score": 85,
            "best_draft": "BEST DRAFT",
            "current_draft": "LAST DRAFT",
            "topic_brief": {"title": "Test"},
            "evaluation_feedback": "good",
        }

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock):
            result = await capture_learning_node.__wrapped__(state)
            assert result["current_draft"] == "LAST DRAFT"

    @pytest.mark.asyncio
    async def test_captures_learning_when_score_above_85(self):
        """When final_score >= 85, should call Zep to write learning."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 85,
            "best_score": 85,
            "best_draft": "BEST",
            "current_draft": "BEST",
            "topic_brief": {"title": "Test"},
            "evaluation_feedback": "Excellent work",
        }
        mock_zep = AsyncMock()

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.memory.zep_store.ZepAudienceModelStore", return_value=mock_zep):
            await capture_learning_node.__wrapped__(state)
            mock_zep.write_learning.assert_called_once()
            call_arg = mock_zep.write_learning.call_args[0][0]
            assert "PROVEN SCRIPT PATTERN" in call_arg
            assert "85%" in call_arg

    @pytest.mark.asyncio
    async def test_no_learning_capture_below_85(self):
        """When final_score < 85, should NOT call Zep write_learning."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 50,
            "best_score": 50,
            "best_draft": "",
            "current_draft": "draft",
            "topic_brief": {"title": "Test"},
            "evaluation_feedback": "meh",
        }
        mock_zep = AsyncMock()

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.memory.zep_store.ZepAudienceModelStore", return_value=mock_zep):
            await capture_learning_node.__wrapped__(state)
            mock_zep.write_learning.assert_not_called()

    @pytest.mark.asyncio
    async def test_always_returns_dict_with_current_draft(self):
        """Even with empty best_draft, should return current_draft."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 0,
            "best_score": 0,
            "best_draft": "",
            "current_draft": "fallback draft",
            "topic_brief": {},
            "evaluation_feedback": "",
        }

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock):
            result = await capture_learning_node.__wrapped__(state)
            assert "current_draft" in result
            assert result["current_draft"] == "fallback draft"


# ═══════════════════════════════════════════════════════════════
# human_review_node
# ═══════════════════════════════════════════════════════════════

class TestHumanReviewNode:
    """Tests for human_review_node — risk tier classification and interrupt logic."""

    @pytest.mark.asyncio
    async def test_low_risk_tier(self):
        """Score >= RISK_TIER_LOW_SCORE → low risk."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 90,
            "current_draft": "draft",
            "visual_plan": "plan",
            "iteration_count": 5,
        }
        mock_settings = MagicMock()
        mock_settings.RISK_TIER_LOW_SCORE = 85
        mock_settings.RISK_TIER_HIGH_SCORE = 60
        mock_settings.RISK_TIER_LOW_SLA_HOURS = 24
        mock_settings.RISK_TIER_MEDIUM_SLA_HOURS = 8
        mock_settings.RISK_TIER_HIGH_SLA_HOURS = 4
        mock_settings.HUMAN_REVIEW_TIMEOUT_HOURS = 48

        mock_types = MagicMock()
        mock_types.interrupt = MagicMock(return_value={"approved": True, "feedback": ""})

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.orchestration.nodes.update_card_stage", new_callable=AsyncMock), \
             patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch.dict(sys.modules, {"langgraph.types": mock_types}):
            result = await human_review_node.__wrapped__(state)
            assert result["risk_tier"] == "low"
            assert result["approved"] is True

    @pytest.mark.asyncio
    async def test_medium_risk_tier(self):
        """Score between HIGH and LOW thresholds → medium risk."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 70,
            "current_draft": "draft",
            "visual_plan": "plan",
            "iteration_count": 3,
        }
        mock_settings = MagicMock()
        mock_settings.RISK_TIER_LOW_SCORE = 85
        mock_settings.RISK_TIER_HIGH_SCORE = 60
        mock_settings.RISK_TIER_LOW_SLA_HOURS = 24
        mock_settings.RISK_TIER_MEDIUM_SLA_HOURS = 8
        mock_settings.RISK_TIER_HIGH_SLA_HOURS = 4
        mock_settings.HUMAN_REVIEW_TIMEOUT_HOURS = 48

        mock_types = MagicMock()
        mock_types.interrupt = MagicMock(return_value={"approved": False, "feedback": "Needs work"})

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.orchestration.nodes.update_card_stage", new_callable=AsyncMock), \
             patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch.dict(sys.modules, {"langgraph.types": mock_types}):
            result = await human_review_node.__wrapped__(state)
            assert result["risk_tier"] == "medium"
            assert result["approved"] is False
            assert result["human_feedback"] == "Needs work"

    @pytest.mark.asyncio
    async def test_high_risk_tier(self):
        """Score below RISK_TIER_HIGH_SCORE → high risk."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 40,
            "current_draft": "draft",
            "visual_plan": "plan",
            "iteration_count": 10,
        }
        mock_settings = MagicMock()
        mock_settings.RISK_TIER_LOW_SCORE = 85
        mock_settings.RISK_TIER_HIGH_SCORE = 60
        mock_settings.RISK_TIER_LOW_SLA_HOURS = 24
        mock_settings.RISK_TIER_MEDIUM_SLA_HOURS = 8
        mock_settings.RISK_TIER_HIGH_SLA_HOURS = 4
        mock_settings.HUMAN_REVIEW_TIMEOUT_HOURS = 48

        mock_types = MagicMock()
        mock_types.interrupt = MagicMock(return_value={"approved": True, "feedback": ""})

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.orchestration.nodes.update_card_stage", new_callable=AsyncMock), \
             patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch.dict(sys.modules, {"langgraph.types": mock_types}):
            result = await human_review_node.__wrapped__(state)
            assert result["risk_tier"] == "high"

    @pytest.mark.asyncio
    async def test_handles_pydantic_decision_object(self):
        """Should handle decision with hasattr 'approved' (Pydantic model)."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 85,
            "current_draft": "draft",
            "visual_plan": "plan",
            "iteration_count": 0,
        }
        mock_settings = MagicMock()
        mock_settings.RISK_TIER_LOW_SCORE = 85
        mock_settings.RISK_TIER_HIGH_SCORE = 60
        mock_settings.RISK_TIER_LOW_SLA_HOURS = 24
        mock_settings.RISK_TIER_MEDIUM_SLA_HOURS = 8
        mock_settings.RISK_TIER_HIGH_SLA_HOURS = 4
        mock_settings.HUMAN_REVIEW_TIMEOUT_HOURS = 48

        mock_decision = MagicMock()
        mock_decision.approved = True
        mock_decision.feedback = "Looks good"

        mock_types = MagicMock()
        mock_types.interrupt = MagicMock(return_value=mock_decision)

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.orchestration.nodes.update_card_stage", new_callable=AsyncMock), \
             patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch.dict(sys.modules, {"langgraph.types": mock_types}):
            result = await human_review_node.__wrapped__(state)
            assert result["approved"] is True
            assert result["human_feedback"] == "Looks good"

    @pytest.mark.asyncio
    async def test_includes_sla_deadline(self):
        """Result should include sla_deadline and review_requested_at."""
        state = {
            "card_id": "card-1",
            "evaluation_score": 85,
            "current_draft": "draft",
            "visual_plan": "plan",
            "iteration_count": 0,
        }
        mock_settings = MagicMock()
        mock_settings.RISK_TIER_LOW_SCORE = 85
        mock_settings.RISK_TIER_HIGH_SCORE = 60
        mock_settings.RISK_TIER_LOW_SLA_HOURS = 24
        mock_settings.RISK_TIER_MEDIUM_SLA_HOURS = 8
        mock_settings.RISK_TIER_HIGH_SLA_HOURS = 4
        mock_settings.HUMAN_REVIEW_TIMEOUT_HOURS = 48

        mock_types = MagicMock()
        mock_types.interrupt = MagicMock(return_value={"approved": True, "feedback": ""})

        with patch("packages.content_factory.orchestration.nodes.report_thought", new_callable=AsyncMock), \
             patch("packages.content_factory.orchestration.nodes.update_card_stage", new_callable=AsyncMock), \
             patch("packages.core.config.get_settings", return_value=mock_settings), \
             patch.dict(sys.modules, {"langgraph.types": mock_types}):
            result = await human_review_node.__wrapped__(state)
            assert "sla_deadline" in result
            assert "review_requested_at" in result
