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

| Stage | Purpose | Gate? |
|-------|---------|-------|
| trend_analysis | Discover topics | No |
| human_topic_approval | Pick topic | **Yes** |
| research | Deep research | No |
| script_writing | Generate script | No |
| visual_planning | Design visuals | No |
| seo | Metadata | No |
| human_review | Review script | **Yes** |
| asset_creation | Create assets | No |
| publish | Publish to Notion | No |

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
