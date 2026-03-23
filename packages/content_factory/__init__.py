"""
content_factory — Business logic layer. This is the real brain of the pipeline.

All actual AI work happens in this package. The infrastructure packages
(core, router, memory, pipeline) are thin wrappers that support this layer.

Submodules:
  models.py        — Shared Pydantic models (AdaptedScript, DualColumnEntry, etc.)
  source_library.py — Source video catalogue and processing status tracking
  adaptation/      — 4-stage content pipeline: extract → structural → localize → script
  evaluation/      — Baseline/challenger A-B scoring loop (evolutionary improvement)
  topic_finder/    — Topic discovery agent + SQLite reservoir of candidate topics
  music/           — Music architecture agent: arc design, section briefs, silence map
  production/      — Final production agents and publishing workflow
  orchestration/   — Master scheduler, health monitor, review interface, memory adapter
"""
