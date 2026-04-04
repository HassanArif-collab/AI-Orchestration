"""Tests for orchestration/master.py — MasterOrchestrator.

Tests cycle management, Zep session init, phase advancement, escalation.
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


# We need to patch the heavy imports at module level before importing master
# The master.py imports from packages.memory.client and packages.content_factory.orchestration.db
# which in turn import from supabase_client. We mock those at the module level.

def _make_master():
    """Create a MasterOrchestrator with mocked dependencies."""
    mock_db = MagicMock()
    mock_zep = AsyncMock()

    with patch("packages.content_factory.orchestration.master.OrchestrationDB", return_value=mock_db), \
         patch("packages.content_factory.orchestration.master.AsyncZepMemoryClient", return_value=mock_zep):
        from packages.content_factory.orchestration.master import MasterOrchestrator
        master = MasterOrchestrator.__new__(MasterOrchestrator)
        master.db = mock_db
        master.zep_client = mock_zep
        master.max_concurrent_cycles = 2
        return master


class TestCheckAndStartNewCycle:
    """Tests for check_and_start_new_cycle — cycle creation from reservoir."""

    @pytest.mark.asyncio
    async def test_skips_when_at_max_capacity(self):
        """Should not start a cycle if at max concurrent cycles."""
        master = _make_master()
        cycle = MagicMock()
        master.db.get_active_cycles.return_value = [cycle, cycle]  # 2 active = max

        await master.check_and_start_new_cycle([])
        master.db.create_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_tier1_topics(self):
        """Should not start a cycle if no Tier 1 topics available."""
        master = _make_master()
        master.db.get_active_cycles.return_value = []

        # Topics with viability_score_breakdown total < 12
        topic = MagicMock()
        topic.viability_score_breakdown = {"total": 5}
        await master.check_and_start_new_cycle([topic])

        master.db.create_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_starts_cycle_for_best_tier1_topic(self):
        """Should create a cycle for the highest-scoring Tier 1 topic."""
        master = _make_master()
        master.db.get_active_cycles.return_value = []

        t1 = MagicMock()
        t1.viability_score_breakdown = {"total": 14}
        t1.topic_statement = "Best topic"
        t1.genre_id = "current_situation"
        t2 = MagicMock()
        t2.viability_score_breakdown = {"total": 12}
        t2.topic_statement = "Second best"
        t2.genre_id = "current_situation"

        with patch("packages.content_factory.orchestration.master.asyncio.create_task"):
            await master.check_and_start_new_cycle([t1, t2])

        master.db.create_cycle.assert_called_once()
        created_cycle = master.db.create_cycle.call_args[0][0]
        assert created_cycle.topic_statement == "Best topic"
        assert created_cycle.genre == "current_situation"

    @pytest.mark.asyncio
    async def test_initializes_zep_session(self):
        """Should create Zep user, session, and initial facts."""
        master = _make_master()
        master.db.get_active_cycles.return_value = []

        topic = MagicMock()
        topic.viability_score_breakdown = {"total": 15}
        topic.topic_statement = "Zep test topic"
        topic.genre_id = "tech"

        with patch("packages.content_factory.orchestration.master.asyncio.create_task"):
            await master.check_and_start_new_cycle([topic])

        master.zep_client.create_user.assert_called_once()
        master.zep_client.create_session.assert_called_once()
        master.zep_client.add_facts.assert_called_once()
        # The fact should mention the topic
        fact_arg = master.zep_client.add_facts.call_args[1]["facts"]
        assert len(fact_arg) == 1
        assert "Zep test topic" in fact_arg[0]["fact"]


class TestAdvancePhase:
    """Tests for advance_phase — sequential routing enforcement."""

    @pytest.mark.asyncio
    async def test_returns_false_when_lock_not_acquired(self):
        """Should return False when lock cannot be acquired."""
        master = _make_master()
        master.db.acquire_lock.return_value = False

        result = await master.advance_phase("cycle-1", "drafting")
        assert result is False

    @pytest.mark.asyncio
    async def test_updates_phase_in_db(self):
        """Should update the phase in Supabase via _cycles().update()."""
        master = _make_master()
        master.db.acquire_lock.return_value = True
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
        master.db._cycles.return_value = mock_table

        result = await master.advance_phase("cycle-1", "drafting")
        assert result is True
        mock_table.update.assert_called_once()
        update_data = mock_table.update.call_args[0][0]
        assert update_data["current_phase"] == "drafting"
        assert "updated_at" in update_data

    @pytest.mark.asyncio
    async def test_releases_lock_after_success(self):
        """Should always release lock, even on success."""
        master = _make_master()
        master.db.acquire_lock.return_value = True
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
        master.db._cycles.return_value = mock_table

        await master.advance_phase("cycle-1", "drafting")
        master.db.release_lock.assert_called_once_with("cycle-1")

    @pytest.mark.asyncio
    async def test_releases_lock_after_failure(self):
        """Should always release lock, even on exception."""
        master = _make_master()
        master.db.acquire_lock.return_value = True
        mock_table = MagicMock()
        mock_table.update.side_effect = Exception("db error")
        master.db._cycles.return_value = mock_table

        result = await master.advance_phase("cycle-1", "drafting")
        assert result is False
        master.db.release_lock.assert_called_once_with("cycle-1")

    @pytest.mark.asyncio
    async def test_writes_zep_fact(self):
        """Should write a Zep fact about the phase advancement."""
        master = _make_master()
        master.db.acquire_lock.return_value = True
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
        master.db._cycles.return_value = mock_table

        await master.advance_phase("cycle-1", "scoring")
        master.zep_client.add_facts.assert_called_once()
        facts = master.zep_client.add_facts.call_args[1]["facts"]
        assert "scoring" in facts[0]["fact"]


class TestHandleEscalation:
    """Tests for handle_escalation — escalation creation and cycle pausing."""

    @pytest.mark.asyncio
    async def test_creates_escalation_in_db(self):
        """Should create an escalation record via db.escalate()."""
        master = _make_master()
        master.db.acquire_lock.return_value = True
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
        master.db._cycles.return_value = mock_table

        await master.handle_escalation(
            cycle_id="cycle-1",
            error_type="hard_failure",
            severity="high",
            context={"message": "test error"},
        )

        master.db.escalate.assert_called_once()
        esc_item = master.db.escalate.call_args[0][0]
        assert esc_item.cycle_id == "cycle-1"
        assert esc_item.type == "hard_failure"
        assert esc_item.severity == "high"

    @pytest.mark.asyncio
    async def test_pauses_cycle(self):
        """Should pause the cycle by updating status and phase."""
        master = _make_master()
        master.db.acquire_lock.return_value = True
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
        master.db._cycles.return_value = mock_table

        await master.handle_escalation("cycle-1", "hard_failure", "high", {})

        mock_table.update.assert_called_once()
        update_data = mock_table.update.call_args[0][0]
        assert update_data["status"] == "paused"
        assert update_data["current_phase"] == "awaiting_review"

    @pytest.mark.asyncio
    async def test_skips_pause_when_lock_fails(self):
        """Should not attempt to pause if lock cannot be acquired."""
        master = _make_master()
        master.db.acquire_lock.return_value = False

        await master.handle_escalation("cycle-1", "hard_failure", "high", {})
        master.db._cycles.assert_not_called()


class TestWriteProductionCycleSummary:
    """Tests for write_production_cycle_summary — Zep fact writing."""

    @pytest.mark.asyncio
    async def test_writes_summary_fact_to_zep(self):
        """Should write a production cycle summary fact to Zep."""
        master = _make_master()

        await master.write_production_cycle_summary(
            cycle_id="cycle-1",
            topic_statement="Test Topic",
            genre="current_situation",
            gap_type="Hidden Mechanism",
            source_type="topic_finder",
            final_score=85.0,
            iterations=12,
            engagement_score=78.0,
            view_duration_pct=65.0,
            subscriber_conversion=2.5,
            narrative_summary="This was a great video about hidden mechanisms.",
        )

        master.zep_client.add_facts.assert_called_once()
        fact = master.zep_client.add_facts.call_args[1]["facts"][0]
        assert fact["fact"] == "This was a great video about hidden mechanisms."
        assert fact["production_cycle_id"] == "cycle-1"
        assert fact["final_binary_score"] == 85.0
        assert fact["experiment_iterations"] == 12


class TestTriggerPipeline:
    """Tests for _trigger_pipeline — no-op stub."""

    @pytest.mark.asyncio
    async def test_handles_import_error_gracefully(self):
        """Should handle ImportError when PipelineRunner is removed."""
        master = _make_master()

        # This should not raise
        await master._trigger_pipeline("cycle-1", MagicMock())
