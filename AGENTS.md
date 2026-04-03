# AGENTS.md — AI-Orchestration / YouTube Pipeline
## Read this before writing any code in this repository.

---

## What this system does

Multi-agent YouTube video production pipeline.  
Given a topic: **discover → adapt → score → music → publish**.  
All LLM calls are free — routed through FreeRouter (Groq / OpenRouter / Ollama auto-fallback).

---

## CRITICAL: Start FreeRouter before anything else

```bash
make freerouter        # LLM proxy on :4000  ← required for ALL LLM calls
make freerouter-web    # Dashboard on :8080   ← optional, manages provider keys
```

- FreeRouter has its **own** `.env` at `freerouter/.env`
- Provider keys (`GROQ_API_KEY`, `OPENROUTER_API_KEY`) go there — managed via dashboard at `:8080`
- **Do NOT add LLM provider keys to the root `.env`**
- Root `.env` is ONLY for pipeline integration keys (Zep, YouTube, Notion)

---

## Two-layer package architecture

### Layer 1 — Infrastructure (`packages/X/`)

| Package | Purpose |
|---|---|
| `packages/core/` | Config (all env vars), logger, errors, shared types, research cache. Everything imports from here. |
| `packages/router/` | HTTP client to FreeRouter — **ALL LLM calls go through here** |
| `packages/memory/` | Zep Cloud agent memory (conversation + long-term facts) |
| `packages/agents/` | Base `AgentClass` + `AgentRegistry`. Skill prompts in `data/skills/*.md` |
| `packages/integrations/` | YouTube Data API, Notion clients |
| `packages/visual/` | Remotion video animations + Radiant shader backgrounds |

### Layer 2 — Business logic (`packages/content_factory/`)

| Module | Purpose |
|---|---|
| `topic_finder/` | Discovers and scores candidate topics, stores in SQLite reservoir |
| `music/` | Music architecture agent: emotional arc, section briefs, silence map |
| `production/` | Final production publishing |
| `orchestration/` | LangGraph graphs, scheduler, health monitor, review interface, thoughts |

---

## Rules — never violate these

- **All LLM calls** must go through `packages/router/client.RouterClient` → FreeRouter
- **All config** must load from `packages/core/config.get_settings()` via root `.env`
- **Never hardcode** an API key anywhere in source code
- **Never import** from `freerouter/` directly — it is a black-box HTTP service
- New agents → `packages/agents/` inheriting `base.BaseAgent`, register in `registry.py`
- New skill prompts → `data/skills/your_agent.md` (loaded via `registry.load_skill()`)
- New tests → `tests/test_*.py` with `def test_` prefix — **never at repo root**
- Generated/runtime data → `packages/data/` (gitignored — never commit `.db` or `.jsonl`)
- `freerouter/` is a standalone service — leave its internals untouched

---

## How to add a new agent

```
1. packages/agents/your_agent.py       ← inherit from base.BaseAgent
2. packages/agents/registry.py         ← AgentRegistry.register(YourAgent())
3. data/skills/your_agent.md           ← skill/prompt definition
4. tests/test_your_agent.py            ← tests with test_ prefix
```

Use `packages/agents/registry.load_skill("your_agent")` to load the prompt.  
Use `packages/router/client.RouterClient` for all LLM calls.

---

## Run commands

```bash
# Install everything
pip install -e ".[all]"

# Start FreeRouter (required first — separate terminal)
make freerouter

# Run test suite
pytest tests/ -v

# Lint / format
make lint
make format
```

---

## Key file locations

| Path | What it is |
|---|---|
| `packages/core/config.py` | Single source of truth for all env vars |
| `packages/router/client.py` | The only way to make LLM calls |
| `packages/content_factory/models.py` | Shared Pydantic models (AdaptedScript, etc.) |
| `packages/content_factory/orchestration/graphs.py` | LangGraph pipeline graph definitions |
| `packages/content_factory/orchestration/nodes.py` | Individual pipeline stage node functions |
| `data/skills/*.md` | Agent skill/prompt definitions (source code — committed) |
| `docs/ARCHITECTURE.md` | Full architecture reference with data flow diagram |
| `freerouter/.env` | LLM provider keys (gitignored — fill via `:8080` dashboard) |
| `.env` | Pipeline integration keys (gitignored — copy from `.env.example`) |

---

## Two separate `.env` files

```
freerouter/.env   ← GROQ_API_KEY, OPENROUTER_API_KEY  (managed via :8080 dashboard)
.env              ← ZEP_API_KEY, YOUTUBE_API_KEY, NOTION_API_KEY, GITHUB_TOKEN
```

See `.env.example` for all required root `.env` variables.

---

## Pipeline Wiring Map

The active pipeline is powered by **LangGraph** (not the legacy PipelineRunner, which was removed in Phase 5).

Entry point: `packages/content_factory/orchestration/graphs.py`

### LangGraph Nodes (defined in `orchestration/nodes.py`)
  - `trend_analysis` — Topic discovery via TopicFinderAgent
  - `human_topic_approval` — Human gate: pick topic
  - `research` — Deep research with web search + LLM synthesis
  - `script_writing` — Dual-column script generation
  - `visual_planning` — Visual direction + music architecture
  - `seo` — Metadata generation (titles, tags, description)
  - `human_review` — Human gate: review script
  - `asset_creation` — Generate visual assets
  - `publish` — Publish to Notion / YouTube

### State persistence
  - `kanban_cards` (Supabase) — Card state for each pipeline run
  - `agent_thoughts` (Supabase) — Real-time agent thinking updates
  - `pipeline_runs` (Supabase) — LangGraph checkpoint snapshots

---

## Genres supported
  - `history`
  - `current_situation`
  - `tech_systems`
  - `comparison`
  - `islamic_history`
  - `south_asian_history`

## Zep memory (optional)
Set `ZEP_ENABLED=true` in `.env` ONLY after confirming `ZEP_API_KEY` works.
Default is false — pipeline runs fully without Zep.

---

## Documentation map — where to learn about each system

| System | Primary docs |
|---|---|
| Hermes memory architecture | `packages/content_factory/orchestration/memory.py` |
| Zep Cloud integration | `packages/memory/client.py` (class docstring) |
| Zep setup (first time) | `packages/memory/init_zep.py` + run the script |
| Session naming conventions | `packages/memory/schemas.py` |
| Knowledge base (4 JSON files) | `packages/content_factory/KNOWLEDGE_BASE.md` |
| Music architecture | `packages/content_factory/music/__init__.py` |
| Orchestration (LangGraph graphs) | `packages/content_factory/orchestration/__init__.py` |
| Topic finder + feedback loop | `packages/content_factory/topic_finder/__init__.py` |
| Agent types (BaseAgent) | `packages/agents/base.py` |
| Capability → model mapping | `packages/router/capabilities.py` |
| API routes | `apps/api/main.py` |
