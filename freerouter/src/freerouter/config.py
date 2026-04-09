"""
config.py — Task-to-model routing table (v6.0).

4 providers with deep fallback chains:
    1. Zhipu AI (PRIMARY) — glm-4-plus, glm-4-0520, glm-4-flash (fast, reliable)
    2. Google AI Studio — gemini-2.0-flash (15 req/min, 1.5K req/day, currently rate-limited)
    3. Ollama Cloud — minimax-m2.5 (weekly limit reached, fallback only)
    4. OpenRouter — gemma-3-27b-it:free (rate-limited shared pool)

LiteLLM model string format:
    openai/glm-4-plus                   → via Zhipu AI (OpenAI-compatible at open.bigmodel.cn)
    gemini/gemini-2.0-flash             → via Google AI Studio
    ollama_chat/<model>                 → via Ollama Cloud
    openrouter/<provider>/<model>       → via OpenRouter

STRATEGY:
    - Zhipu AI is the most reliable provider (no rate limits in testing)
    - Google AI Studio is second (15 req/min, 1.5K/day)
    - Ollama Cloud when weekly limit resets
    - OpenRouter free as last resort (heavily rate-limited)
    - Each route has 6-level fallback chain
"""

# Zhipu AI base URL (used by server.py and client.py)
ZHIPU_API_BASE = "https://open.bigmodel.cn/api/paas/v4"

ROUTES: dict[str, dict[str, str]] = {
    # ── Generic fallback ─────────────────────────────────────────────────
    "auto": {
        "model":      "openai/glm-4-plus",               # Zhipu — fast, reliable
        "fallback":   "openai/glm-4-0520",               # Zhipu — strong reasoning
        "fallback2":  "gemini/gemini-2.0-flash",         # Google AI Studio
        "fallback3":  "openai/glm-4-flash",              # Zhipu — fastest
        "fallback4":  "ollama_chat/minimax-m2.5",        # Ollama (when limit resets)
        "fallback5":  "openrouter/google/gemma-3-27b-it:free",  # OR Free
    },

    # ── Task 1: Researcher (deep synthesis, large context) ───────────────
    "researcher": {
        "model":      "openai/glm-4-plus",
        "fallback":   "openai/glm-4-0520",
        "fallback2":  "openai/glm-4-long",               # Zhipu — 128K context for research
        "fallback3":  "gemini/gemini-2.0-flash",
        "fallback4":  "ollama_chat/minimax-m2.5",
        "fallback5":  "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 2: Topic Finder (creative ideation, gap analysis) ────────────
    "topic_finder": {
        "model":      "openai/glm-4-0520",               # Strong reasoning for ideation
        "fallback":   "openai/glm-4-plus",
        "fallback2":  "gemini/gemini-2.0-flash",
        "fallback3":  "openai/glm-4-flash",
        "fallback4":  "ollama_chat/minimax-m2.5",
        "fallback5":  "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 3: Script Writer (creative prose, narrative) ────────────────
    "script_writer": {
        "model":      "openai/glm-4-plus",               # Creative + factual
        "fallback":   "openai/glm-4-0520",
        "fallback2":  "gemini/gemini-2.0-flash",
        "fallback3":  "openai/glm-4-long",               # Long context for full script
        "fallback4":  "ollama_chat/minimax-m2.5",
        "fallback5":  "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 4: Scoring Engine (fast pass/fail, logical precision) ───────
    "scorer": {
        "model":      "openai/glm-4-flash",              # Fast, precise for JSON output
        "fallback":   "openai/glm-4-plus",
        "fallback2":  "openai/glm-4-0520",
        "fallback3":  "gemini/gemini-2.0-flash",
        "fallback4":  "ollama_chat/minimax-m2.5",
        "fallback5":  "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 5: Challenger Generator (strategic mutation, deep reasoning) ─
    "challenger": {
        "model":      "openai/glm-4-0520",               # Strong reasoning
        "fallback":   "openai/glm-4-plus",
        "fallback2":  "gemini/gemini-2.0-flash",
        "fallback3":  "openai/glm-4-long",
        "fallback4":  "ollama_chat/minimax-m2.5",
        "fallback5":  "openrouter/google/gemma-3-27b-it:free",
    },

    # ── Task 6: Visual Annotator (short cues, descriptive) ───────────────
    "annotator": {
        "model":      "openai/glm-4-flash",              # Fast, efficient
        "fallback":   "openai/glm-4-plus",
        "fallback2":  "openai/glm-4-0520",
        "fallback3":  "gemini/gemini-2.0-flash",
        "fallback4":  "ollama_chat/minimax-m2.5",
        "fallback5":  "openrouter/google/gemma-3-27b-it:free",
    },
}
