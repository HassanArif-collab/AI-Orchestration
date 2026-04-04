"""
config.py — Task-to-model routing table (v3.1).

2 providers: OpenRouter (free tier) + Ollama Cloud.
7 routes with multi-fallback chains.

Providers:
    OpenRouter   — free tier models (Qwen 3.6, StepFun 3.5 Flash, Mistral)
    Ollama Cloud — creative models (gemma4, nemotron-cascade-2)

Set your API keys in freerouter/.env:
    OPENROUTER_API_KEY=sk-or-...   # required
    OLLAMA_API_KEY=...             # required

LiteLLM model string format:
    openrouter/<provider>/<model>       →  routes via OpenRouter
    ollama_chat/<model>                 →  routes via Ollama (local or cloud)

Each route has: model, fallback (optional), fallback2 (optional).
server.py tries them in order: model → fallback → fallback2.
"""

ROUTES: dict[str, dict[str, str]] = {
    # ── Generic fallback ─────────────────────────────────────────────────
    "auto": {
        "model":      "openrouter/qwen/qwen3.6-plus:free",
        "fallback":   "openrouter/stepfun/step-3.5-flash:free",
    },

    # ── Task 1: Researcher (deep synthesis, 1M context) ─────────────────
    # Qwen 3.6 Plus: strong synthesis, 1M context window
    "researcher": {
        "model":      "openrouter/qwen/qwen3.6-plus:free",
        "fallback":   "openrouter/stepfun/step-3.5-flash:free",
    },

    # ── Task 2: Topic Finder (creative ideation, gap analysis) ────────────
    # Ollama gemma4: frontier-level creative agentic ideation (31b cloud variant)
    "topic_finder": {
        "model":      "ollama_chat/gemma4:31b",
        "fallback":   "openrouter/qwen/qwen3.6-plus:free",
    },

    # ── Task 3: Script Writer (creative prose, 1M context) ───────────────
    # Qwen 3.6 Plus: strong creative writing, style adherence, 1M context
    "script_writer": {
        "model":      "openrouter/qwen/qwen3.6-plus:free",
        "fallback":   "openrouter/mistral/mistral-small-3.1:free",
    },

    # ── Task 4: Scoring Engine (fast pass/fail, logical precision) ───────
    # StepFun 3.5 Flash: 88.2% τ²-Bench, deterministic evaluation
    "scorer": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "openrouter/qwen/qwen3.6-plus:free",
    },

    # ── Task 5: Challenger Generator (JSON rewrite, structured output) ───
    # Ollama nemotron-3-nano: frontier reasoning, structured rewriting
    # Note: nemotron-cascade-2 not available on Ollama Cloud; using nemotron-3-nano
    "challenger": {
        "model":      "ollama_chat/nemotron-3-nano:30b",
        "fallback":   "openrouter/qwen/qwen3.6-plus:free",
    },

    # ── Task 6: Visual Annotator (short cues, repetitive) ────────────────
    # Qwen 3.6 Plus: high quality descriptive output
    "annotator": {
        "model":      "openrouter/qwen/qwen3.6-plus:free",
        "fallback":   "openrouter/stepfun/step-3.5-flash:free",
    },
}
