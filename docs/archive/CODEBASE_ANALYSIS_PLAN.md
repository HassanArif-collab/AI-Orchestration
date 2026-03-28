# AI-Orchestration Codebase Analysis Plan

This document contains step-by-step prompts for an AI agent to analyze the codebase for flaws, errors, broken code, and clarification questions.

---

## Overview for the AI Agent

You are analyzing the **AI-Orchestration** system - a video production pipeline that:
- Generates Pakistani documentary content using AI
- Uses deer-flow methodology for deep research
- Integrates with multiple LLM providers via FreeRouter
- Has a 9-stage pipeline with human approval gates

**Your task**: Systematically analyze each component, find issues, and ask clarifying questions about intended behavior.

---

## Phase 0: High-Level System Understanding

### Prompt 0.1 - What Does This System Do?
```
Your first task is to understand the big picture. Read the following files to understand 
what this system is and what it does:

1. Read README.md - Project overview
2. Read AGENTS.md - AI session context and architecture map
3. Read docs/ARCHITECTURE.md - Technical architecture
4. Read pyproject.toml - Project metadata and dependencies

Then explain in SIMPLE LANGUAGE:

1. WHAT IS THIS SYSTEM?
   - What problem does it solve?
   - Who is it for?
   - What does it produce as output?

2. HOW DOES IT WORK AT A HIGH LEVEL?
   - What are the main components?
   - How do they connect to each other?
   - What is the flow from start to finish?

3. WHAT EXTERNAL SERVICES DOES IT NEED?
   - What APIs or external tools are required?
   - What needs to be running for this to work?

4. WHAT ARE THE KEY TECHNOLOGIES?
   - Programming language and version
   - Web framework
   - Database
   - AI/LLM integration

After reading, summarize the system in 2-3 paragraphs that a non-technical person could understand.
```

### Prompt 0.2 - Step-by-Step Flow Explanation
```
Now trace through the system step by step. Read these files:

1. packages/pipeline/stages.py - All pipeline stages
2. packages/pipeline/runner.py - How stages are executed
3. packages/pipeline/handlers.py - What happens at each stage
4. packages/content_factory/router.py - Content creation routing

Then explain the FLOW in simple terms:

STEP 1: How does the user start?
- What does the user provide as input? (A topic? A video URL? A file?)
- How does the user interact with the system? (Web UI? CLI? API call?)

STEP 2: What happens first?
- What is "Trend Analysis"?
- Does the system suggest topics or does the user provide one?

STEP 3: Research Phase
- What information does the system gather?
- Where does it get information from? (Web search? LLM knowledge?)
- How long does this typically take?

STEP 4: Script Writing
- How does the system write the script?
- What format is the script in?
- How does the system know if the script is good enough?

STEP 5: Visual Planning
- What is visual planning?
- What outputs does it produce?

STEP 6: SEO & Publishing
- What SEO work is done?
- Where does the final output go? (Notion? YouTube? File?)

STEP 7: Human Interaction Points
- Where does the system pause for human approval?
- How does the human approve or reject?
- Can the human provide feedback?

Draw a simple flow diagram using text:
[Input] → [Stage 1] → [Stage 2] → ... → [Output]
```

### Prompt 0.3 - Component Map
```
Now map out all the components. Explore the directory structure and create a map:

Run these commands (or equivalent file system exploration):
- List all directories in packages/
- List all directories in apps/
- List all directories in freerouter/

Then create a COMPONENT MAP:

┌─────────────────────────────────────────────────────────────┐
│                    AI-Orchestration System                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   INPUT      │    │   CORE       │    │   OUTPUT     │  │
│  │              │    │              │    │              │  │
│  │  - Topic     │───▶│  - Research  │───▶│  - Script    │  │
│  │  - Video URL │    │  - Writing   │    │  - Notion    │  │
│  │              │    │  - Scoring   │    │  - YouTube   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   LLM        │    │   DATA       │    │   EXTERNAL   │  │
│  │              │    │              │    │              │  │
│  │  - FreeRouter│    │  - SQLite DB │    │  - Web Search│  │
│  │  - OpenAI    │    │  - Cache     │    │  - Notion API│  │
│  │  - Groq      │    │  - Checkpoint│    │  - YouTube   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘

For each component, answer:
1. What is its purpose?
2. What files implement it?
3. What does it depend on?
4. What happens if it fails?
```

