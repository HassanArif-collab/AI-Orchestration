
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from pathlib import Path

from packages.content_factory.evaluation.loop import ExperimentLoop
from packages.content_factory.evaluation.mutation import ChallengerGenerator
from packages.content_factory.models import AdaptedScript, DualColumnEntry, SelfCheckResult

# MOCK DATA
MOCK_EVAL_SUITE = {
    "questions": [
        {"id": "TEST1", "category": "script_prose_quality", "text": "Test Q1"},
        {"id": "TEST2", "category": "visual_anchor_quality", "text": "Test Q2"}
    ]
}

@pytest.fixture
def mock_script():
    return AdaptedScript(
        video_id="test_vid",
        genre="history",
        entries=[
            DualColumnEntry(prose="Line 1", visual_direction="Vis 1", section_label="HOOK"),
            DualColumnEntry(prose="Line 2", visual_direction="Vis 2", section_label="BRIDGE"),
            ],
            self_check_results=[

            SelfCheckResult(question_id="TEST1", passed=False, failure_reason="Bad prose", question_text="Test Q1"),
            SelfCheckResult(question_id="TEST2", passed=True, failure_reason=None, question_text="Test Q2")
        ],
        production_readiness_score=50.0
    )

@pytest.mark.asyncio
async def test_challenger_generator_dynamic_mapping(mock_script):
    with patch("packages.content_factory.evaluation.mutation._load_json", return_value=MOCK_EVAL_SUITE):
        generator = ChallengerGenerator()
        
        # Verify mapping
        assert "script_prose_quality" in generator.category_question_map
        assert "TEST1" in generator.category_question_map["script_prose_quality"]
        
        # Mock LLM response
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.complete_text.return_value = json.dumps({
            "entries": [
                {"prose": "New Line 1", "visual_direction": "Vis 1", "section_label": "HOOK"},
                {"prose": "Line 2", "visual_direction": "Vis 2", "section_label": "BRIDGE"}
            ]
        })
        
        # Test generation targeting "script_prose" (which maps to script_prose_quality -> TEST1)
        challenger = await generator.generate_challenger(mock_script, "script_prose", router_client=mock_client)
        
        assert challenger is not None
        assert challenger.video_id.startswith("mutated_")
        assert len(challenger.entries) == 2

@pytest.mark.asyncio
async def test_challenger_generator_strict_validation(mock_script):
    with patch("packages.content_factory.evaluation.mutation._load_json", return_value=MOCK_EVAL_SUITE):
        generator = ChallengerGenerator()
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        
        # Case 1: Malformed JSON structure (entries not a list)
        mock_client.complete_text.return_value = json.dumps({"entries": "not a list"})
        challenger = await generator.generate_challenger(mock_script, "script_prose", router_client=mock_client)
        assert challenger is None

        # Case 2: Truncated script (1 entry instead of 2 -> 50% < 90%)
        mock_client.complete_text.return_value = json.dumps({
            "entries": [
                {"prose": "Line 1", "visual_direction": "Vis 1", "section_label": "HOOK"}
            ]
        })
        challenger = await generator.generate_challenger(mock_script, "script_prose", router_client=mock_client)
        assert challenger is None

@pytest.mark.asyncio
async def test_loop_linear_threshold_logic(mock_script):
    # Mock dependencies
    def _mock_supabase():
        m = MagicMock()
        r = MagicMock()
        r.data = []
        t = MagicMock()
        for method in ['select', 'insert', 'update', 'upsert', 'delete',
                       'eq', 'neq', 'or_', 'order', 'limit', 'maybe_single', 'single']:
            getattr(t, method).return_value = t
        t.execute.return_value = r
        m.table.return_value = t
        return m

    with patch("packages.content_factory.evaluation.mutation._load_json", return_value=MOCK_EVAL_SUITE), \
         patch("packages.content_factory.evaluation.loop.ScoringEngine") as MockScoring, \
         patch("packages.content_factory.evaluation.loop.BaselineManager") as MockBaseline, \
         patch("packages.core.supabase_client.get_supabase", return_value=_mock_supabase()):
        
        loop = ExperimentLoop(enable_persistence=False)
        
        # Setup Baseline Mock to always accept new best
        loop.baseline.process_challenger.return_value = True
        
        # Setup Scoring Mock to increment score
        mock_scoring_instance = MockScoring.return_value
        
        async def mock_score(script, client):
            # Return copy with increased score
            s = script.model_copy()
            s.production_readiness_score += 10.0
            return s
            
        mock_scoring_instance.score_script.side_effect = mock_score

        # Mock Challenger to return copy of baseline (to keep accumulated score for the mock scorer to add to)
        async def mock_generate(baseline, **kwargs):
            return baseline.model_copy(deep=True)

        loop.challenger.generate_challenger = AsyncMock(side_effect=mock_generate)

        # Run with threshold

        # Initial score 50. Threshold 75. 
        # Iteration 1: 60
        # Iteration 2: 70
        # Iteration 3: 80 -> Break
        
        final_script = await loop.run_with_threshold(
            mock_script, 
            threshold=75.0, 
            max_iterations=5
        )
        
        assert final_script.production_readiness_score >= 75.0
        
        # Verify run_iterations was called ONCE (delegated)
        # But we want to verify the loop inside run_iterations ran correct number of times
        # OR verify that generate_challenger was called ~3 times.
        
        assert loop.challenger.generate_challenger.call_count == 3
