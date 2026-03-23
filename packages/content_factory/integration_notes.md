# Phase 1 → Phase 2+ Integration Notes

## How Future Phases Reference Phase 1 Outputs

All Phase 1 files live in `packages/content_factory/`. Import or read them directly — never copy them into other locations. If Phase 1 files are updated, all downstream behavior must update automatically.

### File Locations

| File | Path | Used By |
|---|---|---|
| Style Reference | `packages/content_factory/style_reference.json` | Script Agent, Visual Agent, Orchestrator |
| Evaluation Suite | `packages/content_factory/evaluation_suite.json` | Auto Research Loop (Phase 4), Orchestrator, all agents during self-check |
| Genre Schema | `packages/content_factory/genre_schema.json` | Researcher (genre classification), Orchestrator (question routing) |
| Anchor Hierarchy | `packages/content_factory/anchor_substitution_hierarchy.json` | Visual Agent (anchor fallback), Researcher (anchor discovery) |

---

## How Agents Should Load the Style Reference

The existing `BaseAgent` class in `packages/agents/base.py` has a `load_skills()` method that reads markdown files from a `skills_path`. For Phase 2+, agents can load the style reference similarly:

```python
import json
from pathlib import Path

CONTENT_FACTORY_DIR = Path(__file__).parent.parent / "content_factory"

def load_style_reference() -> dict:
    return json.loads((CONTENT_FACTORY_DIR / "style_reference.json").read_text("utf-8"))

def load_evaluation_suite() -> dict:
    return json.loads((CONTENT_FACTORY_DIR / "evaluation_suite.json").read_text("utf-8"))

def load_genre_schema() -> dict:
    return json.loads((CONTENT_FACTORY_DIR / "genre_schema.json").read_text("utf-8"))

def load_anchor_hierarchy() -> dict:
    return json.loads((CONTENT_FACTORY_DIR / "anchor_substitution_hierarchy.json").read_text("utf-8"))
```

---

## How the Evaluation Suite Connects to the Auto Research Loop (Phase 4)

Phase 4's Auto Research Loop will:

1. Accept a "Shame Draft" (a dual-column script with section metadata)
2. Run every applicable binary question against the draft
3. Score the draft (pass count / applicable question count)
4. For each failing question, generate a targeted mutation prompt
5. Feed the mutation back to the responsible agent
6. Re-score and compare

The `evaluation_suite.json` is designed for this exact flow:
- `genres` field determines which questions apply (filter by genre or "all")
- `responsible_agent` field determines which agent receives the mutation prompt
- `failure_reason` field is populated by the scoring engine with the specific reason

---

## How the Genre Schema Maps to Pipeline Stages

The existing pipeline in `packages/pipeline/stages.py` defines 9 stages. Phase 1's genre schema adds a classification step that determines which evaluation questions apply:

| Pipeline Stage | Genre Schema Interaction |
|---|---|
| `research` | Genre determines which genre-specific research questions apply (G, H, I, or J) |
| `script_writing` | Genre determines conclusion pattern and structural backbone type |
| `visual_planning` | Genre affects anchor expectations (history = archival, tech = data viz) |

---

## Compatibility with Hermes Agent Framework (Phase 7)

Phase 1 schemas are designed as pure JSON data — no code dependencies, no framework coupling. When Phase 7 integrates the Hermes agent framework:

- The evaluation suite questions can be loaded as tool descriptions or evaluation criteria
- The style reference sections can be injected as system prompts
- The genre schema can drive conditional tool activation
- The anchor hierarchy can be exposed as a queryable tool

No schema changes are needed for Hermes compatibility. The JSON format is framework-agnostic by design.

---

## Compatibility with Existing Data Patterns

| Existing Pattern | Phase 1 Alignment |
|---|---|
| JSON for snapshots (`packages/data/analytics/`) | All Phase 1 schemas are JSON |
| SQLite for state (`packages/data/pipeline.db`) | Phase 1 is read-only data — no DB tables needed |
| Pydantic models (`packages/core/types.py`) | Phase 2+ can wrap Phase 1 JSON in Pydantic models if needed |
| `.env` for secrets | Phase 1 requires no secrets or env vars |
| `data/skills/*.md` placeholder stubs | Phase 1 fills the knowledge gap those stubs were meant to address |

---

## What Phase 2 Should Do First

1. Read this document
2. Read all four Phase 1 JSON files
3. Re-examine the YouTube API integration in `packages/integrations/youtube/`
4. Build the Adaptation Engine as a new module that imports Phase 1 schemas — never copies them
5. Extend the existing YouTube client with transcript extraction — do not create a parallel client
6. Use the Source Video Library schema with the same SQLite storage pattern as `pipeline.db`