### Prompt 0.4 - Questions for the User
```
Before diving deeper, ask the user these clarifying questions:

ABOUT THE GOAL:
1. What is the main output you want from this system? 
   - A script document?
   - A published video?
   - Just research notes?

2. Who is the target audience for the generated content?
   - Pakistani viewers?
   - YouTube audience?
   - Internal documentation?

ABOUT THE WORKFLOW:
3. How do you currently use this system?
   - Through the web dashboard?
   - Through API calls?
   - Through scripts/CLI?

4. How often do you run it?
   - Daily?
   - Weekly?
   - On-demand?

ABOUT THE PROBLEMS:
5. What are the main issues you're facing right now?
   - Does it crash?
   - Does it produce bad output?
   - Does it hang or timeout?
   - Is it too slow?

6. Are there any parts that definitely work and you don't want changed?

ABOUT THE INFRASTRUCTURE:
7. Where is this system running?
   - Local machine?
   - Cloud server?
   - Docker container?

8. What external services are you actually using?
   - Which LLM providers do you have API keys for?
   - Do you have Notion set up?
   - Is FreeRouter running?

DOCUMENT THE ANSWERS in a clear format for reference in later phases.
```

---

## Phase 1: Core Configuration & Environment

### Prompt 1.1 - Environment & Settings
```
Analyze the configuration system:

1. Read packages/core/config.py
2. Read .env.example files
3. Check all required environment variables

Questions to ask the user:
- Which LLM providers do you have API keys for? (OpenAI, Groq, OpenRouter, Ollama?)
- Do you have Notion API credentials? Are they required for the system to work?
- What is your FreeRouter setup? Is it running locally on port 4000?
- Do you have Zep memory server configured? Is it required?

Look for:
- Missing required environment variables
- Hardcoded values that should be configurable
- Dead configuration options
- Inconsistent default values
```

### Prompt 1.2 - Dependencies & Imports
```
Analyze package dependencies:

1. Read pyproject.toml
2. Read requirements.txt files
3. Check all __init__.py files for proper exports

Questions to ask the user:
- Are all these dependencies actually used?
- Are there missing dependencies that cause import errors?
- Which Python version are you targeting?

Look for:
- Missing dependencies in pyproject.toml
- Unused dependencies
- Version conflicts
- Import errors when trying: from packages.X import Y
```

---

## Phase 2: Router & LLM Integration

### Prompt 2.1 - FreeRouter Integration
```
Analyze the LLM routing system:

1. Read packages/router/client.py
2. Read packages/router/web_search.py
3. Read freerouter/src/freerouter/*.py

Questions to ask the user:
- Is FreeRouter supposed to be running as a separate process?
- What happens if FreeRouter is not running? Does the system fail gracefully?
- Do you want automatic fallback between providers?
- How should rate limiting work across providers?

Look for:
- Hardcoded URLs (localhost:4000)
- Missing error handling when FreeRouter is down
- Timeout issues
- Connection pool exhaustion
- Missing retries for transient failures
```

### Prompt 2.2 - Web Search Integration
```
Analyze web search capabilities:

1. Read packages/router/web_search.py
2. Check if z-ai-web-dev-sdk is properly imported
3. Test the fallback behavior

Questions to ask the user:
- Do you have the z-ai-web-dev-sdk installed and configured?
- What should happen when web search fails? Fail the research or continue with LLM knowledge only?
- Are there rate limits on web searches you need to respect?

Look for:
- Missing API credentials for web search
- Empty search results not handled
- Rate limiting issues
- SDK import failures
```

---

## Phase 3: Deep Research Engine

### Prompt 3.1 - Research Engine Core
```
Analyze the deep research system:

1. Read packages/content_factory/production/deep_research.py
2. Read packages/content_factory/production/models.py
3. Read packages/content_factory/production/workflow.py

Questions to ask the user:
- What is the expected output format of the research? (ResearchDossier or markdown?)
- How many web searches should a typical research use? (Currently max 20)
- What happens if research fails to find enough facts/anchors?
- Should research continue if completeness score is below threshold?

Look for:
- Infinite loops in research phases
- Memory leaks from accumulating facts
- Missing cleanup of checkpoint files
- Research hanging on slow web searches
- Incomplete dossier causing downstream failures
```

