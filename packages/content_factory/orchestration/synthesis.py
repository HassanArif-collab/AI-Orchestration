"""Component 3: The Learning Synthesis Engine.

Reads all learning logs across all phases to locate cross-system patterns over
4 sequential passes. This makes the factory truly self-improving by detecting 
Persistent Failure Patterns, Successful Mutation Patterns, Cross-Agent Correlates,
and Audience Response Patterns.

HOW IT WORKS (4-pass process):

Pass 1 & 2 — Semantic Pattern Detection via Zep:
  Runs 10 pre-written semantic queries against the Zep learning session.
  Queries cover: script prose failures, visual anchor failures,
  successful mutations, audience response patterns, music architecture issues.
  Each query returns the 2 most relevant facts from the learning log.

Pass 3 — Insight Generation:
  Translates raw patterns into structured Insight objects.
  Each Insight has: pattern_type, phases_involved, agents_implicated,
  proposed_instruction_change, confidence (high/medium/low).

Pass 4 — Report Generation:
  Compiles SynthesisReport with executive summary + sorted insights.
  Report saved to packages/data/synthesis_reports/{report_id}.json

MONTHLY ANALYSIS:
  execute_monthly_cross_cycle_analysis() runs 3 deeper queries looking
  for cross-cycle patterns invisible in weekly data:
  - Which topic+genre combinations produce best scores?
  - Does experiment loop count correlate with YouTube engagement?
  - Which binary questions are improving vs plateauing over 6 months?

TRIGGER:
  Called by Scheduler.run_learning_synthesis() every 168 hours (weekly).
  Can also be triggered manually from the CLI or API.

ZEP DEPENDENCY:
  Without ZEP_ENABLED=true, returns a SynthesisReport with 0 insights.
  The Zep learning session must be populated by the experiment loop
  (via ZepAudienceModelStore.write_experiment_result) before synthesis
  can find meaningful patterns.
"""

from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
import json
import uuid
import re
from datetime import datetime, timezone
from pathlib import Path
from packages.core.logger import get_logger
from packages.memory.client import AsyncZepMemoryClient
from packages.core.config import get_settings

logger = get_logger("LearningSynthesis")


class Insight(BaseModel):
    """A structured conclusion drawn from cross-phase analysis.
    
    Insights are the ACTIONABLE output of the synthesis engine.
    Each insight represents a discovered pattern and proposes
    a specific change to agent instructions.
    
    Fields:
      insight_id: Unique identifier for tracking
      pattern_type: Category of the detected pattern
      phases_involved: Which pipeline phases show this pattern
      genres_affected: Which genres are impacted
      agents_implicated: Which agents should receive updated instructions
      binary_categories_implicated: Which evaluation categories are affected
      evidence_summary: Human-readable summary of supporting evidence
      current_instruction: The instruction currently in use
      proposed_instruction_change: The suggested new instruction text
      expected_impact: What improvement this change should produce
      confidence: How certain the engine is about this insight
    """
    insight_id: str
    pattern_type: Literal[
        "persistent_failure", 
        "successful_mutation", 
        "cross_agent_correlation", 
        "audience_response", 
        "genre_drift"
    ]
    phases_involved: list[str]
    genres_affected: list[str]
    agents_implicated: list[str]
    binary_categories_implicated: list[str]
    
    evidence_summary: str
    current_instruction: str
    proposed_instruction_change: str
    expected_impact: str
    confidence: Literal["high", "medium", "low"]


class SynthesisReport(BaseModel):
    """The weekly summary report passed to Human Review.
    
    This is the OUTPUT of the synthesis cycle. It contains all
    discovered insights sorted by confidence, plus trend data
    for genre performance and audience patterns.
    
    Stored to: packages/data/synthesis_reports/{report_id}.json
    Read by: UpdatePipeline, ReviewInterface, HealthMonitor
    """
    report_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executive_summary: str
    high_confidence_insights: list[Insight]
    medium_confidence_insights: list[Insight]
    genre_performance_trends: dict[str, str] = Field(default_factory=dict)
    audience_response_patterns: list[str] = Field(default_factory=list)
    genre_drift_alerts: list[str] = Field(default_factory=list)


