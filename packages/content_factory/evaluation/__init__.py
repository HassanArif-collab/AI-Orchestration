"""
Self-Correction Loop — Evolutionary Script Improvement.

Scores scripts against 56 binary questions, mutates failing zones,
promotes the best version. Works identically for Mode A and Mode B output.

Components:
  scoring.py    → ScoringEngine: grades script against genre-specific questions
  mutation.py   → ChallengerGenerator: mutates ONE zone at a time to fix failures
  loop.py       → ExperimentLoop: orchestrates score → mutate → compare → promote
  baseline.py   → BaselineManager: SQLite store of best scripts per genre

Three mutation zones:
  Zone 1 (script_prose)          → questions C, F (prose + conclusion)
  Zone 2 (visual_direction)      → questions B, E (anchors + coding)
  Zone 3 (structural_architecture)→ question D   (anchor-bridge structure)

Stop condition: 85% threshold OR 20 iterations OR no more failing zones.
Entry point: loop.py → ExperimentLoop.run_iterations(script, iterations=20)
"""

# packages/content_factory/evaluation — Phase 4 Auto-Research Loop