### Prompt 3.2 - Research Caching
```
Analyze the caching system:

1. Read packages/pipeline/research_cache.py
2. Check checkpoint mechanism in deep_research.py
3. Read packages/pipeline/handlers.py for ScriptCache

Questions to ask the user:
- How long should research be cached? (Currently 24 hours)
- Should cached research be invalidated when web search results change?
- Where should cache files be stored?
- Is it OK to cache AdaptedScript results or just ResearchDossier?

Look for:
- Cache corruption issues
- Cache not being used (the bug we just fixed)
- Disk space issues from unbounded cache growth
- Stale cache data being used
```

---

## Phase 4: Pipeline System

### Prompt 4.1 - Pipeline Runner
```
Analyze the pipeline orchestration:

1. Read packages/pipeline/runner.py
2. Read packages/pipeline/stages.py
3. Read packages/pipeline/state.py

Questions to ask the user:
- What happens when a pipeline run crashes mid-way? Can it resume?
- How are human approval gates supposed to work? (UI, CLI, API?)
- Should failed stages be retryable? How many times?
- How do you want to monitor pipeline progress?

Look for:
- Pipeline state corruption on crash
- Missing cleanup on failure
- Human gates with no way to approve
- Race conditions in concurrent runs
- Database lock issues with SQLite
```

### Prompt 4.2 - Stage Handlers
```
Analyze each pipeline stage:

1. Read packages/pipeline/handlers.py
2. Check each handler function: handle_trend_analysis, handle_research, handle_script_writing, etc.

Questions to ask the user:
- Should handle_research fail if topic not found, or use a fallback?
- What happens if handle_script_writing never reaches the threshold score?
- Is handle_asset_creation required or optional? (It has a feature flag)
- Should handle_publish always publish to Notion?

Look for:
- Handlers returning None causing crashes
- Missing error handling in async handlers
- Feature flags not working
- External service failures not handled (Notion down, etc.)
```

---

## Phase 5: Content Factory

### Prompt 5.1 - Script Generation
```
Analyze script generation:

1. Read packages/content_factory/production/workflow.py
2. Read packages/content_factory/production/agents.py
3. Read packages/content_factory/router.py

Questions to ask the user:
- What is the expected format of AdaptedScript? (DualColumnEntry structure)
- How should the script handle missing research data?
- What genres are supported? Is there a genre schema?
- Should scripts have a minimum/maximum length?

Look for:
- JSON parsing failures from LLM output
- Missing fields in AdaptedScript
- Invalid section labels
- Visual directions not matching anchor hierarchy
```

### Prompt 5.2 - Evaluation & Scoring
```
Analyze the scoring system:

1. Read packages/content_factory/evaluation/scoring.py
2. Read packages/content_factory/evaluation/loop.py
3. Read packages/content_factory/evaluation/baseline.py

Questions to ask the user:
- What score threshold is considered "production ready"? (Currently 85%)
- How many iterations should the experiment loop run?
- What happens if no improvement is found after max iterations?
- Should the best script be persisted even if below threshold?

Look for:
- Scoring returning NaN or invalid values
- Experiment loop stuck in local maxima
- Challenger generator producing invalid scripts
- Baseline comparison not working
```

---

## Phase 6: API & Web Interface

### Prompt 6.1 - FastAPI Routes
```
Analyze the API layer:

1. Read apps/api/main.py
2. Read all files in apps/api/routers/
3. Check apps/api/dependencies.py

Questions to ask the user:
- Which endpoints are actually being used?
- Do you need authentication/authorization?
- Should the API be public or internal only?
- How are CORS and security headers configured?

Look for:
- Missing route error handlers
- Unhandled exceptions returning 500 errors
- Missing request validation
- Inconsistent response formats
- WebSocket connections not handled properly
```

### Prompt 6.2 - Static Files & Dashboard
```
Analyze the web dashboard:

1. Read apps/api/static/index.html
2. Check all JS files in apps/api/static/js/
3. Check CSS in apps/api/static/css/

Questions to ask the user:
- Is this dashboard actively used or just for debugging?
- Do you need real-time updates (WebSocket)?
- Should the dashboard require authentication?

Look for:
- Broken JavaScript references
- API endpoints called that don't exist
- Missing error handling in UI
- Memory leaks in long-running dashboard sessions
```

---