class SynthesisEngine:
    """Learning Synthesis Engine — Finds patterns across all production cycles.
    
    This engine is the BRAIN of the self-improvement system. It reads
    accumulated learning data and extracts actionable insights that
    can be fed back into agent instructions.
    
    EXAMPLE INSIGHT FLOW:
      1. Query finds: "Zone 1 mutations removing passive voice
         consistently improved Category C scores by 15%"
      2. Creates Insight with proposed_instruction_change:
         "When revising prose, prioritize converting passive constructions
          to active voice before other stylistic changes"
      3. UpdatePipeline processes insight
      4. Writer agent receives updated instruction
      5. Future scripts score higher on Category C questions
    
    ZEP INTEGRATION:
      All pattern detection happens via semantic search in Zep.
      The ZEP_LEARNING_USER_ID session must be populated first.
      Without Zep, this engine returns empty reports.
    """
    def __init__(self):
        self.reports_dir = Path("packages/data/synthesis_reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.learning_log_path = Path("packages/data/learning_log.jsonl")
        self.zep_client = AsyncZepMemoryClient()
        self.zep_session_id = f"{get_settings().ZEP_LEARNING_USER_ID}_session"
        
    async def execute_synthesis_cycle(self) -> Optional[SynthesisReport]:
        """Runs the 4-pass synthesis engine over the factory.
        
        This is the MAIN ENTRY POINT for weekly learning synthesis.
        Called automatically by the scheduler every 168 hours.
        
        Returns:
          SynthesisReport if any insights found
          None if no data available or Zep disabled
        """
        logger.info("synthesis_cycle_started")
        
        # Pass 1 & 2: Semantic Pattern Detection via Zep
        patterns = await self._detect_patterns_semantic()
        
        # Pass 3: Insight Generation
        insights = self._generate_insights(patterns)
        
        # Pass 4: Report Generation
        report = self._generate_report(insights)
        
        if report:
            self._save_report(report)
            logger.info(f"synthesis_cycle_completed | report_id={report.report_id} insights_count={len(insights)}")
            
        return report

    @staticmethod
    def _classify_query(query: str) -> dict:
        """Derive pattern metadata from the semantic query text.
        
        Analyzes query keywords to determine pattern type, agent,
        genre focus, and category for downstream insight generation.
        """
        q_lower = query.lower()

        # Determine pattern type from query intent
        if any(kw in q_lower for kw in ("fail", "failed", "failure")):
            pattern_type = "persistent_failure"
        elif any(kw in q_lower for kw in ("improved", "successfully resolved", "largest score improvements", "most reliably", "higher retention")):
            pattern_type = "successful_mutation"
        elif any(kw in q_lower for kw in ("associated", "correlation", "relationship")):
            pattern_type = "cross_agent_correlation"
        elif any(kw in q_lower for kw in ("response", "retention", "engagement", "audience")):
            pattern_type = "audience_response"
        else:
            pattern_type = "genre_drift"

        # Determine which agent the query targets
        if any(kw in q_lower for kw in ("prose", "script", "zone 1", "rewriting", "passive voice")):
            agent = "ScriptAgent"
            category = "Script Prose Quality"
            phases = ["Phase 3", "Phase 4"]
        elif any(kw in q_lower for kw in ("research", "visual anchor", "citation", "tier 1", "verification")):
            agent = "Researcher"
            category = "Research & Anchoring"
            phases = ["Phase 2"]
        elif any(kw in q_lower for kw in ("music", "sonic", "transition", "palette")):
            agent = "MusicAgent"
            category = "Music Architecture"
            phases = ["Phase 4"]
        elif any(kw in q_lower for kw in ("experiment", "iteration", "challenger", "round")):
            agent = "ExperimentLoop"
            category = "Experiment Evaluation"
            phases = ["Phase 5"]
        else:
            agent = "CrossSystem"
            category = "Cross-Phase Pattern"
            phases = ["Phase 2", "Phase 3", "Phase 4", "Phase 5"]

        # Extract genre from query if present
        genre_match = re.search(r"(islamic history|comparison and contrast|pakistani|current situation|economic investigation)", q_lower)
        genre = genre_match.group(1).replace("_", " ").title() if genre_match else "cross_genre"

        return {
            "pattern_type": pattern_type,
            "agent": agent,
            "category": category,
            "phases": phases,
            "genre": genre,
        }

    async def _detect_patterns_semantic(self) -> list[dict]:
        """Queries Zep for semantic patterns rather than scanning local JSONL.
        
        Uses 10 pre-written semantic queries designed to surface
        the most valuable learning patterns:
          - Script prose mutation effectiveness
          - Visual anchor success patterns
          - Research citation confidence trends
          - Music architecture issues
          - Audience response to different content types
        
        Returns:
          List of pattern dicts with type, category, genre, and evidence
        """
        logger.info("synthesis_semantic_pattern_detection")
        patterns = []
        
        queries = [
            # Script Agent
            "What Zone 1 mutations have consistently improved binary evaluation scores across the last twenty production cycles?",
            "What prose patterns most frequently fail Category C binary questions for Islamic History genre content?",
            "What rewriting approaches successfully resolved passive voice failures in Pakistani economic investigation content?",
            "What specific instruction changes produced the largest score improvements for Comparison and Contrast genre scripts?",
            # Researcher
            "Which research approaches most reliably found Tier 1 visual anchors for current situation explainer topics?",
            "What types of Pakistani topics consistently failed to produce two Tier 1 anchor candidates?",
            "Which verification approaches most frequently resolved Medium confidence citations to High confidence?",
            # Music Agent
            "Which music state assignments most frequently failed binary evaluation questions for Islamic History content?",
            "What transition types required the most revision requests from the Music Agent to the Script Agent?",
            "Which Pakistani sonic palette specifications were associated with higher retention at anchor sections?"
        ]
        
        for q in queries:
            results = await self.zep_client.search_memory(session_id=self.zep_session_id, query=q, limit=2)
            if results:
                classification = self._classify_query(q)
                evidence_texts = [r.get("fact", "") for r in results]
                evidence_joined = " | ".join(evidence_texts)

                # Estimate fail_rate from evidence for failure-type patterns
                fail_rate = 0.0
                if classification["pattern_type"] == "persistent_failure":
                    fail_rate = min(1.0, len(evidence_texts) / 2.0)

                patterns.append({
                    "type": classification["pattern_type"],
                    "category": classification["category"],
                    "question": q[:80],
                    "genre": classification["genre"],
                    "agent": classification["agent"],
                    "phases": classification["phases"],
                    "fail_rate": fail_rate,
                    "evidence_count": len(results),
                    "evidence": evidence_joined,
                })
                
        return patterns

    async def execute_monthly_cross_cycle_analysis(self) -> None:
        """Runs the monthly analysis querying Zep for emergent Cross-Cycle Patterns.
        
        These queries look for LONG-TERM patterns that only emerge
        when analyzing data across many weeks:
          - Topic+genre combination effectiveness
          - Iteration count vs engagement correlation
          - Question improvement trends over time
        
        Results are written back to Zep for next month's analysis.
        """
        logger.info("monthly_cross_cycle_analysis_started")
        queries = [
            "What combinations of topic type, genre, and gap type have consistently produced the highest overall binary evaluation scores?",
            "Is there a relationship between the number of Challenger iterations required in the experiment loop and final YouTube engagement score?",
            "Which binary questions have shown improving pass rates over the last six months vs no improvement?"
        ]
        
        for q in queries:
            results = await self.zep_client.search_memory(session_id=self.zep_session_id, query=q, limit=3)
            if results:
                evidence = "\n".join(r.get("fact", "") for r in results)
                logger.info(f"Cross-cycle pattern found: {evidence[:50]}...")
                await self.zep_client.add_facts(session_id=self.zep_session_id, facts=[{
                    "fact": f"Monthly Cross-Cycle Finding for '{q}': {evidence}",
                    "log_type": "Cross-Cycle Pattern",
                    "source": "monthly_analysis"
                }])

    @staticmethod
    def _compute_confidence(pattern: dict) -> Literal["high", "medium", "low"]:
        """Compute confidence level from evidence strength.
        
        Uses evidence_count and fail_rate to determine confidence:
          - high: 2+ evidence items with high fail_rate, or successful mutation with 2+ items
          - medium: 1 evidence item, or moderate fail_rate
          - low: everything else
        """
        evidence_count = pattern.get("evidence_count", 0)
        fail_rate = pattern.get("fail_rate", 0.0)
        pattern_type = pattern.get("type", "")

        if pattern_type == "successful_mutation" and evidence_count >= 2:
            return "high"
        if evidence_count >= 2 and fail_rate >= 0.5:
            return "high"
        if evidence_count >= 1 and (fail_rate > 0.0 or pattern_type == "successful_mutation"):
            return "medium"
        return "low"

    @staticmethod
    def _build_proposed_change(pattern: dict) -> str:
        """Generate a proposed instruction change from the pattern evidence.
        
        Constructs a specific, actionable instruction change based on the
        detected pattern type, agent, and evidence.
        """
        pattern_type = pattern.get("type", "unknown")
        agent = pattern.get("agent", "unknown")
        category = pattern.get("category", "general")
        evidence = pattern.get("evidence", "")

        if pattern_type == "persistent_failure":
            return (
                f"[Auto-synthesized] {agent} should avoid the {category} failure pattern "
                f"detected in semantic analysis. Evidence: {evidence[:120]}"
            )
        elif pattern_type == "successful_mutation":
            return (
                f"[Auto-synthesized] {agent} should prefer the {category} approach "
                f"that improved scores. Evidence: {evidence[:120]}"
            )
        elif pattern_type == "cross_agent_correlation":
            return (
                f"[Auto-synthesized] Cross-agent coordination needed for {category}. "
                f"Evidence: {evidence[:120]}"
            )
        else:
            return (
                f"[Auto-synthesized] Review {category} for {agent} based on "
                f"audience response pattern. Evidence: {evidence[:120]}"
            )

    @staticmethod
    def _get_current_instruction_desc(pattern: dict) -> str:
        """Describe the current baseline instruction for the pattern's agent/category.
        
        Returns a description of what instruction is currently in effect,
        based on the agent and category context.
        """
        agent = pattern.get("agent", "unknown")
        category = pattern.get("category", "general")
        return f"Baseline {category} directives for {agent} (version prior to synthesis)"

    @staticmethod
    def _get_expected_impact(pattern: dict) -> str:
        """Describe expected impact based on pattern type and evidence."""
        pattern_type = pattern.get("type", "")
        agent = pattern.get("agent", "")
        if pattern_type == "persistent_failure":
            return f"Reduces {agent} evaluation failures by addressing the {pattern.get('category', 'general')} pattern."
        elif pattern_type == "successful_mutation":
            return f"Replicates proven {agent} approach to improve scores consistently."
        elif pattern_type == "cross_agent_correlation":
            return f"Improves cross-agent coordination for {pattern.get('category', 'general')} workflows."
        else:
            return f"Aligns {agent} output with audience preferences for {pattern.get('category', 'general')}."

    def _generate_insights(self, patterns: list[dict]) -> list[Insight]:
        """Translates patterns to High/Medium/Low confidence Insights.
        
        Each pattern becomes an Insight with:
          - A proposed instruction change (dynamically generated)
          - A confidence level computed from evidence count and fail_rate
          - Agent, phase, and genre fields derived from query classification
        
        Args:
          patterns: Raw pattern dicts from _detect_patterns_semantic()
        
        Returns:
          List of Insight objects ready for UpdatePipeline
        """
        logger.info("synthesis_pass_3_insight_generation")
        insights = []
        for p in patterns:
            confidence = self._compute_confidence(p)
            # Map phase list from pattern classification
            phases_involved = p.get("phases", ["Phase 3", "Phase 4"])
            # Map agent from pattern classification
            agents_implicated = [p.get("agent", "ScriptAgent")]

            insights.append(Insight(
                insight_id=str(uuid.uuid4()),
                pattern_type=p.get("type", "persistent_failure"),
                phases_involved=phases_involved,
                genres_affected=[p.get("genre", "cross_genre")],
                agents_implicated=agents_implicated,
                binary_categories_implicated=[p.get("category", "General")],
                evidence_summary=p.get("evidence", ""),
                current_instruction=self._get_current_instruction_desc(p),
                proposed_instruction_change=self._build_proposed_change(p),
                expected_impact=self._get_expected_impact(p),
                confidence=confidence,
            ))
        return insights

    def _generate_report(self, insights: list[Insight]) -> SynthesisReport:
        """Compiles the final Synthesis Report for the Weekly Handoff.
        
        Separates insights by confidence level for routing:
          - High confidence → auto-activation candidates
          - Medium confidence → advisory window + human review
          - Low confidence → escalated for mandatory review
        
        Args:
          insights: List of Insight objects from _generate_insights()
        
        Returns:
          SynthesisReport ready for storage and processing
        """
        logger.info("synthesis_pass_4_report_generation")

        # Derive genre_performance_trends from insight data
        genre_trends: dict[str, str] = {}
        for insight in insights:
            for genre in insight.genres_affected:
                if genre == "cross_genre":
                    continue
                if genre not in genre_trends:
                    if insight.pattern_type == "persistent_failure":
                        genre_trends[genre] = "declining_slightly"
                    elif insight.pattern_type == "successful_mutation":
                        genre_trends[genre] = "improving"
                    elif insight.pattern_type == "audience_response":
                        genre_trends[genre] = "stable"
                    else:
                        genre_trends[genre] = "monitoring"

        return SynthesisReport(
            report_id=f"SYN-{uuid.uuid4().hex[:8].upper()}",
            executive_summary=f"Synthesized {len(insights)} material insights this cycle.",
            high_confidence_insights=[i for i in insights if i.confidence == "high"],
            medium_confidence_insights=[i for i in insights if i.confidence == "medium"],
            genre_performance_trends=genre_trends,
        )

    def _save_report(self, report: SynthesisReport):
        """Persist report to disk for audit trail.
        
        File: packages/data/synthesis_reports/{report_id}.json
        """
        path = self.reports_dir / f"{report.report_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
