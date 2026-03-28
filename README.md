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
| SQLite state | Zero-config, file-based, concurrent-safe |
| 9 stages with gates | Human oversight at critical decisions |
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
  api/             ← Web dashboard (port 3000)
  worker/          ← CLI pipeline runner
packages/
  core/            ← Config, logging (no dependencies)
  router/          ← FreeRouter HTTP client
  pipeline/        ← 9-stage state machine
  agents/          ← Agent base classes
  content_factory/ ← Business logic
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
| [Getting Started](docs/HOW_TO_PULL_AND_RUN.md) | Detailed setup |
| [Architecture](docs/ARCHITECTURE.md) | System design + why |
| [Decisions](docs/DECISIONS.md) | ADRs with reasoning |
| [API Reference](docs/API_REFERENCE.md) | Endpoints |

## Requirements

- Python 3.10+
- At least one LLM API key
