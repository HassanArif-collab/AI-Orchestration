# AI-Orchestration

Multi-agent YouTube video production pipeline built on FreeRouter, with a unified web dashboard for pipeline management, LLM provider configuration, and real-time monitoring.

> **New to this project?** See the [Step-by-Step Guide](docs/HOW_TO_PULL_AND_RUN.md) for detailed instructions on how to pull, setup, and run this codebase.

## Quick start

```bash
# 1. Install
pip install -e ".[all]"

# 2. Copy env file and add your keys
cp .env.example .env
# Edit .env and add your API keys (ZEP_API_KEY, YOUTUBE_API_KEY, etc.)

# 3. Configure FreeRouter API keys
cd freerouter
cp .env.example .env
# Edit freerouter/.env and add GROQ_API_KEY and/or OPENROUTER_API_KEY
```

## Running the Web Dashboard

The system includes a unified web dashboard that provides a visual interface for managing the pipeline, configuring LLM providers, chatting with models, and monitoring analytics.

### Start Both Services (Recommended)

You need **two terminals**:

**Terminal 1 — FreeRouter Proxy (port 4000)**
```bash
cd freerouter
python -m freerouter proxy
```

**Terminal 2 — Web Dashboard (port 3000)**
```bash
python -m apps.api.main
```

Then open **http://localhost:3000** in your browser.

### Quick Start with Make

```bash
# Start FreeRouter proxy (port 4000)
make freerouter

# In another terminal, start the dashboard
python -m apps.api.main
```

### Dashboard Features

| Tab | Description |
|-----|-------------|
| **Pipeline** | Create and manage video production runs, approve human gates, view stage outputs |
| **Chat** | Direct chat interface with LLM providers through FreeRouter |
| **Providers** | Configure and monitor LLM providers (Groq, OpenRouter, Ollama) |
| **Memory** | Browse Zep Cloud agent memory sessions and facts |
| **Analytics** | YouTube channel analytics and competitor tracking |
| **Visual** | Visual asset manifest management for video production |
| **Settings** | System configuration and health status |

### Real-time Updates

The dashboard uses **Server-Sent Events (SSE)** for real-time pipeline updates:
- Stage completion notifications
- Human gate alerts with badge counter
- Pipeline completion announcements
- System health monitoring (every 30 seconds)

## Running the Pipeline

### CLI Mode

```bash
# Start the pipeline worker
python apps/worker/main.py start

# Run a smoke test
python scripts/run_pipeline.py
```

### API Mode

```bash
# Create a new pipeline run via API
curl -X POST http://localhost:3000/api/pipeline/runs

# List all runs
curl http://localhost:3000/api/pipeline/runs

# Get run details
curl http://localhost:3000/api/pipeline/runs/{run_id}

# Approve a human gate
curl -X POST http://localhost:3000/api/pipeline/runs/{run_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"selection": {...}, "feedback": ""}'
```

## Architecture

See `docs/ARCHITECTURE.md` for full details.

```
freerouter/   ← LLM proxy (Groq, OpenRouter, Ollama — auto-fallback)
apps/
  api/        ← Web dashboard (FastAPI, port 3000)
  worker/     ← CLI worker for pipeline execution
packages/
  core/       ← shared types, config, logging, errors
  router/     ← HTTP client for FreeRouter at :4000
  pipeline/   ← state machine, 9 stages, human gates
  agents/     ← base agent class, registry
  memory/     ← Zep Cloud agent memory
  content_factory/ ← Johnny Harris-style video production
  integrations/
    youtube/  ← YouTube Data API v3
    notion/   ← Notion script pages
    mirofish/ ← MiroFish trend simulation
  visual/
    remotion/ ← programmatic video animations
    radiant/  ← canvas shader backgrounds
```

### Dashboard Architecture

