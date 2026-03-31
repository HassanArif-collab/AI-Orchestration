"""Phase 4 Auto-Research Loop: Challenger Generator.

Accepts a baseline script, identifies a single mutation zone
(Script Prose, Visual Direction, Structural Architecture), and
re-writes that specific zone using LLM to fix failed evaluation questions.
"""

import json
from pathlib import Path
from typing import Optional

from packages.core.logger import get_logger
from packages.router.client import RouterClient
from ..models import AdaptedScript, DualColumnEntry

logger = get_logger(__name__)

CONTENT_FACTORY_DIR = Path(__file__).parent.parent
EVALUATION_SUITE_PATH = CONTENT_FACTORY_DIR / "evaluation_suite.json"


def _load_json(p: Path) -> dict:
    if not p.exists():
        return {}
    return json.loads(p.read_text("utf-8"))


class ChallengerGenerator:
    """Mutates baseline scripts to generate competitive challengers."""

    # Map mutation zones to Evaluation Suite categories (NOT ID prefixes)
    ZONE_CATEGORIES = {
        "script_prose": ["script_prose_quality", "conclusion_quality"],
        "visual_direction": ["visual_anchor_quality", "dual_column_coding_quality"],
        "structural_architecture": ["anchor_bridge_structure"],
    }

    def __init__(self) -> None:
        self.eval_suite = _load_json(EVALUATION_SUITE_PATH)
        self.category_question_map = self._build_category_map()

    def _build_category_map(self) -> dict[str, set[str]]:
        """Map category names to sets of Question IDs."""
        mapping = {}
        for q in self.eval_suite.get("questions", []):
            cat = q.get("category")
            qid = q.get("id")
            if cat and qid:
                if cat not in mapping:
                    mapping[cat] = set()
                mapping[cat].add(qid)
        return mapping

    def _get_target_question_ids(self, zone: str) -> set[str]:
        """Get all question IDs relevant to a mutation zone."""
        categories = self.ZONE_CATEGORIES.get(zone, [])
        target_ids = set()
        for cat in categories:
            target_ids.update(self.category_question_map.get(cat, set()))
        return target_ids

    async def generate_challenger(
        self,
        baseline: AdaptedScript,
        mutation_zone: str,
        router_client: RouterClient | None = None
    ) -> Optional[AdaptedScript]:
        """Generate a mutated script targeting a specific zone's failures.

        Args:
            baseline: The script to mutate.
            mutation_zone: 'script_prose', 'visual_direction', or 'structural_architecture'.

        Returns:
            New AdaptedScript or None if mutation failed/invalid.
        """
        if mutation_zone not in self.ZONE_CATEGORIES:
            raise ValueError(f"Invalid mutation zone: {mutation_zone}")

        target_ids = self._get_target_question_ids(mutation_zone)

        # Identify failed questions in this zone
        failed_checks = [
            c for c in baseline.self_check_results
            if not c.passed and c.question_id in target_ids
        ]

        if not failed_checks:
            logger.warning(f"mutation_skipped: No failures in zone {mutation_zone} for {baseline.video_id}")
            return None

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
              "visual_type": "talking_head",
              "duration_estimate_seconds": 15.0,
              "anchor_hierarchy_level": 1
            }
          ]
        }

        IMPORTANT: You MUST copy these fields exactly from the baseline for each entry:
        - duration_estimate_seconds
        - anchor_hierarchy_level
        If the baseline entry has these fields, include them in your output unchanged.
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
                    model="groq/llama-3.3-70b-versatile"  # Llama 70b for fast challenger generation
                )

                from packages.core.json_utils import extract_json_object
                json_str = extract_json_object(response_text)
                if not json_str:
                    raise ValueError("Could not extract JSON from Challenger Generator")

                data = json.loads(json_str)

        except Exception as e:
            logger.error(f"mutation_failed_llm_error: {e}")
            return None

        # Build new script with STRICT validation
        entries = []
        raw_entries = data.get("entries", [])
        
        if not isinstance(raw_entries, list):
             logger.error("mutation_failed_structure: 'entries' is not a list")
             return None

        for idx, item in enumerate(raw_entries):
            try:
                # Merge with baseline entry to preserve fields LLM might omit
                if idx < len(baseline.entries):
                    merged = {**baseline.entries[idx].model_dump(), **item}
                    entries.append(DualColumnEntry(**merged))
                else:
                    entries.append(DualColumnEntry(**item))
            except Exception as e:
                logger.error(f"mutation_failed_validation: Entry {idx} invalid: {e}")
                return None # Fail whole batch on single entry failure

        # Validate truncation (90% threshold)
        if len(entries) < len(baseline.entries) * 0.9:
            logger.error(f"mutation_failed_truncation: Returned {len(entries)} entries, expected ~{len(baseline.entries)}")
            return None

        # Copy baseline and update only the core content
        challenger = baseline.model_copy(deep=True)
        challenger.entries = entries
        challenger.video_id = f"mutated_{baseline.video_id[:8]}"

        # Reset check results (Scoring Engine will recalculate)
        challenger.self_check_results = []
        challenger.production_readiness_score = 0.0

        logger.info(f"challenger_generated: {challenger.video_id} (mutated zone: {mutation_zone})")
        return challenger
