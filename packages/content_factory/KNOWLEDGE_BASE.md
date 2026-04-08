# Content Factory Knowledge Base

The four JSON files in this directory are the ground truth for the entire
self-improving content pipeline. They were built in Phase 1 and must NEVER
be modified without understanding the downstream impact.

---

## style_reference.json
**What it is:** Machine-readable encoding of Johnny Harris's documentary style.
**Used by:** `draft_node` (script writer prompt + system prompt), `mutate_node` (challenger prompt + system prompt)
             — both in `orchestration/nodes.py`.
**Contains:** 10 sections covering core philosophy, anchor-bridge formula, classic style writing rules,
              peer-to-peer framing, motive loading, dual-column format, conclusion shift, genre variations,
              and Pakistani adaptation rules.
**Rule:** If you change a style rule here, it changes what the Writer agent and Mutator produce.
          Test on a full pipeline run before committing. Changes take effect on server restart
          (loaded once at module level).

---

## evaluation_suite.json
**What it is:** 56 binary questions (yes/no) that score every script.
**Used by:** LangGraph nodes in `orchestration/nodes.py` for script scoring and evaluation.
**Structure:**
  - 11 categories (A through K, O, P, Q)
  - Each question has: id, text, category, responsible_agent
  - responsible_agent identifies WHO fixes failures (researcher, writer, visual_agent)

**Category map:**
  | ID | Name                        | Responsible Agent  |
  |----|-----------------------------|--------------------|
  | A  | Research Quality            | researcher         |
  | B  | Visual Anchor Quality       | visual_agent       |
  | C  | Script Prose Quality        | writer             |
  | D  | Anchor-Bridge Structure     | writer             |
  | E  | Dual-Column Coding Quality  | visual_agent       |
  | F  | Conclusion Quality          | writer             |
  | G  | History/Documentary         | researcher         |
  | H  | Current Situation           | researcher         |
  | I  | Tech and Systems            | researcher         |
  | J  | Comparison and Contrast     | researcher         |
  | K  | Pakistani Audience          | all agents         |
  | O  | Universal Music             | music_agent        |
  | P  | Pakistani Audience Music    | music_agent        |
  | Q  | Genre-Specific Music        | music_agent        |

**Mutation zone mapping:**
  Zone 1 (script_prose)         → categories C, F
  Zone 2 (visual_direction)     → categories B, E
  Zone 3 (structural_arch)      → category D

---

## genre_schema.json
**What it is:** Maps each genre to its applicable question categories and
               structural rules.
**Used by:** Script scoring node in `orchestration/nodes.py` (loads questions per genre), TopicFinderAgent
             (classifies topics).
**Genres:**
  - history — chronological narrative, JH-style reveals
  - current_situation — gap between perception and reality
  - tech_systems — human consequence, not technical mechanism
  - comparison — A vs B with local grounding
  - islamic_history — scholarly sourcing + tonal calibration (Phase 4 addition)
  - south_asian_history — regional context + colonial lens (Phase 4 addition)

**Adding a genre:** Add to genre_schema.json AND add genre-specific questions
to evaluation_suite.json AND update the scoring logic in `orchestration/nodes.py`.

---

## anchor_substitution_hierarchy.json
**What it is:** A 5-level system for visual anchors when ideal evidence isn't available.
**Used by:** Visual Director agent, Stage 4 script generation, Stage 5 refinement.
**The 5 levels:**
  Level 1: Primary Source Artifacts (best) — original documents, footage
  Level 2: Geographic Proof — real locations, maps
  Level 3: Expert Deposition — interview or statement
  Level 4: Abstract Data Visualization — charts, graphs
  Level 5: Illustrative Metaphor (worst) — avoid if possible

**Rule:** Never use Level 5 if Level 1-3 is findable. Binary question B1-B7
evaluates anchor quality — Level 5 usage fails most B questions.

---

## Where these files are loaded

| File | Loaded By | How |
|------|-----------|-----|
| `style_reference.json` | `draft_node` and `mutate_node` in `orchestration/nodes.py` | `_load_style_reference()` at module level → `_build_style_context()` extracts key rules → injected into prompt |
| `evaluation_suite.json` | `score_node` in `orchestration/nodes.py` | 56-question checklist hardcoded in scorer prompt (JSON file serves as documentation) |
| `genre_schema.json` | `draft_node` in `orchestration/nodes.py` | `_load_genre_schema()` at module level → `_get_genre_rules(genre_id)` extracts per-genre rules → injected into prompt |
| `anchor_substitution_hierarchy.json` | Visual Director agent, Stage 4 script generation | `json.loads()` from content factory directory |

**Note:** `style_reference.json` and `genre_schema.json` are loaded once at module level and cached. Reload the server to pick up changes.

```python
# In orchestration/nodes.py (module level):
_STYLE_REFERENCE = _load_style_reference()
_GENRE_SCHEMA = _load_genre_schema()
_STYLE_CONTEXT = _build_style_context(_STYLE_REFERENCE)
```

Never copy these files to other locations. Always import from this directory.
