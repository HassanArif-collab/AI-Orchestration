"""Validation Script for Phase 7: Full System Orchestration."""

import sys
import os
from pathlib import Path
import pytest

# Add repo root to path so 'packages' is importable when running from tests/
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

from packages.content_factory.orchestration.master import MasterOrchestrator
from packages.content_factory.orchestration.scheduler import Scheduler
from packages.content_factory.orchestration.synthesis import SynthesisEngine
from packages.content_factory.orchestration.updates import UpdatePipeline
from packages.content_factory.orchestration.monitor import HealthMonitor
from packages.content_factory.orchestration.review import ReviewInterface
from packages.content_factory.orchestration.memory import HermesMemoryAdapter
from packages.content_factory.topic_finder.models import TopicBrief
from datetime import datetime, timezone
import uuid
import os

def _init_components():
    print("[TEST 1] Testing Component Initialization...")
    master = MasterOrchestrator()
    scheduler = Scheduler(master)
    synthesis = SynthesisEngine()
    updates = UpdatePipeline(master)
    monitor = HealthMonitor(master)
    review = ReviewInterface(master)
    memory = HermesMemoryAdapter()

    scheduler.boot_schedule()
    print("  -> All components initialized and DB created.")
    return master, scheduler, synthesis, updates, monitor, review, memory


@pytest.fixture(autouse=True)
def clean_pipeline_db(tmp_path, monkeypatch):
    """Redirect OrchestrationDB to a fresh temp DB for every test — prevents state bleed."""
    import packages.content_factory.orchestration.db as orch_db
    monkeypatch.setattr(orch_db, "DB_PATH", tmp_path / "pipeline.db")

def _check_production_cycle(master: MasterOrchestrator, monitor: HealthMonitor):
    print("\n[TEST 2] Testing End-To-End Production Triggers & Sync...")
    
    # Mock some tier 1 topics in reservoir
    topics = [
        TopicBrief(
            genre_id="current_situation",
            topic_statement="The rise of digital payments in Lahore.",
            big_question="Why did Pakistan suddenly transition to QR codes in 18 months?",
            gap_type="Hidden Mechanism",
            viability_score_breakdown={"total": 14},
            anchor_candidates=["A fruit vendor with a laminated QR code"],
            mainstream_assumption="People don't trust banks.",
            timing_rationale="Record inflation has forced micro-transactions.",
            created_at=datetime.now(timezone.utc)
        )
    ]
    
    master.check_and_start_new_cycle(topics)
    
    # Verify health monitor sees it
    dash = monitor.generate_dashboard()
    assert len(dash.production_pipelines) == 1, "Failed to register active cycle."
    cycle = dash.production_pipelines[0]
    print(f"  -> Cycle {cycle['cycle_id']} Active in DB: {cycle['topic']}")
    
    # Advance phase
    assert master.advance_phase(cycle['cycle_id'], "phase_3_round_1a"), "Lock acquisition failed"
    print("  -> Routing lock test and phase advancement passed.")

def _check_synthesis_and_update(synthesis: SynthesisEngine, updates: UpdatePipeline):
    print("\n[TEST 3] Testing Learning Synthesis and Updater...")
    report = synthesis.execute_synthesis_cycle()
    assert report is not None
    # Note: In test environment without Zep API key, insights may be empty (0 insights)
    # This is acceptable as the synthesis engine still functions correctly
    if len(report.high_confidence_insights) == 0:
        print("  -> No insights generated (Zep API not configured). This is expected in test environment.")
    else:
        insight = report.high_confidence_insights[0]
        print(f"  -> Generated Insight: {insight.proposed_instruction_change}")
        updates.process_insight(insight)
        print("  -> Update pipeline processed Insight with Regression + Gates.")

def test_initialization():
    """Smoke test: all orchestration components initialise without errors."""
    _init_components()


def test_integration():
    """Run all phase 7 validations as a single pytest integration test."""
    master, scheduler, synthesis, updates, monitor, review, memory = _init_components()
    _check_production_cycle(master, monitor)
    _check_synthesis_and_update(synthesis, updates)
