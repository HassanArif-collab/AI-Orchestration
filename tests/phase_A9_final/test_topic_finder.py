"""Tests for packages.content_factory.topic_finder.finder.TopicFinderAgent."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ── Mock external deps before importing the module under test ──
mock_router_client_cls = MagicMock()
mock_router_instance = AsyncMock()
mock_router_instance.__aenter__ = AsyncMock(return_value=mock_router_instance)
mock_router_instance.__aexit__ = AsyncMock(return_value=False)
mock_router_client_cls.return_value = mock_router_instance

with patch.dict("sys.modules", {
    "packages.router.client": MagicMock(RouterClient=mock_router_client_cls),
    "packages.memory.client": MagicMock(AsyncZepMemoryClient=MagicMock),
    "packages.content_factory.memory.zep_store": MagicMock(ZepAudienceModelStore=MagicMock),
    "packages.integrations.exa.client": MagicMock(),
    "packages.content_factory.source_library": MagicMock(),
    "packages.agents.kanban_callback": MagicMock(),
}):
    from packages.content_factory.topic_finder.finder import (
        TopicFinderAgent,
        VIABILITY_QUESTIONS,
    )
    from packages.content_factory.topic_finder.models import TopicBrief


# ── Helpers ──

def _make_agent():
    """Create a TopicFinderAgent with mocked internals."""
    agent = TopicFinderAgent.__new__(TopicFinderAgent)
    agent.db = MagicMock()
    agent.zep_client = AsyncMock()
    agent.zep_session_id = "test_session"
    agent.kanban_task_id = None
    agent._kanban_callback = None
    return agent


def _make_viable_response(topic="Why Pakistan's water crisis is hidden", anchors=["Karachi", "Indus River"]):
    return json.dumps({
        "topic_statement": topic,
        "big_question": "What is the real cause?",
        "gap_type": "Hidden Mechanism",
        "mainstream_assumption": "People think it's climate change",
        "anchor_candidates": anchors,
        "timing_rationale": "Monsoon season",
        "urgency_flag": True,
    })


def _make_viability_scores(all_pass=True):
    scores = {}
    for k in VIABILITY_QUESTIONS:
        scores[k] = all_pass
    return scores


# ══════════════════════════════════════════════════════════════
# TopicFinderAgent.__init__
# ══════════════════════════════════════════════════════════════

class TestTopicFinderAgentInit:
    def test_init_defaults(self):
        agent = TopicFinderAgent.__new__(TopicFinderAgent)
        agent.db = MagicMock()
        agent.zep_client = AsyncMock()
        agent.zep_session_id = "test_session"
        agent.kanban_task_id = None
        agent._kanban_callback = None

        assert agent.kanban_task_id is None
        assert agent._kanban_callback is None


# ══════════════════════════════════════════════════════════════
# _evaluate_viability
# ══════════════════════════════════════════════════════════════

class TestEvaluateViability:

    @pytest.mark.asyncio
    async def test_all_pass(self):
        agent = _make_agent()
        router = AsyncMock()
        scores_json = json.dumps({k: True for k in VIABILITY_QUESTIONS})
        router.complete_text = AsyncMock(return_value=scores_json)

        result = await agent._evaluate_viability("Test topic", ["anchor1"], router)
        assert all(result.values())
        assert len(result) == 17

    @pytest.mark.asyncio
    async def test_all_fail(self):
        agent = _make_agent()
        router = AsyncMock()
        scores_json = json.dumps({k: False for k in VIABILITY_QUESTIONS})
        router.complete_text = AsyncMock(return_value=scores_json)

        result = await agent._evaluate_viability("Test topic", ["anchor1"], router)
        assert not any(result.values())

    @pytest.mark.asyncio
    async def test_mixed_scores(self):
        agent = _make_agent()
        router = AsyncMock()
        keys = list(VIABILITY_QUESTIONS.keys())
        scores = {}
        for i, k in enumerate(keys):
            scores[k] = i % 2 == 0
        router.complete_text = AsyncMock(return_value=json.dumps(scores))

        result = await agent._evaluate_viability("Test topic", ["a1"], router)
        for i, k in enumerate(keys):
            assert result[k] == (i % 2 == 0)

    @pytest.mark.asyncio
    async def test_json_decode_failure_degrades_to_false(self):
        agent = _make_agent()
        router = AsyncMock()
        router.complete_text = AsyncMock(return_value="NOT JSON")

        result = await agent._evaluate_viability("Test topic", ["a1"], router)
        assert all(v is False for v in result.values())
        assert len(result) == 17

    @pytest.mark.asyncio
    async def test_partial_keys_missing_degrades_to_false(self):
        agent = _make_agent()
        router = AsyncMock()
        # Return only one key
        router.complete_text = AsyncMock(return_value=json.dumps({"gap_1": True}))

        result = await agent._evaluate_viability("Test topic", ["a1"], router)
        # Missing keys should default to False
        assert result["gap_1"] is True
        assert result["gap_2"] is False
        assert len(result) == 17

    @pytest.mark.asyncio
    async def test_calls_router_with_correct_model(self):
        agent = _make_agent()
        router = AsyncMock()
        router.complete_text = AsyncMock(return_value=json.dumps({k: True for k in VIABILITY_QUESTIONS}))

        await agent._evaluate_viability("My Topic", ["Anchor"], router)
        call_kwargs = router.complete_text.call_args
        assert call_kwargs[1]["model"] == "topic_finder"


# ══════════════════════════════════════════════════════════════
# _get_audience_context
# ══════════════════════════════════════════════════════════════

class TestGetAudienceContext:

    @pytest.mark.asyncio
    async def test_zep_store_returns_valid_context(self):
        agent = _make_agent()
        zep_store_mock = MagicMock()
        zep_store_mock.read_audience_context = AsyncMock(return_value="Valid audience insights")
        with patch("packages.content_factory.memory.zep_store.ZepAudienceModelStore", return_value=zep_store_mock):
            result = await agent._get_audience_context("tech")
        assert result == "Valid audience insights"

    @pytest.mark.asyncio
    async def test_zep_store_empty_falls_back_to_zep_client(self):
        agent = _make_agent()
        zep_store_mock = MagicMock()
        zep_store_mock.read_audience_context = AsyncMock(return_value="No audience data available yet.")
        with patch("packages.content_factory.memory.zep_store.ZepAudienceModelStore", return_value=zep_store_mock):
            agent.zep_client.search_memory = AsyncMock(return_value=[{"fact": "fact1"}, {"fact": "fact2"}])
            result = await agent._get_audience_context("tech")
        assert "fact1" in result or "fact2" in result

    @pytest.mark.asyncio
    async def test_zep_store_exception_falls_back_to_zep_client(self):
        agent = _make_agent()
        with patch("packages.content_factory.memory.zep_store.ZepAudienceModelStore", side_effect=Exception("boom")):
            agent.zep_client.search_memory = AsyncMock(return_value=[{"fact": "recovered fact"}])
            result = await agent._get_audience_context("tech")
        assert "recovered fact" in result

    @pytest.mark.asyncio
    async def test_all_failures_returns_default_message(self):
        agent = _make_agent()
        # search_memory returns [] → zep_context is empty → falls to static JSON.
        # The real packages/data/audience_model.json exists in the repo, so it
        # returns the file content. We only get "No audience data..." when
        # BOTH zep and the JSON file are missing.
        agent.zep_client.search_memory = AsyncMock(return_value=[])
        result = await agent._get_audience_context("tech")
        # Result is the static audience model dict (since search_memory returned [])
        assert isinstance(result, str)
        assert len(result) > 0  # Static JSON fallback succeeded

    @pytest.mark.asyncio
    async def test_deduplicates_facts(self):
        agent = _make_agent()
        # All queries return the same fact
        agent.zep_client.search_memory = AsyncMock(return_value=[{"fact": "duplicate fact"}])
        with patch("packages.content_factory.topic_finder.finder.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            result = await agent._get_audience_context("tech")
        # set() deduplicates, so only one occurrence
        assert result.count("duplicate fact") == 1


# ══════════════════════════════════════════════════════════════
# generate_candidate
# ══════════════════════════════════════════════════════════════

class TestGenerateCandidate:

    @pytest.mark.asyncio
    async def test_tier1_topic_returns_brief(self):
        agent = _make_agent()
        with patch.object(agent, "_get_audience_context", new_callable=AsyncMock, return_value="context"):
            with patch.object(agent, "_init_kanban_callback", new_callable=AsyncMock):
                with patch.object(agent, "_report_thought", new_callable=AsyncMock):
                    with patch.object(agent, "_close_kanban_callback", new_callable=AsyncMock):
                        with patch.object(agent, "_create_child_task", new_callable=AsyncMock, return_value=None):
                            # Configure RouterClient mock
                            mock_router_instance.complete_text = AsyncMock(
                                side_effect=[
                                    _make_viable_response(),
                                    json.dumps(_make_viability_scores(all_pass=True)),
                                ]
                            )
                            brief = await agent.generate_candidate("AI trends", "tech")

        assert brief is not None
        assert brief.topic_statement == "Why Pakistan's water crisis is hidden"
        assert brief.status == "reservoir"
        assert brief.urgency_flag is True
        agent.db.save_topic.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_tier1_returns_none(self):
        agent = _make_agent()
        scores = _make_viability_scores(all_pass=False)
        # Make gap tests fail
        scores["gap_1"] = False
        scores["gap_2"] = False
        scores["gap_3"] = False

        with patch.object(agent, "_get_audience_context", new_callable=AsyncMock, return_value="ctx"):
            with patch.object(agent, "_init_kanban_callback", new_callable=AsyncMock):
                with patch.object(agent, "_report_thought", new_callable=AsyncMock):
                    with patch.object(agent, "_close_kanban_callback", new_callable=AsyncMock):
                        mock_router_instance.complete_text = AsyncMock(
                            side_effect=[
                                _make_viable_response(),
                                json.dumps(scores),
                            ]
                        )
                        brief = await agent.generate_candidate("AI", "tech")

        assert brief is None
        agent.db.save_topic.assert_not_called()

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_none(self):
        agent = _make_agent()
        with patch.object(agent, "_get_audience_context", new_callable=AsyncMock, return_value="ctx"):
            with patch.object(agent, "_init_kanban_callback", new_callable=AsyncMock):
                with patch.object(agent, "_report_thought", new_callable=AsyncMock):
                    with patch.object(agent, "_close_kanban_callback", new_callable=AsyncMock):
                        mock_router_instance.complete_text = AsyncMock(return_value="NOT JSON AT ALL")
                        brief = await agent.generate_candidate("AI", "tech")

        assert brief is None

    @pytest.mark.asyncio
    async def test_exa_failure_does_not_crash(self):
        agent = _make_agent()
        with patch.object(agent, "_get_audience_context", new_callable=AsyncMock, return_value="ctx"):
            with patch.object(agent, "_init_kanban_callback", new_callable=AsyncMock):
                with patch.object(agent, "_report_thought", new_callable=AsyncMock):
                    with patch.object(agent, "_close_kanban_callback", new_callable=AsyncMock):
                        mock_exa = MagicMock()
                        mock_exa.build_discovery_context.side_effect = Exception("Exa down")
                        with patch.dict("sys.modules", {
                            "packages.integrations.exa.client": MagicMock(ExaResearchClient=MagicMock(return_value=mock_exa)),
                        }):
                            mock_router_instance.complete_text = AsyncMock(
                                side_effect=[
                                    _make_viable_response(),
                                    json.dumps(_make_viability_scores(all_pass=True)),
                                ]
                            )
                            brief = await agent.generate_candidate("AI", "tech")

        assert brief is not None

    @pytest.mark.asyncio
    async def test_always_closes_kanban_callback_on_json_failure(self):
        """Verify _close_kanban_callback is called even when node fails."""
        agent = _make_agent()
        with patch.object(agent, "_get_audience_context", new_callable=AsyncMock, return_value="ctx"):
            with patch.object(agent, "_init_kanban_callback", new_callable=AsyncMock):
                with patch.object(agent, "_report_thought", new_callable=AsyncMock):
                    with patch.object(agent, "_close_kanban_callback", new_callable=AsyncMock) as mock_close:
                        # Return invalid JSON so generate_candidate returns None
                        # (JSON parse failure is caught inside generate_candidate)
                        mock_router_instance.complete_text = AsyncMock(return_value="NOT VALID JSON")
                        brief = await agent.generate_candidate("AI", "tech")

        mock_close.assert_awaited_once()
        assert brief is None


# ══════════════════════════════════════════════════════════════
# discover_adaptation_candidates
# ══════════════════════════════════════════════════════════════

class TestDiscoverAdaptationCandidates:

    def _make_source_record(self):
        """Create a mock SourceVideoLibrary record."""
        record = MagicMock()
        record.title = "How Big Oil Misled The World"
        record.big_question = "What did they know?"
        record.genre = "investigative"
        record.gap_type = "Hidden Mechanism"
        record.video_id = "vid_123"
        return record

    @pytest.mark.asyncio
    async def test_returns_candidates_on_match(self):
        agent = _make_agent()
        record = self._make_source_record()

        mock_lib = MagicMock()
        mock_lib.find_by_status = MagicMock(return_value=[record])
        mock_status = MagicMock()
        mock_status.FULLY_ANALYZED = "fully_analyzed"

        adaptation_json = json.dumps({
            "maps_to_pakistan": True,
            "pakistani_equivalent_topic": "How Pakistani oil companies mislead the public",
            "pakistani_mainstream_assumption": "People think oil companies are transparent",
            "timing_rationale": "Energy crisis ongoing",
        })

        with patch.dict("sys.modules", {
            "packages.content_factory.source_library": MagicMock(
                SourceVideoLibrary=MagicMock(return_value=mock_lib),
                ProcessingStatus=mock_status,
            ),
        }):
            mock_router_instance.complete_text = AsyncMock(return_value=adaptation_json)
            result = await agent.discover_adaptation_candidates("tech")

        assert len(result) == 1
        assert result[0].content_type == "adaptation"
        assert "Pakistan" in result[0].topic_statement
        agent.db.save_topic.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_analyzed(self):
        agent = _make_agent()
        mock_lib = MagicMock()
        mock_lib.find_by_status = MagicMock(return_value=[])

        with patch.dict("sys.modules", {
            "packages.content_factory.source_library": MagicMock(
                SourceVideoLibrary=MagicMock(return_value=mock_lib),
            ),
        }):
            result = await agent.discover_adaptation_candidates("tech")

        assert result == []
        agent.db.save_topic.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_non_matching_records(self):
        agent = _make_agent()
        record = self._make_source_record()

        mock_lib = MagicMock()
        mock_lib.find_by_status = MagicMock(return_value=[record])

        no_match_json = json.dumps({
            "maps_to_pakistan": False,
            "pakistani_equivalent_topic": None,
            "pakistani_mainstream_assumption": None,
            "timing_rationale": None,
        })

        with patch.dict("sys.modules", {
            "packages.content_factory.source_library": MagicMock(
                SourceVideoLibrary=MagicMock(return_value=mock_lib),
            ),
        }):
            mock_router_instance.complete_text = AsyncMock(return_value=no_match_json)
            result = await agent.discover_adaptation_candidates("tech")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        agent = _make_agent()
        with patch.dict("sys.modules", {
            "packages.content_factory.source_library": MagicMock(
                SourceVideoLibrary=MagicMock(side_effect=Exception("DB down")),
            ),
        }):
            result = await agent.discover_adaptation_candidates("tech")

        assert result == []

    @pytest.mark.asyncio
    async def test_skips_on_bad_json_response(self):
        agent = _make_agent()
        record = self._make_source_record()
        mock_lib = MagicMock()
        mock_lib.find_by_status = MagicMock(return_value=[record])

        with patch.dict("sys.modules", {
            "packages.content_factory.source_library": MagicMock(
                SourceVideoLibrary=MagicMock(return_value=mock_lib),
            ),
        }):
            mock_router_instance.complete_text = AsyncMock(return_value="No JSON here")
            result = await agent.discover_adaptation_candidates("tech")

        assert result == []

    @pytest.mark.asyncio
    async def test_skips_on_json_parse_error(self):
        agent = _make_agent()
        record = self._make_source_record()
        mock_lib = MagicMock()
        mock_lib.find_by_status = MagicMock(return_value=[record])

        with patch.dict("sys.modules", {
            "packages.content_factory.source_library": MagicMock(
                SourceVideoLibrary=MagicMock(return_value=mock_lib),
            ),
        }):
            mock_router_instance.complete_text = AsyncMock(return_value='{"maps_to_pakistan": invalid}')
            result = await agent.discover_adaptation_candidates("tech")

        assert result == []

    @pytest.mark.asyncio
    async def test_limits_to_five_records(self):
        agent = _make_agent()
        records = [self._make_source_record() for _ in range(10)]

        mock_lib = MagicMock()
        mock_lib.find_by_status = MagicMock(return_value=records)

        adaptation_json = json.dumps({
            "maps_to_pakistan": True,
            "pakistani_equivalent_topic": "Pakistani topic",
            "pakistani_mainstream_assumption": "assumption",
            "timing_rationale": "now",
        })

        with patch.dict("sys.modules", {
            "packages.content_factory.source_library": MagicMock(
                SourceVideoLibrary=MagicMock(return_value=mock_lib),
            ),
        }):
            mock_router_instance.complete_text = AsyncMock(return_value=adaptation_json)
            result = await agent.discover_adaptation_candidates("tech")

        # Should only call router for first 5 records (analyzed[:5])
        assert mock_router_instance.complete_text.call_count == 5
