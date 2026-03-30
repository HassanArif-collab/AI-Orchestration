"""Tests for cross-script learning via Zep memory."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
@patch("packages.content_factory.evaluation.loop.AsyncZepMemoryClient")
@patch("packages.content_factory.evaluation.loop.get_settings")
async def test_winning_mutation_saved_to_zep(mock_settings, MockZep):
    """When a mutation wins, a structured fact is saved to Zep."""
    # Mock settings
    settings = MagicMock()
    settings.ZEP_LEARNING_USER_ID = "learning_synthesis_v1"
    settings.ZEP_API_KEY = "test-key"
    settings.ZEP_ENABLED = True
    mock_settings.return_value = settings

    # Mock Zep client
    mock_zep = AsyncMock()
    MockZep.return_value = mock_zep

    # Import and test the method
    from packages.content_factory.evaluation.loop import ExperimentLoop

    loop = ExperimentLoop()
    await loop._save_winning_learning(
        mutation_zone="script_prose",
        score_before=70.0,
        score_after=82.5,
        fixed_questions=["C3", "C5"],
        genre_id="current_situation",
        cycle_id="exp_test123",
    )

    # Verify Zep was called with structured fact
    mock_zep.add_facts.assert_called_once()
    call_args = mock_zep.add_facts.call_args
    facts = call_args.kwargs.get("facts", call_args[0][1] if call_args[0] else [])
    assert len(facts) == 1
    fact = facts[0]
    assert "PROVEN SCRIPT IMPROVEMENT" in fact["fact"]
    assert "+12.5%" in fact["fact"]
    assert fact["zone_mutated"] == "script_prose"


@pytest.mark.asyncio
@patch("packages.content_factory.evaluation.loop.AsyncZepMemoryClient")
@patch("packages.content_factory.evaluation.loop.get_settings")
async def test_winning_learning_graceful_fallback_on_zep_error(mock_settings, MockZep):
    """When Zep fails, the learning save should not crash the loop."""
    settings = MagicMock()
    settings.ZEP_LEARNING_USER_ID = "learning_synthesis_v1"
    settings.ZEP_API_KEY = "test-key"
    mock_settings.return_value = settings

    # Mock Zep to raise an error
    mock_zep = AsyncMock()
    mock_zep.add_facts.side_effect = Exception("Zep connection failed")
    MockZep.return_value = mock_zep

    from packages.content_factory.evaluation.loop import ExperimentLoop

    loop = ExperimentLoop()
    # Should not raise - just log warning
    await loop._save_winning_learning(
        mutation_zone="script_prose",
        score_before=70.0,
        score_after=82.5,
        fixed_questions=[],
        genre_id="test",
        cycle_id="exp_test",
    )


@pytest.mark.asyncio
@patch("packages.content_factory.production.workflow.AsyncZepMemoryClient")
@patch("packages.content_factory.production.workflow.get_settings")
async def test_script_writer_retrieves_learnings(mock_settings, MockZep):
    """ScriptWriter should query Zep for past learnings before drafting."""
    settings = MagicMock()
    settings.ZEP_API_KEY = "test-key"
    settings.ZEP_ENABLED = True
    settings.ZEP_LEARNING_USER_ID = "learning_synthesis_v1"
    mock_settings.return_value = settings

    mock_zep = AsyncMock()
    mock_zep.search_memory.return_value = [
        {"fact": "Opening hooks under 3 sentences improve retention by 15%"},
        {"fact": "Data-driven bridges reduce drop-off significantly"},
    ]
    MockZep.return_value = mock_zep

    from packages.content_factory.production.workflow import RoundBasedProductionWorkflow

    workflow = RoundBasedProductionWorkflow()
    result = await workflow._get_past_learnings("Pakistan AI Policy", "tech_systems")

    assert "LESSONS FROM PAST SCRIPTS" in result
    assert "Opening hooks" in result
    assert "Data-driven bridges" in result


@pytest.mark.asyncio
@patch("packages.content_factory.production.workflow.AsyncZepMemoryClient")
@patch("packages.content_factory.production.workflow.get_settings")
async def test_graceful_fallback_when_zep_disabled(mock_settings, MockZep):
    """When ZEP_ENABLED is False, return empty string without error."""
    settings = MagicMock()
    settings.ZEP_API_KEY = ""
    settings.ZEP_ENABLED = False
    mock_settings.return_value = settings

    from packages.content_factory.production.workflow import RoundBasedProductionWorkflow

    workflow = RoundBasedProductionWorkflow()
    result = await workflow._get_past_learnings("Any Topic", "any_genre")

    assert result == ""
    # Zep should not be instantiated
    MockZep.assert_not_called()


@pytest.mark.asyncio
@patch("packages.content_factory.production.workflow.AsyncZepMemoryClient")
@patch("packages.content_factory.production.workflow.get_settings")
async def test_learnings_capped_at_eight(mock_settings, MockZep):
    """More than 8 facts should be truncated to save tokens."""
    settings = MagicMock()
    settings.ZEP_API_KEY = "test-key"
    settings.ZEP_ENABLED = True
    settings.ZEP_LEARNING_USER_ID = "learning_synthesis_v1"
    mock_settings.return_value = settings

    # Return many facts
    mock_zep = AsyncMock()
    mock_zep.search_memory.return_value = [
        {"fact": f"Learning number {i}"} for i in range(15)
    ]
    MockZep.return_value = mock_zep

    from packages.content_factory.production.workflow import RoundBasedProductionWorkflow

    workflow = RoundBasedProductionWorkflow()
    result = await workflow._get_past_learnings("Topic", "genre")

    # Count numbered items
    import re
    numbered_items = re.findall(r'^\s*\d+\.', result, re.MULTILINE)
    assert len(numbered_items) <= 8


@pytest.mark.asyncio
@patch("packages.content_factory.production.workflow.AsyncZepMemoryClient")
@patch("packages.content_factory.production.workflow.get_settings")
async def test_learnings_deduplicated(mock_settings, MockZep):
    """Duplicate facts should not appear twice."""
    settings = MagicMock()
    settings.ZEP_API_KEY = "test-key"
    settings.ZEP_ENABLED = True
    settings.ZEP_LEARNING_USER_ID = "learning_synthesis_v1"
    mock_settings.return_value = settings

    # Return same fact from multiple queries
    mock_zep = AsyncMock()
    mock_zep.search_memory.return_value = [
        {"fact": "Same important learning"},
        {"fact": "Same important learning"},
        {"fact": "Different learning"},
    ]
    MockZep.return_value = mock_zep

    from packages.content_factory.production.workflow import RoundBasedProductionWorkflow

    workflow = RoundBasedProductionWorkflow()
    result = await workflow._get_past_learnings("Topic", "genre")

    # Count occurrences of "Same important learning"
    assert result.count("Same important learning") == 1


@pytest.mark.asyncio
@patch("packages.content_factory.production.workflow.AsyncZepMemoryClient")
@patch("packages.content_factory.production.workflow.get_settings")
async def test_no_facts_returns_empty_string(mock_settings, MockZep):
    """When no facts found, return empty string."""
    settings = MagicMock()
    settings.ZEP_API_KEY = "test-key"
    settings.ZEP_ENABLED = True
    settings.ZEP_LEARNING_USER_ID = "learning_synthesis_v1"
    mock_settings.return_value = settings

    mock_zep = AsyncMock()
    mock_zep.search_memory.return_value = []
    MockZep.return_value = mock_zep

    from packages.content_factory.production.workflow import RoundBasedProductionWorkflow

    workflow = RoundBasedProductionWorkflow()
    result = await workflow._get_past_learnings("New Topic", "genre")

    assert result == ""


@pytest.mark.asyncio
@patch("packages.content_factory.production.workflow.AsyncZepMemoryClient")
@patch("packages.content_factory.production.workflow.get_settings")
async def test_zep_error_returns_empty_string(mock_settings, MockZep):
    """When Zep throws an error, return empty string gracefully."""
    settings = MagicMock()
    settings.ZEP_API_KEY = "test-key"
    settings.ZEP_ENABLED = True
    settings.ZEP_LEARNING_USER_ID = "learning_synthesis_v1"
    mock_settings.return_value = settings

    mock_zep = AsyncMock()
    mock_zep.search_memory.side_effect = Exception("Connection timeout")
    MockZep.return_value = mock_zep

    from packages.content_factory.production.workflow import RoundBasedProductionWorkflow

    workflow = RoundBasedProductionWorkflow()
    result = await workflow._get_past_learnings("Topic", "genre")

    assert result == ""
