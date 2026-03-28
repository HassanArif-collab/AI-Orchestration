# Phase 0 Analysis: High-Level System Understanding

**Date**: 2026-03-25
**Status**: Complete

---

## 1. WHAT IS THIS SYSTEM?

### Simple Explanation

This is an **AI-powered YouTube video production pipeline**. Think of it like a factory that takes a topic idea and produces a complete video script with visual directions, music cues, and SEO metadata - all automatically using AI.

**What problem does it solve?**
- Creating documentary-style videos is time-consuming
- Research, script writing, visual planning, and SEO optimization require different skills
- This system automates all of that using AI agents

**Who is it for?**
- Content creators who want to produce Pakistani documentary content
- Specifically designed for "Johnny Harris-style" explanatory videos

**What does it produce?**
- A dual-column script (spoken words on left, visual directions on right)
- SEO package (7 titles, description, 20 tags, thumbnail concepts)
- Music architecture document
- Published page on Notion (optional)

---

## 2. HOW DOES IT WORK AT A HIGH LEVEL?

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AI-Orchestration System                         │
│                                                                         │
│   USER INPUT          AI PROCESSING           OUTPUT                   │
│   ──────────          ─────────────           ──────                   │
│                                                                         │
│   ┌──────────┐       ┌──────────────┐       ┌──────────────┐          │
│   │  Topic   │  ───▶ │   Research   │  ───▶ │   Script     │          │
│   │  Idea    │       │   (Web + LLM)│       │   Document   │          │
│   └──────────┘       └──────────────┘       └──────────────┘          │
│                              │                      │                   │
│                              ▼                      ▼                   │
│                      ┌──────────────┐       ┌──────────────┐          │
│                      │   Scoring    │  ◀─── │   Music      │          │
│                      │   (Self-fix) │       │   Architecture│          │
│                      └──────────────┘       └──────────────┘          │
│                              │                                          │
│                              ▼                                          │
│                      ┌──────────────┐                                   │
│                      │     SEO      │                                   │
│                      │   Package    │                                   │
│                      └──────────────┘                                   │
│                              │                                          │
│                              ▼                                          │
│                      ┌──────────────┐                                   │
│                      │   Notion     │                                   │
│                      │   (optional) │                                   │
│                      └──────────────┘                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Two Modes of Operation

| Mode | Description | When Used |
|------|-------------|-----------|
| **Mode A (Adaptation)** | Takes an existing Johnny Harris video URL, extracts content, adapts for Pakistani audience | When `content_type="adaptation"` |
| **Mode B (Original)** | Creates completely original content from scratch using AI research | When `content_type="original"` (default) |

---

## 3. STEP-BY-STEP FLOW

