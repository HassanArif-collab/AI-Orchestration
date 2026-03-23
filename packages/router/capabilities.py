"""
router/capabilities.py — Maps task types to preferred LLM models.

Context: Different pipeline tasks benefit from different models.
These are HINTS passed to FreeRouter — if the preferred model is
unavailable, RouterClient automatically falls back to "auto" and
FreeRouter picks the best available provider.

Do NOT hardcode these into agent code. Always call get_model_for_capability()
so defaults can be overridden via capabilities.yaml without code changes.

Usage:
    from packages.router.capabilities import get_model_for_capability
    model = get_model_for_capability("research")
    # → "groq/llama-3.3-70b-versatile"

Imports: pathlib, yaml (optional override)
Imported by: packages/agents/
"""

from __future__ import annotations

from pathlib import Path

# Default capability → preferred model mapping.
# Models use FreeRouter's "provider/model" syntax.
# "auto" = let FreeRouter decide.
CAPABILITY_MODELS: dict[str, str] = {
    "research":        "groq/llama-3.3-70b-versatile",
    "scripting":       "openrouter/stepfun/step-3.5-flash:free",
    "compression":     "ollama/llama3.2",
    "trend_analysis":  "groq/llama-3.3-70b-versatile",
    "code_generation": "groq/llama-3.3-70b-versatile",
    "quick":           "ollama/llama3.2",
    "creative":        "openrouter/stepfun/step-3.5-flash:free",
    "seo":             "groq/llama-3.3-70b-versatile",
    "visual_planning": "openrouter/stepfun/step-3.5-flash:free",
}

# Optional override file — create packages/capabilities.yaml to customise
_OVERRIDE_PATH = Path(__file__).parent.parent / "capabilities.yaml"


def _load_overrides() -> dict[str, str]:
    """Load model overrides from capabilities.yaml if it exists."""
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
    """
    overrides = _load_overrides()
    merged = {**CAPABILITY_MODELS, **overrides}
    return merged.get(capability, "auto")


def list_capabilities() -> list[str]:
    """Return all known capability names."""
    return list(CAPABILITY_MODELS.keys())
