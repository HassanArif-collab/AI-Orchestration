# AI-Orchestration Architecture

## What This System Does

A multi-agent YouTube video production pipeline. Given a topic, it:
1. **Discovers** candidate topics via the Topic Finder agent (stored in SQLite reservoir)
2. **Adapts** source content through a 4-stage pipeline (extract → structural → localize → script)
3. **Scores** each script against a baseline via an evolutionary A-B evaluation loop
4. **Designs** a music architecture (arc, section briefs, silence map) via the Music agent
5. **Publishes** the final output to YouTube via the production workflow

All LLM calls are free — routed through FreeRouter which auto-selects the best available provider (Groq → OpenRouter → Ollama).

---

## Two Services — Both Must Run

This system is split into two separately-running processes:

### Service 1: FreeRouter (start this FIRST)
```bash
make freerouter        # LLM proxy on :4000 — required for all LLM calls
make freerouter-web    # Web dashboard on :8080 — manage provider API keys
```

FreeRouter is a **standalone service** in `freerouter/`. It has its own `pyproject.toml`, `.env`, and `tests/`. **Never import from `freerouter/` directly** — always call it via HTTP through `packages/router/client.py`.

### Service 2: The Pipeline (the main app)
```bash
pip install -e ".[all]"
python apps/worker/main.py start   # full worker
python scripts/run_pipeline.py     # smoke test
```

---

## Two-Layer Package Architecture

```
packages/
│
│  ── Layer 1: Infrastructure ──────────────────────────────────────────
│
├── core/           Config (loads .env), logger, typed errors, shared types.
│                   Foundation — everything else imports from here.
│
├── router/         HTTP client to FreeRouter at :4000.
│                   ALL LLM calls go through RouterClient here.
│                   Never call LLM APIs directly.
│
├── memory/         Zep Cloud agent memory.
│                   Handles conversation history + long-term facts for agents.
│
├── pipeline/       9-stage state machine runner.
│                   Persists state in packages/data/pipeline.db.
│                   Stages with human gates pause for approval.
│
├── agents/         Base AgentClass + AgentRegistry.
│                   Skill/prompt files live in data/skills/*.md
│
├── integrations/   External API clients:
│   ├── youtube/      YouTube Data API v3 (upload, analytics)
│   ├── notion/       Notion API (script pages)
│   └── mirofish/     MiroFish trend simulation
│
├── visual/         Video rendering support:
│   ├── remotion/     Remotion config generation (React-based animations)
│   └── radiant/      Canvas shader background selection
│
│  ── Layer 2: Business Logic ──────────────────────────────────────────
│
└── content_factory/   The actual AI pipeline work.
    │
    ├── models.py          Shared Pydantic models (AdaptedScript, DualColumnEntry…)
    ├── source_library.py  Source video catalogue + processing status
    │
    ├── topic_finder/      Topic discovery agent.
    │                      Stores candidates in SQLite reservoir.
    │                      Scores topics by gap type, viability, urgency.
    │
    ├── adaptation/        4-stage content pipeline:
    │   ├── stage1_extraction.py   Extract raw content from source
    │   ├── stage2_structural.py   Build structural map
    │   ├── stage3_localization.py Localise for target audience
    │   └── stage4_script.py       Generate dual-column script
    │
    ├── evaluation/        Evolutionary A-B improvement loop:
    │   ├── baseline.py    Champion script store (SQLite)
    │   ├── scoring.py     Production readiness scorer
    │   ├── mutation.py    Script mutation strategies
    │   └── loop.py        Challenger vs baseline cycle
    │
    ├── music/             Music architecture agent:
    │   ├── arc_designer.py   Emotional arc across sections
    │   ├── section_brief.py  Per-section music brief
    │   └── transitions.py    Transition design between sections
    │
    ├── production/        Final production workflow and agents.
    │
    └── orchestration/     System-level coordination:
        ├── master.py      MasterOrchestrator — top-level cycle controller
        ├── scheduler.py   Automated production schedule
        ├── monitor.py     Health dashboard
        ├── review.py      Human review interface
        ├── synthesis.py   Learning synthesis engine (reads Zep insights)
        └── updates.py     Applies synthesised learnings to system prompts
```

---

## Data Flow

```
TopicBrief (from topic_finder)
    │
    ▼
content_factory/adaptation/runner.py
    │   stage1: RawExtraction
    │   stage2: StructuralMap
    │   stage3: LocalizationMap
    │   stage4: AdaptedScript
    ▼
content_factory/evaluation/loop.py
    │   score script → compare to baseline → keep winner
    ▼
content_factory/music/agent.py
    │   generate MusicArchitectureDocument
    ▼
content_factory/production/workflow.py
    │   run production agents
    ▼
packages/integrations/youtube/client.py
    │   upload to YouTube
    ▼
Published Video
```

---

## Two Separate `.env` Files

| File | Contains | Managed by |
|------|----------|------------|
| `freerouter/.env` | LLM provider keys: `GROQ_API_KEY`, `OPENROUTER_API_KEY` | FreeRouter dashboard at `:8080` |
| `.env` (repo root) | Pipeline keys: `ZEP_API_KEY`, `YOUTUBE_API_KEY`, `NOTION_API_KEY`, `GITHUB_TOKEN` | Copy from `.env.example`, fill manually |

**Never put LLM provider keys in the root `.env`.** They belong in `freerouter/.env`.

---

## Package Dependency Order

```
packages/core           ← no internal dependencies (load this first)
packages/router         ← packages/core
packages/memory         ← packages/core
packages/integrations   ← packages/core
packages/pipeline       ← packages/core, packages/router, packages/memory
packages/agents         ← packages/core, packages/router, packages/memory
packages/visual         ← packages/core, packages/router
packages/content_factory← packages/core, packages/router (via orchestration)
apps/api                ← all packages
apps/worker             ← packages/pipeline, packages/agents
```

---

## How to Add a New Agent

1. Create `packages/agents/your_agent.py` — inherit from `packages/agents/base.BaseAgent`
2. Register it in `packages/agents/registry.py` via `AgentRegistry.register()`
3. Add its skill/prompt file at `data/skills/your_agent.md`
4. Use `packages/agents/registry.load_skill("your_agent")` to load the prompt
5. All LLM calls must go through `packages/router/client.RouterClient`
6. Add tests in `tests/test_your_agent.py`

---

## Key Runtime Data Locations

| Path | Contents | Git status |
|------|----------|------------|
| `packages/data/pipeline.db` | Pipeline run state | Gitignored — auto-created |
| `packages/data/synthesis_reports/` | Learning loop JSON outputs | Gitignored |
| `freerouter/data/conversations.db` | FreeRouter chat history | Gitignored |
| `data/skills/*.md` | Agent skill/prompt definitions | Committed — source code |
