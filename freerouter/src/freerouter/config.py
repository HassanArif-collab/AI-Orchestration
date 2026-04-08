"""
config.py — Task-to-model routing table (v5.2).

3 providers: OpenRouter (free + paid) + Ollama Cloud.
7 routes with deep fallback chains + task-specialized models.

Providers:
    OpenRouter FREE (primary): 20 req/min shared, no credit card needed
      stepfun-3.5-flash (256K output), qwen3-next-80b-a3b (262K output),
      hermes-3-llama-3.1-405b (131K output), llama-3.3-70b (65K output)
    OpenRouter PAID (fallback): requires credits
      deepseek-chat, llama-4-maverick, mistral-small-24b
    Ollama Cloud: various models (auth currently not working — 401)
    NOTE: Google AI Studio models (gemma-4-31b, gemma-3-27b) are GEO-BLOCKED
          from this server's location. Keep them at the end of fallback chains.

LiteLLM model string format:
    openrouter/<provider>/<model>  →  via OpenRouter
    ollama_chat/<model>            →  via Ollama

TASK-SPECIFIC MODEL STRATEGY (v5.2):
    StepFun 3.5 Flash is the most reliable free model (no geo-block).
    FREE models handle most tasks; PAID models are last-resort fallbacks.
    Rate limit retries are handled by RouterClient (5s cooldown between calls).
"""

ROUTES: dict[str, dict[str, str]] = {
    # ── Generic fallback ─────────────────────────────────────────────────
    "auto": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "openrouter/deepseek/deepseek-chat",
        "fallback2":  "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback3":  "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "fallback4":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback5":  "openrouter/meta-llama/llama-4-maverick",
    },

    # ── Task 1: Researcher (deep synthesis, large context) ───────────────
    # StepFun 3.5 Flash: most reliable free model for this server location
    "researcher": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "openrouter/deepseek/deepseek-chat",
        "fallback2":  "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback3":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback4":  "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    },

    # ── Task 2: Topic Finder (creative ideation, gap analysis) ────────────
    # DeepSeek for creative reasoning (paid but reliable)
    "topic_finder": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "openrouter/deepseek/deepseek-chat",
        "fallback2":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback3":  "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback4":  "openrouter/meta-llama/llama-4-maverick",
    },

    # ── Task 3: Script Writer (creative prose, narrative) ────────────────
    # DeepSeek for creative writing (paid but reliable, no geo-block)
    "script_writer": {
        "model":      "openrouter/deepseek/deepseek-chat",
        "fallback":   "openrouter/stepfun/step-3.5-flash:free",
        "fallback2":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback3":  "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback4":  "openrouter/meta-llama/llama-4-maverick",
    },

    # ── Task 4: Scoring Engine (fast pass/fail, logical precision) ───────
    # StepFun 3.5 Flash: fast and precise for JSON output
    "scorer": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "openrouter/deepseek/deepseek-chat",
        "fallback2":  "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback3":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback4":  "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    },

    # ── Task 5: Challenger Generator (strategic mutation, deep reasoning) ─
    # DeepSeek for strategic mutation (paid but reliable, no geo-block)
    "challenger": {
        "model":      "openrouter/deepseek/deepseek-chat",
        "fallback":   "openrouter/stepfun/step-3.5-flash:free",
        "fallback2":  "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback3":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback4":  "openrouter/meta-llama/llama-4-maverick",
    },

    # ── Task 6: Visual Annotator (short cues, descriptive) ───────────────
    # StepFun 3.5 Flash: fast, efficient for short-form output
    "annotator": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "openrouter/deepseek/deepseek-chat",
        "fallback2":  "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "fallback3":  "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback4":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
    },
}
