"""
config.py — Task-to-model routing table.

Each key is a task name (or "auto") that your app passes as the model field.
Set your API keys in freerouter/.env:

    OPENROUTER_API_KEY=sk-or-...
    GROQ_API_KEY=gsk_...
    OLLAMA_BASE_URL=http://localhost:11434   # optional

LiteLLM model string format:
    openrouter/<provider>/<model>   →  routes via OpenRouter
    groq/<model>                    →  routes via Groq LPU
    ollama/<model>                  →  routes via local Ollama
"""

ROUTES: dict[str, dict[str, str]] = {
    # ── Generic fallback ─────────────────────────────────────────────────
    "auto": {
        "model":    "openrouter/stepfun/step-3.5-flash:free",
        "fallback": "groq/llama-3.3-70b-versatile",
    },

    # ── Task 1: Researcher (256K context, deep synthesis) ────────────────
    "researcher": {
        "model":    "openrouter/stepfun/step-3.5-flash:free",
        "fallback": "openrouter/qwen/qwen3.6-plus:free",
    },

    # ── Task 2: Topic Finder (creative ideation, gap analysis) ───────────
    "topic_finder": {
        "model":    "openrouter/qwen/qwen3.6-plus:free",
        "fallback": "openrouter/stepfun/step-3.5-flash:free",
    },

    # ── Task 3: Script Writer (1M context, creative prose) ───────────────
    "script_writer": {
        "model":    "openrouter/qwen/qwen3.6-plus:free",
        "fallback": "openrouter/mistralai/mistral-small-3.1:free",
    },

    # ── Task 4: Scoring Engine (fast pass/fail loop, 70K TPM) ────────────
    "scorer": {
        "model":    "groq/compound-beta-mini",
        "fallback": "groq/llama-3.1-8b-instant",
    },

    # ── Task 5: Challenger Generator (JSON rewrite, structured output) ────
    "challenger": {
        "model":    "groq/llama-3.1-8b-instant",
        "fallback": "groq/llama-3.3-70b-versatile",
    },

    # ── Task 6: Visual Annotator (60 RPM, repetitive 1-sentence cues) ────
    "annotator": {
        "model":    "groq/qwen-qwq-32b",
        "fallback": "groq/llama-3.1-8b-instant",
    },
}
