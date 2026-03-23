"""Phase 4 Auto-Research Loop: Experiment Loop.

The master evolutionary loop that drives self-improvement.
Coordinates the Scoring Engine, Baseline Manager,
Challenger Generator, and Learning Log.
"""

import uuid
from datetime import datetime, timezone
import random

from packages.core.logger import get_logger
from packages.router.client import RouterClient

from ..models import AdaptedScript
from .baseline import BaselineManager
from .learning_log import LearningLogEntry, LearningLogger
from .mutation import ChallengerGenerator
from .scoring import ScoringEngine

logger = get_logger(__name__)


class ExperimentLoop:
    """The unified runner for the evolutionary Auto-Research loop."""

    def __init__(self) -> None:
        self.baseline = BaselineManager()
        self.scoring = ScoringEngine()
        self.challenger = ChallengerGenerator()
        self.logger = LearningLogger()

    async def run_iterations(
        self,
        script: AdaptedScript,
        iterations: int = 3,
        router_client: RouterClient | None = None
    ) -> AdaptedScript:
        """Run the script through the evolutionary loop multiple times.
        
        Args:
            script: The initial script to evolve.
            iterations: Number of mutation/scoring cycles.
            router_client: Client for LLM calls.
            
        Returns:
            The highest scoring script found during the run (could be the initial).
        """
        cycle_id = f"exp_{uuid.uuid4().hex[:8]}"
        logger.info(f"experiment_started: cycle={cycle_id} video_id={script.video_id} iterations={iterations}")

        current_best = script

        # Score the initial script first if it hasn't been scored
        if not current_best.self_check_results:
            current_best = await self.scoring.score_script(current_best, router_client)

        # Ensure initial script is recorded in baseline if it's the best so far
        self.baseline.process_challenger(current_best)
        initial_score = current_best.production_readiness_score

        for i in range(iterations):
            logger.info(f"experiment_cycle: {cycle_id} iteration={i+1}/{iterations} current_score={current_best.production_readiness_score:.1f}%")

            # 1. Select Mutation Zone (weighted towards historical failure areas)
            # For simplicity, we just pick a zone that actually has failures in the current best
            available_zones = []
            for zone, categories in ChallengerGenerator.ZONES.items():
                if any(not c.passed and any(c.question_id.startswith(cat) for cat in categories) 
                       for c in current_best.self_check_results):
                    available_zones.append(zone)
            
            if not available_zones:
                logger.info(f"experiment_completed: {cycle_id} - Perfect score achieved or no mutatable zones left.")
                break
                
            mutation_zone = random.choice(available_zones)
            
            # 2. Generate Challenger
            challenger = await self.challenger.generate_challenger(
                baseline=current_best,
                mutation_zone=mutation_zone,
                router_client=router_client
            )
            
            # 3. Score Challenger
            challenger = await self.scoring.score_script(challenger, router_client)
            
            # 4. Compare and Update Baseline
            baseline_score = current_best.production_readiness_score
            challenger_score = challenger.production_readiness_score
            
            is_new_best = self.baseline.process_challenger(challenger)
            if is_new_best and challenger_score > baseline_score:
                current_best = challenger
                
            # Compute specific fixed/regressed questions for logging
            baseline_fails = {c.question_id for c in current_best.self_check_results if not c.passed}
            challenger_fails = {c.question_id for c in challenger.self_check_results if not c.passed}
            
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
                timestamp=datetime.now(timezone.utc)
            )
            self.logger.log_experiment(log_entry)

        logger.info(f"experiment_ended: cycle={cycle_id} initial_score={initial_score:.1f}% final_score={current_best.production_readiness_score:.1f}%")
        return current_best
