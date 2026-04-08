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
| Quality control | Human gates at critical decisions | LangGraph orchestration nodes |
| Resumability | Supabase-backed state persistence | `kanban_cards` + `agent_thoughts` tables |
| Provider fragility | FreeRouter proxy with failover | `freerouter/` service |

---

## Two-Layer Design

### Why Two Layers?

```
Layer 1: Infrastructure (reusable)
├── core/       ← Config, logging, errors, research cache
├── router/     ← LLM proxy client
├── agents/     ← Base classes + registry
├── memory/     ← Zep Cloud client
├── integrations/ ← YouTube, Notion clients
└── visual/     ← Remotion video animations

Layer 2: Business Logic (domain-specific)
└── content_factory/   ← LangGraph orchestration + video production logic
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

## Production Pipeline (LangGraph)

### Current Pipeline — 4 Feedback Loops

The production pipeline uses LangGraph with **four feedback loops** for iterative quality improvement:

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

### Nodes (defined in `orchestration/nodes.py`)

| Node | Purpose | Model | Feedback Loop |
|------|---------|-------|---------------|
| `load_learnings` | Load past winning patterns from Zep memory | system | — |
| `research` | Deep research via Exa.ai web search + LLM synthesis (5-phase deer-flow methodology) | researcher | — |
| `research_gap` | Targeted supplementary search when credibility is low | researcher | Research Feedback |
| `draft` | Generate script from research + style constitution + genre rules | script_writer | All loops return here |
| `score` | 56-question binary checklist evaluation (9 categories) | scorer | Karpathy Loop |
| `mutate` | Improve weakest sections per scorer feedback | challenger | Karpathy Loop |
| `capture_learning` | Store winning patterns to Zep for future scripts | — | — |
| `visuals` | Add visual annotations + structural review | annotator | Visual Feedback |
| `human_review` | Pause graph for human approval (LangGraph interrupt) | — | Human Review |
| `publish` | Publish approved script to Notion | — | — |

### The 4 Feedback Loops

1. **Karpathy Mutation Loop** (`score → mutate → score`): Up to 20 iterations. Scorer identifies weak sections, mutator rewrites them. Best draft is tracked across all iterations.

2. **Research Feedback Loop** (`score → research_gap → draft`): When credibility score < 60% on first pass AND research hasn't been supplemented yet. Runs targeted supplementary searches on 2-3 identified gaps, appends findings to dossier, then routes back to draft. Max 1 additional research round.

3. **Visual Feedback Loop** (`visuals → draft`): Visual annotator runs structural review. If the script is too abstract or visually unproduceable, routes back to draft with specific feedback for the writer.

4. **Human Review Loop** (`human_review → draft`): After visual annotations, the graph pauses for human review. If rejected, routes back to draft with human feedback. Iteration count resets for fresh mutation budget.

### Style & Genre Injection

The script writer loads two JSON files at module level:
- **`style_reference.json`** — Full Johnny Harris constitution (anchor-bridge formula, classic style writing, peer-to-peer framing, motive loading, conclusion shift, Pakistani adaptation)
- **`genre_schema.json`** — Genre-specific structural backbone, key challenge, and conclusion pattern

These are injected into the script writer prompt and mutator prompt, ensuring consistent non-AI voice across all iterations.

### Why This Design?

- **Quality without human fatigue**: 3 automated feedback loops handle routine improvements. Human only reviews the final result.
- **Voice consistency**: Style constitution is loaded once and injected into every draft and mutation, preventing the "each iteration sounds more generic" problem.
- **Research depth**: If the scorer detects thin evidence, the pipeline automatically gets more research before continuing — the writer never has to work with shallow research.
- **Crash-proof**: LangGraph checkpoints state after every node. If the server dies at iteration 14, restart picks up exactly where it left off.

### Discovery Graph (Separate)

The discovery graph finds and grades candidate topics. It runs independently with no loops or human gates:

```
gather_context → search_web → generate_topics → grade_viability → save_topics → END
```

---

## Supabase for State Persistence

### Why Supabase?

**Context**: Pipeline runs take 5-15 minutes. The system needs realtime updates for the frontend.

**Options Considered**:
| Database | Pros | Cons |
|----------|------|------|
| PostgreSQL (Supabase) | Production-ready, realtime, concurrent | Requires external service |
| Redis | Fast, in-memory | Data lost on restart |
| SQLite | Zero-config, file-based | Single-server, no realtime |

**Decision**: Supabase (managed PostgreSQL)

**Reasoning**:
- Realtime subscriptions for live frontend updates
- Concurrent connections for API + frontend
- JSONB columns for flexible metadata storage
- Managed service with auth and RLS support

**Key Tables**:
- `kanban_cards` — Pipeline task cards moving through columns
- `agent_thoughts` — Real-time agent thinking updates
- `pipeline_runs` — LangGraph checkpoint snapshots
- `research_dossiers` — Cached research results

**Consequences**:
- Requires Supabase project setup
- External dependency (but managed, no self-hosting)
- Realtime enables reactive frontend without polling

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
packages/core            ← Load first (no internal deps)
packages/router          ← Depends on: core
packages/memory          ← Depends on: core
packages/agents          ← Depends on: core, router, memory
packages/integrations    ← Depends on: core
packages/content_factory ← Depends on: core, router, memory (via orchestration)
```

**Rules**:
1. `core` has no internal dependencies — everything can import from it
2. Business logic (`content_factory`) imports from infrastructure, never the reverse
3. Circular imports = architecture violation

**How to add a new package**:
1. If infrastructure: import only from `core`
2. If business logic: import from infrastructure, never from other business logic

---

## Key File Locations

| What | Where | Why |
|------|-------|-----|
| Pipeline state | Supabase (`kanban_cards`, `agent_thoughts`) | PostgreSQL, realtime |
| Agent prompts | `data/skills/*.md` | Source-controlled, editable |
| LLM config | `freerouter/.env` | Separate from main app |
| Main config | `.env` | Root level |
| LangGraph graphs | `packages/content_factory/orchestration/graphs.py` | Active pipeline execution |

---

## Adding New Components

### Adding a New Agent

1. Create `packages/agents/your_agent.py` — inherit from `BaseAgent`
2. Register in `packages/agents/registry.py`
3. Add prompt at `data/skills/your_agent.md`
4. All LLM calls through `RouterClient`
5. Add tests in `tests/test_your_agent.py`

### Adding a New Pipeline Stage

1. Add a node function in `packages/content_factory/orchestration/nodes.py`
2. Wire it into the LangGraph graph in `packages/content_factory/orchestration/graphs.py`
3. Add the stage definition in `apps/api/routers/pipeline_routes.py` (`STAGE_DEFINITIONS`)
4. Add frontend UI in the React app (`apps/web/src/`)

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