```
apps/api/
  main.py              ← FastAPI app entry point (port 3000)
  events.py            ← SSE event emitter for real-time updates
  dependencies.py      ← Shared clients (pipeline, memory, YouTube)
  routers/
    pipeline_routes.py ← Pipeline CRUD and human gate approval
    provider_routes.py ← FreeRouter provider management (proxied)
    chat_routes.py     ← Direct chat with LLMs (proxied)
    memory_routes.py   ← Zep Cloud memory browser
    analytics_routes.py← YouTube analytics dashboard
    visual_routes.py   ← Visual asset management
    settings_routes.py ← System config and health status
  static/
    index.html         ← Single-page dashboard UI
    css/dashboard.css  ← Dark theme styling (Fabro-inspired)
    js/                ← Tab-specific JavaScript modules
```

## Requirements

- Python 3.11+
- API keys in `freerouter/.env`:
  - `GROQ_API_KEY` — Required for Groq provider
  - `OPENROUTER_API_KEY` — Optional, for OpenRouter models
- API keys in `.env` (optional):
  - `ZEP_API_KEY` — For persistent agent memory
  - `YOUTUBE_API_KEY` — For YouTube analytics
  - `NOTION_API_KEY` — For Notion integration

## Environment Variables

| Variable | Location | Purpose |
|----------|----------|---------|
| `GROQ_API_KEY` | `freerouter/.env` | Groq LLM provider |
| `OPENROUTER_API_KEY` | `freerouter/.env` | OpenRouter model access |
| `ZEP_API_KEY` | `.env` | Zep Cloud memory storage |
| `YOUTUBE_API_KEY` | `.env` | YouTube Data API |
| `NOTION_API_KEY` | `.env` | Notion API integration |
| `LOG_LEVEL` | `.env` | Logging verbosity (default: INFO) |

### New Configuration (Phase 2 & 3)

| Variable | Default | Purpose |
|----------|---------|---------|
| `RATE_LIMIT_BACKEND` | `memory` | Rate limit storage: `memory` or `redis` |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before circuit opens |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `60` | Seconds before retry |
| `FREEROUTER_CONNECT_TIMEOUT` | `10.0` | HTTP connect timeout (seconds) |
| `FREEROUTER_READ_TIMEOUT` | `120.0` | HTTP read timeout (seconds) |
| `ESCALATION_ENABLED` | `true` | Enable escalation alerts |
| `ESCALATION_WEBHOOK_URL` | - | Webhook URL for alerts |
| `ESCALATION_MIN_SCORE` | `50.0` | Minimum score to trigger escalation |

## Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| `docs/HOW_TO_PULL_AND_RUN.md` | **New Users** | **Step-by-step guide to pull, setup, and run** |
| `docs/ARCHITECTURE.md` | Developers | System architecture overview |
| `docs/PHASE_2_3_IMPLEMENTATION_GUIDE.md` | Developers | Phase 2 & 3 implementation details |
| `docs/KIDS_GUIDE.md` | Everyone | Simple explanations of changes |
| `docs/CHANGES.json` | AI Systems | Structured change documentation |
| `freerouter/FIXES_APPLIED.md` | Developers | FreeRouter-specific fixes |
| `freerouter/USAGE.md` | Developers | FreeRouter usage examples |

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pipeline/stages` | GET | Get pipeline stage definitions |
| `/api/pipeline/runs` | GET, POST | List or create pipeline runs |
| `/api/pipeline/runs/{id}` | GET, DELETE | Get or delete a run |
| `/api/pipeline/runs/{id}/approve` | POST | Approve human gate |
| `/api/pipeline/runs/{id}/reject` | POST | Reject with feedback |
| `/api/providers/health` | GET | Check provider status |
| `/api/chat/conversations` | GET, POST | Chat conversation management |
| `/api/memory/sessions` | GET | List Zep sessions |
| `/api/memory/sessions/{id}` | GET | Get session memory |
| `/api/analytics/channel` | GET | YouTube channel stats |
| `/api/events` | GET | SSE stream for real-time updates |
