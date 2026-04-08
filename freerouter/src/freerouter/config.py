"""
config.py — Task-to-model routing table (v5.1).

3 providers: OpenRouter (free + paid) + Ollama Cloud.
7 routes with deep fallback chains + task-specialized models.

Providers:
    OpenRouter FREE (primary): 20 req/min shared, no credit card needed
      qwen3-next-80b-a3b (262K output), stepfun-3.5-flash (256K output),
      hermes-3-llama-3.1-405b (131K output), gemma-4-31b-it (32K output),
      llama-3.3-70b (65K output), gemma-3-27b-it (rate-limited)
    OpenRouter PAID (fallback): requires credits
      deepseek-chat, llama-4-maverick, mistral-small-24b
    Ollama Cloud: gemma4:31b (thinking mode)

LiteLLM model string format:
    openrouter/<provider>/<model>  →  via OpenRouter
    ollama_chat/<model>            →  via Ollama

TASK-SPECIFIC MODEL STRATEGY (v5.1):
    FREE models handle most tasks; PAID models are last-resort fallbacks.
    Rate limit retries are handled by RouterClient (3s delay on 429).
"""

ROUTES: dict[str, dict[str, str]] = {
    # ── Generic fallback ─────────────────────────────────────────────────
    "auto": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback2":  "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "fallback3":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
        "fallback5":  "openrouter/meta-llama/llama-4-maverick",
    },

    # ── Task 1: Researcher (deep synthesis, large context) ───────────────
    # Qwen 3 Next 80B (free): 262K output, MoE, excellent for synthesis
    "researcher": {
        "model":      "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback":   "openrouter/stepfun/step-3.5-flash:free",
        "fallback2":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback3":  "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
        "fallback5":  "ollama_chat/gemma4:31b",
    },

    # ── Task 2: Topic Finder (creative ideation, gap analysis) ────────────
    # Hermes 3 405B (free): largest free model, strongest creative reasoning
    "topic_finder": {
        "model":      "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback":   "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback2":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback3":  "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "fallback4":  "openrouter/meta-llama/llama-4-maverick",
        "fallback5":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 3: Script Writer (creative prose, narrative) ────────────────
    # Hermes 3 405B (free): 131K output, excellent creative instruction following
    "script_writer": {
        "model":      "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback":   "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback2":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback3":  "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "fallback4":  "openrouter/meta-llama/llama-4-maverick",
        "fallback5":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 4: Scoring Engine (fast pass/fail, logical precision) ───────
    # Qwen 3 Next 80B (free): precise JSON output for 56-question checklist
    "scorer": {
        "model":      "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback":   "openrouter/stepfun/step-3.5-flash:free",
        "fallback2":  "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        "fallback3":  "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 5: Challenger Generator (strategic mutation, deep reasoning) ─
    # Gemma 4 31B (free, thinking): deep chain-of-thought for strategic mutation
    "challenger": {
        "model":      "openrouter/google/gemma-4-31b-it:free",
        "fallback":   "ollama_chat/gemma4:31b",
        "fallback2":  "openrouter/stepfun/step-3.5-flash:free",
        "fallback3":  "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback4":  "openrouter/deepseek/deepseek-chat",
    },

    # ── Task 6: Visual Annotator (short cues, descriptive) ───────────────
    # StepFun 3.5 Flash (free, MoE): fast, efficient for short-form output
    "annotator": {
        "model":      "openrouter/stepfun/step-3.5-flash:free",
        "fallback":   "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "fallback2":  "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
        "fallback3":  "openrouter/google/gemma-3-27b-it:free",
        "fallback4":  "openrouter/mistralai/mistral-small-24b-instruct-2501",
    },
}
