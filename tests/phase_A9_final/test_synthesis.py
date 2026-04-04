"""Tests for packages.content_factory.orchestration.synthesis — SynthesisEngine.

Focuses on static methods and pure-logic parts:
  - _classify_query() — all query pattern branches
  - _compute_confidence() — threshold logic
  - _build_proposed_change() — change generation
  - _get_current_instruction_desc() — instruction baseline
  - _get_expected_impact() — impact descriptions
  - Insight / SynthesisReport models
  - _generate_report() — report compilation (pure logic)
  - _generate_insights() — insight generation (pure logic)
  - execute_synthesis_cycle() — mocked Zep
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from packages.content_factory.orchestration.synthesis import (
    Insight,
    SynthesisEngine,
    SynthesisReport,
)


# ── Insight model ─────────────────────────────────────────────────────────────

class TestInsightModel:
    def test_valid_insight_creation(self):
        insight = Insight(
            insight_id="ins-001",
            pattern_type="persistent_failure",
            phases_involved=["Phase 3", "Phase 4"],
            genres_affected=["islamic_history"],
            agents_implicated=["ScriptAgent"],
            binary_categories_implicated=["Script Prose Quality"],
            evidence_summary="Passive voice fails 40% of the time",
            current_instruction="Write in standard English",
            proposed_instruction_change="Convert passive to active voice",
            expected_impact="Reduce failures by 20%",
            confidence="high",
        )
        assert insight.insight_id == "ins-001"
        assert insight.confidence == "high"

    def test_all_pattern_types(self):
        for pt in ("persistent_failure", "successful_mutation", "cross_agent_correlation", "audience_response", "genre_drift"):
            insight = Insight(
                insight_id=f"ins-{pt}",
                pattern_type=pt,
                phases_involved=["Phase 3"],
                genres_affected=["cross_genre"],
                agents_implicated=["CrossSystem"],
                binary_categories_implicated=["General"],
                evidence_summary="evidence",
                current_instruction="current",
                proposed_instruction_change="proposed",
                expected_impact="impact",
                confidence="low",
            )
            assert insight.pattern_type == pt

    def test_all_confidence_levels(self):
        for cl in ("high", "medium", "low"):
            insight = Insight(
                insight_id=f"ins-{cl}",
                pattern_type="persistent_failure",
                phases_involved=["Phase 3"],
                genres_affected=[],
                agents_implicated=[],
                binary_categories_implicated=[],
                evidence_summary="e",
                current_instruction="c",
                proposed_instruction_change="p",
                expected_impact="i",
                confidence=cl,
            )
            assert insight.confidence == cl

    def test_invalid_pattern_type_raises(self):
        with pytest.raises(Exception):
            Insight(
                insight_id="bad",
                pattern_type="invalid_type",  # type: ignore
                phases_involved=[],
                genres_affected=[],
                agents_implicated=[],
                binary_categories_implicated=[],
                evidence_summary="",
                current_instruction="",
                proposed_instruction_change="",
                expected_impact="",
                confidence="low",
            )


# ── SynthesisReport model ─────────────────────────────────────────────────────

class TestSynthesisReportModel:
    def test_basic_report_creation(self):
        report = SynthesisReport(
            report_id="SYN-TEST001",
            executive_summary="2 insights found.",
            high_confidence_insights=[],
            medium_confidence_insights=[],
        )
        assert report.report_id == "SYN-TEST001"
        assert report.genre_performance_trends == {}
        assert report.audience_response_patterns == []
        assert report.genre_drift_alerts == []

    def test_created_at_defaults_to_utc_now(self):
        before = datetime.now(timezone.utc)
        report = SynthesisReport(
            report_id="SYN-TEST002",
            executive_summary="test",
            high_confidence_insights=[],
            medium_confidence_insights=[],
        )
        after = datetime.now(timezone.utc)
        assert before <= report.created_at <= after

    def test_with_insights(self):
        insight = Insight(
            insight_id="i1",
            pattern_type="persistent_failure",
            phases_involved=["Phase 3"],
            genres_affected=[],
            agents_implicated=["ScriptAgent"],
            binary_categories_implicated=["Script Prose Quality"],
            evidence_summary="evidence",
            current_instruction="current",
            proposed_instruction_change="proposed",
            expected_impact="impact",
            confidence="high",
        )
        report = SynthesisReport(
            report_id="SYN-TEST003",
            executive_summary="1 high insight",
            high_confidence_insights=[insight],
            medium_confidence_insights=[],
        )
        assert len(report.high_confidence_insights) == 1


# ── _classify_query (static) ─────────────────────────────────────────────────

class TestClassifyQuery:
    """Test all pattern type branches and agent routing."""

    # -- Pattern type detection --

    def test_failure_keywords(self):
        for kw in ("fail", "failed", "failure"):
            result = SynthesisEngine._classify_query(f"What prose patterns {kw}?")
            assert result["pattern_type"] == "persistent_failure"

    def test_success_keywords(self):
        for kw in ("improved", "successfully resolved", "largest score improvements", "most reliably", "higher retention"):
            result = SynthesisEngine._classify_query(f"What mutations {kw}?")
            assert result["pattern_type"] == "successful_mutation"

    def test_correlation_keywords(self):
        for kw in ("associated", "correlation", "relationship"):
            result = SynthesisEngine._classify_query(f"What is the {kw}?")
            assert result["pattern_type"] == "cross_agent_correlation"

    def test_audience_keywords(self):
        for kw in ("response", "retention", "engagement", "audience"):
            result = SynthesisEngine._classify_query(f"What {kw} patterns exist?")
            assert result["pattern_type"] == "audience_response"

    def test_genre_drift_fallback(self):
        result = SynthesisEngine._classify_query("Some random query about weather")
        assert result["pattern_type"] == "genre_drift"

    # -- Agent routing --

    def test_prose_agent(self):
        for kw in ("prose", "script", "zone 1", "rewriting", "passive voice"):
            result = SynthesisEngine._classify_query(f"What {kw} mutations work?")
            assert result["agent"] == "ScriptAgent"

    def test_research_agent(self):
        for kw in ("research", "visual anchor", "citation", "tier 1", "verification"):
            result = SynthesisEngine._classify_query(f"What {kw} approaches work?")
            assert result["agent"] == "Researcher"

    def test_music_agent(self):
        for kw in ("music", "sonic", "transition", "palette"):
            result = SynthesisEngine._classify_query(f"What {kw} issues exist?")
            assert result["agent"] == "MusicAgent"

    def test_experiment_agent(self):
        for kw in ("experiment", "iteration", "challenger", "round"):
            result = SynthesisEngine._classify_query(f"What {kw} patterns?")
            assert result["agent"] == "ExperimentLoop"

    def test_cross_system_fallback(self):
        result = SynthesisEngine._classify_query("Some random topic about weather")
        assert result["agent"] == "CrossSystem"

    # -- Genre extraction --

    def test_genre_extraction_islamic_history(self):
        result = SynthesisEngine._classify_query("failures in islamic history genre content")
        assert result["genre"] == "Islamic History"

    def test_genre_extraction_comparison(self):
        result = SynthesisEngine._classify_query("comparison and contrast genre issues")
        assert result["genre"] == "Comparison And Contrast"

    def test_genre_extraction_pakistani(self):
        result = SynthesisEngine._classify_query("pakistani topics that fail")
        assert result["genre"] == "Pakistani"

    def test_genre_extraction_current_situation(self):
        result = SynthesisEngine._classify_query("current situation content patterns")
        assert result["genre"] == "Current Situation"

    def test_genre_extraction_economic(self):
        result = SynthesisEngine._classify_query("economic investigation failures")
        assert result["genre"] == "Economic Investigation"

    def test_no_genre_cross_genre(self):
        result = SynthesisEngine._classify_query("random topic about weather patterns")
        assert result["genre"] == "cross_genre"

    # -- Category and phases --

    def test_script_agent_has_correct_category(self):
        result = SynthesisEngine._classify_query("What prose patterns fail?")
        assert result["category"] == "Script Prose Quality"
        assert result["phases"] == ["Phase 3", "Phase 4"]

    def test_researcher_has_correct_category(self):
        result = SynthesisEngine._classify_query("What research approaches work?")
        assert result["category"] == "Research & Anchoring"
        assert result["phases"] == ["Phase 2"]

    def test_music_agent_has_correct_category(self):
        result = SynthesisEngine._classify_query("What music transitions fail?")
        assert result["category"] == "Music Architecture"
        assert result["phases"] == ["Phase 4"]

    def test_experiment_loop_has_correct_category(self):
        result = SynthesisEngine._classify_query("What experiment iterations?")
        assert result["category"] == "Experiment Evaluation"
        assert result["phases"] == ["Phase 5"]

    def test_cross_system_has_all_phases(self):
        result = SynthesisEngine._classify_query("random weather topic")
        assert result["phases"] == ["Phase 2", "Phase 3", "Phase 4", "Phase 5"]


# ── _compute_confidence (static) ─────────────────────────────────────────────

class TestComputeConfidence:
    def test_successful_mutation_two_evidence_high(self):
        pattern = {"type": "successful_mutation", "evidence_count": 2, "fail_rate": 0.0}
        assert SynthesisEngine._compute_confidence(pattern) == "high"

    def test_successful_mutation_one_evidence_medium(self):
        pattern = {"type": "successful_mutation", "evidence_count": 1, "fail_rate": 0.0}
        assert SynthesisEngine._compute_confidence(pattern) == "medium"

    def test_failure_two_evidence_high_fail_rate_high(self):
        pattern = {"type": "persistent_failure", "evidence_count": 2, "fail_rate": 0.5}
        assert SynthesisEngine._compute_confidence(pattern) == "high"

    def test_failure_two_evidence_low_fail_rate_medium(self):
        pattern = {"type": "persistent_failure", "evidence_count": 2, "fail_rate": 0.3}
        assert SynthesisEngine._compute_confidence(pattern) == "medium"

    def test_failure_one_evidence_fail_rate_medium(self):
        pattern = {"type": "persistent_failure", "evidence_count": 1, "fail_rate": 0.5}
        assert SynthesisEngine._compute_confidence(pattern) == "medium"

    def test_failure_one_evidence_no_fail_rate_low(self):
        pattern = {"type": "persistent_failure", "evidence_count": 1, "fail_rate": 0.0}
        assert SynthesisEngine._compute_confidence(pattern) == "low"

    def test_zero_evidence_low(self):
        pattern = {"type": "persistent_failure", "evidence_count": 0, "fail_rate": 0.0}
        assert SynthesisEngine._compute_confidence(pattern) == "low"

    def test_missing_keys_defaults_low(self):
        assert SynthesisEngine._compute_confidence({}) == "low"

    def test_audience_response_one_evidence_no_fail_rate_low(self):
        pattern = {"type": "audience_response", "evidence_count": 1, "fail_rate": 0.0}
        assert SynthesisEngine._compute_confidence(pattern) == "low"

    def test_successful_mutation_three_evidence_high(self):
        pattern = {"type": "successful_mutation", "evidence_count": 3, "fail_rate": 0.0}
        assert SynthesisEngine._compute_confidence(pattern) == "high"

    def test_failure_two_evidence_fail_rate_one_high(self):
        pattern = {"type": "persistent_failure", "evidence_count": 2, "fail_rate": 1.0}
        assert SynthesisEngine._compute_confidence(pattern) == "high"


# ── _build_proposed_change (static) ──────────────────────────────────────────

class TestBuildProposedChange:
    def test_persistent_failure(self):
        pattern = {
            "type": "persistent_failure",
            "agent": "ScriptAgent",
            "category": "Script Prose Quality",
            "evidence": "Passive voice fails Category C 40%",
        }
        change = SynthesisEngine._build_proposed_change(pattern)
        assert "avoid" in change.lower()
        assert "ScriptAgent" in change
        assert "Script Prose Quality" in change

    def test_successful_mutation(self):
        pattern = {
            "type": "successful_mutation",
            "agent": "Researcher",
            "category": "Research & Anchoring",
            "evidence": "Tier 1 anchors improved scores by 15%",
        }
        change = SynthesisEngine._build_proposed_change(pattern)
        assert "prefer" in change.lower()
        assert "Researcher" in change

    def test_cross_agent_correlation(self):
        pattern = {
            "type": "cross_agent_correlation",
            "agent": "MusicAgent",
            "category": "Music Architecture",
            "evidence": "Music state correlates with audience retention",
        }
        change = SynthesisEngine._build_proposed_change(pattern)
        assert "coordination" in change.lower()
        assert "Music Architecture" in change

    def test_audience_response(self):
        pattern = {
            "type": "audience_response",
            "agent": "ScriptAgent",
            "category": "Script Prose Quality",
            "evidence": "Audience drops off during long bridges",
        }
        change = SynthesisEngine._build_proposed_change(pattern)
        assert "audience response pattern" in change.lower()

    def test_genre_drift(self):
        pattern = {
            "type": "genre_drift",
            "agent": "CrossSystem",
            "category": "General",
            "evidence": "Genre scores declining over 3 months",
        }
        change = SynthesisEngine._build_proposed_change(pattern)
        assert "audience response pattern" in change.lower()

    def test_evidence_truncated_at_120_chars(self):
        long_evidence = "x" * 200
        pattern = {
            "type": "persistent_failure",
            "agent": "ScriptAgent",
            "category": "General",
            "evidence": long_evidence,
        }
        change = SynthesisEngine._build_proposed_change(pattern)
        # Evidence in output should be capped at ~120 chars
        assert "x" * 130 not in change

    def test_missing_keys_uses_defaults(self):
        change = SynthesisEngine._build_proposed_change({})
        assert "Auto-synthesized" in change
        assert "unknown" in change.lower()


# ── _get_current_instruction_desc (static) ────────────────────────────────────

class TestGetCurrentInstructionDesc:
    def test_returns_baseline_description(self):
        pattern = {"agent": "ScriptAgent", "category": "Script Prose Quality"}
        desc = SynthesisEngine._get_current_instruction_desc(pattern)
        assert "Baseline" in desc
        assert "ScriptAgent" in desc
        assert "Script Prose Quality" in desc

    def test_missing_keys_uses_defaults(self):
        desc = SynthesisEngine._get_current_instruction_desc({})
        assert "Baseline" in desc
        assert "unknown" in desc


# ── _get_expected_impact (static) ─────────────────────────────────────────────

class TestGetExpectedImpact:
    def test_persistent_failure_impact(self):
        pattern = {"type": "persistent_failure", "agent": "ScriptAgent", "category": "Script Prose Quality"}
        impact = SynthesisEngine._get_expected_impact(pattern)
        assert "Reduces" in impact
        assert "ScriptAgent" in impact

    def test_successful_mutation_impact(self):
        pattern = {"type": "successful_mutation", "agent": "Researcher", "category": "Research"}
        impact = SynthesisEngine._get_expected_impact(pattern)
        assert "Replicates" in impact
        assert "Researcher" in impact

    def test_cross_agent_correlation_impact(self):
        pattern = {"type": "cross_agent_correlation", "agent": "MusicAgent", "category": "Music"}
        impact = SynthesisEngine._get_expected_impact(pattern)
        assert "Improves cross-agent coordination" in impact

    def test_audience_response_impact(self):
        pattern = {"type": "audience_response", "agent": "ScriptAgent", "category": "General"}
        impact = SynthesisEngine._get_expected_impact(pattern)
        assert "audience preferences" in impact

    def test_missing_keys(self):
        impact = SynthesisEngine._get_expected_impact({})
        assert "Aligns" in impact


# ── _generate_insights ────────────────────────────────────────────────────────

class TestGenerateInsights:
    def test_empty_patterns_empty_insights(self):
        engine = SynthesisEngine.__new__(SynthesisEngine)
        insights = engine._generate_insights([])
        assert insights == []

    def test_single_pattern_produces_insight(self):
        engine = SynthesisEngine.__new__(SynthesisEngine)
        pattern = {
            "type": "persistent_failure",
            "category": "Script Prose Quality",
            "genre": "islamic_history",
            "agent": "ScriptAgent",
            "phases": ["Phase 3", "Phase 4"],
            "fail_rate": 0.5,
            "evidence_count": 2,
            "evidence": "Passive voice failures in Islamic History content",
        }
        insights = engine._generate_insights([pattern])
        assert len(insights) == 1
        assert isinstance(insights[0], Insight)
        assert insights[0].confidence == "high"
        assert insights[0].pattern_type == "persistent_failure"
        assert insights[0].agents_implicated == ["ScriptAgent"]
        assert insights[0].phases_involved == ["Phase 3", "Phase 4"]
        assert "islamic_history" in insights[0].genres_affected

    def test_insight_has_unique_ids(self):
        engine = SynthesisEngine.__new__(SynthesisEngine)
        pattern = {
            "type": "persistent_failure",
            "category": "General",
            "genre": "cross_genre",
            "agent": "ScriptAgent",
            "phases": ["Phase 3"],
            "fail_rate": 1.0,
            "evidence_count": 2,
            "evidence": "evidence text",
        }
        insights = engine._generate_insights([pattern, pattern])
        assert len(insights) == 2
        assert insights[0].insight_id != insights[1].insight_id

    def test_proposed_change_populated(self):
        engine = SynthesisEngine.__new__(SynthesisEngine)
        pattern = {
            "type": "successful_mutation",
            "category": "Research & Anchoring",
            "genre": "cross_genre",
            "agent": "Researcher",
            "phases": ["Phase 2"],
            "fail_rate": 0.0,
            "evidence_count": 2,
            "evidence": "Tier 1 anchors improved",
        }
        insights = engine._generate_insights([pattern])
        assert "Auto-synthesized" in insights[0].proposed_instruction_change
        assert "Researcher" in insights[0].proposed_instruction_change


# ── _generate_report ──────────────────────────────────────────────────────────

class TestGenerateReport:
    def _make_engine(self):
        engine = SynthesisEngine.__new__(SynthesisEngine)
        return engine

    def test_empty_insights_returns_report(self):
        engine = self._make_engine()
        report = engine._generate_report([])
        assert isinstance(report, SynthesisReport)
        assert report.executive_summary == "Synthesized 0 material insights this cycle."

    def test_high_and_medium_separation(self):
        engine = self._make_engine()
        high = Insight(
            insight_id="h1", pattern_type="persistent_failure",
            phases_involved=[], genres_affected=[], agents_implicated=[],
            binary_categories_implicated=[], evidence_summary="e",
            current_instruction="c", proposed_instruction_change="p",
            expected_impact="i", confidence="high",
        )
        med = Insight(
            insight_id="m1", pattern_type="persistent_failure",
            phases_involved=[], genres_affected=[], agents_implicated=[],
            binary_categories_implicated=[], evidence_summary="e",
            current_instruction="c", proposed_instruction_change="p",
            expected_impact="i", confidence="medium",
        )
        low = Insight(
            insight_id="l1", pattern_type="persistent_failure",
            phases_involved=[], genres_affected=[], agents_implicated=[],
            binary_categories_implicated=[], evidence_summary="e",
            current_instruction="c", proposed_instruction_change="p",
            expected_impact="i", confidence="low",
        )
        report = engine._generate_report([high, med, low])
        assert len(report.high_confidence_insights) == 1
        assert len(report.medium_confidence_insights) == 1
        # Low confidence insights are NOT included in the report
        assert report.high_confidence_insights[0].insight_id == "h1"
        assert report.medium_confidence_insights[0].insight_id == "m1"

    def test_report_id_format(self):
        engine = self._make_engine()
        report = engine._generate_report([])
        assert report.report_id.startswith("SYN-")
        assert len(report.report_id) == 12  # SYN-XXXXXXXX

    def test_genre_performance_trends(self):
        engine = self._make_engine()
        insight_failure = Insight(
            insight_id="g1", pattern_type="persistent_failure",
            phases_involved=[], genres_affected=["Islamic History"], agents_implicated=[],
            binary_categories_implicated=[], evidence_summary="e",
            current_instruction="c", proposed_instruction_change="p",
            expected_impact="i", confidence="high",
        )
        insight_success = Insight(
            insight_id="g2", pattern_type="successful_mutation",
            phases_involved=[], genres_affected=["Pakistani"], agents_implicated=[],
            binary_categories_implicated=[], evidence_summary="e",
            current_instruction="c", proposed_instruction_change="p",
            expected_impact="i", confidence="high",
        )
        insight_audience = Insight(
            insight_id="g3", pattern_type="audience_response",
            phases_involved=[], genres_affected=["Current Situation"], agents_implicated=[],
            binary_categories_implicated=[], evidence_summary="e",
            current_instruction="c", proposed_instruction_change="p",
            expected_impact="i", confidence="high",
        )
        report = engine._generate_report([insight_failure, insight_success, insight_audience])
        assert report.genre_performance_trends["Islamic History"] == "declining_slightly"
        assert report.genre_performance_trends["Pakistani"] == "improving"
        assert report.genre_performance_trends["Current Situation"] == "stable"

    def test_cross_genre_excluded_from_trends(self):
        engine = self._make_engine()
        insight = Insight(
            insight_id="cg1", pattern_type="persistent_failure",
            phases_involved=[], genres_affected=["cross_genre"], agents_implicated=[],
            binary_categories_implicated=[], evidence_summary="e",
            current_instruction="c", proposed_instruction_change="p",
            expected_impact="i", confidence="high",
        )
        report = engine._generate_report([insight])
        assert "cross_genre" not in report.genre_performance_trends


# ── execute_synthesis_cycle (mocked Zep) ─────────────────────────────────────

class TestExecuteSynthesisCycle:
    @pytest.mark.asyncio
    async def test_no_patterns_returns_none(self):
        """When Zep returns no results, _generate_report returns a report
        with 0 insights. But the report is still generated and saved.
        Actually: _generate_report always returns a report, even if empty.
        So execute_synthesis_cycle returns it."""
        engine = SynthesisEngine.__new__(SynthesisEngine)
        engine.reports_dir = MagicMock()
        engine.reports_dir.mkdir = MagicMock()
        engine.reports_dir.__truediv__ = MagicMock(return_value=MagicMock())
        engine.learning_log_path = MagicMock()

        with patch.object(engine, "_detect_patterns_semantic", new_callable=AsyncMock, return_value=[]):
            with patch.object(engine, "_generate_insights", return_value=[]):
                with patch.object(engine, "_generate_report") as mock_report:
                    with patch.object(engine, "_save_report"):
                        mock_report.return_value = SynthesisReport(
                            report_id="SYN-EMPTY",
                            executive_summary="0 insights",
                            high_confidence_insights=[],
                            medium_confidence_insights=[],
                        )
                        result = await engine.execute_synthesis_cycle()
                        assert result is not None
                        assert result.report_id == "SYN-EMPTY"

    @pytest.mark.asyncio
    async def test_full_cycle_with_patterns(self):
        """Simulate a full cycle with patterns returning from Zep."""
        engine = SynthesisEngine.__new__(SynthesisEngine)
        engine.reports_dir = MagicMock()
        engine.reports_dir.mkdir = MagicMock()
        engine.reports_dir.__truediv__ = MagicMock(return_value=MagicMock())
        engine.learning_log_path = MagicMock()

        patterns = [{
            "type": "persistent_failure",
            "category": "Script Prose Quality",
            "genre": "islamic_history",
            "agent": "ScriptAgent",
            "phases": ["Phase 3", "Phase 4"],
            "fail_rate": 1.0,
            "evidence_count": 2,
            "evidence": "Passive voice failures",
        }]

        with patch.object(engine, "_detect_patterns_semantic", new_callable=AsyncMock, return_value=patterns):
            with patch.object(engine, "_generate_insights") as mock_insights:
                with patch.object(engine, "_generate_report") as mock_report:
                    with patch.object(engine, "_save_report"):
                        fake_insight = Insight(
                            insight_id="i1", pattern_type="persistent_failure",
                            phases_involved=["Phase 3"], genres_affected=["Islamic History"],
                            agents_implicated=["ScriptAgent"],
                            binary_categories_implicated=["Script Prose Quality"],
                            evidence_summary="e", current_instruction="c",
                            proposed_instruction_change="p", expected_impact="i",
                            confidence="high",
                        )
                        mock_insights.return_value = [fake_insight]
                        fake_report = SynthesisReport(
                            report_id="SYN-FULL",
                            executive_summary="1 insight",
                            high_confidence_insights=[fake_insight],
                            medium_confidence_insights=[],
                        )
                        mock_report.return_value = fake_report
                        result = await engine.execute_synthesis_cycle()
                        assert result is not None
                        assert result.report_id == "SYN-FULL"
                        mock_save = engine._save_report
                        mock_save.assert_called_once_with(fake_report)
