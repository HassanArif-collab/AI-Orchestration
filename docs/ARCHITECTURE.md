# AI-Orchestration Architecture

## What This System Does

A multi-agent YouTube video production pipeline. Given a topic, it:
1. **Discovers** candidate topics via the Topic Finder agent
2. **Researches** deeply using web search + LLM synthesis
3. **Writes** dual-column scripts (narration + visual direction)
4. **Reviews** through human gates for quality control
5. **Publishes** final output to Notion/YouTube

---

## Why This Architecture Exists

### The Problem We're Solving

Video production has three challenges:
1. **Quality control** — AI can generate content, but needs human oversight
2. **Resumability** — Long pipelines crash; state must persist
3. **Provider fragility** — LLM APIs fail, rate limit, or change

### The Architecture Solution

| Problem | Solution | Where |
|---------|----------|-------|
| Quality control | Human gates at critical decisions | Pipeline stages 2, 7 |
| Resumability | SQLite state persistence | `packages/pipeline/state.py` |
| Provider fragility | FreeRouter proxy with failover | `freerouter/` service |

---

## Two-Layer Design

### Why Two Layers?

```
Layer 1: Infrastructure (reusable)
├── core/       ← Config, logging, errors
├── router/     ← LLM proxy client
├── pipeline/   ← State machine
├── agents/     ← Base classes
└── memory/     ← Zep Cloud client

Layer 2: Business Logic (domain-specific)
└── content_factory/   ← Video production logic
```

**Reasoning**:
- Infrastructure can be reused for other AI projects
- Business logic changes don't affect core systems
- Clear dependency direction prevents circular imports
- New developers can understand layers independently

**Consequence**: You can build a different content factory (e.g., blog writing) using the same infrastructure.

---

## Two-Service Architecture

### Why Two Services?

```
┌─────────────────────┐     HTTP      ┌─────────────────────┐
│   Main API          │ ───────────→  │   FreeRouter        │
│   (port 3000)       │               │   (port 4000)       │
│                     │               │                     │
│   - Dashboard       │               │   - LLM routing     │
│   - Pipeline state  │               │   - Rate limiting   │
│   - User facing     │               │   - Failover        │
└─────────────────────┘               └─────────────────────┘
```

**Reasoning**:
1. **Isolation**: LLM complexity (rate limits, retries, provider quirks) is isolated from business logic
2. **Scaling**: FreeRouter can serve multiple services (e.g., separate workers)
3. **Testing**: Mock one HTTP endpoint instead of multiple LLM APIs
4. **Security**: LLM keys only exist in FreeRouter, never in main app

**Consequence**: Must run two services. This is acceptable for the benefits gained.

### Why HTTP Instead of Import?

You might ask: "Why not import FreeRouter as a Python package?"

