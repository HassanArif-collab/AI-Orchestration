"""
Self-Evaluator Module

Evaluates scripts against quality criteria.
Each criterion has specific questions to answer.

The evaluation covers:
- Hook effectiveness
- Visual storytelling
- Narrative flow
- Evidence quality
- Audience connection
"""

import json
import re
from typing import Any

from packages.core.logger import get_logger
from packages.router.client import RouterClient
from .models import DualColumnScript, EvaluationResult, SelfEvaluationReport

log = get_logger(__name__)


# ─── Evaluation Criteria ─────────────────────────────────────────────────────────

EVALUATION_CRITERIA = {
    "hook_effectiveness": {
        "weight": 0.20,
        "description": "How well the opening captures attention",
        "questions": [
            {
                "id": "H1",
                "text": "Does the first line create immediate curiosity?",
                "guidance": "Look for questions, surprising statements, or knowledge gaps"
            },
            {
                "id": "H2",
                "text": "Is there a clear knowledge gap established?",
                "guidance": "The viewer should want to know something they don't know"
            },
            {
                "id": "H3",
                "text": "Would a viewer want to keep watching after 5 seconds?",
                "guidance": "The hook should create momentum within the first sentence"
            },
            {
                "id": "H4",
                "text": "Is the mainstream assumption stated or implied?",
                "guidance": "There should be a contrast to what people commonly believe"
            }
        ]
    },
    
    "visual_storytelling": {
        "weight": 0.20,
        "description": "How well the script translates to visuals",
        "questions": [
            {
                "id": "V1",
                "text": "Can each section be shown visually?",
                "guidance": "Every narration should have a corresponding visual direction"
            },
            {
                "id": "V2",
                "text": "Are there specific visual directions for each point?",
                "guidance": "Visual directions should be concrete (e.g., 'Close-up of the document' not 'Show the document')"
            },
            {
                "id": "V3",
                "text": "Do visual directions complement the narration?",
                "guidance": "Visuals should enhance, not just repeat, what's being said"
            },
            {
                "id": "V4",
                "text": "Is there variety in visual types?",
                "guidance": "Mix of B-roll, graphics, archive footage, animations"
            }
        ]
    },
    
    "narrative_flow": {
        "weight": 0.20,
        "description": "How well the story progresses",
        "questions": [
            {
                "id": "N1",
                "text": "Does the story progress logically?",
                "guidance": "Each section should build on the previous one"
            },
            {
                "id": "N2",
                "text": "Are transitions smooth between sections?",
                "guidance": "No jarring jumps between topics"
            },
            {
                "id": "N3",
                "text": "Is there a clear beginning, middle, and end?",
                "guidance": "Hook → Investigation → Reveal → Conclusion"
            },
            {
                "id": "N4",
                "text": "Does complexity match the research depth?",
                "guidance": "More research should lead to richer narrative"
            }
        ]
    },
    
    "evidence_quality": {
        "weight": 0.20,
        "description": "Quality of supporting evidence",
        "questions": [
            {
                "id": "E1",
                "text": "Is every claim supported by research?",
                "guidance": "Check that factual statements have sources"
            },
            {
                "id": "E2",
                "text": "Are sources credible and current?",
                "guidance": "Sources should be authoritative and recent"
            },
            {
                "id": "E3",
                "text": "Is there a 'smoking gun' moment?",
                "guidance": "A key piece of evidence that proves the thesis"
            },
            {
                "id": "E4",
                "text": "Are facts presented with appropriate confidence?",
                "guidance": "Distinguish between facts, analysis, and speculation"
            }
        ]
    },
    
    "audience_connection": {
        "weight": 0.20,
        "description": "Relevance to Pakistani audience",
        "questions": [
            {
                "id": "A1",
                "text": "Does this matter to Pakistani audience?",
                "guidance": "The topic should connect to Pakistani interests/concerns"
            },
            {
                "id": "A2",
                "text": "Is local context integrated?",
                "guidance": "Pakistani examples, references, implications"
            },
            {
                "id": "A3",
                "text": "Are there local examples and references?",
                "guidance": "Not just translated content but locally adapted"
            },
            {
                "id": "A4",
                "text": "Does it explain 'why things are this way'?",
                "guidance": "Connect to audience's lived experience"
            }
        ]
    }
}


# ─── Self Evaluator ──────────────────────────────────────────────────────────────

