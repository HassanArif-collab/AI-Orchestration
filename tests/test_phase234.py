"""Validation script for Phase 2, 3, and 4 architecture.

Tests Pydantic models, SQLite baseline operations, and JSON loading
without triggering live LLM calls.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Add repo root to path so 'packages' is importable when running from tests/
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

from packages.content_factory.models import (
    RawExtraction, StructuralMap, LocalizationMap, AdaptedScript, DualColumnEntry
)
from packages.content_factory.source_library import SourceVideoLibrary, ProcessingStatus
from packages.content_factory.evaluation.baseline import BaselineManager
from packages.content_factory.evaluation.learning_log import LearningLogger, LearningLogEntry

def test_models():
    print("[OK] Testing Pydantic models...")
    entry = DualColumnEntry(
        prose="The city of Karachi was built on trade.",
        visual_direction="Archival footage of Karachi port circa 1960",
        visual_type="archive",
        section_label="ANCHOR"
    )
    
    script = AdaptedScript(
        video_id="test_vid_123",
        source_video_id="source_vid_456",
        adapted_title="Karachi: The Hidden History",
        genre="history",
        entries=[entry],
        section_sequence=["ANCHOR"],
        production_readiness_score=85.0
    )
    assert script.video_id == "test_vid_123"
    assert len(script.entries) == 1

def test_sqlite_baseline():
    print("[OK] Testing Baseline Manager (SQLite)...")
    pm = BaselineManager("packages/data/test_pipeline.db")
    script = AdaptedScript(
        video_id="test_vid_123",
        source_video_id="source_vid_456",
        adapted_title="Test Baseline",
        genre="history",
        production_readiness_score=85.0
    )
    
    # Process challenger - should be new baseline since score is high
    is_new = pm.process_challenger(script)
    # Note: is_new may be True or False depending on if it beats existing baseline
    
    # Retrieve
    retrieved = pm.get_baseline("history")
    assert retrieved is not None
    assert retrieved.video_id == "test_vid_123"
    
    # Clean up test DB (with retry for Windows file locking)
    import time
    import gc
    gc.collect()  # Force garbage collection to release file handles
    time.sleep(0.1)
    try:
        if os.path.exists("packages/data/test_pipeline.db"):
            os.remove("packages/data/test_pipeline.db")
    except PermissionError:
        pass  # File may still be locked, that's OK for test

def test_learning_log():
    print("[OK] Testing Learning Log...")
    logger = LearningLogger("packages/data/test_log.jsonl")
    entry = LearningLogEntry(
        cycle_id="cycle_1",
        genre_id="history",
        baseline_id="vid_1",
        challenger_id="vid_2",
        mutation_zone="script_prose",
        baseline_score=50.0,
        challenger_score=60.0,
        beat_baseline=True,
        timestamp=datetime.now(timezone.utc)
    )
    logger.log_experiment(entry)
    logs = logger.read_logs()
    assert len(logs) == 1
    assert logs[0].cycle_id == "cycle_1"
    
    if os.path.exists("packages/data/test_log.jsonl"):
        os.remove("packages/data/test_log.jsonl")

def test_integration():
    """Run all phase 2/3/4 validations as a single pytest integration test."""
    test_models()
    test_sqlite_baseline()
    test_learning_log()
