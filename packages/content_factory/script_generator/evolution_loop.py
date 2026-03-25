"""
Self-Evolving Script Generation Loop

Implements Karpathy's auto-research methodology:
- Generate script
- Self-evaluate against criteria
- Analyze gaps and what didn't work
- Adjust prompt strategy
- Repeat until threshold (NO MAX ITERATIONS)

KEY FEATURES:
1. Learning Log: Tracks what improved and what didn't work
2. Decision History: Records strategy decisions and their outcomes
3. Pattern Recognition: Uses historical patterns for better decisions
4. Stagnation Detection: Identifies when approaches aren't working
5. Automatic Strategy Switching: Changes approach when stuck

The system logs both successes AND failures to make better decisions
in future iterations. This is the core of the self-evolving capability.

Based on Implementation Plan V4 requirements.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from packages.core.config import get_settings
from packages.core.logger import get_logger
from packages.router.client import RouterClient

from .models import DualColumnScript, DualColumnEntry, SelfEvaluationReport
from .self_evaluator import SelfEvaluator, EVALUATION_CRITERIA
from .prompt_adjuster import PromptAdjuster
from .complexity_assessor import ComplexityResult, ComplexityLevel
from .jh_style import JHStyleGenerator

log = get_logger(__name__)


# ─── Learning Entry Models ──────────────────────────────────────────────────────

@dataclass
class ImprovementRecord:
    """
    Records what improved between iterations.
    
    Tracks:
    - Which criteria improved
    - How much they improved
    - What strategy caused the improvement
    """
    iteration: int
    criterion_id: str
    criterion_name: str
    previous_score: float
    new_score: float
    improvement_delta: float
    strategy_used: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class FailureRecord:
    """
    Records what didn't work in an iteration.
    
    This is CRUCIAL for the self-evolving system - by tracking
    what didn't work, the system can avoid repeating mistakes.
    
    Tracks:
    - Which criteria failed
    - What was attempted
    - Why it didn't work
    - Alternative approaches to try
    """
    iteration: int
    criterion_id: str
    criterion_name: str
    attempted_strategy: str
    why_failed: str
    alternative_approaches: list[str] = field(default_factory=list)
    repeated_failure: bool = False  # Has this same failure happened before?
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class IterationDecision:
    """
    Records the decision made at each iteration.
    
    This creates an audit trail of why certain strategies
    were chosen and what the expected outcomes were.
    """
    iteration: int
    current_score: float
    weak_areas: list[str]
    
    # Decision details
    chosen_strategy: str
    strategy_reason: str
    
    # Expected vs actual (filled after next iteration)
    expected_improvement: float = 0.0
    actual_improvement: float = 0.0
    
    # Pattern matching
    similar_past_situations: list[str] = field(default_factory=list)
    applied_learnings: list[str] = field(default_factory=list)
    
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EvolutionLog:
    """
    Complete log of an evolution cycle.
    
    Contains all the learning data for analysis and future decisions.
    """
    evolution_id: str
    topic: str
    started_at: str
    completed_at: str = ""
    
    # Results
    initial_score: float = 0.0
    final_score: float = 0.0
    total_iterations: int = 0
    threshold_reached: bool = False
    
    # Learning records
    improvements: list[ImprovementRecord] = field(default_factory=list)
    failures: list[FailureRecord] = field(default_factory=list)
    decisions: list[IterationDecision] = field(default_factory=list)
    
    # Pattern summary
    successful_strategies: list[str] = field(default_factory=list)
    failed_strategies: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "evolution_id": self.evolution_id,
            "topic": self.topic,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "initial_score": self.initial_score,
            "final_score": self.final_score,
            "total_iterations": self.total_iterations,
            "threshold_reached": self.threshold_reached,
            "improvements": [
                {
                    "iteration": i.iteration,
                    "criterion_id": i.criterion_id,
                    "previous_score": i.previous_score,
                    "new_score": i.new_score,
                    "improvement_delta": i.improvement_delta,
                    "strategy_used": i.strategy_used
                }
                for i in self.improvements
            ],
            "failures": [
                {
                    "iteration": f.iteration,
                    "criterion_id": f.criterion_id,
                    "attempted_strategy": f.attempted_strategy,
                    "why_failed": f.why_failed,
                    "repeated_failure": f.repeated_failure
                }
                for f in self.failures
            ],
            "successful_strategies": self.successful_strategies,
            "failed_strategies": self.failed_strategies
        }


# ─── Evolution State ────────────────────────────────────────────────────────────

class EvolutionState:
    """
    Manages state for the evolution loop.
    
    Persists state to disk for recovery and analysis.
    """
    
    def __init__(self, state_dir: Optional[Path] = None):
        settings = get_settings()
        self.state_dir = state_dir or Path(settings.DATA_DIR) / "evolution_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, evolution_id: str, state: dict) -> None:
        """Save evolution state to disk."""
        state_file = self.state_dir / f"{evolution_id}.json"
        try:
            temp_file = state_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str, ensure_ascii=False)
            temp_file.rename(state_file)
            log.debug(f"evolution_state_saved: {evolution_id}")
        except Exception as e:
            log.warning(f"evolution_state_save_failed: {e}")
    
    def load(self, evolution_id: str) -> Optional[dict]:
        """Load evolution state from disk."""
        state_file = self.state_dir / f"{evolution_id}.json"
        if not state_file.exists():
            return None
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"evolution_state_load_failed: {e}")
            return None
    
    def clear(self, evolution_id: str) -> None:
        """Clear evolution state after completion."""
        state_file = self.state_dir / f"{evolution_id}.json"
        state_file.unlink(missing_ok=True)


# ─── Pattern Learner ────────────────────────────────────────────────────────────

class PatternLearner:
    """
    Learns from past evolution cycles to make better decisions.
    
    This is the core of the self-evolving system's intelligence.
    It analyzes past patterns to:
    1. Predict which strategies work for which situations
    2. Avoid repeating failed approaches
    3. Identify when to switch strategies
    """
    
    def __init__(self, log_path: Optional[Path] = None):
        settings = get_settings()
        self.log_path = log_path or Path(settings.DATA_DIR) / "evolution_patterns.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._pattern_cache = self._load_patterns()
    
    def _load_patterns(self) -> dict:
        """Load historical patterns from log."""
        patterns = {
            "successful_strategies": {},  # strategy -> {success_count, avg_improvement}
            "failed_strategies": {},      # strategy -> {failure_count, common_reasons}
            "criterion_patterns": {},     # criterion_id -> {best_strategies, worst_strategies}
            "stagnation_signals": []      # patterns that indicate stagnation
        }
        
        if not self.log_path.exists():
            return patterns
        
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        self._update_patterns_from_entry(patterns, entry)
        except Exception as e:
            log.warning(f"pattern_load_failed: {e}")
        
        return patterns
    
    def _update_patterns_from_entry(self, patterns: dict, entry: dict) -> None:
        """Update pattern statistics from a log entry."""
        # Track successful strategies
        for strategy in entry.get("successful_strategies", []):
            if strategy not in patterns["successful_strategies"]:
                patterns["successful_strategies"][strategy] = {"count": 0, "total_improvement": 0}
            patterns["successful_strategies"][strategy]["count"] += 1
        
        # Track failed strategies
        for strategy in entry.get("failed_strategies", []):
            if strategy not in patterns["failed_strategies"]:
                patterns["failed_strategies"][strategy] = {"count": 0}
            patterns["failed_strategies"][strategy]["count"] += 1
        
        # Track criterion-specific patterns
        for improvement in entry.get("improvements", []):
            criterion_id = improvement.get("criterion_id")
            strategy = improvement.get("strategy_used")
            delta = improvement.get("improvement_delta", 0)
            
            if criterion_id and strategy:
                if criterion_id not in patterns["criterion_patterns"]:
                    patterns["criterion_patterns"][criterion_id] = {"best": [], "worst": []}
                
                if delta > 0.1:  # Significant improvement
                    patterns["criterion_patterns"][criterion_id]["best"].append(strategy)
                elif delta < 0:  # Got worse
                    patterns["criterion_patterns"][criterion_id]["worst"].append(strategy)
    
    def record_evolution(self, evolution_log: EvolutionLog) -> None:
        """Record an evolution cycle for future learning."""
        entry = evolution_log.to_dict()
        
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            
            # Update cache
            self._update_patterns_from_entry(self._pattern_cache, entry)
            log.info(f"pattern_recorded: evolution_id={evolution_log.evolution_id}")
        except Exception as e:
            log.warning(f"pattern_record_failed: {e}")
    
    def get_best_strategy_for_criterion(self, criterion_id: str) -> Optional[str]:
        """Get the historically best strategy for a criterion."""
        criterion_patterns = self._pattern_cache.get("criterion_patterns", {}).get(criterion_id, {})
        best_strategies = criterion_patterns.get("best", [])
        
        if best_strategies:
            # Return most common best strategy
            from collections import Counter
            return Counter(best_strategies).most_common(1)[0][0]
        return None
    
    def get_strategies_to_avoid(self, criterion_id: str) -> list[str]:
        """Get strategies that historically failed for a criterion."""
        criterion_patterns = self._pattern_cache.get("criterion_patterns", {}).get(criterion_id, {})
        worst_strategies = criterion_patterns.get("worst", [])
        
        # Return strategies that failed more than once
        from collections import Counter
        return [s for s, count in Counter(worst_strategies).items() if count > 1]
    
    def is_repeated_failure(self, criterion_id: str, strategy: str) -> bool:
        """Check if this strategy has repeatedly failed for this criterion."""
        avoid = self.get_strategies_to_avoid(criterion_id)
        return strategy in avoid
    
    def get_overall_best_strategies(self, limit: int = 5) -> list[str]:
        """Get overall best performing strategies."""
        successful = self._pattern_cache.get("successful_strategies", {})
        sorted_strategies = sorted(
            successful.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        return [s[0] for s in sorted_strategies[:limit]]


# ─── Script Evolution Loop ──────────────────────────────────────────────────────

class ScriptEvolutionLoop:
    """
    Iterative script generation with self-evaluation.
    
    Continues until production readiness threshold is met.
    No maximum iterations - runs until quality achieved.
    
    LEARNING FEATURES:
    1. Tracks what improved in each iteration
    2. Records what didn't work
    3. Uses historical patterns for better decisions
    4. Detects stagnation and switches strategies
    5. Creates comprehensive evolution log
    
    USAGE:
        loop = ScriptEvolutionLoop()
        final_script = await loop.evolve(
            initial_prompt="Generate script about...",
            dossier=research_dossier,
            complexity=complexity_result
        )
        
        # Access learning data
        print(loop.evolution_log.improvements)
        print(loop.evolution_log.failures)
    """
    
    PRODUCTION_THRESHOLD = 0.85  # 85%
    STAGNATION_WINDOW = 5        # Check last N iterations for stagnation
    STAGNATION_THRESHOLD = 0.02  # Max score variance to be considered stagnant
    
    def __init__(
        self,
        router_client: Optional[RouterClient] = None,
        enable_persistence: bool = True,
    ):
        self.router = router_client
        self.generator = JHStyleGenerator(router_client)
        self.evaluator = SelfEvaluator(router_client)
        self.adjuster = PromptAdjuster()
        self.learner = PatternLearner()
        
        self._enable_persistence = enable_persistence
        self._state = EvolutionState() if enable_persistence else None
        
        # Evolution tracking
        self.evolution_id = f"evo_{uuid.uuid4().hex[:8]}"
        self.iteration = 0
        self.score_history: list[float] = []
        self.current_script: Optional[DualColumnScript] = None
        
        # Learning records
        self.evolution_log = EvolutionLog(
            evolution_id=self.evolution_id,
            topic="",
            started_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Previous scores for comparison
        self._previous_scores: dict[str, float] = {}
    
    async def evolve(
        self,
        initial_prompt: str,
        dossier: dict = None,
        complexity: ComplexityResult = None,
        topic: str = "",
        resume: bool = True,
    ) -> DualColumnScript:
        """
        Main evolution loop.
        
        Args:
            initial_prompt: The prompt for script generation
            dossier: Research dossier with facts and sources
            complexity: Complexity assessment (determines depth)
            topic: Topic statement for logging
            resume: Whether to resume from saved state
        
        Returns:
            Production-ready dual-column script
        
        Note:
            This loop has NO maximum iterations.
            It continues until the threshold is met.
        """
        # Set topic for logging
        self.evolution_log.topic = topic or initial_prompt[:100]
        
        log.info(
            f"evolution_started: id={self.evolution_id} "
            f"threshold={self.PRODUCTION_THRESHOLD*100}%"
        )
        
        # Check for resume
        if resume and self._state:
            saved_state = self._state.load(self.evolution_id)
            if saved_state:
                self._restore_state(saved_state)
                log.info(
                    f"evolution_resumed: iteration={self.iteration} "
                    f"score={self.score_history[-1] if self.score_history else 0:.1%}"
                )
        
        current_prompt = initial_prompt
        current_strategy = "initial_generation"
        
        # Main evolution loop - NO MAX ITERATIONS
        while True:
            self.iteration += 1
            
            log.info(f"evolution_iteration_{self.iteration}")
            
            # 1. GENERATE SCRIPT
            self.current_script = await self.generator.generate(
                prompt=current_prompt,
                dossier=dossier,
                complexity=complexity.to_dict() if complexity else None
            )
            
            # 2. EVALUATE
            evaluation = await self.evaluator.evaluate(
                script=self.current_script,
                research_data=dossier
            )
            
            overall_score = evaluation.overall_score
            self.score_history.append(overall_score)
            self.current_script.production_readiness_score = overall_score * 100
            
            # Record initial score
            if self.iteration == 1:
                self.evolution_log.initial_score = overall_score
            
            log.info(
                f"iteration_{self.iteration}_score: {overall_score*100:.1f}% "
                f"weak_areas: {evaluation.weak_areas}"
            )
            
            # 3. CHECK THRESHOLD
            if overall_score >= self.PRODUCTION_THRESHOLD:
                log.info(
                    f"evolution_complete: threshold_met after {self.iteration} iterations "
                    f"(score: {overall_score*100:.1f}%)"
                )
                self._finalize_evolution(overall_score, success=True)
                return self.current_script
            
            # 4. ANALYZE WHAT IMPROVED AND WHAT DIDN'T
            self._analyze_iteration(evaluation, current_strategy)
            
            # 5. RECORD DECISION
            decision = self._record_decision(evaluation, current_strategy)
            
            # 6. CHECK FOR STAGNATION
            if self._is_stagnating():
                log.warning(f"stagnation_detected at iteration {self.iteration}")
                current_strategy = self._choose_alternative_strategy(evaluation.weak_areas)
                current_prompt = self.adjuster.try_alternative_strategy(
                    current_prompt,
                    evaluation.weak_areas
                )
                decision.strategy_reason = "Stagnation detected, switching strategy"
            else:
                # 7. NORMAL ADJUSTMENT
                current_strategy = self._choose_strategy(evaluation.weak_areas)
                current_prompt = self.adjuster.adjust(
                    current_prompt=current_prompt,
                    weak_areas=evaluation.weak_areas,
                    detailed_scores={},  # Could pass detailed scores
                    iteration=self.iteration,
                    previous_script=self.current_script
                )
                decision.strategy_reason = f"Targeting weak areas: {evaluation.weak_areas}"
            
            # Update decision with expected improvement
            decision.expected_improvement = 0.1  # Expect 10% improvement
            self.evolution_log.decisions.append(decision)
            
            # 8. PERSIST STATE
            if self._enable_persistence and self._state:
                self._save_state(current_prompt, current_strategy)
            
            # 9. UPDATE PREVIOUS SCORES FOR NEXT ITERATION
            for result in evaluation.results:
                self._previous_scores[result.criterion_id] = result.score
    
    def _analyze_iteration(
        self,
        evaluation: SelfEvaluationReport,
        strategy_used: str
    ) -> None:
        """
        Analyze what improved and what didn't work.
        
        This is the core learning mechanism.
        """
        for result in evaluation.results:
            criterion_id = result.criterion_id
            current_score = result.score
            previous_score = self._previous_scores.get(criterion_id, current_score)
            
            # Check if this was a repeated failure
            is_repeated = self.learner.is_repeated_failure(criterion_id, strategy_used)
            
            if current_score > previous_score:
                # IMPROVEMENT - Record it
                improvement = ImprovementRecord(
                    iteration=self.iteration,
                    criterion_id=criterion_id,
                    criterion_name=result.criterion_name,
                    previous_score=previous_score,
                    new_score=current_score,
                    improvement_delta=current_score - previous_score,
                    strategy_used=strategy_used
                )
                self.evolution_log.improvements.append(improvement)
                
                log.info(
                    f"improvement_logged: {criterion_id} "
                    f"{previous_score:.2f} → {current_score:.2f} "
                    f"(+{current_score - previous_score:.2f})"
                )
            
            elif current_score < previous_score or (not result.passed and previous_score < 0.7):
                # FAILURE OR REGRESSION - Record it
                failure = FailureRecord(
                    iteration=self.iteration,
                    criterion_id=criterion_id,
                    criterion_name=result.criterion_name,
                    attempted_strategy=strategy_used,
                    why_failed=result.feedback or "Unknown reason",
                    repeated_failure=is_repeated,
                    alternative_approaches=self._get_alternative_approaches(criterion_id, strategy_used)
                )
                self.evolution_log.failures.append(failure)
                
                if is_repeated:
                    log.warning(
                        f"repeated_failure: {criterion_id} with strategy '{strategy_used}'"
                    )
    
    def _record_decision(
        self,
        evaluation: SelfEvaluationReport,
        strategy: str
    ) -> IterationDecision:
        """Record the decision made at this iteration."""
        
        # Find similar past situations
        similar_situations = []
        for criterion_id in evaluation.weak_areas:
            best_strategy = self.learner.get_best_strategy_for_criterion(criterion_id)
            if best_strategy:
                similar_situations.append(f"{criterion_id}: {best_strategy}")
        
        # Get applied learnings
        applied_learnings = []
        for criterion_id in evaluation.weak_areas:
            avoid = self.learner.get_strategies_to_avoid(criterion_id)
            if avoid:
                applied_learnings.append(f"Avoid {avoid} for {criterion_id}")
        
        return IterationDecision(
            iteration=self.iteration,
            current_score=evaluation.overall_score,
            weak_areas=evaluation.weak_areas,
            chosen_strategy=strategy,
            strategy_reason="",
            similar_past_situations=similar_situations,
            applied_learnings=applied_learnings
        )
    
    def _choose_strategy(self, weak_areas: list[str]) -> str:
        """Choose the best strategy based on weak areas and historical patterns."""
        
        # Check historical patterns first
        for criterion_id in weak_areas:
            best_strategy = self.learner.get_best_strategy_for_criterion(criterion_id)
            if best_strategy:
                log.info(f"strategy_chosen: {best_strategy} (historical best for {criterion_id})")
                return best_strategy
        
        # Default strategies based on weak area types
        if any(c.startswith('H') for c in weak_areas):  # Hook issues
            return "hook_enhancement"
        elif any(c.startswith('V') for c in weak_areas):  # Visual issues
            return "visual_first_approach"
        elif any(c.startswith('N') for c in weak_areas):  # Narrative issues
            return "structure_simplification"
        elif any(c.startswith('E') for c in weak_areas):  # Evidence issues
            return "evidence_strengthening"
        elif any(c.startswith('A') for c in weak_areas):  # Audience issues
            return "local_context_enhancement"
        
        return "general_improvement"
    
    def _choose_alternative_strategy(self, weak_areas: list[str]) -> str:
        """Choose an alternative strategy when stagnation is detected."""
        
        # Get strategies to avoid
        avoid = set()
        for criterion_id in weak_areas:
            avoid.update(self.learner.get_strategies_to_avoid(criterion_id))
        
        # Available alternative strategies
        alternatives = [
            "angle_change",
            "simplify_structure",
            "add_emotional_layer",
            "visual_first_approach",
            "fresh_start"
        ]
        
        # Choose first alternative not in avoid list
        for alt in alternatives:
            if alt not in avoid:
                log.info(f"alternative_strategy_chosen: {alt}")
                return alt
        
        # If all alternatives have failed, try fresh start
        return "fresh_start"
    
    def _get_alternative_approaches(self, criterion_id: str, failed_strategy: str) -> list[str]:
        """Get alternative approaches for a failed criterion."""
        
        # From historical data
        best_strategy = self.learner.get_best_strategy_for_criterion(criterion_id)
        
        alternatives = []
        if best_strategy and best_strategy != failed_strategy:
            alternatives.append(best_strategy)
        
        # From criterion type
        if criterion_id.startswith('H'):  # Hook
            alternatives.extend(["provocative_question", "surprising_statistic", "visual_contrast"])
        elif criterion_id.startswith('V'):  # Visual
            alternatives.extend(["animation_focus", "archive_footage", "data_visualization"])
        elif criterion_id.startswith('N'):  # Narrative
            alternatives.extend(["change_angle", "add_transition", "restructure"])
        
        return alternatives[:3]  # Return top 3 alternatives
    
    def _is_stagnating(self) -> bool:
        """Check if scores aren't improving significantly."""
        if len(self.score_history) < self.STAGNATION_WINDOW:
            return False
        
        recent = self.score_history[-self.STAGNATION_WINDOW:]
        variance = max(recent) - min(recent)
        
        # Also check if we're not improving relative to improvements logged
        recent_improvements = [
            i for i in self.evolution_log.improvements
            if i.iteration > self.iteration - self.STAGNATION_WINDOW
        ]
        
        return variance < self.STAGNATION_THRESHOLD and len(recent_improvements) < 2
    
    def _save_state(self, prompt: str, strategy: str) -> None:
        """Save evolution state for recovery."""
        state = {
            "evolution_id": self.evolution_id,
            "iteration": self.iteration,
            "score_history": self.score_history,
            "current_prompt": prompt,
            "current_strategy": strategy,
            "previous_scores": self._previous_scores,
            "evolution_log": self.evolution_log.to_dict()
        }
        self._state.save(self.evolution_id, state)
    
    def _restore_state(self, state: dict) -> None:
        """Restore evolution state from saved data."""
        self.iteration = state.get("iteration", 0)
        self.score_history = state.get("score_history", [])
        self._previous_scores = state.get("previous_scores", {})
        
        # Restore evolution log
        log_data = state.get("evolution_log", {})
        self.evolution_log.total_iterations = log_data.get("total_iterations", 0)
        self.evolution_log.initial_score = log_data.get("initial_score", 0)
    
    def _finalize_evolution(self, final_score: float, success: bool) -> None:
        """Finalize the evolution log and record patterns."""
        self.evolution_log.completed_at = datetime.now(timezone.utc).isoformat()
        self.evolution_log.final_score = final_score
        self.evolution_log.total_iterations = self.iteration
        self.evolution_log.threshold_reached = success
        
        # Summarize successful and failed strategies
        strategy_outcomes = {}
        for imp in self.evolution_log.improvements:
            strategy = imp.strategy_used
            if strategy not in strategy_outcomes:
                strategy_outcomes[strategy] = {"success": 0, "failure": 0}
            strategy_outcomes[strategy]["success"] += 1
        
        for fail in self.evolution_log.failures:
            strategy = fail.attempted_strategy
            if strategy not in strategy_outcomes:
                strategy_outcomes[strategy] = {"success": 0, "failure": 0}
            strategy_outcomes[strategy]["failure"] += 1
        
        for strategy, outcomes in strategy_outcomes.items():
            if outcomes["success"] > outcomes["failure"]:
                self.evolution_log.successful_strategies.append(strategy)
            else:
                self.evolution_log.failed_strategies.append(strategy)
        
        # Record for future learning
        self.learner.record_evolution(self.evolution_log)
        
        # Clear state if persisted
        if self._state:
            self._state.clear(self.evolution_id)
        
        # Log summary
        log.info(
            f"evolution_log_saved: {len(self.evolution_log.improvements)} improvements, "
            f"{len(self.evolution_log.failures)} failures, "
            f"successful_strategies={self.evolution_log.successful_strategies}"
        )
    
    def get_learning_summary(self) -> dict:
        """Get a summary of learnings from this evolution cycle."""
        return {
            "evolution_id": self.evolution_id,
            "total_iterations": self.iteration,
            "score_improvement": (
                self.score_history[-1] - self.score_history[0]
                if len(self.score_history) > 1 else 0
            ),
            "improvements_by_criterion": {
                criterion_id: sum(i.improvement_delta for i in self.evolution_log.improvements if i.criterion_id == criterion_id)
                for criterion_id in set(i.criterion_id for i in self.evolution_log.improvements)
            },
            "failures_by_criterion": {
                criterion_id: len([f for f in self.evolution_log.failures if f.criterion_id == criterion_id])
                for criterion_id in set(f.criterion_id for f in self.evolution_log.failures)
            },
            "successful_strategies": self.evolution_log.successful_strategies,
            "failed_strategies": self.evolution_log.failed_strategies,
            "stagnation_encountered": self._is_stagnating()
        }
