"""
System Orchestration — Production Cycle Management.

Coordinates the full production lifecycle across all phases.

Components:
  master.py    → MasterOrchestrator: top-level cycle controller
  scheduler.py → Scheduler: cron-based production automation
  monitor.py   → HealthMonitor: dashboard and health checks
  review.py    → ReviewInterface: human review gate
  synthesis.py → SynthesisEngine: weekly learning synthesis (reads Zep)
  updates.py   → UpdatePipeline: applies learning insights to system prompts
  memory.py    → HermesMemoryAdapter: Zep memory interface for orchestrator
  db.py        → OrchestrationDB: SQLite for production cycle state

Trigger: MasterOrchestrator.check_and_start_new_cycle(topics) →
         triggers packages/pipeline/runner.PipelineRunner per cycle
"""
