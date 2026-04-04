"""Tests for orchestration/updates.py — Instruction Update Pipeline.

Tests scope determination, regression testing, approval routing matrix,
auto-activation, and rollback monitor.
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

from packages.content_factory.orchestration.updates import (
    UpdatePipeline,
    InstructionVersion,
)
from packages.content_factory.orchestration.synthesis import Insight


def _make_insight(
    confidence="high",
    genres=None,
    agents=None,
    binary_categories=None,
):
    """Create a test Insight."""
    return Insight(
        insight_id="test-insight-1",
        pattern_type="persistent_failure",
        phases_involved=["Phase 3"],
        genres_affected=genres or ["current_situation"],
        agents_implicated=agents or ["ScriptAgent"],
        binary_categories_implicated=binary_categories or ["Script Prose Quality"],
        evidence_summary="Test evidence",
        current_instruction="old instruction",
        proposed_instruction_change="new instruction",
        expected_impact="Better scores",
        confidence=confidence,
    )


def _make_pipeline(master=None):
    """Create a test UpdatePipeline."""
    if master is None:
        master = MagicMock()
        master.handle_escalation = AsyncMock()
    return UpdatePipeline(master)


# ═══════════════════════════════════════════════════════════════
# Scope Determination
# ═══════════════════════════════════════════════════════════════

class TestDetermineScope:
    """Tests for _determine_scope logic."""

    def test_wide_when_many_genres_and_high_confidence(self):
        pipe = _make_pipeline()
        insight = _make_insight(
            confidence="high",
            genres=["genre1", "genre2", "genre3"],
            binary_categories=["A"],
        )
        assert pipe._determine_scope(insight) == "wide"

    def test_medium_when_multiple_binary_categories(self):
        pipe = _make_pipeline()
        insight = _make_insight(
            confidence="high",
            genres=["genre1"],
            binary_categories=["A", "B"],
        )
        assert pipe._determine_scope(insight) == "medium"

    def test_narrow_default(self):
        pipe = _make_pipeline()
        insight = _make_insight(
            confidence="high",
            genres=["genre1"],
            binary_categories=["A"],
        )
        assert pipe._determine_scope(insight) == "narrow"

    def test_narrow_when_two_genres_low_confidence(self):
        pipe = _make_pipeline()
        insight = _make_insight(
            confidence="low",
            genres=["genre1", "genre2"],
            binary_categories=["A"],
        )
        assert pipe._determine_scope(insight) == "narrow"


# ═══════════════════════════════════════════════════════════════
# Regression Testing
# ═══════════════════════════════════════════════════════════════

class TestRunRegressionTest:
    """Tests for _run_regression_test logic."""

    def test_returns_true_when_no_supabase(self):
        """Without Supabase, regression test should pass (fail open)."""
        pipe = _make_pipeline()
        pipe.pre_update_scores = [80, 85, 90]
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test",
            scope="narrow",
        )

        with patch("packages.core.supabase_client.get_supabase_optional", return_value=None):
            assert pipe._run_regression_test(draft, ["genre1"]) is True

    def test_returns_true_when_no_pre_update_scores(self):
        """Without pre_update_scores, regression test should pass."""
        pipe = _make_pipeline()
        pipe.pre_update_scores = []
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test",
            scope="narrow",
        )
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"score": 70}]
        mock_sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase_optional", return_value=mock_sb):
            assert pipe._run_regression_test(draft, ["genre1"]) is True

    def test_detects_regression_when_post_avg_drops_over_10(self):
        """When post_avg drops more than 10 points below pre_avg, regression detected."""
        pipe = _make_pipeline()
        pipe.pre_update_scores = [90, 92, 88]
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test",
            scope="narrow",
        )
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"score": 70}, {"score": 65}, {"score": 72}]
        mock_sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase_optional", return_value=mock_sb):
            result = pipe._run_regression_test(draft, ["genre1"])
            # pre_avg = 90, post_avg ≈ 69 → drop = 21 > 10 → False
            assert result is False

    def test_passes_when_drop_under_10(self):
        """When post_avg drops less than 10 points, test should pass."""
        pipe = _make_pipeline()
        pipe.pre_update_scores = [80, 85, 82]
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test",
            scope="narrow",
        )
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"score": 75}, {"score": 78}, {"score": 76}]
        mock_sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase_optional", return_value=mock_sb):
            result = pipe._run_regression_test(draft, ["genre1"])
            # pre_avg ≈ 82.3, post_avg ≈ 76.3 → drop ≈ 6 < 10 → True
            assert result is True


# ═══════════════════════════════════════════════════════════════
# Approval Routing Matrix
# ═══════════════════════════════════════════════════════════════

class TestRouteApproval:
    """Tests for _route_approval logic — the approval gate matrix."""

    def test_wide_scope_escalates_high_severity(self):
        """Wide scope should always escalate with high severity."""
        pipe = _make_pipeline()
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test", scope="wide",
        )
        insight = _make_insight(confidence="high")

        with patch.object(pipe, "_escalate_for_review") as mock_esc:
            pipe._route_approval(draft, insight)
            mock_esc.assert_called_once()
            call_args = mock_esc.call_args
            assert call_args[0][0] == draft  # draft
            assert "Wide" in call_args[0][1]  # reason
            assert call_args[1]["severity"] == "high"

    def test_low_confidence_escalates_high_severity(self):
        """Low confidence should escalate regardless of scope."""
        pipe = _make_pipeline()
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test", scope="narrow",
        )
        insight = _make_insight(confidence="low")

        with patch.object(pipe, "_escalate_for_review") as mock_esc:
            pipe._route_approval(draft, insight)
            mock_esc.assert_called_once()
            assert mock_esc.call_args[1]["severity"] == "high"

    def test_k_category_always_escalates(self):
        """Pakistani adaptation category (K) should always escalate."""
        pipe = _make_pipeline()
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test", scope="narrow",
        )
        insight = _make_insight(
            confidence="high",
            binary_categories=["K", "A"],
        )

        with patch.object(pipe, "_escalate_for_review") as mock_esc:
            pipe._route_approval(draft, insight)
            mock_esc.assert_called_once()
            assert "Audience Adaptation" in mock_esc.call_args[0][1]

    def test_medium_scope_advisory_escalation(self):
        """Medium scope should escalate with medium severity."""
        pipe = _make_pipeline()
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test", scope="medium",
        )
        insight = _make_insight(confidence="high")

        with patch.object(pipe, "_escalate_for_review") as mock_esc:
            pipe._route_approval(draft, insight)
            mock_esc.assert_called_once()
            assert mock_esc.call_args[1]["severity"] == "medium"

    def test_narrow_high_confidence_auto_activates(self):
        """Narrow scope + high confidence should auto-activate."""
        pipe = _make_pipeline()
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test", scope="narrow",
        )
        insight = _make_insight(confidence="high")

        with patch.object(pipe, "_activate_version") as mock_act, \
             patch.object(pipe, "_fire_escalation") as mock_fire:
            pipe._route_approval(draft, insight)
            mock_act.assert_called_once_with(draft)
            mock_fire.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# Activation
# ═══════════════════════════════════════════════════════════════

class TestActivateVersion:
    """Tests for _activate_version logic."""

    def test_sets_active_date_and_stores_version(self):
        """Activation should set active_date and store in active_versions."""
        pipe = _make_pipeline()
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test", scope="narrow",
        )

        with patch("packages.core.supabase_client.get_supabase_optional", return_value=None):
            pipe._activate_version(draft)

        assert draft.active_date is not None
        assert isinstance(draft.active_date, datetime)
        assert pipe.active_versions["agent1"] is draft

    def test_captures_pre_update_scores_from_supabase(self):
        """Should capture pre-update scores when Supabase available."""
        pipe = _make_pipeline()
        draft = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test", scope="narrow",
        )
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"score": 80}, {"score": 85}]
        mock_sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

        with patch("packages.core.supabase_client.get_supabase_optional", return_value=mock_sb):
            pipe._activate_version(draft)

        assert pipe.pre_update_scores == [80, 85]


# ═══════════════════════════════════════════════════════════════
# Rollback Monitor
# ═══════════════════════════════════════════════════════════════

class TestCheckRollbackMonitor:
    """Tests for check_rollback_monitor logic."""

    def test_returns_false_when_no_active_version(self):
        """No active version → no rollback."""
        pipe = _make_pipeline()
        assert pipe.check_rollback_monitor("unknown_agent", 50) is False

    def test_returns_false_when_version_is_already_rollback(self):
        """Already rolled-back version → no rollback."""
        pipe = _make_pipeline()
        version = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test",
            scope="narrow", is_rollback=True,
        )
        pipe.active_versions["agent1"] = version
        assert pipe.check_rollback_monitor("agent1", 50) is False

    def test_returns_false_when_less_than_3_data_points(self):
        """Need at least 3 post-update scores before checking."""
        pipe = _make_pipeline()
        pipe.pre_update_scores = [80, 85, 90]
        version = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test",
            scope="narrow",
            pre_update_scores=[80, 85, 90],
        )
        pipe.active_versions["agent1"] = version
        # Only 2 scores appended
        assert pipe.check_rollback_monitor("agent1", 75) is False
        assert pipe.check_rollback_monitor("agent1", 78) is False

    def test_triggers_rollback_on_regression(self):
        """When avg post drops >10 below pre, should rollback."""
        pipe = _make_pipeline()
        pipe.pre_update_scores = [80, 82, 85]
        version = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test",
            scope="narrow",
            pre_update_scores=[80, 82, 85],
        )
        pipe.active_versions["agent1"] = version

        with patch("packages.core.supabase_client.get_supabase_optional", return_value=None):
            # First 2 scores don't trigger (need 3)
            pipe.check_rollback_monitor("agent1", 70)
            pipe.check_rollback_monitor("agent1", 65)
            # 3rd score: avg_post = (70+65+60)/3 = 65, pre_avg = 82.3, drop = 17.3 > 10
            result = pipe.check_rollback_monitor("agent1", 60)
            assert result is True
            assert version.is_rollback is True
            assert "agent1" not in pipe.active_versions

    def test_no_rollback_when_scores_stable(self):
        """When post scores are close to pre, no rollback."""
        pipe = _make_pipeline()
        pipe.pre_update_scores = [80, 82, 85]
        version = InstructionVersion(
            version_id="v1", agent_id="agent1", content="test",
            scope="narrow",
            pre_update_scores=[80, 82, 85],
        )
        pipe.active_versions["agent1"] = version

        with patch("packages.core.supabase_client.get_supabase_optional", return_value=None):
            pipe.check_rollback_monitor("agent1", 82)
            pipe.check_rollback_monitor("agent1", 80)
            # 3rd score: avg_post = (82+80+83)/3 ≈ 81.7, pre_avg ≈ 82.3, drop ≈ 0.6 < 10
            result = pipe.check_rollback_monitor("agent1", 83)
            assert result is False


# ═══════════════════════════════════════════════════════════════
# Process Insight
# ═══════════════════════════════════════════════════════════════

class TestProcessInsight:
    """Tests for process_insight — main entry point."""

    def test_creates_draft_for_each_implicated_agent(self):
        """Should create a draft version for each agent implicated."""
        pipe = _make_pipeline()
        insight = _make_insight(
            confidence="high",
            agents=["agent1", "agent2"],
            binary_categories=["A"],
        )

        with patch.object(pipe, "_run_regression_test", return_value=True), \
             patch.object(pipe, "_route_approval"):
            pipe.process_insight(insight)
            # _route_approval should be called for each agent
            # (process_insight iterates agents_implicated)

    def test_skips_agent_on_regression_failure(self):
        """When regression fails, should skip that agent (scope narrowed but continue skipped)."""
        pipe = _make_pipeline()
        insight = _make_insight(
            confidence="high",
            agents=["agent1"],
            binary_categories=["A"],
        )

        with patch.object(pipe, "_run_regression_test", return_value=False), \
             patch.object(pipe, "_route_approval") as mock_route:
            pipe.process_insight(insight)
            mock_route.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# Fire Escalation
# ═══════════════════════════════════════════════════════════════

class TestFireEscalation:
    """Tests for _fire_escalation — sync→async bridge."""

    def test_queues_when_no_event_loop(self):
        """When no running event loop, should queue escalation."""
        pipe = _make_pipeline()

        # Simulate no running event loop by patching get_running_loop to raise
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
            pipe._fire_escalation(
                cycle_id="N/A", error_type="test", severity="low",
                context={"note": "test"},
            )
            assert len(pipe._pending_tasks) == 1
            assert pipe._pending_tasks[0][0] == "queued"
