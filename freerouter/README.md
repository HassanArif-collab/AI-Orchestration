# FreeRouter

> **LiteLLM-based task router — 3 providers, 7 routes, always free**

FreeRouter v3.1 is a slim OpenAI-compatible proxy built on [LiteLLM](https://github.com/BerriAI/litellm). Send a task name as the `model` field and FreeRouter resolves it to the best model with automatic multi-fallback.

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────────────────────┐
│  Your App    │────▶│   FreeRouter    │────▶│  OpenRouter: StepFun, Qwen, Mistral│
│  (OpenAI SDK)│     │  localhost:4000 │     │  Groq: compound-mini, llama, qwen3 │
└──────────────┘     └─────────────────┘     │  Ollama Cloud: gemma4, nemotron   │
                                              └──────────────────────────────────┘
```

## Named Routes

| Route | Primary | Fallback | Fallback2 | Provider |
|-------|---------|----------|-----------|----------|
| `auto` | stepfun/step-3.5-flash:free | groq/qwen3-32b | qwen/qwen3.6-plus:free | OR → G → OR |
| `researcher` | stepfun/step-3.5-flash:free | ollama/nemotron-3-nano:30b | ollama/gemma4:26b | OR → OC → OC |
| `topic_finder` | ollama/nemotron-3-nano:30b | stepfun/step-3.5-flash:free | qwen/qwen3.6-plus:free | OC → OR → OR |
| `script_writer` | qwen/qwen3.6-plus:free | mistral/mistral-small-3.1:free | — | OR → OR |
| `scorer` | groq/compound-beta | groq/llama-3.1-8b-instant | — | G → G |
| `challenger` | groq/llama-3.1-8b-instant | groq/qwen3-32b | — | G → G |
| `annotator` | groq/qwen3-32b | groq/llama-3.1-8b-instant | — | G → G |

**OR** = OpenRouter, **G** = Groq, **OC** = Ollama Cloud

### Why these models

- **Researcher**: StepFun 3.5 Flash (88.2% τ²-Bench agentic, 256K context) → Ollama nemotron-3-nano (frontier reasoning)
- **Topic Finder**: Ollama nemotron-3-nano (creative agentic ideation) → StepFun (agentic strengths)
- **Script Writer**: Qwen 3.6 Plus (creative writing, 1M context) → Mistral Small 3.1 (prose)
- **Scorer**: Groq compound-beta (logical precision on LPU, 70K TPM) → llama-3.1-8b (fast)
- **Challenger**: Groq llama-3.1-8b (JSON mode, fast) → qwen3-32b (structured output)
- **Annotator**: Groq qwen3-32b (high RPM, short output) → llama-3.1-8b (fast)

## Quick Start

```bash
# Install dependencies
pip install -e .

# Configure API keys
cp .env.example .env
# Edit .env — add OPENROUTER_API_KEY, GROQ_API_KEY, OLLAMA_API_KEY

# Start the server
python -m freerouter
```

Server runs on `http://0.0.0.0:4000`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Chat completions (OpenAI-compatible) |
| GET | `/v1/models` | List available task routes with full fallback chains |
| GET | `/health` | Health check + provider status |

## Usage

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:4000/v1", api_key="any_key")

response = client.chat.completions.create(
    model="script_writer",
    messages=[{"role": "user", "content": "Write a YouTube intro about quantum physics"}],
)
print(response.choices[0].message.content)
```

### cURL

```bash
# Score a script (uses Groq — ultra-fast)
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "scorer",
    "messages": [{"role": "user", "content": "Rate this script: Hello world"}]
  }'

# Research (uses StepFun → Ollama fallback)
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "researcher",
    "messages": [{"role": "user", "content": "Research quantum computing trends 2026"}]
  }'
```

### Health Check

```bash
curl http://localhost:4000/health
```

Response:
```json
{
  "status": "ok",
  "version": "3.1.0",
  "providers": {
    "openrouter": true,
    "groq": true,
    "ollama": true
  },
  "ollama_base": "https://ollama.com",
  "tasks": ["auto", "researcher", "topic_finder", "script_writer", "scorer", "challenger", "annotator"]
}
```

## Configuration

Set API keys in `freerouter/.env`:

```bash
# OpenRouter — https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-v1-...

# Groq — https://console.groq.com/keys
GROQ_API_KEY=gsk_...

# Ollama Cloud — https://ollama.com/settings/api-keys
OLLAMA_API_KEY=...

# Ollama base URL (https://ollama.com for cloud, http://localhost:11434 for local)
OLLAMA_API_BASE=https://ollama.com
```

All three providers are used in the routing table. Groq handles the fast scoring/annotating loop, OpenRouter handles research and scripting, Ollama Cloud handles creative ideation.

## Architecture

```
freerouter/
├── __init__.py      # Package init, exports ROUTES and __version__
├── __main__.py      # Entry point: python -m freerouter
├── config.py        # ROUTES table (7 tasks, 3 providers, multi-fallback)
├── server.py        # FastAPI app with multi-fallback chain logic
└── storage.py       # SQLite pipeline task storage
```

~250 lines total. Provider management, fallbacks, and rate limiting are all handled by LiteLLM.

## How Fallback Works

Each route has up to 3 models in a chain. server.py tries them in order:

```
request → primary model → fail? → fallback → fail? → fallback2 → fail? → 503
```

If a specific route returns 503, the `RouterClient` in your main app automatically retries with `model="auto"`, which has its own fallback chain.

## Troubleshooting

### Port already in use
```bash
lsof -i :4000 && kill -9 <PID>
```

### Check if running
```bash
curl http://localhost:4000/health
```

### All models fail (503)
- Check your API keys in `.env`
- Verify provider status: OpenRouter dashboard, Groq console, Ollama Cloud
- The `RouterClient` will auto-retry with `"auto"` route

### Ollama models not working
- Make sure `OLLAMA_API_KEY` is set (get one at https://ollama.com/settings/api-keys)
- For local Ollama: set `OLLAMA_API_BASE=http://localhost:11434` (no API key needed)

## License

MIT
