"""
Decision Log Module

Provides comprehensive logging of decisions made during the evolution process.
This enables the system to learn from past decisions and improve over time.

KEY FEATURES:
1. Decision Audit Trail: Every decision is logged with context and outcome
2. Outcome Tracking: Expected vs actual results are compared
3. Pattern Recognition: Identifies decision patterns that lead to success/failure
4. Query Interface: Easy retrieval of decision history for analysis

This module implements the user's requirement to "log what is improved and also
what didn't work to make the decisions better."

Based on Implementation Plan V4 requirements.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Any

from packages.core.config import get_settings
from packages.core.logger import get_logger

log = get_logger(__name__)


class DecisionOutcome(str, Enum):
    """Possible outcomes of a decision."""
    SUCCESS = "success"           # Decision led to improvement
    PARTIAL = "partial"           # Some improvement, not as expected
    NEUTRAL = "neutral"           # No significant change
    FAILURE = "failure"           # Made things worse
    PENDING = "pending"           # Outcome not yet determined


class DecisionType(str, Enum):
    """Types of decisions made during evolution."""
    STRATEGY_SELECTION = "strategy_selection"
    PROMPT_ADJUSTMENT = "prompt_adjustment"
    STAGNATION_RESPONSE = "stagnation_response"
    ALTERNATIVE_APPROACH = "alternative_approach"
    ITERATION_CONTINUE = "iteration_continue"
    THRESHOLD_EXIT = "threshold_exit"


@dataclass
class DecisionContext:
    """Context in which a decision was made."""
    iteration: int
    current_score: float
    weak_areas: list[str]
    strong_areas: list[str]
    stagnation_detected: bool
    consecutive_failures: int
    time_in_evolution_seconds: float
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DecisionExpected:
    """What was expected from the decision."""
    improvement_target: float
    target_areas: list[str]
    strategy_reasoning: str
    confidence_level: float  # 0.0 to 1.0
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DecisionActual:
    """What actually happened after the decision."""
    new_score: float
    actual_improvement: float
    improved_areas: list[str]
    regressed_areas: list[str]
    new_weak_areas: list[str]
    outcome: DecisionOutcome
    
    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "outcome": self.outcome.value
        }


@dataclass
class DecisionRecord:
    """
    Complete record of a single decision.
    
    This is the atomic unit of decision logging.
    Each record captures:
    - Context: State when decision was made
    - Decision: What was decided and why
    - Expected: What was expected to happen
    - Actual: What actually happened (filled after next iteration)
    - Learnings: What can be learned from this decision
    """
    decision_id: str
    evolution_id: str
    decision_type: DecisionType
    timestamp: str
    
    # The decision
    chosen_strategy: str
    chosen_over_alternatives: list[str]  # What other options were considered
    
    # Context
    context: DecisionContext
    
    # Expected outcome
    expected: DecisionExpected
    
    # Actual outcome (filled after execution)
    actual: Optional[DecisionActual] = None
    
    # Learnings extracted
    learnings: list[str] = field(default_factory=list)
    
    # Similar past decisions
    similar_past_decision_ids: list[str] = field(default_factory=list)
    past_decision_outcomes: list[DecisionOutcome] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "decision_id": self.decision_id,
            "evolution_id": self.evolution_id,
            "decision_type": self.decision_type.value,
            "timestamp": self.timestamp,
            "chosen_strategy": self.chosen_strategy,
            "chosen_over_alternatives": self.chosen_over_alternatives,
            "context": self.context.to_dict() if self.context else None,
            "expected": self.expected.to_dict() if self.expected else None,
            "actual": self.actual.to_dict() if self.actual else None,
            "learnings": self.learnings,
            "similar_past_decision_ids": self.similar_past_decision_ids,
            "past_decision_outcomes": [o.value for o in self.past_decision_outcomes]
        }


class DecisionLog:
    """
    Manages decision logging and retrieval.
    
    Provides:
    1. Persistent storage of decisions
    2. Query interface for analysis
    3. Pattern extraction for learning
    4. Integration with evolution loop
    
    USAGE:
        decision_log = DecisionLog()
        
        # Log a decision
        record = decision_log.log_decision(
            evolution_id="evo_123",
            decision_type=DecisionType.STRATEGY_SELECTION,
            chosen_strategy="hook_enhancement",
            context=DecisionContext(...),
            expected=DecisionExpected(...)
        )
        
        # Update with actual outcome
        decision_log.update_outcome(
            decision_id=record.decision_id,
            new_score=0.78,
            improved_areas=["H1", "H2"],
            regressed_areas=[]
        )
        
        # Query for analysis
        successful_decisions = decision_log.query(outcome=DecisionOutcome.SUCCESS)
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        settings = get_settings()
        self.log_dir = log_dir or Path(settings.DATA_DIR) / "decision_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_decisions: dict[str, DecisionRecord] = {}
        self._decision_counter = 0
    
    def log_decision(
        self,
        evolution_id: str,
        decision_type: DecisionType,
        chosen_strategy: str,
        context: DecisionContext,
        expected: DecisionExpected,
        alternatives: list[str] = None,
        similar_past: list[tuple[str, DecisionOutcome]] = None
    ) -> DecisionRecord:
        """
        Log a new decision.
        
        Args:
            evolution_id: ID of the evolution cycle
            decision_type: Type of decision
            chosen_strategy: The strategy that was chosen
            context: Context when decision was made
            expected: Expected outcome
            alternatives: Other strategies that were considered
            similar_past: List of (decision_id, outcome) for similar past decisions
        
        Returns:
            DecisionRecord with assigned ID
        """
        self._decision_counter += 1
        decision_id = f"dec_{evolution_id}_{self._decision_counter:03d}"
        
        # Process similar past decisions
        similar_ids = []
        past_outcomes = []
        if similar_past:
            for past_id, outcome in similar_past:
                similar_ids.append(past_id)
                past_outcomes.append(outcome)
        
        record = DecisionRecord(
            decision_id=decision_id,
            evolution_id=evolution_id,
            decision_type=decision_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            chosen_strategy=chosen_strategy,
            chosen_over_alternatives=alternatives or [],
            context=context,
            expected=expected,
            similar_past_decision_ids=similar_ids,
            past_decision_outcomes=past_outcomes
        )
        
        self._current_decisions[decision_id] = record
        
        log.info(
            f"decision_logged: {decision_id} strategy={chosen_strategy} "
            f"expected_improvement={expected.improvement_target:.2f}"
        )
        
        return record
    
    def update_outcome(
        self,
        decision_id: str,
        new_score: float,
        improved_areas: list[str],
        regressed_areas: list[str],
        new_weak_areas: list[str]
    ) -> Optional[DecisionRecord]:
        """
        Update a decision with its actual outcome.
        
        This is called after the next iteration to record what actually happened.
        
        Args:
            decision_id: The decision to update
            new_score: Score after the decision was executed
            improved_areas: Areas that improved
            regressed_areas: Areas that got worse
            new_weak_areas: Current weak areas
        
        Returns:
            Updated DecisionRecord or None if not found
        """
        if decision_id not in self._current_decisions:
            log.warning(f"decision_not_found: {decision_id}")
            return None
        
        record = self._current_decisions[decision_id]
        
        # Calculate actual improvement
        actual_improvement = new_score - record.context.current_score
        
        # Determine outcome
        expected_improvement = record.expected.improvement_target
        
        if actual_improvement >= expected_improvement * 0.8:
            outcome = DecisionOutcome.SUCCESS
        elif actual_improvement > 0:
            outcome = DecisionOutcome.PARTIAL
        elif actual_improvement == 0:
            outcome = DecisionOutcome.NEUTRAL
        else:
            outcome = DecisionOutcome.FAILURE
        
        # Create actual outcome record
        record.actual = DecisionActual(
            new_score=new_score,
            actual_improvement=actual_improvement,
            improved_areas=improved_areas,
            regressed_areas=regressed_areas,
            new_weak_areas=new_weak_areas,
            outcome=outcome
        )
        
        # Extract learnings
        record.learnings = self._extract_learnings(record)
        
        # Persist the decision
        self._persist_decision(record)
        
        log.info(
            f"decision_outcome: {decision_id} outcome={outcome.value} "
            f"improvement={actual_improvement:.3f} (expected={expected_improvement:.3f})"
        )
        
        return record
    
    def _extract_learnings(self, record: DecisionRecord) -> list[str]:
        """Extract learnings from a decision record."""
        learnings = []
        
        if not record.actual:
            return learnings
        
        # Learning from success
        if record.actual.outcome == DecisionOutcome.SUCCESS:
            learnings.append(
                f"Strategy '{record.chosen_strategy}' effective for "
                f"{', '.join(record.expected.target_areas)}"
            )
            
            # What specifically worked
            for area in record.actual.improved_areas:
                learnings.append(
                    f"Strategy '{record.chosen_strategy}' improved {area}"
                )
        
        # Learning from failure
        elif record.actual.outcome == DecisionOutcome.FAILURE:
            learnings.append(
                f"Strategy '{record.chosen_strategy}' failed for "
                f"{', '.join(record.expected.target_areas)}"
            )
            
            # What specifically didn't work
            for area in record.actual.regressed_areas:
                learnings.append(
                    f"Strategy '{record.chosen_strategy}' regressed {area}"
                )
            
            # Suggest alternative
            if record.chosen_over_alternatives:
                learnings.append(
                    f"Consider alternatives: {', '.join(record.chosen_over_alternatives)}"
                )
        
        # Learning from partial success
        elif record.actual.outcome == DecisionOutcome.PARTIAL:
            learnings.append(
                f"Strategy '{record.chosen_strategy}' partially effective - "
                f"consider combining with other approaches"
            )
        
        # Pattern from similar past decisions
        if record.past_decision_outcomes:
            success_rate = sum(
                1 for o in record.past_decision_outcomes 
                if o == DecisionOutcome.SUCCESS
            ) / len(record.past_decision_outcomes)
            
            if success_rate > 0.7:
                learnings.append(
                    f"High historical success rate ({success_rate:.0%}) for this decision type"
                )
            elif success_rate < 0.3:
                learnings.append(
                    f"Low historical success rate ({success_rate:.0%}) - "
                    f"this decision type often fails"
                )
        
        return learnings
    
    def _persist_decision(self, record: DecisionRecord) -> None:
        """Persist decision to disk."""
        log_file = self.log_dir / f"{record.evolution_id}_decisions.jsonl"
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), default=str) + "\n")
        except Exception as e:
            log.warning(f"decision_persist_failed: {e}")
    
    def query(
        self,
        evolution_id: str = None,
        decision_type: DecisionType = None,
        outcome: DecisionOutcome = None,
        strategy: str = None,
        limit: int = 100
    ) -> list[DecisionRecord]:
        """
        Query decisions by various filters.
        
        Args:
            evolution_id: Filter by evolution cycle
            decision_type: Filter by decision type
            outcome: Filter by outcome
            strategy: Filter by strategy used
            limit: Maximum results to return
        
        Returns:
            List of matching DecisionRecords
        """
        results = []
        
        # Check in-memory first
        for record in self._current_decisions.values():
            if self._matches_filters(record, evolution_id, decision_type, outcome, strategy):
                results.append(record)
        
        # Also check persisted files if needed
        if len(results) < limit:
            results.extend(self._query_from_files(
                evolution_id, decision_type, outcome, strategy, limit - len(results)
            ))
        
        return results[:limit]
    
    def _matches_filters(
        self,
        record: DecisionRecord,
        evolution_id: str = None,
        decision_type: DecisionType = None,
        outcome: DecisionOutcome = None,
        strategy: str = None
    ) -> bool:
        """Check if record matches all filters."""
        if evolution_id and record.evolution_id != evolution_id:
            return False
        if decision_type and record.decision_type != decision_type:
            return False
        if outcome and (not record.actual or record.actual.outcome != outcome):
            return False
        if strategy and record.chosen_strategy != strategy:
            return False
        return True
    
    def _query_from_files(
        self,
        evolution_id: str,
        decision_type: DecisionType,
        outcome: DecisionOutcome,
        strategy: str,
        limit: int
    ) -> list[DecisionRecord]:
        """Query decisions from persisted files."""
        results = []
        
        for log_file in self.log_dir.glob("*_decisions.jsonl"):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        data = json.loads(line)
                        record = self._dict_to_record(data)
                        
                        if self._matches_filters(record, evolution_id, decision_type, outcome, strategy):
                            results.append(record)
                            
                            if len(results) >= limit:
                                return results
            except Exception as e:
                log.warning(f"decision_query_file_error: {log_file} - {e}")
        
        return results
    
    def _dict_to_record(self, data: dict) -> DecisionRecord:
        """Convert dictionary to DecisionRecord."""
        return DecisionRecord(
            decision_id=data["decision_id"],
            evolution_id=data["evolution_id"],
            decision_type=DecisionType(data["decision_type"]),
            timestamp=data["timestamp"],
            chosen_strategy=data["chosen_strategy"],
            chosen_over_alternatives=data.get("chosen_over_alternatives", []),
            context=DecisionContext(**data["context"]) if data.get("context") else None,
            expected=DecisionExpected(**data["expected"]) if data.get("expected") else None,
            actual=DecisionActual(
                **{**data["actual"], "outcome": DecisionOutcome(data["actual"]["outcome"])}
            ) if data.get("actual") else None,
            learnings=data.get("learnings", []),
            similar_past_decision_ids=data.get("similar_past_decision_ids", []),
            past_decision_outcomes=[
                DecisionOutcome(o) for o in data.get("past_decision_outcomes", [])
            ]
        )
    
    def get_success_rate_by_strategy(self) -> dict[str, float]:
        """Get success rate for each strategy."""
        all_decisions = self.query(limit=1000)
        
        strategy_stats = {}
        for record in all_decisions:
            if not record.actual:
                continue
            
            strategy = record.chosen_strategy
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {"success": 0, "total": 0}
            
            strategy_stats[strategy]["total"] += 1
            if record.actual.outcome in [DecisionOutcome.SUCCESS, DecisionOutcome.PARTIAL]:
                strategy_stats[strategy]["success"] += 1
        
        return {
            strategy: stats["success"] / stats["total"]
            for strategy, stats in strategy_stats.items()
            if stats["total"] > 0
        }
    
    def get_best_strategy_for_situation(
        self,
        weak_areas: list[str],
        decision_type: DecisionType = None
    ) -> Optional[str]:
        """
        Get the best strategy for a given situation based on history.
        
        Args:
            weak_areas: Current weak areas
            decision_type: Type of decision being made
        
        Returns:
            Best strategy name or None
        """
        all_decisions = self.query(decision_type=decision_type, limit=500)
        
        strategy_scores = {}
        for record in all_decisions:
            if not record.actual:
                continue
            
            # Check if this decision addressed similar weak areas
            overlap = len(set(record.expected.target_areas) & set(weak_areas))
            if overlap == 0:
                continue
            
            strategy = record.chosen_strategy
            if strategy not in strategy_scores:
                strategy_scores[strategy] = {"weighted_success": 0, "count": 0}
            
            # Weight by overlap and outcome
            weight = overlap / len(weak_areas)
            outcome_score = {
                DecisionOutcome.SUCCESS: 1.0,
                DecisionOutcome.PARTIAL: 0.5,
                DecisionOutcome.NEUTRAL: 0.0,
                DecisionOutcome.FAILURE: -0.5
            }.get(record.actual.outcome, 0)
            
            strategy_scores[strategy]["weighted_success"] += weight * outcome_score
            strategy_scores[strategy]["count"] += 1
        
        if not strategy_scores:
            return None
        
        # Return strategy with highest average weighted success
        best_strategy = max(
            strategy_scores.items(),
            key=lambda x: x[1]["weighted_success"] / max(x[1]["count"], 1)
        )
        
        return best_strategy[0] if best_strategy[1]["weighted_success"] > 0 else None
    
    def get_decision_summary(self, evolution_id: str) -> dict:
        """Get a summary of decisions for an evolution cycle."""
        decisions = self.query(evolution_id=evolution_id)
        
        if not decisions:
            return {"total": 0}
        
        outcomes = {}
        for record in decisions:
            if record.actual:
                outcome = record.actual.outcome.value
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        return {
            "total": len(decisions),
            "outcomes": outcomes,
            "strategies_used": list(set(d.chosen_strategy for d in decisions)),
            "all_learnings": [
                learning
                for d in decisions
                for learning in d.learnings
            ]
        }
