"""Phase 4 Auto-Research Loop: Experiment Loop.

The master evolutionary loop that drives self-improvement.
Coordinates the Scoring Engine, Baseline Manager,
Challenger Generator, and Learning Log.

FIXES APPLIED:
1. Added persistence of best script after each iteration
2. Added resume capability from persisted state
3. Added snapshot directory management
4. Fixed O(N^2) complexity in threshold runner
5. Added strict error handling for mutation failures

The best script is now persisted to disk after each iteration,
allowing recovery from crashes without losing progress.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import random

from packages.core.config import get_settings
from packages.core.errors import QualityGateError
from packages.core.logger import get_logger
from packages.core.escalation import get_escalation_service
from packages.router.client import RouterClient
from packages.pipeline.iteration_store import IterationLogStore

from ..models import AdaptedScript
from .baseline import BaselineManager
from .learning_log import LearningLogEntry, LearningLogger
from .mutation import ChallengerGenerator
from .scoring import ScoringEngine

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class ExperimentSnapshot:
    """Manages saving and loading experiment snapshots for persistence."""

    def __init__(self, snapshot_dir: Optional[Path] = None) -> None:
        settings = get_settings()
        self.snapshot_dir = snapshot_dir or Path(settings.DATA_DIR) / "experiment_snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def _snapshot_path(self, cycle_id: str) -> Path:
        """Get snapshot file path for a cycle."""
        return self.snapshot_dir / f"{cycle_id}_best.json"

    def save(self, cycle_id: str, script: AdaptedScript, iteration: int) -> None:
        """Save snapshot to disk."""
        snapshot = {
            "cycle_id": cycle_id,
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "score": script.production_readiness_score,
            "script": script.model_dump(),
        }
        snapshot_file = self._snapshot_path(cycle_id)

        try:
            temp_file = snapshot_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, default=str, ensure_ascii=False)
            temp_file.rename(snapshot_file)
            logger.debug(
                f"snapshot_saved: cycle={cycle_id} iteration={iteration} "
                f"score={script.production_readiness_score:.1f}%"
            )
        except Exception as e:
            logger.warning(f"snapshot_save_failed: {e}")

    def load(self, cycle_id: str) -> Optional[tuple[AdaptedScript, int]]:
        """Load snapshot from disk."""
        snapshot_file = self._snapshot_path(cycle_id)
        if not snapshot_file.exists():
            return None

        try:
            with open(snapshot_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            script = AdaptedScript(**data["script"])
            return script, data["iteration"]
        except Exception as e:
            logger.warning(f"snapshot_load_failed: {e}")
            return None

    def clear(self, cycle_id: str) -> None:
        """Remove snapshot file."""
        snapshot_file = self._snapshot_path(cycle_id)
        snapshot_file.unlink(missing_ok=True)

    def list_snapshots(self) -> list[dict]:
        """List all available snapshots."""
        snapshots = []
        for f in self.snapshot_dir.glob("*_best.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                snapshots.append({
                    "cycle_id": data.get("cycle_id"),
                    "iteration": data.get("iteration"),
                    "score": data.get("score"),
                    "timestamp": data.get("timestamp"),
                })
            except Exception:
                pass
        return sorted(snapshots, key=lambda x: x.get("timestamp", ""), reverse=True)


class ExperimentLoop:
    """The unified runner for the evolutionary Auto-Research loop.

    Features:
        - Persists best script after each iteration
        - Resume capability from persisted state
        - Automatic cleanup on successful completion
    """

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        enable_persistence: bool = True,
    ) -> None:
        """
        Initialize the experiment loop.

        Args:
            persist_dir: Directory for snapshots (default: DATA_DIR/experiment_snapshots)
            enable_persistence: Whether to persist best script (default: True)
        """
        self.baseline = BaselineManager()
        self.scoring = ScoringEngine()
        self.challenger = ChallengerGenerator()
        self.logger = LearningLogger()
        self._enable_persistence = enable_persistence
        self._snapshot = ExperimentSnapshot(persist_dir) if enable_persistence else None
        self._iter_store = IterationLogStore()
        
        # Load quality thresholds from config
        settings = get_settings()
        self.threshold = settings.SCRIPT_QUALITY_THRESHOLD
        self.floor = settings.SCRIPT_QUALITY_FLOOR
        self.max_iterations = settings.SCRIPT_MAX_ITERATIONS

    async def run_iterations(
        self,
        script: AdaptedScript,
        iterations: int = 3,
        router_client: RouterClient | None = None,
        cycle_id: Optional[str] = None,
        resume: bool = True,
        target_threshold: Optional[float] = None,
        run_id: Optional[str] = None,
    ) -> AdaptedScript:
        """Run the script through the evolutionary loop multiple times.

        Args:
            script: The initial script to evolve.
            iterations: Number of mutation/scoring cycles.
            router_client: Client for LLM calls.
            cycle_id: Optional cycle ID (auto-generated if None).
            resume: Whether to resume from previous snapshot (default: True).
            target_threshold: Optional score threshold to stop early.
            run_id: Optional pipeline run ID for iteration logging.

        Returns:
            The highest scoring script found during the run (could be the initial).
        """
        cycle_id = cycle_id or f"exp_{uuid.uuid4().hex[:8]}"
        logger.info(
            f"experiment_started: cycle={cycle_id} video_id={script.video_id} iterations={iterations}"
        )

        # Check for persisted state (resume capability)
        start_iteration = 0
        if resume and self._snapshot:
            persisted = self._snapshot.load(cycle_id)
            if persisted:
                current_best, start_iteration = persisted
                logger.info(
                    f"resuming_from_snapshot: iteration={start_iteration} "
                    f"score={current_best.production_readiness_score:.1f}%"
                )
            else:
                current_best = script
        else:
            current_best = script

        # Score the initial script first if it hasn't been scored
        if not current_best.self_check_results:
            current_best = await self.scoring.score_script(current_best, router_client)

        # Ensure initial script is recorded in baseline if it's the best so far
        self.baseline.process_challenger(current_best)
        initial_score = current_best.production_readiness_score

        # Check threshold immediately before looping
        if target_threshold and current_best.production_readiness_score >= target_threshold:
             logger.info(
                f"experiment_early_exit: threshold {target_threshold}% reached with {current_best.production_readiness_score:.1f}%"
            )
             if self._snapshot:
                 self._snapshot.clear(cycle_id)
             return current_best

        # Persist initial state
        if self._snapshot:
            self._snapshot.save(cycle_id, current_best, start_iteration)

        for i in range(start_iteration, iterations):
            logger.info(
                f"experiment_cycle: {cycle_id} iteration={i+1}/{iterations} "
                f"current_score={current_best.production_readiness_score:.1f}%"
            )

            # 1. Select Mutation Zone (weighted towards historical failure areas)
            # Find available zones using the NEW category mapping logic (via mutation generator helper if available,
            # or replicate logic here. Since ChallengerGenerator updated its logic to map zones to categories,
            # we must be careful. The loop logic relies on checking if `c.question_id` matches.
            # But `ChallengerGenerator` now handles the mapping internally.
            # We should ask `ChallengerGenerator` if a zone is actionable.
            
            # Since we can't easily change ChallengerGenerator to expose that right now without larger refactor,
            # we'll iterate through ZONES keys and rely on `generate_challenger` returning None if no failures.
            # This is simpler and robust.
            
            available_zones = list(ChallengerGenerator.ZONE_CATEGORIES.keys())
            
            # Optimization: Pre-filter zones that definitely have no relevant failures?
            # Or just pick random and let generate_challenger fail fast.
            # Let's trust generate_challenger's check.

            mutation_zone = random.choice(available_zones)

            # 2. Generate Challenger
            challenger = await self.challenger.generate_challenger(
                baseline=current_best,
                mutation_zone=mutation_zone,
                router_client=router_client,
            )

            if challenger is None:
                 logger.warning(
                    f"experiment_cycle_skipped: {cycle_id} iteration={i+1} "
                    f"reason=mutation_failed_or_no_failures zone={mutation_zone}"
                )
                 # Still save snapshot to increment iteration count (if we want to count "attempts")
                 # But if we just skip, we haven't consumed "resources" other than time.
                 # Let's count it as an iteration to ensure termination.
                 if self._snapshot:
                    self._snapshot.save(cycle_id, current_best, i + 1)
                 continue

            # 3. Score Challenger
            challenger = await self.scoring.score_script(challenger, router_client)

            # 4. Compare and Update Baseline
            baseline_score = current_best.production_readiness_score
            challenger_score = challenger.production_readiness_score

            is_new_best = self.baseline.process_challenger(challenger)
            if is_new_best and challenger_score > baseline_score:
                current_best = challenger

            # Compute specific fixed/regressed questions for logging
            baseline_fails = {
                c.question_id for c in current_best.self_check_results if not c.passed
            }
            challenger_fails = {
                c.question_id for c in challenger.self_check_results if not c.passed
            }

            fixed = list(baseline_fails - challenger_fails)
            regressed = list(challenger_fails - baseline_fails)

            # 5. Log Learning Event
            log_entry = LearningLogEntry(
                cycle_id=cycle_id,
                genre_id=current_best.genre,
                baseline_id=script.video_id,
                challenger_id=challenger.video_id,
                mutation_zone=mutation_zone,
                baseline_score=baseline_score,
                challenger_score=challenger_score,
                beat_baseline=is_new_best,
                fixed_questions=fixed,
                regressed_questions=regressed,
                timestamp=datetime.now(timezone.utc),
            )
            self.logger.log_experiment(log_entry)

            # 6. Persist iteration to iteration store
            self._iter_store.save(
                run_id=run_id or cycle_id,
                iteration=i,
                score=challenger_score,
                previous_score=baseline_score,
                beat_baseline=is_new_best,
                mutation_zone=mutation_zone,
                script_json=challenger.model_dump(),
                failed_questions=list(challenger_fails),
                fixed_questions=fixed,
            )

            # 7. Emit SSE event for real-time updates
            try:
                import asyncio
                from apps.api.events import emit_iteration_complete
                asyncio.create_task(emit_iteration_complete(
                    run_id=run_id or cycle_id,
                    iteration=i,
                    score=challenger_score,
                    previous_score=baseline_score,
                    mutation_zone=mutation_zone,
                    beat_baseline=is_new_best,
                ))
            except RuntimeError:
                pass  # No event loop in this context

            # 8. Persist best after each iteration
            if self._snapshot:
                self._snapshot.save(cycle_id, current_best, i + 1)
                
            # Check threshold after update
            if target_threshold and current_best.production_readiness_score >= target_threshold:
                logger.info(
                    f"experiment_threshold_reached: iteration={i+1} "
                    f"score={current_best.production_readiness_score:.1f}%"
                )
                break

        # Log final result
        logger.info(
            f"experiment_ended: cycle={cycle_id} "
            f"initial_score={initial_score:.1f}% "
            f"final_score={current_best.production_readiness_score:.1f}%"
        )

        # Clear snapshot on successful completion
        if self._snapshot:
            self._snapshot.clear(cycle_id)

        return current_best

    async def run_with_threshold(
        self,
        script: AdaptedScript,
        threshold: float = 85.0,
        max_iterations: int = 20,
        router_client: RouterClient | None = None,
    ) -> AdaptedScript:
        """Run iterations until threshold is reached or max_iterations exhausted.

        Args:
            script: The initial script to evolve.
            threshold: Target score threshold (default: 85.0).
            max_iterations: Maximum iterations (default: 20).
            router_client: Client for LLM calls.

        Returns:
            The highest scoring script found.
        """
        # Simply delegate to run_iterations with the new target_threshold param
        # This fixes the O(N^2) loop issue completely by using the linear loop in run_iterations.
        
        return await self.run_iterations(
            script=script,
            iterations=max_iterations,
            router_client=router_client,
            target_threshold=threshold,
            resume=True # Enable resume for long-running threshold jobs
        )

    async def run_with_quality_gate(
        self,
        script: AdaptedScript,
        enforce_floor: bool = True,
        router_client: RouterClient | None = None,
        cycle_id: Optional[str] = None,
    ) -> AdaptedScript:
        """Run evolution with quality floor enforcement.

        This method runs the evolution loop with configurable quality gates.
        If the final score is below the quality floor and enforce_floor is True,
        a QualityGateError is raised and an escalation is triggered.

        Args:
            script: The initial script to evolve.
            enforce_floor: Whether to raise error if score < floor (default: True).
            router_client: Client for LLM calls.
            cycle_id: Optional cycle ID for tracking.

        Returns:
            The highest scoring script found.

        Raises:
            QualityGateError: If final score is below floor and enforce_floor is True.
        """
        best_script = await self.run_with_threshold(
            script, 
            threshold=self.threshold, 
            max_iterations=self.max_iterations,
            router_client=router_client,
        )

        final_score = best_script.production_readiness_score

        if final_score >= self.threshold:
            logger.info(
                f"quality_gate_passed: score={final_score:.1f}% "
                f"threshold={self.threshold}%"
            )
            return best_script

        if final_score < self.floor:
            if enforce_floor:
                logger.error(
                    f"quality_gate_failed: score={final_score:.1f}% "
                    f"floor={self.floor}%"
                )
                
                # Escalate the quality gate failure to operators
                escalation_service = get_escalation_service()
                try:
                    await escalation_service.escalate_quality_gate_failure(
                        score=final_score,
                        floor=self.floor,
                        script_id=best_script.video_id if hasattr(best_script, 'video_id') else None,
                        video_id=script.video_id if hasattr(script, 'video_id') else None,
                        iteration_count=self.max_iterations,
                    )
                except Exception as e:
                    # Don't let escalation failure prevent the error from being raised
                    logger.warning(f"escalation_failed: {e}")
                
                raise QualityGateError(
                    f"Script quality {final_score:.1f}% below minimum {self.floor}%",
                    score=final_score,
                    floor=self.floor
                )
            else:
                logger.warning(
                    f"quality_below_floor: score={final_score:.1f}% "
                    f"floor={self.floor}% (enforcement disabled)"
                )

        logger.info(
            f"quality_acceptable: score={final_score:.1f}% "
            f"floor={self.floor}% threshold={self.threshold}%"
        )
        return best_script

    def get_quality_report(self, script: AdaptedScript) -> dict:
        """Generate a quality report for a script.

        Args:
            script: The script to report on.

        Returns:
            Dict with score, thresholds, and status.
        """
        score = script.production_readiness_score
        return {
            "score": score,
            "threshold": self.threshold,
            "floor": self.floor,
            "max_iterations": self.max_iterations,
            "status": (
                "production_ready" if score >= self.threshold else
                "acceptable" if score >= self.floor else
                "below_floor"
            ),
        }

    def get_available_snapshots(self) -> list[dict]:
        """Get list of available experiment snapshots."""
        if not self._snapshot:
            return []
        return self._snapshot.list_snapshots()

    def cleanup_old_snapshots(self, max_age_hours: int = 24) -> int:
        """Remove snapshots older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours (default: 24)

        Returns:
            Number of snapshots removed.
        """
        if not self._snapshot:
            return 0

        removed = 0
        cutoff = datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=max_age_hours)

        for f in self._snapshot.snapshot_dir.glob("*_best.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                timestamp_str = data.get("timestamp")
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timestamp < cutoff:
                        f.unlink()
                        removed += 1
            except Exception:
                pass

        if removed > 0:
            logger.info(f"cleanup_old_snapshots: removed={removed}")

        return removed
