# Architecture Decision Records

This document records significant architectural decisions and their reasoning. Each decision follows the ADR format: Context, Decision, Reasoning, Consequences.

---

## ADR-001: Two-Service Architecture

**Date**: 2025-03-20  
**Status**: Accepted

### Context

We needed to support multiple LLM providers (Groq, OpenRouter, Ollama, OpenAI, Anthropic) with automatic failover and rate limit tracking. The main application handles video production pipeline logic.

### Decision

Split the system into two separately-running services:
1. **FreeRouter** (port 4000) — LLM proxy
2. **Main API** (port 3000) — Dashboard and pipeline

### Reasoning

| Factor | Two Services | Single Service |
|--------|--------------|----------------|
| Complexity isolation | ✅ LLM complexity isolated | ❌ LLM code mixed with business logic |
| Key security | ✅ LLM keys only in FreeRouter | ❌ Keys in main process |
| Testing | ✅ Mock one HTTP endpoint | ❌ Mock multiple LLM APIs |
| Scaling | ✅ FreeRouter can serve multiple apps | ❌ Must scale together |
| Deployment | ❌ Must run two services | ✅ Single deployment |

The benefits of isolation outweigh the deployment complexity.

### Consequences

**Positive**:
- Clear separation of concerns
- LLM provider changes don't affect main app
- Multiple services can share FreeRouter
- Easier to test with HTTP mocking

**Negative**:
- Must start two services
- Network latency between services (negligible)
- Additional deployment complexity

---

## ADR-002: SQLite for Pipeline State

**Date**: 2025-03-20  
**Status**: Accepted

### Context

Pipeline runs take 5-15 minutes. The system must:
- Survive crashes and restart
- Resume from last successful stage
- Handle concurrent access from dashboard and worker

### Decision

Use SQLite with WAL (Write-Ahead Logging) mode for state persistence.

### Reasoning

| Option | Pros | Cons |
|--------|------|------|
| PostgreSQL | Production-ready, concurrent connections | Requires server, configuration |
| Redis | Fast, in-memory | Data lost on restart, no queries |
| SQLite | Zero-config, file-based, WAL for concurrency | Single-server limitation |

SQLite is sufficient because:
1. Single server is acceptable for current scale
2. Zero configuration means faster development
3. File-based storage enables easy debugging
4. WAL mode handles concurrent reads

### Consequences

**Positive**:
- No database server to manage
- Easy backup (copy the file)
- Can query state with SQL for debugging
- Atomic transactions prevent corruption

**Negative**:
- Cannot run multiple API servers (horizontal scaling blocked)
- Must handle SQLite file carefully
- Write contention under very high load

**Revisit When**: Need to run multiple API instances serving same pipeline state.

---

## ADR-003: Nine Pipeline Stages

**Date**: 2025-03-20  
**Status**: Accepted

### Context

Video production involves multiple distinct creative tasks. We need to balance:
- Granularity (enough stages for control)
- Simplicity (not too many stages)
- Human oversight (gates at critical decisions)

### Decision

Implement 9 stages with 2 human gates:

```
1. trend_analysis          → AI discovers topics
2. human_topic_approval    → HUMAN GATE
3. research                → AI researches
4. script_writing          → AI writes script
5. visual_planning         → AI designs visuals
6. seo                     → AI generates metadata
7. human_review            → HUMAN GATE
8. asset_creation          → AI creates assets
9. publish                 → AI publishes
```

### Reasoning

**Why 9 stages?**
- Each stage = distinct creative task
- Stages can be independently tested
- Failures resume from last stage

**Why gates at stages 2 and 7?**
- Stage 2 (topic): Wrong topic wastes entire pipeline
- Stage 7 (review): Script quality = video quality

**Why not more gates?**
- Gate fatigue reduces human attention
- AI handles routine decisions well
- Gates at highest-impact decisions

### Consequences

**Positive**:
- Clear separation of concerns
- Resumability from any stage
- Human oversight at critical points
- Each stage independently testable

**Negative**:
- Pipeline takes longer with gates
- Human availability affects throughput

---

## ADR-004: All LLM Calls Through RouterClient

**Date**: 2025-03-20  
**Status**: Accepted  
**Enforcement**: Strict

### Context

Multiple parts of the codebase need LLM calls. Without a standard approach:
- Inconsistent error handling
- No centralized failover
- Difficult to track costs

### Decision

All LLM calls must go through `packages/router/client.RouterClient`. Direct API calls are forbidden.

```python
# ❌ FORBIDDEN
import openai
response = openai.chat.completions.create(...)

# ✅ REQUIRED
from packages.router.client import RouterClient
response = await router_client.chat(...)
```

### Reasoning

1. **Failover**: If one provider fails, RouterClient tries the next
2. **Rate limits**: Track remaining quota per provider
3. **Costs**: All usage through one point enables monitoring
4. **Testing**: Mock one client instead of multiple APIs
5. **Security**: LLM keys only in FreeRouter

### Consequences

