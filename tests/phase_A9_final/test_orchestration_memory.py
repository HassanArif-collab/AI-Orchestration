"""Tests for orchestration/memory.py — HermesMemoryAdapter.

Tests skills dict, audience memory, cross-production search, and persistence.
"""

import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

for mod_name in [
    "langgraph", "langgraph.graph", "langgraph.types",
    "langgraph.prebuilt", "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

from packages.content_factory.orchestration.memory import (
    HermesMemoryAdapter,
    HermesSkillPayload,
    AudienceMemoryState,
    CrossProductionSessionGraph,
)


class TestHermesSkillPayload:
    """Tests for HermesSkillPayload model."""

    def test_valid_payload(self):
        payload = HermesSkillPayload(
            skill_name="researcher_instruction_set",
            description="Active directives",
            active_prompt="Be thorough",
            version_id="v1",
            last_updated="2024-01-01T00:00:00Z",
        )
        assert payload.skill_name == "researcher_instruction_set"

    def test_model_dump(self):
        payload = HermesSkillPayload(
            skill_name="test",
            description="desc",
            active_prompt="prompt",
            version_id="v1",
            last_updated="2024-01-01T00:00:00Z",
        )
        d = payload.model_dump()
        assert d["skill_name"] == "test"
        assert "description" in d


class TestAudienceMemoryState:
    """Tests for AudienceMemoryState model."""

    def test_default_values(self):
        state = AudienceMemoryState()
        assert state.audience_id == "pakistani_youtube_demographic"
        assert state.knowledge_baseline == []
        assert state.attention_pattern_curve == "flat_drop_at_bridge"
        assert state.topic_resonance_map == {}
        assert state.genre_engagement_rankings == {}

    def test_custom_values(self):
        state = AudienceMemoryState(
            attention_pattern_curve="steep_drop",
            topic_resonance_map={"tech": 0.8},
            genre_engagement_rankings={"tech": 1},
        )
        assert state.attention_pattern_curve == "steep_drop"
        assert state.topic_resonance_map["tech"] == 0.8


class TestCrossProductionSessionGraph:
    """Tests for CrossProductionSessionGraph model."""

    def test_defaults(self):
        graph = CrossProductionSessionGraph(
            genre="current_situation",
            question_category="C",
        )
        assert graph.failed_mutations == []

    def test_with_failures(self):
        graph = CrossProductionSessionGraph(
            genre="islamic_history",
            question_category="D",
            failed_mutations=["mutation1", "mutation2"],
        )
        assert len(graph.failed_mutations) == 2


class TestHermesMemoryAdapter:
    """Tests for HermesMemoryAdapter — the central memory adapter."""

    def test_init(self):
        adapter = HermesMemoryAdapter()
        assert adapter.skills == {}
        assert isinstance(adapter.audience_memory, AudienceMemoryState)

    def test_update_agent_skill_stores_in_dict(self):
        """update_agent_skill should store a HermesSkillPayload in skills dict."""
        adapter = HermesMemoryAdapter()
        adapter.update_agent_skill("researcher", "New instruction text", "v1")

        assert "researcher" in adapter.skills
        payload = adapter.skills["researcher"]
        assert isinstance(payload, HermesSkillPayload)
        assert payload.active_prompt == "New instruction text"
        assert payload.version_id == "v1"
        assert payload.skill_name == "researcher_instruction_set"
        assert payload.last_updated is not None

    def test_update_agent_skill_overwrites(self):
        """Updating the same agent should overwrite the previous skill."""
        adapter = HermesMemoryAdapter()
        adapter.update_agent_skill("researcher", "v1 instruction", "v1")
        adapter.update_agent_skill("researcher", "v2 instruction", "v2")

        assert adapter.skills["researcher"].version_id == "v2"
        assert adapter.skills["researcher"].active_prompt == "v2 instruction"

    def test_update_agent_skill_sync_fallback(self):
        """When no event loop, should use sync Supabase fallback."""
        adapter = HermesMemoryAdapter()
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value = mock_result

        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")), \
             patch("packages.core.supabase_client.get_supabase_optional", return_value=mock_sb):
            adapter.update_agent_skill("writer", "instruction", "v1")

        mock_sb.table.assert_called_once_with("hermes_memory_state")

    def test_update_audience_memory(self):
        """update_audience_memory should update fields from ingestion data."""
        adapter = HermesMemoryAdapter()
        ingestion = {
            "retention_curve": "sharp_drop_at_anchor",
            "genre": "technology",
            "engagement": 85,
        }
        adapter.update_audience_memory(ingestion)

        assert adapter.audience_memory.attention_pattern_curve == "sharp_drop_at_anchor"
        assert adapter.audience_memory.genre_engagement_rankings["technology"] == 85

    def test_update_audience_memory_partial_data(self):
        """Should handle partial ingestion data gracefully."""
        adapter = HermesMemoryAdapter()
        adapter.update_audience_memory({"retention_curve": "flat"})

        assert adapter.audience_memory.attention_pattern_curve == "flat"
        # genre_engagement_rankings should be unchanged
        assert "technology" not in adapter.audience_memory.genre_engagement_rankings


class TestUpdateAudienceMemoryAsync:
    """Tests for async audience memory update."""

    @pytest.mark.asyncio
    async def test_calls_persist_after_update(self):
        """Async version should call _persist_audience_memory after updating."""
        adapter = HermesMemoryAdapter()
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            await adapter.update_audience_memory_async({"retention_curve": "test"})

        assert adapter.audience_memory.attention_pattern_curve == "test"
        mock_sb.table.assert_called_once_with("hermes_memory_state")


class TestSearchCrossProductionMemory:
    """Tests for search_cross_production_memory — mutation history check."""

    def test_returns_true_for_safe_mutation(self):
        """New mutation not in history should be safe."""
        adapter = HermesMemoryAdapter()
        assert adapter.search_cross_production_memory(
            "current_situation", "C", "improve hook opening"
        ) is True

    def test_returns_false_for_known_bad_mutation(self):
        """Known-bad mutation should be blocked."""
        adapter = HermesMemoryAdapter()
        assert adapter.search_cross_production_memory(
            "current_situation", "C", "adding explicit nominals"
        ) is False

    def test_returns_false_for_another_known_bad_mutation(self):
        """Second known-bad mutation should also be blocked."""
        adapter = HermesMemoryAdapter()
        assert adapter.search_cross_production_memory(
            "islamic_history", "D", "removing visual anchors"
        ) is False


class TestLoadState:
    """Tests for load_state — persistence recovery."""

    @pytest.mark.asyncio
    async def test_loads_skills_from_supabase(self):
        """Should restore skills from Supabase on startup."""
        adapter = HermesMemoryAdapter()
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{
            "value": {
                "writer": {
                    "skill_name": "writer_instruction_set",
                    "description": "desc",
                    "active_prompt": "prompt",
                    "version_id": "v1",
                    "last_updated": "2024-01-01T00:00:00Z",
                }
            }
        }]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            await adapter._load_skills()

        assert "writer" in adapter.skills
        assert adapter.skills["writer"].active_prompt == "prompt"

    @pytest.mark.asyncio
    async def test_loads_audience_memory_from_supabase(self):
        """Should restore audience memory from Supabase on startup."""
        adapter = HermesMemoryAdapter()
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{
            "value": {
                "audience_id": "pakistani_youtube_demographic",
                "attention_pattern_curve": "steep_drop",
                "knowledge_baseline": ["knows about tech"],
                "topic_resonance_map": {},
                "genre_engagement_rankings": {"tech": 1},
            }
        }]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb):
            await adapter._load_audience_memory()

        assert adapter.audience_memory.attention_pattern_curve == "steep_drop"
        assert adapter.audience_memory.genre_engagement_rankings["tech"] == 1

    @pytest.mark.asyncio
    async def test_load_state_calls_both_loaders(self):
        """load_state should call both _load_skills and _load_audience_memory."""
        adapter = HermesMemoryAdapter()

        with patch.object(adapter, "_load_skills", new_callable=AsyncMock) as mock_skills, \
             patch.object(adapter, "_load_audience_memory", new_callable=AsyncMock) as mock_audience:
            await adapter.load_state()

            mock_skills.assert_called_once()
            mock_audience.assert_called_once()
