"""
Mode A Pipeline — Johnny Harris Video Adaptation.

Takes a JH YouTube URL and produces a Pakistani-localized DualColumnScript.

Flow: URL → stage1_extraction (transcript) → stage2_structural (structure map)
      → stage3_localization (Pakistan substitution) → stage4_script (dual-column)
      → THEN researcher/visual director/writer agents refine it
      → ExperimentLoop (self-correction)

Entry point: adaptation/runner.py → run_adaptation(url, cycle_id)
"""

# packages/content_factory/adaptation — Phase 2 Adaptation Engine Pipeline
