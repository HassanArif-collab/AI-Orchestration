"""
router/capabilities.py — Maps task types to preferred LLM models.

Context: Different pipeline tasks benefit from different models.
These are HINTS passed to FreeRouter — if the preferred model is
unavailable, RouterClient automatically falls back to "auto" and
FreeRouter picks the best available provider.

The model mapping is derived from freerouter.config.ROUTES, which is the
single source of truth for task-to-model routing.

Do NOT hardcode these into agent code. Always call get_model_for_capability()
so defaults can be overridden via capabilities.yaml without code changes.

Usage:
    from packages.router.capabilities import get_model_for_capability
    model = get_model_for_capability("research")
    # → "openrouter/stepfun/step-3.5-flash:free"

Imports: pathlib, yaml (optional override)
Imported by: packages/agents/
"""

from __future__ import annotations

from pathlib import Path

# Import ROUTES as the single source of truth for task-to-model mapping.
from freerouter.config import ROUTES

# Maps old capability names to ROUTES task names.
# Each capability is resolved to its ROUTES entry, and the "model" value
# from that route is used as the preferred model for the capability.
CAPABILITY_ROUTE_MAP: dict[str, str] = {
    "research":        "researcher",
    "scripting":       "script_writer",
    "creative":        "topic_finder",
    "compression":     "script_writer",
    "trend_analysis":  "topic_finder",
    "code_generation": "auto",
    "quick":           "scorer",
    "seo":             "scorer",
    "visual_planning": "annotator",
}

# Default capability → preferred model mapping.
# Populated from freerouter.config.ROUTES via CAPABILITY_ROUTE_MAP.
# Models use FreeRouter's "provider/model" syntax.
# "auto" = let FreeRouter decide.
CAPABILITY_MODELS: dict[str, str] = {
    cap: ROUTES[task_name]["model"]
    for cap, task_name in CAPABILITY_ROUTE_MAP.items()
    if task_name in ROUTES
}

# HOW TO OVERRIDE MODELS WITHOUT CODE CHANGES:
# Create packages/capabilities.yaml with your overrides:
#
# research: groq/llama-3.3-70b-versatile
# scripting: anthropic/claude-3-5-sonnet
# creative: openrouter/google/gemini-2.0-flash-exp:free
#
# This file is gitignored — safe to put experimental model names here.
# Overrides merge with CAPABILITY_MODELS (your values win).
_OVERRIDE_PATH = Path(__file__).parent.parent / "capabilities.yaml"


def _load_overrides() -> dict[str, str]:
    """Load model overrides from capabilities.yaml if it exists.
    
    The override file is OPTIONAL. If it doesn't exist, defaults are used.
    If it exists but has errors, empty dict is returned (graceful degradation).
    """
    if not _OVERRIDE_PATH.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(_OVERRIDE_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_model_for_capability(capability: str) -> str:
    """
    Return the preferred model string for a named capability.
    Falls back to 'auto' for unknown capabilities.
    The caller should still handle 503 and retry with 'auto'.
    
    OVERRIDE PRIORITY:
      1. capabilities.yaml values (if file exists)
      2. CAPABILITY_MODELS defaults (populated from ROUTES)
      3. "auto" fallback
    
    Args:
        capability: The task type (e.g., "research", "scripting")
    
    Returns:
        Model string like "groq/llama-3.1-8b-instant" or "auto"
    """
    overrides = _load_overrides()
    merged = {**CAPABILITY_MODELS, **overrides}
    return merged.get(capability, "auto")


def list_capabilities() -> list[str]:
    """Return all known capability names.
    
    Useful for UI dropdowns or debugging.
    Does NOT include unknown capabilities (would get "auto" anyway).
    
    Returns:
        List of capability keys from CAPABILITY_MODELS
    """
    return list(CAPABILITY_MODELS.keys())