class SelfEvaluator:
    """
    Evaluates scripts against quality criteria.
    
    Uses LLM to assess each criterion and provide detailed feedback.
    """
    
    PRODUCTION_THRESHOLD = 0.85  # 85%
    
    def __init__(self, router_client: RouterClient = None):
        self.router = router_client
    
    async def evaluate(
        self,
        script: DualColumnScript,
        research_data: dict = None,
        detailed: bool = True
    ) -> SelfEvaluationReport:
        """
        Evaluate a script against all criteria.
        
        Args:
            script: The script to evaluate
            research_data: Optional research dossier for context
            detailed: Whether to provide detailed feedback
        
        Returns:
            SelfEvaluationReport with scores and feedback
        """
        results = []
        weak_areas = []
        strong_areas = []
        suggestions = []
        
        # Evaluate each category
        for category_id, category in EVALUATION_CRITERIA.items():
            category_score = 0.0
            category_results = []
            
            for question in category["questions"]:
                result = await self._evaluate_question(
                    script=script,
                    question=question,
                    category=category,
                    research_data=research_data,
                    detailed=detailed
                )
                category_results.append(result)
                
                if not result.passed:
                    weak_areas.append(question["id"])
                    if result.feedback:
                        suggestions.append(result.feedback)
                else:
                    strong_areas.append(question["id"])
            
            # Calculate weighted score for category
            passed_count = sum(1 for r in category_results if r.passed)
            category_score = passed_count / len(category_results)
            
            results.extend(category_results)
        
        # Calculate overall score (weighted average)
        overall_score = sum(r.score for r in results) / len(results) if results else 0.0
        
        # Determine if threshold passed
        passed_threshold = overall_score >= self.PRODUCTION_THRESHOLD
        
        return SelfEvaluationReport(
            overall_score=overall_score,
            passed_threshold=passed_threshold,
            results=results,
            weak_areas=weak_areas,
            strong_areas=strong_areas,
            improvement_suggestions=suggestions
        )
    
    async def _evaluate_question(
        self,
        script: DualColumnScript,
        question: dict,
        category: dict,
        research_data: dict = None,
        detailed: bool = True
    ) -> EvaluationResult:
        """Evaluate a single question against the script."""
        
        # Build evaluation prompt
        script_text = "\n".join([
            f"[{e.section_label.value}] {e.prose}"
            for e in script.entries
        ])
        
        visual_text = "\n".join([
            f"[{e.section_label.value}] {e.visual_direction}"
            for e in script.entries
        ])
        
        prompt = f"""You are a script evaluator for investigative documentary content in the Johnny Harris style.

SCRIPT TO EVALUATE:
Title: {script.adapted_title}

NARRATION:
{script_text[:2000]}

VISUAL DIRECTIONS:
{visual_text[:2000]}

QUESTION: {question["text"]}

GUIDANCE: {question["guidance"]}

Evaluate this specific aspect of the script. Respond in JSON format:
{{
    "score": 0.0-1.0,
    "passed": true/false,
    "feedback": "Specific feedback on what could be improved"
}}

Score 0.7 or above = passed. Be critical but constructive.
"""
        
        try:
            from packages.router.client import RouterClient
            
            async with RouterClient() as router:
                response = await router.complete_text(
                    prompt,
                    system="You are a strict but fair script evaluator. Output only valid JSON.",
                    max_tokens=500
                )
                
                # Parse response
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    score = float(data.get("score", 0.0))
                    passed = data.get("passed", score >= 0.7)
                    feedback = data.get("feedback", "")
                    
                    return EvaluationResult(
                        criterion_id=question["id"],
                        criterion_name=question["text"],
                        score=score,
                        passed=passed,
                        feedback=feedback
                    )
        
        except Exception as e:
            log.warning(f"evaluation_question_failed: {question['id']} - {e}")
        
        # Default to failing result if evaluation fails
        return EvaluationResult(
            criterion_id=question["id"],
            criterion_name=question["text"],
            score=0.0,
            passed=False,
            feedback="Could not evaluate this criterion"
        )
    
    async def quick_score(
        self,
        script: DualColumnScript
    ) -> float:
        """
        Quick scoring without detailed feedback.
        
        Returns an overall score 0.0-1.0.
        """
        report = await self.evaluate(script, detailed=False)
        return report.overall_score
