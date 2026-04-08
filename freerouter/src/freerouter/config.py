"""
config.py — Task-to-model routing table (v3.4).

2 providers: OpenRouter (paid + free) + Ollama Cloud.
7 routes with multi-fallback chains.

Providers:
    OpenRouter   — models that work in current environment:
                    deepseek-chat (paid, reliable), llama-4-maverick (paid),
                    llama-3.1-70b (paid), gemma-3-27b-it (free, rate-limited),
                    stepfun-3.5-flash (free, rate-limited), mistral-small-24b (paid)
    Ollama Cloud — creative models (gemma2, llama3)

Set your API keys in freerouter/.env:
    OPENROUTER_API_KEY=sk-or-...   # required
    OLLAMA_API_KEY=...             # optional

LiteLLM model string format:
    openrouter/<provider>/<model>       →  routes via OpenRouter
    ollama_chat/<model>                 →  routes via Ollama (local or cloud)

Each route has: model, fallback (optional), fallback2 (optional), fallback3 (optional).
server.py tries them in order: model → fallback → fallback2 → fallback3.
"""

ROUTES: dict[str, dict[str, str]] = {
    # ── Generic fallback ─────────────────────────────────────────────────
    "auto": {
        "model":      "openrouter/deepseek/deepseek-chat",
        "fallback":   "openrouter/meta-llama/llama-4-maverick",
        "fallback2":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback3":  "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 1: Researcher (deep synthesis, large context) ───────────────
    # DeepSeek Chat: excellent reasoning, large context
    "researcher": {
        "model":      "openrouter/deepseek/deepseek-chat",
        "fallback":   "openrouter/meta-llama/llama-4-maverick",
        "fallback2":  "openrouter/meta-llama/llama-3.1-70b-instruct",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
    },

    # ── Task 2: Topic Finder (creative ideation, gap analysis) ────────────
    # Llama 4 Maverick: strong creative reasoning with 128k context
    "topic_finder": {
        "model":      "openrouter/meta-llama/llama-4-maverick",
        "fallback":   "openrouter/deepseek/deepseek-chat",
        "fallback2":  "openrouter/meta-llama/llama-3.1-70b-instruct",
        "fallback3":  "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 3: Script Writer (creative prose, large context) ────────────
    # Llama 4 Maverick: excellent creative writing with style adherence
    "script_writer": {
        "model":      "openrouter/meta-llama/llama-4-maverick",
        "fallback":   "openrouter/deepseek/deepseek-chat",
        "fallback2":  "openrouter/meta-llama/llama-3.1-70b-instruct",
        "fallback3":  "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 4: Scoring Engine (fast pass/fail, logical precision) ───────
    # DeepSeek Chat: fast, precise evaluation
    "scorer": {
        "model":      "openrouter/deepseek/deepseek-chat",
        "fallback":   "openrouter/meta-llama/llama-4-maverick",
        "fallback2":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback3":  "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 5: Challenger Generator (JSON rewrite, structured output) ───
    # DeepSeek Chat: strong reasoning for mutation
    "challenger": {
        "model":      "openrouter/deepseek/deepseek-chat",
        "fallback":   "openrouter/meta-llama/llama-4-maverick",
        "fallback2":  "openrouter/mistralai/mistral-small-24b-instruct-2501",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
    },

    # ── Task 6: Visual Annotator (short cues, descriptive) ───────────────
    # Mistral Small: efficient, descriptive output
    "annotator": {
        "model":      "openrouter/mistralai/mistral-small-24b-instruct-2501",
        "fallback":   "openrouter/meta-llama/llama-4-maverick",
        "fallback2":  "openrouter/google/gemma-3-27b-it:free",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
    },
}