### The 9-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PIPELINE STAGES                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Stage 1: TREND_ANALYSIS                                               │
│  ────────────────────────                                              │
│  What: AI generates 3 topic candidates for user to choose from         │
│  Input: Seed query (e.g., "Pakistan economy")                         │
│  Output: List of topic briefs with viability scores                   │
│  Time: ~30 seconds                                                     │
│                                                                         │
│         ⬇️                                                             │
│                                                                         │
│  Stage 2: HUMAN_TOPIC_APPROVAL ⚠️ [HUMAN GATE]                         │
│  ────────────────────────────────────────                              │
│  What: User picks one topic from candidates                            │
│  Input: User clicks/selects a topic                                    │
│  Output: Single approved TopicBrief                                    │
│  Time: User-dependent                                                  │
│                                                                         │
│         ⬇️                                                             │
│                                                                         │
│  Stage 3: RESEARCH                                                     │
│  ────────────────────────                                              │
│  What: Deep research using web search + LLM synthesis                  │
│  Input: Approved TopicBrief                                           │
│  Output: ResearchDossier (facts, anchors, characters, sources)         │
│  Time: ~2-5 minutes (up to 20 web searches)                           │
│                                                                         │
│         ⬇️                                                             │
│                                                                         │
│  Stage 4: SCRIPT_WRITING                                               │
│  ────────────────────────                                              │
│  What: Write dual-column script, then self-improve via A/B testing     │
│  Input: ResearchDossier                                                │
│  Output: AdaptedScript with production_readiness_score                 │
│  Time: ~5-15 minutes (up to 20 improvement iterations)                │
│                                                                         │
│         ⬇️                                                             │
│                                                                         │
│  Stage 5: VISUAL_PLANNING                                              │
│  ─────────────────────────                                              │
│  What: Design music/emotional architecture for the video               │
│  Input: Refined AdaptedScript                                          │
│  Output: MusicArchitectureDocument                                     │
│  Time: ~30 seconds                                                     │
│                                                                         │
│         ⬇️                                                             │
│                                                                         │
│  Stage 6: HUMAN_REVIEW ⚠️ [HUMAN GATE]                                 │
│  ────────────────────────────────                                       │
│  What: User reviews script and music plan                              │
│  Input: User approval/feedback                                         │
│  Output: Approved or feedback for revision                             │
│  Time: User-dependent                                                  │
│                                                                         │
│         ⬇️                                                             │
│                                                                         │
│  Stage 7: ASSET_CREATION                                               │
│  ────────────────────────                                              │
│  What: Register visual render jobs (Remotion animations)               │
│  Input: MusicArchitectureDocument                                      │
│  Output: VisualManifest with pending jobs                              │
│  Time: ~10 seconds (can be disabled via feature flag)                  │
│                                                                         │
│         ⬇️                                                             │
│                                                                         │
│  Stage 8: SEO                                                          │
│  ────────────────────────                                              │
│  What: Generate titles, description, tags, thumbnail concepts          │
│  Input: Final AdaptedScript                                            │
│  Output: SEO package (7 titles + desc + 20 tags + 3 thumbnails)        │
│  Time: ~30 seconds                                                     │
│                                                                         │
│         ⬇️                                                             │
│                                                                         │
│  Stage 9: PUBLISH                                                      │
│  ────────────────────────                                              │
│  What: Send to Notion (if API key configured)                          │
│  Input: Script + SEO package                                           │
│  Output: Notion page URL or dry-run log                                │
│  Time: ~10 seconds                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Human Interaction Points

The pipeline pauses at two stages requiring human approval:

1. **HUMAN_TOPIC_APPROVAL**: After AI suggests 3 topics, user picks one
2. **HUMAN_REVIEW**: After script is written, user reviews and approves

---

