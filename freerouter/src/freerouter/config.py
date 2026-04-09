"""
config.py — Task-to-model routing table (v5.3).

3 providers: Ollama Cloud (primary) + OpenRouter (free + paid).
7 routes with deep fallback chains + task-specialized models.

Providers:
    Ollama Cloud (PRIMARY): 38 models, no rate limits, no geo-block
      minimax-m2.5 (fast), mistral-large-3:675b, kimi-k2.5, deepseek-v3.2,
      qwen3-next:80b, gemma4:31b, and many more
    OpenRouter FREE (fallback): 20 req/min shared
      stepfun-3.5-flash, qwen3-next-80b-a3b, hermes-3-llama-3.1-405b
    OpenRouter PAID (last resort): requires credits
      deepseek-chat, llama-4-maverick
    NOTE: Google AI Studio models (gemma-4-31b on OpenRouter) are GEO-BLOCKED.
          Use gemma4:31b via Ollama Cloud instead.
    NOTE: Thinking models (deepseek-v3.2, qwen3-next:80b, gemma4:31b) are
          SLOW (10-30s per call). Prefer fast non-thinking models.

LiteLLM model string format:
    openrouter/<provider>/<model>  →  via OpenRouter
    ollama_chat/<model>            →  via Ollama Cloud

TASK-SPECIFIC MODEL STRATEGY (v5.3):
    Ollama Cloud is the primary provider (no rate limits, no geo-block).
    minimax-m2.5 is the fastest model (~1s/call), used for most tasks.
    mistral-large-3:675b for tasks requiring deeper reasoning.
    kimi-k2.5 for creative tasks (1.1T params, thinking model).
    OpenRouter free models are fallback; OpenRouter paid is last resort.
    Rate limit retries are handled by RouterClient (8s cooldown between calls).
"""

ROUTES: dict[str, dict[str, str]] = {
    # ── Generic fallback ─────────────────────────────────────────────────
    "auto": {
        "model":      "ollama_chat/minimax-m2.5",
        "fallback":   "ollama_chat/mistral-large-3:675b",
        "fallback2":  "ollama_chat/minimax-m2.7",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 1: Researcher (deep synthesis, large context) ───────────────
    # minimax-m2.5: fast, 230B params, good for synthesis
    "researcher": {
        "model":      "ollama_chat/minimax-m2.5",
        "fallback":   "ollama_chat/mistral-large-3:675b",
        "fallback2":  "ollama_chat/kimi-k2.5",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 2: Topic Finder (creative ideation, gap analysis) ────────────
    # mistral-large-3:675b: 675B params, strongest reasoning for ideation
    "topic_finder": {
        "model":      "ollama_chat/mistral-large-3:675b",
        "fallback":   "ollama_chat/minimax-m2.5",
        "fallback2":  "ollama_chat/kimi-k2.5",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 3: Script Writer (creative prose, narrative) ────────────────
    # mistral-large-3:675b: excellent creative writing with facts
    "script_writer": {
        "model":      "ollama_chat/mistral-large-3:675b",
        "fallback":   "ollama_chat/minimax-m2.5",
        "fallback2":  "ollama_chat/kimi-k2.5",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 4: Scoring Engine (fast pass/fail, logical precision) ───────
    # minimax-m2.5: fast and precise for JSON output
    "scorer": {
        "model":      "ollama_chat/minimax-m2.5",
        "fallback":   "ollama_chat/mistral-large-3:675b",
        "fallback2":  "ollama_chat/minimax-m2.7",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 5: Challenger Generator (strategic mutation, deep reasoning) ─
    # mistral-large-3:675b: strong reasoning for strategic script mutation
    "challenger": {
        "model":      "ollama_chat/mistral-large-3:675b",
        "fallback":   "ollama_chat/minimax-m2.5",
        "fallback2":  "ollama_chat/kimi-k2.5",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 6: Visual Annotator (short cues, descriptive) ───────────────
    # minimax-m2.5: fast, efficient for short-form output
    "annotator": {
        "model":      "ollama_chat/minimax-m2.5",
        "fallback":   "ollama_chat/mistral-large-3:675b",
        "fallback2":  "ollama_chat/minimax-m2.7",
        "fallback3":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
    },
}
