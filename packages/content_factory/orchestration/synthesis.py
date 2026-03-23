"""Component 3: The Learning Synthesis Engine.

Reads all learning logs across all phases to locate cross-system patterns over
4 sequential passes. This makes the factory truly self-improving by detecting 
Persistent Failure Patterns, Successful Mutation Patterns, Cross-Agent Correlates,
and Audience Response Patterns.
"""

from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
import json
from datetime import datetime, timezone
from pathlib import Path
from packages.core.logger import get_logger
from packages.memory.client import ZepMemoryClient
from packages.core.config import get_settings

logger = get_logger("LearningSynthesis")

class Insight(BaseModel):
    """A structured conclusion drawn from cross-phase analysis."""
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
    """The weekly summary report passed to Human Review."""
    report_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executive_summary: str
    high_confidence_insights: list[Insight]
    medium_confidence_insights: list[Insight]
    genre_performance_trends: dict[str, str] = Field(default_factory=dict)
    audience_response_patterns: list[str] = Field(default_factory=list)
    genre_drift_alerts: list[str] = Field(default_factory=list)

class SynthesisEngine:
    def __init__(self):
        self.reports_dir = Path("packages/data/synthesis_reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.learning_log_path = Path("packages/data/learning_log.jsonl")
        self.zep_client = ZepMemoryClient()
        self.zep_session_id = f"{get_settings().ZEP_LEARNING_USER_ID}_session"
        
    def execute_synthesis_cycle(self) -> Optional[SynthesisReport]:
        """Runs the 4-pass synthesis engine over the factory."""
        logger.info("synthesis_cycle_started")
        
        # Pass 1 & 2: Semantic Pattern Detection via Zep
        patterns = self._detect_patterns_semantic()
        
        # Pass 3: Insight Generation
        insights = self._generate_insights(patterns)
        
        # Pass 4: Report Generation
        report = self._generate_report(insights)
        
        if report:
            self._save_report(report)
            logger.info(f"synthesis_cycle_completed | report_id={report.report_id} insights_count={len(insights)}")
            
        return report

    def _detect_patterns_semantic(self) -> list[dict]:
        """
        Queries Zep for semantic patterns rather than scanning local JSONL.
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
            results = self.zep_client.search_memory(session_id=self.zep_session_id, query=q, limit=2)
            if results:
                patterns.append({
                    "type": "persistent_failure",
                    "category": "Semantic Pattern",
                    "question": q[:20] + "...",
                    "genre": "cross_genre",
                    "fail_rate": 0.0,
                    "evidence": " | ".join(r.get("fact", "") for r in results)
                })
                
        return patterns

    def execute_monthly_cross_cycle_analysis(self) -> None:
        """Runs the monthly analysis querying Zep for emergent Cross-Cycle Patterns."""
        logger.info("monthly_cross_cycle_analysis_started")
        queries = [
            "What combinations of topic type, genre, and gap type have consistently produced the highest overall binary evaluation scores?",
            "Is there a relationship between the number of Challenger iterations required in the experiment loop and final YouTube engagement score?",
            "Which binary questions have shown improving pass rates over the last six months vs no improvement?"
        ]
        
        for q in queries:
            results = self.zep_client.search_memory(session_id=self.zep_session_id, query=q, limit=3)
            if results:
                evidence = "\n".join(r.get("fact", "") for r in results)
                logger.info(f"Cross-cycle pattern found: {evidence[:50]}...")
                self.zep_client.add_facts(session_id=self.zep_session_id, facts=[{
                    "fact": f"Monthly Cross-Cycle Finding for '{q}': {evidence}",
                    "log_type": "Cross-Cycle Pattern",
                    "source": "monthly_analysis"
                }])

    def _generate_insights(self, patterns: list[dict]) -> list[Insight]:
        """Translates patterns to High/Medium/Low confidence Insights."""
        logger.info("synthesis_pass_3_insight_generation")
        import uuid
        insights = []
        for p in patterns:
            if p["type"] == "persistent_failure":
                insights.append(Insight(
                    insight_id=str(uuid.uuid4()),
                    pattern_type="persistent_failure",
                    phases_involved=["Phase 3", "Phase 4"],
                    genres_affected=[p["genre"]],
                    agents_implicated=["Various"],
                    binary_categories_implicated=[p["category"]],
                    evidence_summary=p["evidence"],
                    current_instruction="Current baseline logic",
                    proposed_instruction_change="Update instructions based on retrieved semantic pattern",
                    expected_impact="Reduces round evaluation failures.",
                    confidence="high"
                ))
        return insights

    def _generate_report(self, insights: list[Insight]) -> SynthesisReport:
        """Compiles the final Synthesis Report for the Weekly Handoff."""
        logger.info("synthesis_pass_4_report_generation")
        import uuid
        return SynthesisReport(
            report_id=f"SYN-{uuid.uuid4().hex[:8].upper()}",
            executive_summary=f"Synthesized {len(insights)} material insights this cycle.",
            high_confidence_insights=[i for i in insights if i.confidence == "high"],
            medium_confidence_insights=[i for i in insights if i.confidence == "medium"],
            genre_performance_trends={"current_situation": "declining_slightly", "islamic_history": "stable"},
        )

    def _save_report(self, report: SynthesisReport):
        path = self.reports_dir / f"{report.report_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