## 4. COMPONENT MAP

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM COMPONENTS                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                     INFRASTRUCTURE LAYER                            ││
│  ├─────────────────────────────────────────────────────────────────────┤│
│  │                                                                     ││
│  │  packages/core/          Config, Logging, Errors, Types            ││
│  │  ├── config.py          ← All environment variables loaded here    ││
│  │  ├── logger.py          ← Structured logging (structlog)           ││
│  │  ├── errors.py          ← Custom exception classes                 ││
│  │  └── types.py           ← Shared type definitions                  ││
│  │                                                                     ││
│  │  packages/router/        LLM Communication                         ││
│  │  ├── client.py          ← HTTP client to FreeRouter (:4000)        ││
│  │  ├── web_search.py      ← Web search via z-ai-web-dev-sdk          ││
│  │  └── capabilities.py    ← Maps tasks to best LLM model             ││
│  │                                                                     ││
│  │  packages/memory/        Persistent Agent Memory (Zep Cloud)       ││
│  │  ├── client.py          ← Zep API client                           ││
│  │  └── schemas.py         ← Memory data structures                   ││
│  │                                                                     ││
│  │  packages/pipeline/      9-Stage State Machine                      ││
│  │  ├── stages.py          ← Stage definitions & dependencies         ││
│  │  ├── runner.py          ← Executes stages in order                 ││
│  │  ├── state.py           ← PipelineRun state (SQLite)               ││
│  │  ├── handlers.py        ← What happens at each stage               ││
│  │  └── research_cache.py  ← Caches research results                  ││
│  │                                                                     ││
│  │  packages/agents/        Agent Framework                            ││
│  │  ├── base.py            ← BaseAgent class                          ││
│  │  └── registry.py        ← Agent registration & skill loading       ││
│  │                                                                     ││
│  │  packages/integrations/  External APIs                              ││
│  │  ├── notion/client.py   ← Notion API (script pages)                ││
│  │  ├── youtube/client.py  ← YouTube Data API                         ││
│  │  └── mirofish/client.py ← Trend simulation                         ││
│  │                                                                     ││
│  │  packages/visual/        Video Rendering Support                    ││
│  │  ├── remotion/          ← React-based animations                   ││
│  │  ├── radiant/           ← Shader backgrounds                       ││
│  │  └── manifest.py        ← Asset tracking                           ││
│  │                                                                     ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                      BUSINESS LOGIC LAYER                          ││
│  ├─────────────────────────────────────────────────────────────────────┤│
│  │                                                                     ││
│  │  packages/content_factory/   Video Production Pipeline              ││
│  │  │                                                                 ││
│  │  ├── models.py           ← AdaptedScript, DualColumnEntry          ││
│  │  ├── router.py           ← Routes to Mode A or Mode B              ││
│  │  │                                                                 ││
│  │  ├── topic_finder/       ← Topic Discovery                         ││
│  │  │   └── finder.py       ← Generates candidate topics              ││
│  │  │                                                                 ││
│  │  ├── production/         ← Original Content Creation (Mode B)      ││
│  │  │   ├── deep_research.py ← 4-phase research methodology           ││
│  │  │   ├── workflow.py     ← RoundBasedProductionWorkflow            ││
│  │  │   └── models.py       ← ResearchDossier, ResearchFact           ││
│  │  │                                                                 ││
│  │  ├── adaptation/         ← Content Adaptation (Mode A)             ││
│  │  │   ├── stage1_extraction.py   ← Extract from source              ││
│  │  │   ├── stage2_structural.py   ← Build structure map              ││
│  │  │   ├── stage3_localization.py ← Adapt for Pakistani audience     ││
│  │  │   └── stage4_script.py       ← Generate dual-column script      ││
│  │  │                                                                 ││
│  │  ├── evaluation/         ← Self-Improvement Loop                   ││
│  │  │   ├── scoring.py      ← Production readiness scorer             ││
│  │  │   ├── baseline.py     ← Champion script store                   ││
│  │  │   ├── mutation.py     ← Script mutation strategies              ││
│  │  │   └── loop.py         ← A/B challenger loop                     ││
│  │  │                                                                 ││
│  │  ├── music/              ← Music Architecture                      ││
│  │  │   ├── arc_designer.py ← Emotional arc design                    ││
│  │  │   └── section_brief.py← Per-section music briefs                ││
│  │  │                                                                 ││
│  │  └── orchestration/      ← System Coordination                     ││
│  │      ├── master.py       ← Top-level cycle controller              ││
│  │      ├── scheduler.py    ← Automated production schedule           ││
│  │      └── synthesis.py    ← Learning synthesis engine               ││
│  │                                                                     ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                        APPLICATION LAYER                            ││
│  ├─────────────────────────────────────────────────────────────────────┤│
│  │                                                                     ││
│  │  apps/api/                Web Dashboard (Port 3000)                ││
│  │  ├── main.py             ← FastAPI application                     ││
│  │  ├── events.py           ← SSE for real-time updates               ││
│  │  └── routers/            ← API endpoints                           ││
│  │      ├── pipeline_routes.py  ← Pipeline CRUD, human gates          ││
│  │      ├── chat_routes.py      ← Direct LLM chat                     ││
│  │      ├── memory_routes.py    ← Zep memory browser                  ││
│  │      └── settings_routes.py  ← System health/config                ││
│  │                                                                     ││
│  │  apps/worker/             CLI Pipeline Worker                      ││
│  │  └── main.py             ← Command-line pipeline runner            ││
│  │                                                                     ││
│  │  freerouter/              LLM Proxy (Port 4000) ⚠️ REQUIRED FIRST  ││
│  │  ├── src/freerouter/     ← Standalone proxy service                ││
│  │  │   ├── proxy_server.py ← HTTP proxy for LLM APIs                 ││
│  │  │   ├── providers.py    ← Groq, OpenRouter, Ollama clients        ││
│  │  │   └── router.py       ← Auto-fallback between providers         ││
│  │  └── .env                ← LLM provider keys (SEPARATE from root)  ││
│  │                                                                     ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. EXTERNAL SERVICES REQUIRED

