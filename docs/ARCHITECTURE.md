# AI-Orchestration Architecture

## Repository Structure

```
AI-Orchestration/
├── freerouter/              ← EXISTING — the LLM proxy server (do not modify)
│   ├── src/freerouter/      ← FreeRouter source code
│   ├── data/conversations.db← FreeRouter's own SQLite DB (chat history)
│   └── .env                 ← Provider API keys (Groq, OpenRouter, etc.)
│
└── packages/                ← NEW — YouTube pipeline built on top of FreeRouter
    ├── core/                ← Shared types, config, logging, errors
    ├── router/              ← HTTP client wrapper around FreeRouter at :4000
    ├── memory/              ← GetZep Cloud agent memory client
    ├── pipeline/            ← State machine, stage orchestration
    ├── agents/              ← Individual agent implementations
    ├── visual/              ← Visual planning, Remotion/Radiant integration
    │   ├── remotion/        ← Remotion config generation
    │   └── radiant/         ← Shader background selection
    ├── integrations/        ← External API clients
    │   ├── youtube/         ← YouTube Data API v3
    │   ├── notion/          ← Notion API
    │   └── mirofish/        ← MiroFish API
    └── data/                ← Package-level SQLite DBs (usage, pipeline state)
        ├── usage_tracker.db ← API usage stats (from packages/router/tracker.py)
        └── pipeline.db      ← Pipeline run state (from packages/pipeline/)
```

## The Golden Rule: FreeRouter is an HTTP Server

FreeRouter is **not** a Python library. You **never** import from `freerouter/`.

```python
# WRONG — never do this
from freerouter.router import Router
from freerouter.providers import get_provider_key

# CORRECT — always call it via HTTP
from packages.router.client import RouterClient

async with RouterClient() as client:
    text = await client.complete_text("Your prompt here")
```

FreeRouter must be running as a separate process before any LLM calls work:
```bash
# Terminal 1
cd freerouter && python -m freerouter web    # dashboard at :8080

# Terminal 2
cd freerouter && python -m freerouter proxy  # API proxy at :4000
```

Or use the Makefile shortcuts:
```bash
make freerouter-web   # dashboard
make freerouter       # proxy
```

## Pipeline Data Flow

```
VideoIdea
    ↓  (research agent)
ResearchOutput
    ↓  (script agent)
Script
    ↓  (visual planning agent)
VisualPlan
    ↓  (SEO agent)
SEOPackage
    ↓  (upload agent)
YouTube
```

All stages use `PipelineState` to pass data. State is persisted in
`packages/data/pipeline.db` so runs survive crashes and can be resumed.

## LLM Routing

Every LLM call goes through `packages/router/client.RouterClient`:

```
RouterClient.complete_text(prompt, model="research")
    ↓
POST http://localhost:4000/v1/chat/completions
    ↓
FreeRouter picks best free provider:
    Ollama (local) → Groq → OpenRouter → Together → DeepInfra
    (auto-fallback if rate-limited)
    ↓
Response with x-freerouter-provider and x-freerouter-model headers
```

## Two Separate .env Files

| File | Purpose | Managed by |
|------|---------|------------|
| `freerouter/.env` | Provider API keys (Groq, OpenRouter, etc.) | FreeRouter dashboard at :8080 |
| `.env` (repo root) | Pipeline config (Zep, YouTube, Notion) | Copy from `.env.example` |

## Package Dependencies

```
packages/core        ← no internal dependencies
packages/router      ← packages/core
packages/memory      ← packages/core
packages/pipeline    ← packages/core, packages/router, packages/memory
packages/agents      ← packages/core, packages/router, packages/memory
packages/visual      ← packages/core, packages/router
packages/integrations← packages/core
```
