# Content Factory Knowledge Base

The four JSON files in this directory are the ground truth for the entire
self-improving content pipeline. They were built in Phase 1 and must NEVER
be modified without understanding the downstream impact.

---

## style_reference.json
**What it is:** Machine-readable encoding of Johnny Harris's documentary style.
**Used by:** Writer agent (system prompt construction), Stage 4 script generation,
             Stage 5 Pakistani refinement.
**Contains:** 10 sections covering narration style, visual language, structural
              patterns, pacing, hook construction, and conclusion rules.
**Rule:** If you change a style rule here, it changes what the Writer agent
          produces. Test on a full pipeline run before committing.

---

## evaluation_suite.json
**What it is:** 56 binary questions (yes/no) that score every script.
**Used by:** ScoringEngine in evaluation/scoring.py.
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
**Used by:** ScoringEngine (loads questions per genre), TopicFinderAgent
             (classifies topics), ContentCreationRouter (selects workflow).
**Genres:**
  - history — chronological narrative, JH-style reveals
  - current_situation — gap between perception and reality
  - tech_systems — human consequence, not technical mechanism
  - comparison — A vs B with local grounding
  - islamic_history — scholarly sourcing + tonal calibration (Phase 4 addition)
  - south_asian_history — regional context + colonial lens (Phase 4 addition)

**Adding a genre:** Add to genre_schema.json AND add genre-specific questions
to evaluation_suite.json AND update the ScoringEngine's applicable questions.

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

Every component that needs these files loads them via:
```python
from pathlib import Path
import json

CONTENT_FACTORY_DIR = Path(__file__).parent.parent  # adjust depth as needed
style_ref = json.loads((CONTENT_FACTORY_DIR / "style_reference.json").read_text())
eval_suite = json.loads((CONTENT_FACTORY_DIR / "evaluation_suite.json").read_text())
genre_schema = json.loads((CONTENT_FACTORY_DIR / "genre_schema.json").read_text())
anchor_hierarchy = json.loads((CONTENT_FACTORY_DIR / "anchor_substitution_hierarchy.json").read_text())
```

Never copy these files to other locations. Always import from this directory.