**Positive**:
- Consistent error handling everywhere
- Automatic failover on provider failure
- Centralized rate limit tracking
- Easier testing and mocking

**Negative**:
- Extra abstraction layer
- Must maintain RouterClient interface

---

## ADR-005: Two-Layer Package Design

**Date**: 2025-03-20  
**Status**: Accepted

### Context

The codebase has infrastructure concerns (logging, config, HTTP clients) and business logic (video production). Mixing them creates:
- Circular dependencies
- Difficulty reusing infrastructure
- Unclear ownership

### Decision

Split packages into two layers:

```
Layer 1: Infrastructure
├── core/      ← Config, logging, errors
├── router/    ← LLM client
├── pipeline/  ← State machine
├── agents/    ← Base classes
└── memory/    ← Zep client

Layer 2: Business Logic
└── content_factory/   ← Video production
```

**Rule**: Business logic imports from infrastructure. Infrastructure never imports from business logic.

### Reasoning

- Infrastructure can be reused for other projects
- Business logic changes don't affect core systems
- Clear dependency direction prevents cycles
- New developers understand one layer at a time

### Consequences

**Positive**:
- Reusable infrastructure
- Clear ownership boundaries
- No circular dependencies
- Easier onboarding

**Negative**:
- More packages to maintain
- Must enforce layer boundaries

---

## ADR-006: Server-Sent Events for Real-time Updates

**Date**: 2025-03-20  
**Status**: Accepted

### Context

The dashboard needs real-time updates for:
- Stage completion
- Human gate alerts
- Pipeline progress

### Decision

Use Server-Sent Events (SSE) for server → client updates.

### Reasoning

| Option | Pros | Cons |
|--------|------|------|
| WebSocket | Bidirectional | Complex, overkill for one-way |
| Polling | Simple | Inefficient, high latency |
| SSE | Simple, native browser support | One-way only |

We only need server → client updates, so SSE is sufficient.

### Consequences

**Positive**:
- Native browser `EventSource` API
- Automatic reconnection
- Simple implementation
- Works through HTTP/2

**Negative**:
- One-way only (but we don't need bidirectional)
- IE not supported (acceptable)

---

## ADR-007: Zep Cloud for Agent Memory

**Date**: 2025-03-21  
**Status**: Accepted

### Context

Agents need to remember context across pipeline runs:
- Previous topic choices
- Learned preferences
- Error patterns to avoid

### Decision

Use Zep Cloud for persistent agent memory.

### Reasoning

| Option | Pros | Cons |
|--------|------|------|
| In-memory | Fast | Lost on restart |
| SQLite | Simple | Not designed for memory patterns |
| Zep Cloud | Purpose-built for AI memory | External dependency |

Zep Cloud provides:
- Fact extraction from conversations
- Long-term memory storage
- Semantic search over memories

### Consequences

**Positive**:
- Agents learn from past runs
- Semantic memory search
- Managed service (no maintenance)

**Negative**:
- External dependency
- Requires ZEP_API_KEY
- Network latency for memory calls

**Fallback**: Memory is optional. System works without ZEP_API_KEY.

---

## ADR-008: File-Based Configuration (.env)

**Date**: 2025-03-20  
**Status**: Accepted

### Context

The system needs configuration for:
- API keys
- Feature flags
- Environment-specific settings

### Decision

Use `.env` files loaded by `python-dotenv`.

### Reasoning

- Industry standard for 12-factor apps
- Easy to manage locally
- Clear separation from code
- Gitignored by default

### Consequences

**Positive**:
- Simple and familiar
- No build-time configuration
- Easy to change without redeploying

**Negative**:
- Must manage multiple .env files (root, freerouter/)
- Secrets in plaintext files (use secret managers in production)

---

## Decision Log

| ADR | Title | Date | Status |
|-----|-------|------|--------|
| 001 | Two-Service Architecture | 2025-03-20 | Accepted |
| 002 | SQLite for Pipeline State | 2025-03-20 | Accepted |
| 003 | Nine Pipeline Stages | 2025-03-20 | Accepted |
| 004 | All LLM Calls Through RouterClient | 2025-03-20 | Accepted |
| 005 | Two-Layer Package Design | 2025-03-20 | Accepted |
| 006 | SSE for Real-time Updates | 2025-03-20 | Accepted |
| 007 | Zep Cloud for Agent Memory | 2025-03-21 | Accepted |
| 008 | File-Based Configuration | 2025-03-20 | Accepted |

---

## How to Add a New ADR

1. Copy this template:

```markdown
## ADR-XXX: [Title]

**Date**: YYYY-MM-DD  
**Status**: Proposed | Accepted | Deprecated | Superseded

### Context
[What is the issue we're addressing?]

### Decision
[What is the change or decision being made?]

### Reasoning
[Why did we make this decision? What alternatives were considered?]

### Consequences
**Positive**:
- [Benefit 1]

**Negative**:
- [Trade-off 1]
```

2. Add to this file
3. Update the Decision Log table
