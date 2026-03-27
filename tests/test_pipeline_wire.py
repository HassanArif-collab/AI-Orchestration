"""Test that MasterOrchestrator._trigger_pipeline calls run_until_gate."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_trigger_pipeline_calls_run_until_gate():
    """Verify that _trigger_pipeline actually executes the pipeline by calling run_until_gate."""
    from packages.content_factory.orchestration.master import MasterOrchestrator

    mock_run = MagicMock()
    mock_run.run_id = "test-run-123"
    mock_runner = AsyncMock()
    mock_runner.create_run = AsyncMock(return_value=mock_run)
    mock_runner.run_until_gate = AsyncMock(return_value=None)

    orchestrator = MasterOrchestrator.__new__(MasterOrchestrator)
    orchestrator.db = MagicMock()
    orchestrator.db.update_pipeline_run_id = MagicMock()

    with patch(
        "packages.pipeline.runner.PipelineRunner",
        return_value=mock_runner,
    ):
        await orchestrator._trigger_pipeline("cycle-abc", MagicMock())

    mock_runner.run_until_gate.assert_called_once_with(mock_run)
