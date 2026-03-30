"""
packages/ — Two-layer architecture for the AI-Orchestration pipeline.

Layer 1 — Infrastructure (thin wrappers, shared utilities):
  core/          Config, logger, errors, shared types
  router/        HTTP client to FreeRouter LLM proxy at :4000
  memory/        Zep Cloud agent memory (conversation + long-term)
  pipeline/      9-stage state machine runner
  agents/        Base AgentClass + registry. Skills in data/skills/*.md
  integrations/  YouTube, Notion API clients
  visual/        Remotion video animations + Radiant shader backgrounds

Layer 2 — Business logic (actual AI pipeline work):
  content_factory/  Topic → Adaptation → Evaluation → Music → Production → Publish

The golden rule: all LLM calls go through packages/router/ → FreeRouter.
Never import from freerouter/ directly. Never hardcode API keys.
"""
