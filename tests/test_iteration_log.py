"""Tests for IterationLogStore."""

import pytest
from pathlib import Path


def test_save_and_retrieve(tmp_path):
    """Test basic save and retrieve operations."""
    from packages.pipeline.iteration_store import IterationLogStore
    
    store = IterationLogStore(db_path=str(tmp_path / "test.db"))
    store.save(
        run_id="r1",
        iteration=1,
        score=74.2,
        previous_score=61.0,
        beat_baseline=True,
        mutation_zone="script_prose",
        script_json={"adapted_title": "T", "entries": []},
        failed_questions=["B3"],
        fixed_questions=["A1"],
    )
    
    rows = store.get_all("r1")
    assert len(rows) == 1
    assert rows[0]["score"] == 74.2
    assert rows[0]["beat_baseline"] is True


def test_multiple_runs(tmp_path):
    """Test that multiple runs are isolated correctly."""
    from packages.pipeline.iteration_store import IterationLogStore
    
    store = IterationLogStore(db_path=str(tmp_path / "test.db"))
    
    # Add 3 iterations for run-1
    for i in range(3):
        store.save(
            run_id="run-1",
            iteration=i,
            score=60.0 + i * 5,
            previous_score=60.0,
            beat_baseline=i > 0,
            mutation_zone="script_prose",
            script_json={},
            failed_questions=[],
            fixed_questions=[],
        )
    
    # Add 1 iteration for run-2
    store.save(
        run_id="run-2",
        iteration=0,
        score=55.0,
        previous_score=0,
        beat_baseline=False,
        mutation_zone="visual_direction",
        script_json={},
        failed_questions=[],
        fixed_questions=[],
    )
    
    assert len(store.get_all("run-1")) == 3
    assert len(store.get_all("run-2")) == 1


def test_empty_run(tmp_path):
    """Test that non-existent run returns empty list."""
    from packages.pipeline.iteration_store import IterationLogStore
    
    store = IterationLogStore(db_path=str(tmp_path / "test.db"))
    assert store.get_all("nobody") == []