## Phase 7: External Integrations

### Prompt 7.1 - Notion Integration
```
Analyze Notion integration:

1. Read packages/integrations/notion/client.py

Questions to ask the user:
- Is Notion integration required or optional?
- What should happen if Notion API is rate limited?
- What content should be published to Notion? Full script? Summary?

Look for:
- Missing Notion credentials causing crashes
- Notion API errors not handled
- Content formatting issues
```

### Prompt 7.2 - YouTube Integration
```
Analyze YouTube integration:

1. Read packages/integrations/youtube/client.py
2. Read packages/integrations/youtube/analytics.py

Questions to ask the user:
- Is this for downloading source videos or uploading generated content?
- Do you have YouTube API credentials configured?
- What analytics data do you need?

Look for:
- Missing OAuth credentials
- API quota exceeded handling
- Video processing failures
```

### Prompt 7.3 - Memory (Zep)
```
Analyze memory integration:

1. Read packages/memory/client.py
2. Read packages/content_factory/memory/zep_store.py

Questions to ask the user:
- Is Zep memory required for the system to work?
- What data should be persisted in memory?
- Should memory be scoped per session or global?

Look for:
- Zep server not running causing failures
- Memory retrieval returning stale data
- Session management issues
```

---

## Phase 8: Error Handling & Logging

### Prompt 8.1 - Error Management
```
Analyze error handling:

1. Read packages/core/errors.py
2. Check try/except blocks throughout the codebase
3. Check logging in packages/core/logger.py

Questions to ask the user:
- How should critical errors be reported? (Logs, alerts, UI?)
- Should errors halt the pipeline or allow continuation?
- Do you need error aggregation/monitoring (Sentry, etc.)?

Look for:
- Bare except: clauses hiding errors
- Errors logged but not propagated
- Missing error context for debugging
- Infinite retry loops
```

### Prompt 8.2 - Logging System
```
Analyze logging:

1. Check all logger calls throughout codebase
2. Check log file configuration

Questions to ask the user:
- What log level should be used in production?
- Do you need structured logging (JSON)?
- Should logs be shipped to external systems?

Look for:
- Sensitive data in logs (API keys, etc.)
- Missing log context (no topic, no run_id)
- Log flooding from tight loops
```

---

## Phase 9: Testing

### Prompt 9.1 - Test Coverage
```
Analyze test coverage:

1. Read all files in tests/
2. Check if tests can actually run

Questions to ask the user:
- Which tests are expected to pass?
- Are there integration tests that require external services?
- How should tests handle API keys and credentials?

Look for:
- Tests importing modules that don't exist
- Tests that pass but shouldn't (mock everything)
- Tests requiring live API keys
- Missing tests for critical paths (research, scoring, pipeline)
```

---

## Phase 10: End-to-End Flow

### Prompt 10.1 - Complete Flow Test
```
Trace the complete flow:

1. Start from: User submits a topic
2. Trace through: Trend Analysis → Topic Approval → Research → Script Writing → Visual Planning → SEO → Asset Creation → Publish
3. Document each step's inputs, outputs, and failure modes

Questions to ask the user:
- Can you walk me through a successful run end-to-end?
- Where does it typically fail or get stuck?
- What are the most common issues you encounter?

Look for:
- Missing data flowing between stages
- Stage A output not matching Stage B expected input
- Silent failures that halt progress
- Infinite loops or hangs
```

---

## Summary Report Template

After completing all phases, generate a report with:

```markdown
# AI-Orchestration Analysis Report

## Executive Summary
- Overall health score (1-10)
- Critical issues found
- Recommended priority order

## Critical Issues (P0)
Issues that break core functionality

## High Priority Issues (P1)
Issues that affect reliability

## Medium Priority Issues (P2)
Issues that affect maintainability

## Low Priority Issues (P3)
Code quality improvements

## Questions Requiring User Input
[All questions gathered during analysis]

## Recommended Next Steps
[Actionable items in priority order]
```

---

## How to Use This Plan

### For the User:
1. Copy each prompt to your AI agent
2. Answer the questions honestly
3. Don't skip phases - they build on each other
4. Document any issues found

### For the AI Agent:
1. Follow each phase in order
2. Ask ALL questions listed
3. Document every issue found with file path and line number
4. Note any assumptions made
5. Flag anything that doesn't make sense
