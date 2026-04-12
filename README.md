# AI-Orchestration

Multi-agent YouTube video production pipeline with human oversight.

## What This Does

Turns topics into production-ready video scripts through a 9-stage AI pipeline:

```
Topic → Research → Script → Visual Plan → Review → Publish
         ↑________________(human gates)________________↑
```

**Key insight**: The pipeline pauses at human gates for approval, ensuring quality control.

## Why This Architecture

| Decision | Reason |
|----------|--------|
| Two services | LLM complexity isolated from business logic |
| Supabase state | PostgreSQL-backed persistence, realtime subscriptions |
| LangGraph orchestration | Declarative graph-based pipeline execution |
| SSE updates | Real-time without WebSocket complexity |

## Quick Start

```bash
# 1. Install
pip install -e ".[all]"

# 2. Configure FreeRouter (port 4000)
cd freerouter && cp .env.example .env
# Add GROQ_API_KEY or OPENROUTER_API_KEY

# 3. Configure main app
cd .. && cp .env.example .env
# Add optional keys: ZEP_API_KEY, YOUTUBE_API_KEY

# 4. Start services (two terminals)
python -m freerouter proxy          # Terminal 1
python -m apps.api.main             # Terminal 2
```

Open **http://localhost:3000**

## Dashboard Features

| Tab | Purpose |
|-----|---------|
| Pipeline | Create runs, approve gates, view outputs |
| Chat | Direct LLM conversation |
| Providers | Monitor LLM health |
| Memory | Browse agent memory |

## Architecture Overview

```
freerouter/        ← LLM proxy (port 4000)
apps/
  api/             ← FastAPI backend (port 3000)
  web/             ← React + TypeScript frontend (Vite)
packages/
  core/            ← Config, logging, research cache (no dependencies)
  router/          ← FreeRouter HTTP client
  memory/          ← Zep Cloud agent memory
  agents/          ← Agent base classes + registry
  content_factory/ ← LangGraph orchestration + business logic
  integrations/    ← YouTube, Notion clients
  visual/          ← Remotion video animations
```

## The Pipeline

### Production Pipeline (4 Feedback Loops)

```
load_learnings → research → draft → score
                                    │
                          ┌─────────┼──────────┐
                     needs_research  mutate     done
                          │         │          │
                     research_gap  → score  capture_learning
                          │                    │
                          ↓                    ↓
                         draft               visuals
                                               │
                                         ┌─────┴──────┐
                                    revise_visual     ok
                                         │            │
                                         ↓            ↓
                                        draft    human_review
                                                      │
                                                ┌─────┴──────┐
                                             approve      revise
                                                │            │
                                                ↓            ↓
                                             publish      draft
```

| Node | Purpose | Gate? |
|------|---------|-------|
| load_learnings | Load past winning patterns from Zep | No |
| research | Deep research (5-phase deer-flow via Exa.ai) | No |
| research_gap | Supplementary search on weak evidence (auto) | No |
| draft | Script generation with style constitution + genre rules | No |
| score | 56-question binary evaluation | No |
| mutate | Improve weakest sections (Karpathy loop, up to 20x) | No |
| capture_learning | Store winning patterns to Zep | No |
| visuals | Visual annotations + structural review | No |
| human_review | Review script | **Yes** |
| publish | Publish to Notion | No |

### Discovery Pipeline

| Stage | Purpose | Gate? |
|-------|---------|-------|
| gather_context | Load audience history | No |
| search_web | Search via Exa.ai | No |
| generate_topics | Discover candidate topics | No |
| grade_viability | Score topics (17-question checklist) | No |
| save_topics | Save passing topics to Kanban | No |

## Environment Variables

**Required** (`freerouter/.env`):
- `GROQ_API_KEY` or `OPENROUTER_API_KEY`

**Optional** (root `.env`):
- `ZEP_API_KEY` — Agent memory
- `YOUTUBE_API_KEY` — Analytics

## Documentation

| Doc | Purpose |
|-----|---------|
| [Getting Started](docs/archive/GETTING_STARTED.md) | Detailed setup |
| [Architecture](docs/ARCHITECTURE.md) | System design + why |
| [Decisions](docs/archive/DECISIONS.md) | ADRs with reasoning |
| [API Reference](docs/archive/API_REFERENCE.md) | Endpoints |
| [Supabase Setup](docs/SUPABASE_SETUP.md) | Database configuration |
| [Changelog](CHANGELOG.md) | Version history |

## Requirements

- Python 3.10+
- At least one LLM API key