### Required Services (System Won't Start Without These)

| Service | Purpose | Setup |
|---------|---------|-------|
| **FreeRouter** | LLM proxy (must run on port 4000) | `make freerouter` |
| **Groq API Key** | LLM provider (primary) | Add to `freerouter/.env` |

### Optional Services (Features Disabled if Missing)

| Service | Purpose | Env Variable | What Happens if Missing |
|---------|---------|--------------|------------------------|
| **OpenRouter** | Alternative LLM provider | `OPENROUTER_API_KEY` | Falls back to Groq only |
| **Zep Cloud** | Persistent agent memory | `ZEP_API_KEY` | Memory features disabled |
| **Notion** | Script publishing | `NOTION_API_KEY` | Dry-run mode (no publish) |
| **YouTube API** | Analytics | `YOUTUBE_API_KEY` | Analytics tab empty |

---

## 6. KEY TECHNOLOGIES

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Primary language |
| **FastAPI** | Latest | Web framework for dashboard |
| **Pydantic** | 2.0+ | Data validation & models |
| **SQLite** | Built-in | Pipeline state, topic reservoir |
| **structlog** | 24.0+ | Structured logging |
| **httpx** | 0.27+ | Async HTTP client |
| **CrewAI** | 0.80+ | Multi-agent orchestration |
| **z-ai-web-dev-sdk** | External | Web search capability |

---

## 7. QUESTIONS FOR THE USER

Before proceeding to Phase 1 (detailed code analysis), I need to understand:

### ABOUT YOUR GOALS:

1. **What is your main use case for this system?**
   - [ ] Generate complete video scripts end-to-end
   - [ ] Just the research phase
   - [ ] Adapt existing Johnny Harris videos
   - [ ] Something else: _____________

2. **What output do you need most?**
   - [ ] Script document (dual-column format)
   - [ ] Published Notion page
   - [ ] SEO metadata (titles, tags)
   - [ ] All of the above

### ABOUT YOUR INFRASTRUCTURE:

3. **Where is this system running?**
   - [ ] Local machine (laptop/desktop)
   - [ ] Cloud server (which provider?)
   - [ ] Docker container
   - [ ] Not sure

4. **Do you have FreeRouter running?**
   - [ ] Yes, on port 4000
   - [ ] No, I need help setting it up
   - [ ] Not sure what this is

5. **Which LLM API keys do you have?**
   - [ ] Groq API key
   - [ ] OpenRouter API key
   - [ ] OpenAI API key
   - [ ] Ollama (local)
   - [ ] None yet

### ABOUT YOUR PROBLEMS:

6. **What issues are you experiencing?** (Check all that apply)
   - [ ] System crashes or errors
   - [ ] Produces bad/low-quality output
   - [ ] Hangs or times out
   - [ ] Too slow
   - [ ] Can't get it to run at all
   - [ ] Other: _____________

7. **What's your experience level with this codebase?**
   - [ ] I wrote most of it
   - [ ] I understand the architecture
   - [ ] I've used it but don't understand internals
   - [ ] New to this codebase

---

## 8. NEXT STEPS

After answering the questions above, I will proceed to:

- **Phase 1**: Analyze configuration and environment
- **Phase 2**: Check FreeRouter integration
- **Phase 3**: Review deep research engine
- **Phase 4**: Examine pipeline handlers
- **Phase 5**: Test script generation
- **Phase 6**: Review API layer
- **Phase 7**: Check external integrations
- **Phase 8**: Error handling analysis
- **Phase 9**: Test coverage
- **Phase 10**: End-to-end flow test

---

**Please answer the questions in Section 7 so I can tailor the analysis to your specific needs.**
