"""
config.py — Task-to-model routing table (v3.1).

3 providers, 7 routes, multi-fallback chains.

Providers:
    OpenRouter  — free tier models (StepFun, Qwen, Mistral)
    Groq        — ultra-fast inference (compound-mini, llama-3.1-8b, qwen3-32b)
    Ollama Cloud — creative models (gemma4, nemotron-3-nano)

Set your API keys in freerouter/.env:
    OPENROUTER_API_KEY=sk-or-...   # required
    GROQ_API_KEY=gsk_...           # required
    OLLAMA_API_KEY=...             # required for Ollama fallbacks

LiteLLM model string format:
    openrouter/<provider>/<model>       →  routes via OpenRouter
    groq/<model>                        →  routes via Groq
    ollama_chat/<model>                 →  routes via Ollama (local or cloud)

Each route has: model, fallback (optional), fallback2 (optional).
server.py tries them in order: model → fallback → fallback2.
"""

ROUTES: dict[str, dict[str, str]] = {
    # ── Generic fallback ─────────────────────────────────────────────────
    "auto": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "groq/qwen/qwen3-32b",
        "fallback2":  "openrouter/qwen/qwen3.6-plus:free",
    },

    # ── Task 1: Researcher (deep synthesis, 256K context) ────────────────
    # StepFun 3.5 Flash: 88.2% τ²-Bench agentic, 256K context
    # Fallback → Ollama nemotron-3-nano (frontier reasoning, 256K)
    "researcher": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "ollama_chat/nemotron-3-nano:30b",
        "fallback2":  "ollama_chat/gemma4:26b",
    },

    # ── Task 2: Topic Finder (creative ideation, gap analysis) ────────────
    # Ollama nemotron-3-nano: frontier-level agentic ideation
    # Fallback → StepFun (agentic strengths, 256K)
    "topic_finder": {
        "model":      "ollama_chat/nemotron-3-nano:30b",
        "fallback":   "openrouter/stepfun/step-3.5-flash:free",
        "fallback2":  "openrouter/qwen/qwen3.6-plus:free",
    },

    # ── Task 3: Script Writer (creative prose, 1M context) ───────────────
    # Qwen 3.6 Plus: strong creative writing, style adherence, 1M context
    # Fallback → Mistral Small 3.1 (excellent creative prose)
    "script_writer": {
        "model":      "openrouter/qwen/qwen3.6-plus:free",
        "fallback":   "openrouter/mistral/mistral-small-3.1:free",
    },

    # ── Task 4: Scoring Engine (fast pass/fail, zero creativity) ─────────
    # Groq compound-beta: logical precision on LPU, 70K TPM
    # Fallback → Groq llama-3.1-8b → OpenRouter StepFun (cross-provider safety net)
    "scorer": {
        "model":      "groq/compound-beta",
        "fallback":   "groq/llama-3.1-8b-instant",
        "fallback2":  "openrouter/stepfun/step-3.5-flash:free",
    },

    # ── Task 5: Challenger Generator (JSON rewrite, structured output) ───
    # Groq llama-3.1-8b: native JSON mode, lightning-fast
    # Fallback → Groq qwen3-32b → OpenRouter Qwen (cross-provider safety net)
    "challenger": {
        "model":      "groq/llama-3.1-8b-instant",
        "fallback":   "groq/qwen/qwen3-32b",
        "fallback2":  "openrouter/qwen/qwen3.6-plus:free",
    },

    # ── Task 6: Visual Annotator (short cues, repetitive) ────────────────
    # Groq qwen3-32b: highest RPM for short repetitive output
    # Fallback → Groq llama-3.1-8b → OpenRouter StepFun (cross-provider safety net)
    "annotator": {
        "model":      "groq/qwen/qwen3-32b",
        "fallback":   "groq/llama-3.1-8b-instant",
        "fallback2":  "openrouter/qwen/qwen3.6-plus:free",
    },
}
