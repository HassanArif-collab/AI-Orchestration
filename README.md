# AI-Orchestration

Multi-agent YouTube video production pipeline built on FreeRouter.

## Quick start

```bash
# 1. Install
pip install -e ".[all]"

# 2. Copy env file and add your keys
cp .env.example .env

# 3. Start FreeRouter (in a separate terminal)
cd freerouter
python -m freerouter proxy

# 4. Run the pipeline smoke test
python scripts/run_pipeline.py

# 5. Use the CLI
python apps/worker/main.py start
```

## Architecture

See `docs/ARCHITECTURE.md` for full details.

```
freerouter/   ← LLM proxy (Groq, OpenRouter, Ollama — auto-fallback)
packages/
  core/       ← shared types, config, logging, errors
  router/     ← HTTP client for FreeRouter at :4000
  pipeline/   ← state machine, 9 stages, human gates
  agents/     ← base agent class, registry
  memory/     ← Zep Cloud agent memory
  integrations/
    youtube/  ← YouTube Data API v3
    notion/   ← Notion script pages
    mirofish/ ← MiroFish trend simulation
  visual/
    remotion/ ← programmatic video animations
    radiant/  ← canvas shader backgrounds
```

## Requirements

- Python 3.11+
- API keys in `freerouter/.env` (Groq, OpenRouter — managed via dashboard)
- API keys in `.env` (Zep, YouTube, Notion — optional)
