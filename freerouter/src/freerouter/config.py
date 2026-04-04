"""
config.py — Task-to-model routing table.

Each key is a task name (or "auto") that your app passes as the model field.
Set your API keys in freerouter/.env:

    OPENROUTER_API_KEY=sk-or-...   # required — primary provider for all routes

LiteLLM model string format:
    openrouter/<provider>/<model>   →  routes via OpenRouter
"""

ROUTES: dict[str, dict[str, str]] = {
    # ── Generic fallback ─────────────────────────────────────────────────
    "auto": {
        "model":    "openrouter/qwen/qwen3.6-plus:free",
        "fallback": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    },

    # ── Task 1: Researcher (deep synthesis, long context) ───────────────
    "researcher": {
        "model":    "openrouter/qwen/qwen3.6-plus:free",
        "fallback": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    },

    # ── Task 2: Topic Finder (creative ideation, gap analysis) ───────────
    "topic_finder": {
        "model":    "openrouter/qwen/qwen3.6-plus:free",
        "fallback": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    },

    # ── Task 3: Script Writer (creative prose, long output) ──────────────
    "script_writer": {
        "model":    "openrouter/qwen/qwen3.6-plus:free",
        "fallback": "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 4: Scoring Engine (fast pass/fail loop) ────────────────────
    "scorer": {
        "model":    "openrouter/google/gemma-3-27b-it:free",
        "fallback": "openrouter/qwen/qwen3.6-plus:free",
    },

    # ── Task 5: Challenger Generator (JSON rewrite, structured output) ──
    "challenger": {
        "model":    "openrouter/qwen/qwen3.6-plus:free",
        "fallback": "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 6: Visual Annotator (short cues, repetitive) ───────────────
    "annotator": {
        "model":    "openrouter/google/gemma-3-27b-it:free",
        "fallback": "openrouter/qwen/qwen3.6-plus:free",
    },
}
