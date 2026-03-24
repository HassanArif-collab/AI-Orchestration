"""
Orchestration System — Production Cycle Management (Phase 7).

The orchestration system runs the MACRO loop: it decides when to start new
video production cycles, tracks their progress, synthesizes learning from
completed cycles, updates agent instructions, and escalates to humans when needed.

7 COMPONENTS (read in this order to understand the system):

  master.py    → MasterOrchestrator
    The central router. Starts new production cycles from the topic reservoir,
    enforces the max 2 concurrent cycles limit, handles escalations.
    Uses Zep client directly for session memory.
    Named "Hermes" — after the messenger god — because it routes documents
    between specialist agents.

  scheduler.py → Scheduler
    Cron-like job runner. Registers timed jobs:
      - TopicFinder daily (every 24h)
      - Production polling (every 6h) — checks if stalled cycles need attention
      - Learning synthesis weekly (every 168h)
      - Health check hourly
      - Analytics sweep daily
      - Maintenance weekly
    Does NOT run in a separate thread — jobs are triggered by calling run_due_jobs().

  synthesis.py → SynthesisEngine
    Weekly learning engine. Reads 10 semantic queries from Zep covering
    script failures, successful mutations, and audience patterns.
    Produces a SynthesisReport with high/medium/low confidence Insights.
    Also runs a monthly cross-cycle analysis for emergent patterns.

  updates.py   → UpdatePipeline
    Risk-controlled instruction updater. Takes Insights from SynthesisEngine
    and proposes instruction changes for affected agents.
    Three scope levels:
      narrow  → auto-activates if high confidence (no human needed)
      medium  → 7-day advisory window, then auto-activates
      wide    → mandatory human review before activation
    Rollback monitor: 3 consecutive score drops after update → auto-rollback.

  monitor.py   → HealthMonitor
    Live dashboard aggregator. Assembles DashboardModel with 6 sections:
    active pipelines, reservoir status, quality trends, learning system,
    published performance, system health indicators.
    Read by: apps/api/routers/analytics_routes.py for the web dashboard.

  review.py    → ReviewInterface
    Human review queue. Fetches pending escalations ordered by severity.
    Escalation types: instruction_update, hard_failure, reservoir_low,
                      weekly_summary, sensitive_content.
    Decisions: approve, reject, modify, continue_baseline,
               revise_manually, abandon.

  memory.py    → HermesMemoryAdapter
    In-memory skill store and audience model. Bridges the learning loop
    to the agent instruction system. See full explanation in memory.py.

  db.py        → OrchestrationDB
    SQLite persistence for production cycle state. Three tables:
      production_registry — cycle lifecycle tracking
      human_escalations   — items waiting for human decision
      instruction_versions — history of agent instruction changes
    Uses optimistic locking (lock_expires_at) to prevent race conditions
    when two processes try to advance the same cycle simultaneously.

  models.py    → Pydantic models shared by all 7 components

PRODUCTION CYCLE LIFECYCLE:
  TopicReservoir (Tier 1 topic)
       ↓ MasterOrchestrator.check_and_start_new_cycle()
  production_registry INSERT (status=active, phase=topic_selected)
       ↓ _trigger_pipeline() → PipelineRunner
  Pipeline runs (trend → research → script → visual → seo → publish)
       ↓ advance_phase() called as each phase completes
  phase=completed, pipeline_run_id recorded
       ↓ Scheduler.run_learning_synthesis() (weekly)
  SynthesisEngine → Insights → UpdatePipeline → better agent instructions
"""
