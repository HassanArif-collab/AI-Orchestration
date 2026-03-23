"""Phase 4 Auto-Research Loop: Scoring Engine.

Loads the evaluation suite and scores a given AdaptedScript
against all applicable binary questions based on its genre.
"""

import json
import re
from pathlib import Path

from packages.core.logger import get_logger
from packages.router.client import RouterClient
from ..models import AdaptedScript, SelfCheckResult

logger = get_logger(__name__)

CONTENT_FACTORY_DIR = Path(__file__).parent.parent
GENRE_SCHEMA_PATH = CONTENT_FACTORY_DIR / "genre_schema.json"
EVALUATION_SUITE_PATH = CONTENT_FACTORY_DIR / "evaluation_suite.json"


def _load_json(p: Path) -> dict:
    if not p.exists():
        return {}
    return json.loads(p.read_text("utf-8"))


class ScoringEngine:
    """Evaluates a dual-column script against 70 binary questions."""

    def __init__(self) -> None:
        self.genre_schema = _load_json(GENRE_SCHEMA_PATH)
        self.eval_suite = _load_json(EVALUATION_SUITE_PATH)

    def _get_applicable_questions(self, genre_id: str) -> list[dict]:
        """Get all universal + genre-specific questions for this script."""
        categories = []
        for g in self.genre_schema.get("genres", []):
            if g["genre_id"] == genre_id:
                categories = g["universal_question_categories"] + g["genre_specific_question_categories"]
                break

        if not categories:
            # Fallback to universal only if genre not found
            genres = self.genre_schema.get("genres", [])
            if genres:
                categories = genres[0]["universal_question_categories"]

        questions = []
        for q in self.eval_suite.get("questions", []):
            if q["category"] in categories:
                questions.append(q)

        return questions

    async def score_script(
        self,
        script: AdaptedScript,
        router_client: RouterClient | None = None
    ) -> AdaptedScript:
        """Run the LLM to answer all binary questions for this script.

        Updates the script's self_check_results and production_readiness_score in place.
        """
        questions = self._get_applicable_questions(script.genre)
        logger.info(f"scoring_engine: Evaluating {len(questions)} questions for {script.video_id} (Genre: {script.genre})")

        q_list_text = "\n".join([f"{q['id']}: {q['text']}" for q in questions])
        
        system_prompt = """
        You are the ultimate Quality Assurance Engine for a Johnny harris-style documentary pipeline.
        Evaluate the provided dual-column script against the numbered list of binary questions.

        For EVERY question, you must return a 1 (Pass) or 0 (Fail). No partial scores or ranges.
        If it fails, provide a very short string for "failure_reason".
        
        Output valid JSON exactly matching this schema:
        {
            "results": [
                {
                    "question_id": "A1",
                    "passed": true,
                    "failure_reason": null
                }
            ]
        }
        """

        user_prompt = f"""
        Questions to evaluate:
        {q_list_text}
        
        Script to evaluate:
        {script.model_dump_json(include={'entries'}, exclude_none=True)}
        """

        try:
            async with RouterClient() if not router_client else router_client as client:
                response_text = await client.complete_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    model="auto",
                    temperature=0.0
                )

                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if not json_match:
                    raise ValueError("Could not extract JSON from Scoring Engine response")

                data = json.loads(json_match.group(0))

        except Exception as e:
            logger.error(f"scoring_engine_failed: {e}")
            # Mock failure evaluation
            return script

        # Parse and apply results
        check_results = []
        passed_count = 0
        q_map = {q["id"]: q["text"] for q in questions}

        for res in data.get("results", []):
            qid = res.get("question_id")
            if qid not in q_map:
                continue
                
            passed = res.get("passed", False)
            if passed:
                passed_count += 1
                
            check_results.append(SelfCheckResult(
                question_id=qid,
                question_text=q_map[qid],
                passed=passed,
                failure_reason=res.get("failure_reason") if not passed else None
            ))

        readiness = (passed_count / len(questions) * 100) if questions else 0.0

        script.self_check_results = check_results
        script.production_readiness_score = readiness

        logger.info(f"scoring_engine_complete: {script.video_id} scored {readiness:.1f}% ({passed_count}/{len(questions)})")
        return script