**Answer**: Importing would:
- Share process memory (crash together)
- Require same Python version
- Make testing harder (can't mock over network)
- Leak LLM keys into main process

HTTP keeps them independent.

---

## 9-Stage Pipeline

### Why 9 Stages?

```
Stage 1:  trend_analysis          ← AI discovers topics
Stage 2:  human_topic_approval    ← HUMAN GATE: You pick the topic
Stage 3:  research                ← AI researches deeply
Stage 4:  script_writing          ← AI writes dual-column script
Stage 5:  visual_planning         ← AI designs visuals
Stage 6:  seo                     ← AI generates metadata
Stage 7:  human_review            ← HUMAN GATE: You review script
Stage 8:  asset_creation          ← AI creates assets
Stage 9:  publish                 ← AI publishes to Notion
```

**Reasoning**:
- Stages map to distinct creative tasks (research ≠ writing ≠ visuals)
- Human gates at irreversible decisions (topic choice, final script)
- Each stage is independently testable
- Failures can resume from last successful stage

**Why human gates at stages 2 and 7?**
- Stage 2 (topic approval): Wrong topic = wasted 10+ minutes
- Stage 7 (script review): Script quality determines video quality

**Why not more human gates?**
- Too many gates creates fatigue
- AI handles routine decisions well
- Gate at points where human judgment matters most

---

## SQLite for State Persistence

### Why SQLite?

**Context**: Pipeline runs take 5-15 minutes. Crashes happen.

**Options Considered**:
| Database | Pros | Cons |
|----------|------|------|
| PostgreSQL | Production-ready, concurrent | Requires server setup |
| Redis | Fast, in-memory | Data lost on restart |
| SQLite | Zero-config, file-based | Single-server limitation |

**Decision**: SQLite with WAL mode

**Reasoning**:
- Zero configuration (no server to manage)
- File-based (easy backup, easy debugging)
- WAL mode handles concurrent reads
- Atomic transactions prevent corruption
- Single-server limitation is acceptable (current scale)

**Consequences**:
- Can't run multiple API servers sharing state
- Must manage SQLite file carefully
- Good for current scale; revisit if scaling horizontally

---

## FreeRouter LLM Proxy

### Why All LLM Calls Through One Client?

```python
# ❌ BAD: Direct API call
import openai
response = openai.chat.completions.create(...)

# ✅ GOOD: Through RouterClient
from packages.router.client import RouterClient
response = await router_client.chat(...)
```

**Reasoning**:
1. **Centralized failover**: If Groq fails, try OpenRouter, then Ollama
2. **Rate limit tracking**: Know when providers are exhausted
3. **Cost monitoring**: All usage goes through one point
4. **Testing**: Mock one client instead of multiple APIs

**Never bypass RouterClient.** This is a core architectural rule.

---

## Event-Driven Updates (SSE)

### Why Server-Sent Events?

```
┌─────────────┐        SSE        ┌─────────────┐
│   Server    │ ───────────────→  │   Browser   │
│             │   one-way stream  │             │
└─────────────┘                   └─────────────┘
```

**Options Considered**:
| Technology | Pros | Cons |
|------------|------|------|
| WebSocket | Bidirectional | Complex, overkill for one-way |
| Polling | Simple | Inefficient, high latency |
| SSE | Simple, native browser support | One-way only |

**Decision**: SSE (Server-Sent Events)

**Reasoning**:
- We only need server → client updates
- Native browser support (`EventSource` API)
- Automatic reconnection built-in
- Simpler than WebSocket

**Use Cases**:
- Stage completion notifications
- Human gate alerts
- Pipeline progress updates

---

## Package Dependency Order

### Why This Order Matters

```
packages/core           ← Load first (no internal deps)
packages/router         ← Depends on: core
packages/memory         ← Depends on: core
packages/pipeline       ← Depends on: core, router, memory
packages/agents         ← Depends on: core, router, memory
packages/content_factory← Depends on: core, router (via orchestration)
```

**Rules**:
1. `core` has no internal dependencies — everything can import from it
2. Business logic (`content_factory`) never imports from infrastructure directly
3. Circular imports = architecture violation

**How to add a new package**:
1. If infrastructure: import only from `core`
2. If business logic: import from infrastructure, never from other business logic

---

## Key File Locations

| What | Where | Why |
|------|-------|-----|
| Pipeline state | `packages/data/pipeline.db` | SQLite, gitignored |
| Agent prompts | `data/skills/*.md` | Source-controlled, editable |
| LLM config | `freerouter/.env` | Separate from main app |
| Main config | `.env` | Root level |

---

## Adding New Components

### Adding a New Agent

1. Create `packages/agents/your_agent.py` — inherit from `BaseAgent`
2. Register in `packages/agents/registry.py`
3. Add prompt at `data/skills/your_agent.md`
4. All LLM calls through `RouterClient`
5. Add tests in `tests/test_your_agent.py`

### Adding a New Pipeline Stage

1. Add to `packages/pipeline/stages.py`
2. Add handler in `packages/pipeline/runner.py`
3. Map to Kanban column in `PIPELINE_TO_KANBAN_STAGE`
4. Add frontend UI in `apps/api/static/js/pipeline.js`
5. Update `STAGE_DEFINITIONS` in `pipeline_routes.py`

---

## Security Model

| Concern | Mitigation |
|---------|------------|
| API key exposure | Keys in `.env` files, never in code |
| LLM key access | Only FreeRouter has LLM keys |
| Rate limit attacks | FreeRouter tracks per-provider limits |
| Input validation | Pydantic models on all API inputs |

---

## When to Revisit These Decisions

| Decision | Revisit When |
|----------|--------------|
| SQLite for state | Need horizontal scaling |
| Two-service architecture | Need to eliminate network latency |
| 9 stages | Business requirements change |
| SSE for updates | Need bidirectional real-time |
