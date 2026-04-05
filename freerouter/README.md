# FreeRouter

> **LiteLLM-based task router — 2 providers, 7 routes, always free**

FreeRouter v3.1 is a slim OpenAI-compatible proxy built on [LiteLLM](https://github.com/BerriAI/litellm). Send a task name as the `model` field and FreeRouter resolves it to the best model with automatic multi-fallback.

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────────────────────┐
│  Your App    │────▶│   FreeRouter    │────▶│  OpenRouter: Qwen 3.6, StepFun   │
│  (OpenAI SDK)│     │  localhost:4000 │     │  Ollama Cloud: gemma4, nemotron  │
└──────────────┘     └─────────────────┘     └──────────────────────────────────┘
```

## Named Routes

| Route | Primary | Fallback | Provider |
|-------|---------|----------|----------|
| `auto` | stepfun/step-3.5-flash:free | qwen/qwen3.6-plus:free | OR → OR |
| `researcher` | qwen/qwen3.6-plus:free | stepfun/step-3.5-flash:free | OR → OR |
| `topic_finder` | ollama/gemma4:26b | qwen/qwen3.6-plus:free | OC → OR |
| `script_writer` | qwen/qwen3.6-plus:free | stepfun/step-3.5-flash:free | OR → OR |
| `scorer` | stepfun/step-3.5-flash:free | qwen/qwen3.6-plus:free | OR → OR |
| `challenger` | ollama/nemotron-cascade-2:30b | qwen/qwen3.6-plus:free | OC → OR |
| `annotator` | qwen/qwen3.6-plus:free | stepfun/step-3.5-flash:free | OR → OR |

**OR** = OpenRouter, **OC** = Ollama Cloud

## Quick Start

```bash
# Install dependencies
pip install -e .

# Configure API keys
cp .env.example .env
# Edit .env — add OPENROUTER_API_KEY and OLLAMA_API_KEY

# Start the server
python -m freerouter
```

Server runs on `http://0.0.0.0:4000`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Chat completions (OpenAI-compatible) |
| GET | `/v1/models` | List available task routes with fallback chains |
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
# Research (Qwen 3.6 via OpenRouter)
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "researcher", "messages": [{"role": "user", "content": "Research quantum computing"}]}'

# Topic finding (gemma4 via Ollama Cloud)
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "topic_finder", "messages": [{"role": "user", "content": "Suggest a documentary topic"}]}'
```

### Health Check

```bash
curl http://localhost:4000/health
```

## Configuration

Set API keys in `freerouter/.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-...    # https://openrouter.ai/keys
OLLAMA_API_KEY=...                  # https://ollama.com/settings/api-keys
OLLAMA_API_BASE=https://ollama.com  # cloud (default) or http://localhost:11434 (local)
```

## Architecture

```
freerouter/
├── __init__.py      # Package init, exports ROUTES and __version__
├── __main__.py      # Entry point: python -m freerouter
├── config.py        # ROUTES table (7 tasks, 2 providers, multi-fallback)
├── server.py        # FastAPI app with multi-fallback chain logic
└── storage.py       # SQLite pipeline task storage
```

## How Fallback Works

Each route has a chain of models. server.py tries them in order:

```
request → primary model → fail? → fallback → fail? → 503
```

If a specific route returns 503, the `RouterClient` in your main app automatically retries with `model="auto"`, which has its own fallback chain.

## Troubleshooting

### Port already in use
```bash
lsof -i :4000 && kill -9 <PID>
```

### All models fail (503)
- Check your API keys in `.env`
- Verify provider status dashboards
- The `RouterClient` will auto-retry with `"auto"` route

### Ollama models not working
- Make sure `OLLAMA_API_KEY` is set (get one at https://ollama.com/settings/api-keys)
- For local Ollama: set `OLLAMA_API_BASE=http://localhost:11434`

## License

MIT
