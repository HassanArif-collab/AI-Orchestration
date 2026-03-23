"""Phase 4 Auto-Research Loop: Challenger Generator.

Accepts a baseline script, identifies a single mutation zone
(Script Prose, Visual Direction, Structural Architecture), and
re-writes that specific zone using LLM to fix failed evaluation questions.
"""

import json
import re
from packages.core.logger import get_logger
from packages.router.client import RouterClient
from ..models import AdaptedScript, DualColumnEntry

logger = get_logger(__name__)


class ChallengerGenerator:
    """Mutates baseline scripts to generate competitive challengers."""

    ZONES = {
        "script_prose": ["C", "F"],  # Prose styling and conclusion tone
        "visual_direction": ["B", "E"], # Anchor quality and coding rules
        "structural_architecture": ["D"], # Anchor-bridge structures
    }

    async def generate_challenger(
        self,
        baseline: AdaptedScript,
        mutation_zone: str,
        router_client: RouterClient | None = None
    ) -> AdaptedScript:
        """Generate a mutated script targeting a specific zone's failures.
        
        Args:
            baseline: The script to mutate.
            mutation_zone: 'script_prose', 'visual_direction', or 'structural_architecture'.
        """
        if mutation_zone not in self.ZONES:
            raise ValueError(f"Invalid mutation zone: {mutation_zone}")

        target_categories = self.ZONES[mutation_zone]
        
        # Identify failed questions in this zone
        failed_checks = [
            c for c in baseline.self_check_results 
            if not c.passed and any(c.question_id.startswith(cat) for cat in target_categories)
        ]
        
        if not failed_checks:
            logger.warning(f"mutation_skipped: No failures in zone {mutation_zone} for {baseline.video_id}")
            return baseline  # No mutation if no failures in this zone
            
        failures_text = "\n".join([f"- {c.question_id}: {c.question_text} (Reason: {c.failure_reason})" for c in failed_checks])
        
        system_prompt = """
        You are the Auto-Research Challenger Generator for a documentary AI system.
        You take a baseline dual-column script and mutate EXACTLY ONE ZONE to fix specific failures.
        
        DO NOT change any part of the script outside the specified mutation zone.
        You must return the ENTIRE script (all entries) as valid JSON matching this schema:
        {
          "entries": [
            {
              "section_label": "HOOK",
              "prose": "spoken narration",
              "visual_direction": "visual plan details",
              "visual_type": "talking_head"
            }
          ]
        }
        """

        user_prompt = f"""
        MUTATION ZONE: {mutation_zone}
        
        To beat the baseline score, you must fix these specific test failures in this script:
        {failures_text}
        
        Baseline Script:
        {baseline.model_dump_json(include={'entries'}, exclude_none=True)}
        """

        try:
            async with RouterClient() if not router_client else router_client as client:
                response_text = await client.complete_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    model="auto"
                )

                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if not json_match:
                    raise ValueError("Could not extract JSON from Challenger Generator")

                data = json.loads(json_match.group(0))

        except Exception as e:
            logger.error(f"mutation_failed: {e}")
            return baseline

        # Build new script
        entries = []
        for item in data.get("entries", []):
            try:
                # Merge original fields that shouldn't be touched by the LLM
                entries.append(DualColumnEntry(**item))
            except Exception:
                pass
                
        if len(entries) < len(baseline.entries) * 0.5:
            logger.error("mutation_failed: LLM truncated script heavily. Aborting mutation.")
            return baseline

        # Copy baseline and update only the core content
        challenger = baseline.model_copy(deep=True)
        challenger.entries = entries
        challenger.video_id = f"mutated_{baseline.video_id[:8]}"
        
        # Reset check results (Scoring Engine will recalculate)
        challenger.self_check_results = []
        challenger.production_readiness_score = 0.0

        logger.info(f"challenger_generated: {challenger.video_id} (mutated zone: {mutation_zone})")
        return challenger
